import asyncio
import copy
import glob
import json
import os
import time
from contextlib import ExitStack
from pathlib import Path
from typing import cast, get_args

import boto3
import nest_asyncio
import streamlit as st
import yaml
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.tools.mcp.mcp_agent_tool import MCPAgentTool
from strands.types.content import ContentBlock, Message, Messages
from strands.types.media import ImageFormat
from strands_tools import current_time, http_request
from dotenv import load_dotenv
load_dotenv()

nest_asyncio.apply()

os.environ["DEV"] = "true"

format = {"image": list(get_args(ImageFormat))}

builtin_tools = [current_time, http_request]


async def streaming(stream):
    """
    ストリーミングデータを処理し、テキストまたはツール使用情報を生成する非同期ジェネレータ関数。

    Args:
        stream: エージェントからのストリーミングレスポンス

    Yields:
        str: テキストデータまたはツール使用情報のフォーマット済み文字列
    """
    async for event in stream:
        # イベントにデータが含まれている場合、テキストとして出力
        if "data" in event:
            # テキストを出力
            data = event["data"]
            yield data
        # イベントにメッセージが含まれている場合、ツール使用情報を抽出して出力
        elif "message" in event:
            # ToolUseを出力
            message: Message = event["message"]
            # メッセージの内容からツール使用情報を抽出
            for content in [
                content for content in message["content"] if "toolUse" in content.keys()
            ]:
                yield f"\n\n🔧 Using tool:\n```json\n{json.dumps(content, indent=2, ensure_ascii=False)}\n```\n\n"


def convert_messages(messages: Messages, enable_cache: bool):
    """
    メッセージ履歴にキャッシュポイントを追加する関数。

    Args:
        messages (Messages): 変換するメッセージ履歴
        enable_cache (bool): キャッシュを有効にするかどうかのフラグ

    Returns:
        Messages: キャッシュポイントが追加されたメッセージ履歴
    """
    messages_with_cache_point: Messages = []
    user_turns_processed = 0

    for message in reversed(messages):
        m = copy.deepcopy(message)

        if enable_cache:
            if message["role"] == "user" and user_turns_processed < 2:
                if len([c for c in m["content"] if "text" in c]) > 0:
                    m["content"].append({"cachePoint": {"type": "default"}})  # type: ignore
                    user_turns_processed += 1
                else:
                    pass

        messages_with_cache_point.append(m)

    messages_with_cache_point.reverse()

    return messages_with_cache_point


async def main():
    """
    Streamlitアプリケーションのメイン関数。チャットインターフェースの設定、
    モデルの初期化、ユーザー入力の処理、およびチャット履歴の管理を行う。

    Returns:
        None
    """
    st.title("Strands agent")

    with open("config/config.json", "r") as f:
        config = json.load(f)

    models = config["models"]
    bedrock_region = config["bedrock_region"]

    def select_chat(chat_history_file):
        st.session_state.chat_history_file = chat_history_file

    with st.sidebar:
        with st.expander(":gear: config", expanded=True):
            st.selectbox("LLM model", models.keys(), key="model_id")
            st.checkbox("Enable prompt cache", value=True, key="enable_prompt_cache")

            chat_history_dir = st.text_input(
                "chat_history_dir", value=config["chat_history_dir"]
            )

            st.text_input(
                "mcp_config_file",
                value=config["mcp_config_file"],
                key="mcp_config_file",
            )

            with open(st.session_state.mcp_config_file, "r") as f:
                mcp_config = json.load(f)["mcpServers"]

            if "multiselect_mcp_tools" not in st.session_state:
                with st.spinner("Tool loading..."):
                    mcp_tools: list[MCPAgentTool] = []
                    with ExitStack() as stack:
                        for _, server_config in mcp_config.items():
                            server_parameter = StdioServerParameters(
                                command=server_config["command"],
                                args=server_config["args"],
                                env=server_config["env"]
                                if "env" in server_config
                                else None,
                            )
                            mcp_client = MCPClient(
                                lambda param=server_parameter: stdio_client(
                                    server=param
                                )
                            )
                            stack.enter_context(mcp_client)  # type: ignore
                            mcp_tools.extend(mcp_client.list_tools_sync())

                    st.session_state.multiselect_mcp_tools = [
                        tool.tool_name for tool in mcp_tools
                    ]

            st.pills(
                "MCP Tool",
                st.session_state.multiselect_mcp_tools,
                selection_mode="multi",
                default=st.session_state.multiselect_mcp_tools,
                key="selected_mcp_tools",
            )

        st.button(
            "New Chat",
            on_click=select_chat,
            args=(f"{chat_history_dir}/{int(time.time())}.yaml",),
            use_container_width=True,
            type="primary",
        )

    if "chat_history_file" not in st.session_state:
        st.session_state["chat_history_file"] = (
            f"{chat_history_dir}/{int(time.time())}.yaml"
        )
    chat_history_file = st.session_state.chat_history_file

    if Path(chat_history_file).exists():
        with open(chat_history_file, mode="rt") as f:
            yaml_msg = yaml.safe_load(f)
            messages: Messages = yaml_msg
    else:
        messages: Messages = []

    for message in messages:
        for content in message["content"]:
            with st.chat_message(message["role"]):
                if "text" in content:
                    st.write(content["text"])
                elif "image" in content:
                    st.image(content["image"]["source"]["bytes"])

    enable_prompt_cache_system = False
    enable_prompt_cache_tools = False
    enable_prompt_cache_messages = False

    if st.session_state.enable_prompt_cache:
        cache_support = models[st.session_state.model_id]["cache_support"]
        enable_prompt_cache_system = True if "system" in cache_support else False
        enable_prompt_cache_tools = True if "tools" in cache_support else False
        enable_prompt_cache_messages = True if "messages" in cache_support else False

    image_support: bool = models[st.session_state.model_id]["image_support"]

    if prompt := st.chat_input(accept_file="multiple", file_type=format["image"]):
        with st.chat_message("user"):
            st.write(prompt.text)
            for file in prompt.files:
                if image_support:
                    st.image(file.getvalue())
                else:
                    st.warning(
                        "このモデルは画像はサポートしていません。画像は使用されません。"
                    )

        if prompt.files and image_support:
            image_content: list[ContentBlock] = []
            for file in prompt.files:
                if (file_format := file.type.split("/")[1]) in format["image"]:
                    image_content.append(
                        {
                            "image": {
                                "format": cast(ImageFormat, file_format),
                                "source": {"bytes": file.getvalue()},
                            }
                        }
                    )
            messages = messages + [
                {"role": "user", "content": image_content},
                {
                    "role": "assistant",
                    "content": [
                        {"text": "I will reference this media in my next response."}
                    ],
                },
            ]

        # ExitStackを使用して可変数のクライアントを管理
        with ExitStack() as stack:
            mcp_tools: list[MCPAgentTool] = []

            for server_name, server_config in mcp_config.items():
                server_parameter = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config["env"] if "env" in server_config else None,
                )
                mcp_client = MCPClient(
                    lambda param=server_parameter: stdio_client(server=param)
                )
                stack.enter_context(mcp_client)  # type: ignore
                mcp_tools.extend(mcp_client.list_tools_sync())

                mcp_tools = [
                    tool
                    for tool in mcp_tools
                    if tool.tool_name in st.session_state.selected_mcp_tools
                ]

            tools = mcp_tools + builtin_tools

            agent = Agent(
                model=BedrockModel(
                    model_id=st.session_state.model_id,
                    boto_session=boto3.Session(region_name=bedrock_region),
                    cache_prompt="default" if enable_prompt_cache_system else None,
                    cache_tools="default" if enable_prompt_cache_tools else None,
                ),
                system_prompt="あなたは優秀なAIエージェントです！",
                messages=convert_messages(
                    messages, enable_cache=enable_prompt_cache_messages
                ),
                callback_handler=None,
                tools=tools,
            )

            agent_stream = agent.stream_async(prompt=prompt.text)

            with st.chat_message("assistant"):
                st.write_stream(streaming(agent_stream))

            with open(chat_history_file, mode="wt") as f:
                yaml.safe_dump(agent.messages, f, allow_unicode=True)

    with st.sidebar:
        history_files = glob.glob(os.path.join(chat_history_dir, "*.yaml"))  # type: ignore

        for h in sorted(history_files, reverse=True)[:20]:  # latest 20
            st.button(h, on_click=select_chat, args=(h,), use_container_width=True)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
