# Amazon Nova Canvas統合Streamlitチャットアプリケーション
# AWS BedrockとStrands Agentフレームワークを使用した高度な画像生成・チャット機能

import asyncio
import copy
import glob
import json
import os
import time
import tempfile
import shutil
import ast
import re
from pathlib import Path
from typing import cast, get_args

import boto3
import nest_asyncio
import streamlit as st
import yaml
from strands import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock, Message, Messages
from strands.types.media import ImageFormat
from strands_tools.current_time import current_time
from nova_canvas_tool import nova_canvas_virtual_tryout, nova_canvas_style_generation, nova_canvas_get_styles, nova_canvas_text_to_image, PROMPT_SAMPLES, NEGATIVE_PROMPT_SAMPLES, ASPECT_RATIO_OPTIONS
from dotenv import load_dotenv
from PIL import Image
import io

# 環境変数の読み込み
load_dotenv()

# 一時ディレクトリのパスを保持
TEMP_IMAGE_DIR = None

# Streamlitの非同期処理制約を回避するため、nest_asyncioを適用
nest_asyncio.apply()

# 開発モードの有効化
os.environ["DEV"] = "true"

# 画像フォーマットの定義（サポートされる画像形式）
format = {"image": list(get_args(ImageFormat))}

# 組み込みツールの定義（基本ツール + Nova Canvas カスタムツール）
builtin_tools = [current_time, nova_canvas_virtual_tryout, nova_canvas_style_generation, nova_canvas_get_styles, nova_canvas_text_to_image]


async def streaming(stream, on_tool_result=None):
    """
    AIエージェントからのストリーミングレスポンスをリアルタイムで処理する非同期関数。
    
    このジェネレータ関数は、AWS BedrockのLLMモデルからのストリーミング応答を受信し、
    テキストコンテンツやツール使用情報（Nova Canvasの画像生成など）を
    Streamlit UIにリアルタイムで表示するために使用されます。

    引数:
        stream: Strands Agentからのストリーミングレスポンスオブジェクト
        on_tool_result: ツール実行結果を受信した際に呼び出されるコールバック関数（オプション）

    戻り値:
        str: StreamlitのUI表示用にフォーマットされたテキストデータまたはツール使用情報
        
    処理フロー:
        1. ストリーミングイベントを逐次処理
        2. テキストデータは即座にyield（リアルタイム表示）
        3. ツール使用情報はJSON形式でフォーマットして表示
        4. ツール実行結果はコールバック経由で後続処理に渡す
    """
    async for event in stream:
        # イベントにデータが含まれている場合、テキストとして出力
        if "data" in event:
            # テキストコンテンツを出力（通常のAIレスポンス）
            data = event["data"]
            yield data
        # イベントにメッセージが含まれている場合、ツール使用情報を抽出して出力
        elif "message" in event:
            # ToolUseメッセージを処理（Nova Canvasなどのツール実行時）
            message: Message = event["message"]
            # メッセージの内容からツール使用情報を抽出
            for content in message["content"]:
                if "toolUse" in content:
                    yield f"\n\n🔧 Using tool:\n```json\n{json.dumps(content, indent=2, ensure_ascii=False)}\n```\n\n"
                elif "toolResult" in content:
                    # ツール結果をコールバックに渡す
                    if on_tool_result:
                        on_tool_result(content["toolResult"])
                    
                    # ツール結果の詳細表示
                    try:
                        result_text = content["toolResult"]["content"][0]["text"]
                        result_data = json.loads(result_text)
                        
                        # エラーの場合は詳細を表示
                        if not result_data.get("success", True):
                            yield f"\n\n❌ **エラーが発生しました**\n"
                            yield f"- **エラーメッセージ**: {result_data.get('error', 'Unknown error')}\n"
                            yield f"- **エラータイプ**: {result_data.get('error_type', 'Unknown')}\n"
                            
                            # トラブルシューティング情報
                            if "troubleshooting" in result_data:
                                yield f"\n**トラブルシューティング**:\n"
                                for key, value in result_data["troubleshooting"].items():
                                    yield f"- {value}\n"
                            
                            # デバッグ情報（開発モード時）
                            if os.environ.get("DEV") == "true" and "debug_info" in result_data:
                                yield f"\n<details>\n<summary>デバッグ情報（クリックして展開）</summary>\n\n"
                                yield f"```json\n{json.dumps(result_data['debug_info'], indent=2, ensure_ascii=False)}\n```\n"
                                yield f"</details>\n\n"
                    except json.JSONDecodeError:
                        # JSON形式でない場合はそのまま表示
                        pass
                    except Exception as e:
                        print(f"[ERROR] ツール結果の解析エラー: {e}")


def safe_parse_tool_result(text: str) -> dict:
    """
    ツール結果のテキストを安全にPython辞書として解析する関数。
    
    JSON形式、Python辞書文字列形式、またはプレーンテキストを適切に処理します。
    
    Args:
        text: 解析するテキスト
        
    Returns:
        dict: 解析された辞書、または{"text": original_text}形式
    """
    try:
        # まずJSON形式として解析を試行
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Python辞書文字列として解析を試行
            # シングルクォートをダブルクォートに変換してJSONとして再解析
            json_text = re.sub(r"'([^']*)':", r'"\1":', text)  # キーをダブルクォートに
            json_text = re.sub(r": '([^']*)'", r': "\1"', json_text)  # 値をダブルクォートに
            json_text = re.sub(r"True", "true", json_text)  # Pythonブール値をJSONに
            json_text = re.sub(r"False", "false", json_text)
            json_text = re.sub(r"None", "null", json_text)
            return json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            try:
                # ast.literal_evalを使用してPython辞書として安全に評価
                return ast.literal_eval(text)
            except (ValueError, SyntaxError):
                # 全ての解析に失敗した場合、プレーンテキストとして返す
                return {"text": text, "is_plain_text": True}


def resize_image_if_needed(image_bytes: bytes, max_size: tuple = (1024, 1024), quality: int = 85) -> bytes:
    """
    アップロードされた画像を必要に応じてリサイズし、LLMのコンテキストウィンドウ制限を回避する。
    
    AWS Bedrockの画像処理制限やStreamlitアプリのパフォーマンスを考慮して、
    大きすぎる画像を自動的に縮小します。アスペクト比は保持されます。
    
    引数:
        image_bytes: 処理対象の画像データ（バイト形式）
        max_size: 最大許可サイズのタプル（幅, 高さ）デフォルト: (1024, 1024)
        quality: JPEG圧縮時の品質設定（1-100）デフォルト: 85
        
    戻り値:
        bytes: リサイズが必要な場合は縮小された画像データ、不要な場合は元のデータ
        
    処理詳細:
        - PIL（Pillow）を使用してサムネイル生成
        - 元の画像形式（PNG/JPEG）を保持
        - LANCZOS リサンプリングで高品質な縮小
        - サイズ制限以下の画像はそのまま返却
    """
    try:
        # 画像を開く
        img = Image.open(io.BytesIO(image_bytes))
        original_size = (img.width, img.height)
        original_format = img.format or 'PNG'
        
        # 画像が最大サイズを超えている場合のみリサイズ
        if img.width > max_size[0] or img.height > max_size[1]:
            # アスペクト比を保持してリサイズ
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # リサイズした画像をバイトに変換
            output = io.BytesIO()
            
            # 元の形式を保持（JPEGの場合は品質設定を適用）
            save_kwargs = {'format': original_format}
            if original_format in ['JPEG', 'JPG']:
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True
            
            img.save(output, **save_kwargs)
            resized_bytes = output.getvalue()
            
            print(f"[INFO] 画像リサイズ: {original_size} -> ({img.width}, {img.height})")
            print(f"[INFO] ファイルサイズ: {len(image_bytes):,} bytes -> {len(resized_bytes):,} bytes")
            
            return resized_bytes
        
        return image_bytes
        
    except Exception as e:
        print(f"[ERROR] 画像リサイズ失敗: {e}")
        # リサイズに失敗した場合は元のデータを返す
        return image_bytes


def convert_messages(messages: Messages, enable_cache: bool):
    """
    チャット履歴メッセージにAWS Bedrockプロンプトキャッシュ設定を適用する。
    
    この関数は、Claudeモデルなどの対応LLMでプロンプトキャッシング機能を活用し、
    レスポンス時間を大幅に短縮します。最新の2つのユーザーターンに
    キャッシュポイントを設定することで、継続的な会話で高速化を実現します。

    引数:
        messages (Messages): Strands Agent形式のメッセージ履歴リスト
        enable_cache (bool): プロンプトキャッシュ機能の有効/無効フラグ

    戻り値:
        Messages: キャッシュポイントが適切に設定されたメッセージ履歴
        
    キャッシュ戦略:
        - 最新2つのユーザーメッセージにキャッシュポイントを追加
        - テキストコンテンツがあるメッセージのみが対象
        - 古いメッセージはキャッシュ対象外（効率性のため）
        - enable_cache=Falseの場合は何も変更しない
    """
    messages_with_cache_point: Messages = []
    user_turns_processed = 0

    # メッセージを逆順で処理して、最新のユーザーターンを特定
    for message in reversed(messages):
        m = copy.deepcopy(message)

        if enable_cache:
            # ユーザーメッセージで、処理済みターンが2未満の場合にキャッシュポイントを追加
            if message["role"] == "user" and user_turns_processed < 2:
                if len([c for c in m["content"] if "text" in c]) > 0:
                    # テキストコンテンツがある場合、キャッシュポイントを追加
                    m["content"].append({"cachePoint": {"type": "default"}})  # type: ignore
                    user_turns_processed += 1
                else:
                    pass

        messages_with_cache_point.append(m)

    # 元の順序に戻す
    messages_with_cache_point.reverse()

    return messages_with_cache_point


async def main():
    """
    Streamlitベースの Nova Canvas統合チャットアプリケーションのメインエントリーポイント。
    
    この非同期関数は、アプリケーション全体の初期化から実行まで一貫して管理し、
    以下の主要機能を提供します：
    
    主要処理:
        1. 設定ファイル（config.json）の読み込みと環境初期化
        2. Streamlit WebUIの構築（タブ形式：チャット・画像生成）
        3. サイドバーでのモデル選択とキャッシュ設定
        4. チャット履歴の永続化管理（YAML形式）
        5. Nova Canvasカスタムツールの統合と実行
        6. リアルタイムストリーミング応答の表示
        7. 画像アップロード・処理・表示機能
    
    アーキテクチャ特徴:
        - AWS Bedrock直接統合（MCP非依存）
        - Strands Agentフレームワーク活用
        - 非同期処理によるレスポンシブUI
        - カスタムツール実装による高度な画像生成機能
    
    戻り値:
        None: Streamlitアプリケーションとして動作するため戻り値なし
    """
    st.title("Strands agent")
    
    # メインタブの設定
    tab1, tab2 = st.tabs(["💬 チャット", "🎨 画像生成"])

    with open("config/config.json", "r") as f:
        config = json.load(f)

    models = config["models"]
    bedrock_region = config["bedrock_region"]

    def select_chat(chat_history_file):
        st.session_state.chat_history_file = chat_history_file

    with st.sidebar:
        with st.expander(":gear: 設定", expanded=True):
            st.selectbox("LLMモデル", models.keys(), key="model_id")
            st.checkbox("プロンプトキャッシュを有効化", value=True, key="enable_prompt_cache")

            chat_history_dir = st.text_input(
                "チャット履歴ディレクトリ", value=config["chat_history_dir"]
            )

            # MCP機能は無効化されています
            st.info("📝 Nova Canvasカスタムツールを使用中")

        st.button(
            "新しいチャット",
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

    # プロンプトキャッシュの設定
    enable_prompt_cache_system = False
    enable_prompt_cache_tools = False
    enable_prompt_cache_messages = False

    if st.session_state.enable_prompt_cache:
        cache_support = models[st.session_state.model_id]["cache_support"]
        enable_prompt_cache_system = True if "system" in cache_support else False
        enable_prompt_cache_tools = True if "tools" in cache_support else False
        enable_prompt_cache_messages = True if "messages" in cache_support else False

    image_support: bool = models[st.session_state.model_id]["image_support"]

    # チャットタブの処理
    with tab1:
        # チャット履歴の表示
        for message in messages:
            for content in message["content"]:
                with st.chat_message(message["role"]):
                    if "text" in content:
                        st.write(content["text"])
                    elif "image" in content:
                        st.image(content["image"]["source"]["bytes"])
                    elif "toolResult" in content:
                        # ツール実行結果の表示
                        display_tool_result(content["toolResult"])

        # チャット入力処理
        handle_chat_input(messages, chat_history_file, models, bedrock_region, enable_prompt_cache_system, enable_prompt_cache_tools, enable_prompt_cache_messages, builtin_tools)
    
    # 画像生成タブの処理
    with tab2:
        handle_image_generation(bedrock_region)

    with st.sidebar:
        with st.expander("📝 チャット履歴", expanded=False):
            history_files = glob.glob(os.path.join(chat_history_dir, "*.yaml"))  # type: ignore

            for h in sorted(history_files, reverse=True)[:20]:  # latest 20
                filename = os.path.basename(h)
                st.button(filename, on_click=select_chat, args=(h,), use_container_width=True)


def display_tool_result_realtime(tool_result):
    """
    ツール実行結果をリアルタイムで表示する関数（ストリーミング完了後）
    
    Nova Canvasツールの結果画像を即座に表示します。
    """
    print(f"[DEBUG] display_tool_result_realtime called")
    
    if "content" in tool_result and isinstance(tool_result["content"], list):
        print(f"[DEBUG] tool_result has content: {len(tool_result['content'])} items")
        
        for result_content in tool_result["content"]:
            if "text" in result_content:
                print(f"[DEBUG] display_tool_result_realtime: 処理中のテキスト長: {len(result_content['text'])}")
                print(f"[DEBUG] display_tool_result_realtime: テキストの最初の200文字: {result_content['text'][:200]}")
                
                # SUCCESS: パターンで始まる場合（Virtual Try-on用のシンプルレスポンス）
                if result_content["text"].startswith("SUCCESS: "):
                    print(f"[DEBUG] display_tool_result_realtime: SUCCESS パターンを検出")
                    image_file_path = result_content["text"][9:]  # "SUCCESS: " を除去
                    print(f"[DEBUG] 抽出された画像ファイルパス: {image_file_path}")
                    
                    try:
                        import os
                        from datetime import datetime
                        
                        if os.path.exists(image_file_path):
                            st.success("Virtual try-on が正常に実行されました")
                            
                            # ファイルパスの表示
                            st.write(f"**生成画像ファイル:** `{image_file_path}`")
                            
                            # 画像の表示
                            with open(image_file_path, 'rb') as f:
                                image_data = f.read()
                            
                            st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                            
                            # ダウンロードボタン
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="🔽 画像をダウンロード",
                                data=image_data,
                                file_name=f"virtual_tryout_{timestamp}.png",
                                mime="image/png",
                                key=f"download_vto_realtime_{timestamp}"
                            )
                            
                            print(f"[DEBUG] display_tool_result_realtime: SUCCESS パターン処理完了")
                        else:
                            st.error(f"画像ファイルが見つかりません: {image_file_path}")
                            
                    except Exception as e:
                        print(f"[ERROR] display_tool_result_realtime: SUCCESS パターン処理エラー: {e}")
                        st.error(f"画像表示エラー: {str(e)}")
                
                # ERROR: パターンで始まる場合
                elif result_content["text"].startswith("ERROR: "):
                    print(f"[DEBUG] display_tool_result_realtime: ERROR パターンを検出")
                    error_message = result_content["text"][7:]  # "ERROR: " を除去
                    st.error(error_message)
                
                # JSONパターンの場合（従来の処理を維持）
                else:
                    try:
                        result_data = safe_parse_tool_result(result_content["text"])
                        print(f"[DEBUG] display_tool_result_realtime: 解析成功")
                        print(f"[DEBUG] Parsed result_data: success={result_data.get('success')}, has_image={'image' in result_data}, has_images={'images' in result_data}, has_image_file={'image_file' in result_data}")
                        
                        # プレーンテキストの場合
                        if result_data.get("is_plain_text"):
                            st.text(result_data["text"])
                            return
                        
                        # Nova Canvas ツールの成功結果のみ処理（エラーはストリーミング中に表示済み）
                        if result_data.get("success", False):
                            print(f"[DEBUG] display_tool_result_realtime: 成功結果を処理中")
                            # ファイルパスから画像を読み込む場合（Context Window節約）
                            if "image_file" in result_data and result_data["image_file"]:
                                st.success(result_data.get("message", "画像生成が完了しました"))
                                try:
                                    import os
                                    from datetime import datetime
                                    
                                    image_file_path = result_data["image_file"]
                                    print(f"[DEBUG] Loading image from file: {image_file_path}")
                                    
                                    # ファイルが存在することを確認
                                    if os.path.exists(image_file_path):
                                        # ファイルから画像を読み込んで表示
                                        with open(image_file_path, 'rb') as f:
                                            image_data = f.read()
                                        
                                        st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                                        
                                        # ダウンロードボタンを追加
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        st.download_button(
                                            label="🔽 画像をダウンロード",
                                            data=image_data,
                                            file_name=f"virtual_tryout_result_{timestamp}.png",
                                            mime="image/png",
                                            key=f"download_file_{timestamp}"
                                        )
                                        
                                        # パラメータ情報の表示
                                        if "parameters" in result_data:
                                            with st.expander("実行パラメータ"):
                                                st.json(result_data["parameters"])
                                        
                                        print(f"[DEBUG] Image from file displayed successfully")
                                    else:
                                        st.error(f"画像ファイルが見つかりません: {image_file_path}")
                                        
                                except Exception as e:
                                    st.error(f"画像表示エラー: {str(e)}")
                                    print(f"[ERROR] Failed to display image from file: {e}")
                        
                        # Base64データから画像を表示する場合（従来の方法）
                        elif "image" in result_data and result_data["image"]:
                            st.success(result_data.get("message", "画像生成が完了しました"))
                            try:
                                import base64
                                from datetime import datetime
                                
                                image_data = base64.b64decode(result_data["image"])
                                st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                                
                                # ダウンロードボタンを追加
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                st.download_button(
                                    label="🔽 画像をダウンロード",
                                    data=image_data,
                                    file_name=f"virtual_tryout_result_{timestamp}.png",
                                    mime="image/png",
                                    key=f"download_single_{timestamp}"
                                )
                                
                                # パラメータ情報の表示
                                if "parameters" in result_data:
                                    with st.expander("実行パラメータ"):
                                        st.json(result_data["parameters"])
                                        
                                print(f"[DEBUG] Single image displayed successfully")
                            except Exception as e:
                                st.error(f"画像表示エラー: {str(e)}")
                                print(f"[ERROR] Failed to display image: {e}")
                        
                        # 複数画像の場合
                        elif "images" in result_data and result_data["images"]:
                            st.success(result_data.get("message", "画像生成が完了しました"))
                            for i, image_b64 in enumerate(result_data["images"]):
                                try:
                                    import base64
                                    from datetime import datetime
                                    
                                    image_data = base64.b64decode(image_b64)
                                    st.image(image_data, caption=f"Generated by Nova Canvas - Image {i+1}", use_column_width=True)
                                    
                                    # 各画像にダウンロードボタンを追加
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    st.download_button(
                                        label=f"🔽 画像{i+1}をダウンロード",
                                        data=image_data,
                                        file_name=f"nova_canvas_result_{i+1}_{timestamp}.png",
                                        mime="image/png",
                                        key=f"download_multi_{i}_{timestamp}"
                                    )
                                except Exception as e:
                                    st.error(f"画像{i+1}表示エラー: {str(e)}")
                                    print(f"[ERROR] Failed to display image {i+1}: {e}")
                            
                            # パラメータ情報の表示
                            if "parameters" in result_data:
                                with st.expander("実行パラメータ"):
                                    st.json(result_data["parameters"])
                                    
                            print(f"[DEBUG] Multiple images displayed successfully")
                        else:
                            print(f"[DEBUG] Result was not successful: {result_data.get('error', 'Unknown error')}")
                                        
                    except Exception as ex:
                        # 解析エラーの場合（safe_parse_tool_result内でハンドリング済み）
                        print(f"[ERROR] display_tool_result_realtime: 予期しないエラー: {str(ex)}")
                        print(f"[ERROR] display_tool_result_realtime: エラータイプ: {type(ex).__name__}")
                        st.error(f"ツール結果の処理中にエラーが発生しました: {str(ex)}")
                        st.text(result_content["text"])
            else:
                print(f"[DEBUG] result_content does not have 'text' key")
    else:
        print(f"[DEBUG] tool_result does not have valid content")


def display_tool_result(tool_result):
    """
    ツール実行結果を表示する関数（チャット履歴表示用）
    
    Nova Canvasツールの結果を適切に表示し、エラーハンドリングを行います。
    """
    if "content" in tool_result and isinstance(tool_result["content"], list):
        for result_content in tool_result["content"]:
            if "text" in result_content:
                # ツール実行結果テキストのJSONパース（詳細なエラーハンドリング付き）
                print(f"[DEBUG] display_tool_result: 処理中のテキスト長: {len(result_content['text'])}")
                print(f"[DEBUG] display_tool_result: テキストの最初の200文字: {result_content['text'][:200]}")
                
                # SUCCESS: パターンで始まる場合（Virtual Try-on用のシンプルレスポンス）
                if result_content["text"].startswith("SUCCESS: "):
                    print(f"[DEBUG] display_tool_result: SUCCESS パターンを検出")
                    image_file_path = result_content["text"][9:]  # "SUCCESS: " を除去
                    print(f"[DEBUG] 抽出された画像ファイルパス: {image_file_path}")
                    
                    try:
                        import os
                        from datetime import datetime
                        
                        if os.path.exists(image_file_path):
                            st.success("Virtual try-on が正常に実行されました")
                            
                            # ファイルパスの表示
                            st.write(f"**生成画像ファイル:** `{image_file_path}`")
                            
                            # 画像の表示
                            with open(image_file_path, 'rb') as f:
                                image_data = f.read()
                            
                            st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                            
                            # ダウンロードボタン
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.download_button(
                                label="🔽 画像をダウンロード",
                                data=image_data,
                                file_name=f"virtual_tryout_history_{timestamp}.png",
                                mime="image/png",
                                key=f"download_vto_history_{timestamp}"
                            )
                            
                            print(f"[DEBUG] display_tool_result: SUCCESS パターン処理完了")
                        else:
                            st.error(f"画像ファイルが見つかりません: {image_file_path}")
                            
                    except Exception as e:
                        print(f"[ERROR] display_tool_result: SUCCESS パターン処理エラー: {e}")
                        st.error(f"画像表示エラー: {str(e)}")
                
                # ERROR: パターンで始まる場合
                elif result_content["text"].startswith("ERROR: "):
                    print(f"[DEBUG] display_tool_result: ERROR パターンを検出")
                    error_message = result_content["text"][7:]  # "ERROR: " を除去
                    st.error(error_message)
                
                # JSONパターンの場合（従来の処理を維持）
                else:
                    try:
                        result_data = safe_parse_tool_result(result_content["text"])
                        print(f"[DEBUG] display_tool_result: 解析成功")
                        
                        # プレーンテキストの場合
                        if result_data.get("is_plain_text"):
                            st.text(result_data["text"])
                            return
                        
                        # Nova Canvas ツールの結果表示
                        if result_data.get("success", False):
                            print(f"[DEBUG] display_tool_result: 成功結果を処理中")
                            # ファイルパスから画像を読み込む場合
                            if "image_file" in result_data and result_data["image_file"]:
                                print(f"[DEBUG] display_tool_result: image_fileフィールドを検出: {result_data['image_file']}")
                                st.success(result_data.get("message", "画像生成が完了しました"))
                                try:
                                    import os
                                    from datetime import datetime
                                    
                                    image_file_path = result_data["image_file"]
                                    print(f"[DEBUG] display_tool_result: ファイル存在確認中: {image_file_path}")
                                    
                                    if os.path.exists(image_file_path):
                                        print(f"[DEBUG] display_tool_result: ファイルが存在します")
                                        with open(image_file_path, 'rb') as f:
                                            image_data = f.read()
                                        
                                        print(f"[DEBUG] display_tool_result: 画像データサイズ: {len(image_data)} bytes")
                                        st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                                        
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        st.download_button(
                                            label="🔽 画像をダウンロード",
                                            data=image_data,
                                            file_name=f"nova_canvas_result_{timestamp}.png",
                                            mime="image/png",
                                            key=f"download_history_file_{timestamp}"
                                        )
                                        
                                        if "parameters" in result_data:
                                            with st.expander("実行パラメータ"):
                                                st.json(result_data["parameters"])
                                        
                                        print(f"[DEBUG] display_tool_result: image_file表示完了")
                                    else:
                                        print(f"[ERROR] display_tool_result: ファイルが見つかりません: {image_file_path}")
                                        st.error(f"画像ファイルが見つかりません: {image_file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] display_tool_result: 画像表示エラー: {e}")
                                    st.error(f"画像表示エラー: {str(e)}")
                                
                        # Base64データの場合
                        elif "image" in result_data and result_data["image"]:
                            st.success(result_data.get("message", "画像生成が完了しました"))
                            
                            # Base64画像の表示
                            try:
                                import base64
                                from io import BytesIO
                                from datetime import datetime
                                
                                image_data = base64.b64decode(result_data["image"])
                                st.image(image_data, caption="Generated by Nova Canvas", use_column_width=True)
                                
                                # ダウンロードボタンを追加
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                st.download_button(
                                    label="🔽 画像をダウンロード",
                                    data=image_data,
                                    file_name=f"nova_canvas_result_{timestamp}.png",
                                    mime="image/png",
                                    key=f"download_history_{timestamp}"
                                )
                                
                                # パラメータ情報の表示
                                if "parameters" in result_data:
                                    with st.expander("実行パラメータ"):
                                        st.json(result_data["parameters"])
                                        
                            except Exception as e:
                                st.error(f"画像表示エラー: {str(e)}")
                                st.json(result_data)
                        
                        # 複数画像の場合を処理
                        elif ("success" in result_data and result_data["success"] and 
                              "images" in result_data and result_data["images"]):
                            
                            st.success(result_data.get("message", "画像生成が完了しました"))
                            
                            # 複数画像の表示
                            for i, image_b64 in enumerate(result_data["images"]):
                                try:
                                    import base64
                                    from io import BytesIO
                                    from datetime import datetime
                                    
                                    image_data = base64.b64decode(image_b64)
                                    st.image(image_data, caption=f"Generated by Nova Canvas - Image {i+1}", use_column_width=True)
                                    
                                    # 各画像にダウンロードボタンを追加
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    st.download_button(
                                        label=f"🔽 画像{i+1}をダウンロード",
                                        data=image_data,
                                        file_name=f"nova_canvas_result_{i+1}_{timestamp}.png",
                                        mime="image/png",
                                        key=f"download_history_multi_{i}_{timestamp}"
                                    )
                                    
                                except Exception as e:
                                    st.error(f"画像{i+1}表示エラー: {str(e)}")
                            
                            # パラメータ情報の表示
                            if "parameters" in result_data:
                                with st.expander("実行パラメータ"):
                                    st.json(result_data["parameters"])
                        
                        elif "success" in result_data and not result_data["success"]:
                            st.error(result_data.get("message", "ツール実行でエラーが発生しました"))
                            if "error" in result_data:
                                st.error(f"エラー詳細: {result_data['error']}")
                        else:
                            st.json(result_data)
                        
                    except Exception as e:
                        # 解析エラーの場合（safe_parse_tool_result内でハンドリング済み）
                        print(f"[ERROR] display_tool_result: 予期しないエラー: {str(e)}")
                        print(f"[ERROR] display_tool_result: エラータイプ: {type(e).__name__}")
                        st.error(f"ツール結果の処理中にエラーが発生しました: {str(e)}")
                        st.text(result_content["text"])


def handle_chat_input(messages, chat_history_file, models, bedrock_region, enable_prompt_cache_system, enable_prompt_cache_tools, enable_prompt_cache_messages, builtin_tools):
    """
    チャットタブでのユーザー入力とAIレスポンスを一元管理する中核関数。
    
    この関数は、テキストメッセージと画像アップロードを統合処理し、
    AWS BedrockのLLMとNova Canvasカスタムツールを組み合わせた
    高度なAIアシスタント機能を提供します。
    
    主要機能:
        - マルチモーダル入力処理（テキスト + 複数画像対応）
        - 画像の自動リサイズとContext Window最適化
        - Nova Canvas Virtual Try-on、スタイル変換機能
        - ストリーミングレスポンス表示
        - チャット履歴の自動保存（YAML形式）
        - ツール実行結果のリアルタイム表示
    
    引数:
        messages: 既存のチャット履歴
        chat_history_file: 履歴保存先ファイルパス
        models: 利用可能なLLMモデル設定
        bedrock_region: AWS Bedrockのリージョン
        enable_prompt_cache_*: プロンプトキャッシュ設定
        builtin_tools: 組み込みツールリスト（Nova Canvasツール含む）
    """
    image_support: bool = models[st.session_state.model_id]["image_support"]
    
    if prompt := st.chat_input("メッセージを入力してください...", accept_file="multiple", file_type=format["image"]):
        with st.chat_message("user"):
            st.write(prompt.text)
            for file in prompt.files:
                if image_support:
                    st.image(file.getvalue())
                else:
                    st.warning(
                        "このモデルは画像はサポートしていません。画像は使用されません。"
                    )

        # アップロードされた画像の処理と一時ファイル保存
        # Nova Canvasツール用の画像データを準備し、Context Window制限を回避
        uploaded_images_info = []
        if prompt.files and image_support:
            # 一時ディレクトリを作成（画像ファイルを保存してツールからアクセス可能にする）
            global TEMP_IMAGE_DIR
            if TEMP_IMAGE_DIR and os.path.exists(TEMP_IMAGE_DIR):
                # 前回実行時の古い一時ディレクトリをクリーンアップ
                shutil.rmtree(TEMP_IMAGE_DIR)
            
            TEMP_IMAGE_DIR = tempfile.mkdtemp(prefix="nova_canvas_")
            
            image_content: list[ContentBlock] = []
            for i, file in enumerate(prompt.files):
                if (file_format := file.type.split("/")[1]) in format["image"]:
                    # Strands Agentフレームワーク用の画像データ構造を作成
                    # LLMモデルが画像内容を理解するためのデータ
                    image_content.append(
                        {
                            "image": {
                                "format": cast(ImageFormat, file_format),
                                "source": {"bytes": file.getvalue()},
                            }
                        }
                    )
                    
                    # アップロードされた画像のバイトデータを取得
                    image_bytes = file.getvalue()
                    
                    # パフォーマンス最適化：大きな画像を自動リサイズ
                    # 環境変数RESIZE_IMAGESでリサイズ機能の有効/無効を制御
                    if os.environ.get("RESIZE_IMAGES", "true").lower() == "true":
                        # Nova Canvas処理とContext Window最適化のため512x512以下にリサイズ
                        # 品質75%で圧縮してファイルサイズも削減
                        image_bytes = resize_image_if_needed(image_bytes, max_size=(512, 512), quality=75)
                    
                    # 一時ファイルシステムに画像を保存
                    # Nova Canvasツールがファイルパス経由で画像にアクセスするため
                    temp_filename = f"image_{i + 1}.{file_format}"
                    temp_path = os.path.join(TEMP_IMAGE_DIR, temp_filename)
                    with open(temp_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    # 画像メタデータを記録（デバッグとユーザー情報提供用）
                    uploaded_images_info.append({
                        "index": i + 1,                    # 画像の順序番号
                        "filename": file.name,             # 元のファイル名
                        "format": file_format,             # 画像形式（png, jpeg等）
                        "size": len(image_bytes),          # リサイズ後のファイルサイズ
                        "file_path": temp_path,            # 一時ファイルの完全パス
                        "reference": f"image_{i + 1}"      # ツール内で使用する参照キー
                    })
            
            # Context Window Overflow を防ぐため、画像データはメッセージ履歴に含めない
            # 代わりに画像アップロードの事実のみを記録
            messages = messages + [
                {"role": "user", "content": [{"text": f"画像{len(uploaded_images_info)}枚をアップロードしました。"}]},
                {
                    "role": "assistant",
                    "content": [
                        {"text": "画像を確認しました。処理を続けてください。"}
                    ],
                },
            ]

        # 画像情報を含むシステムプロンプトの作成
        base_system_prompt = """あなたは優秀なAIエージェントです！

画像が含まれている場合は、以下のNova Canvas機能を適切に使用してください：

1. **Virtual Try-on機能**: 人物画像と服・商品画像の組み合わせの場合
   - 人物画像をソース画像、商品画像を参照画像として使用
   - 上半身の服の場合は "UPPER_BODY" ガーメントクラスを指定
   - 下半身の服の場合は "LOWER_BODY" ガーメントクラスを指定
   - 全身衣装の場合は "FULL_BODY" ガーメントクラスを指定
   - 靴の場合は "FOOTWEAR" ガーメントクラスを指定

2. **スタイル変換機能**: 画像のスタイルを変更したい場合
   - 利用可能スタイル: "3D animated family film", "Design sketch", "Flat vector illustration", "Graphic novel", "Maximalism", "Midcentury retro", "Photorealism", "Soft digital painting"

3. **画像生成機能**: テキストプロンプトから新しい画像を生成する場合

画像をアップロードされた際は、まず画像の内容を分析し、最適なNova Canvas機能を提案してください。"""

        # アップロードされた画像がある場合の追加情報（軽量版）
        if uploaded_images_info:
            images_info_text = f"\n\n## 利用可能な画像: {len(uploaded_images_info)}枚\n"
            images_info_text += """
**画像データの指定方法:**
- source_image: "image_1" (最初の画像)
- reference_image: "image_2" (2番目の画像)
- 以降は "image_3", "image_4" など

画像データは自動的に取得されるため、画像番号文字列のみを指定してください。
"""
            system_prompt = base_system_prompt + images_info_text
        else:
            system_prompt = base_system_prompt

        # MCPツールは無効化されており、Nova Canvasカスタムツールのみ使用
        tools = builtin_tools

        agent = Agent(
            model=BedrockModel(
                model_id=st.session_state.model_id,
                boto_session=boto3.Session(region_name=bedrock_region),
                cache_prompt="default" if enable_prompt_cache_system else None,
                cache_tools="default" if enable_prompt_cache_tools else None,
            ),
            system_prompt=system_prompt,
            messages=convert_messages(
                messages, enable_cache=enable_prompt_cache_messages
            ),
            callback_handler=None,
            tools=tools,
        )

        # ユーザープロンプトに画像参照情報のみを含める（Base64データは除外）
        user_prompt = prompt.text
        if uploaded_images_info:
            user_prompt += "\n\n## アップロードされた画像情報:\n"
            
            for img_info in uploaded_images_info:
                user_prompt += f"- 画像{img_info['index']}: {img_info['filename']} ({img_info['format']}, {img_info['size']:,} bytes)\n"
            
            if len(uploaded_images_info) >= 2:
                user_prompt += "\n**Virtual Try-on機能の使用方法:**\n"
                user_prompt += "nova_canvas_virtual_tryout(\n"
                user_prompt += f"    source_image=\"image_1\",  # {uploaded_images_info[0]['filename']}\n"
                user_prompt += f"    reference_image=\"image_2\",  # {uploaded_images_info[1]['filename']}\n"
                user_prompt += "    mask_type=\"GARMENT\",\n"
                user_prompt += "    garment_class=\"UPPER_BODY\"  # または LOWER_BODY, FULL_BODY, FOOTWEAR\n"
                user_prompt += ")\n"
            
            user_prompt += "\n**重要**: ツール呼び出し時は画像番号（\"image_1\", \"image_2\"など）を指定してください。実際の画像データは自動的に取得されます。\n"

        # デバッグ情報を表示
        if uploaded_images_info:
            with st.sidebar:
                st.success(f"✅ 画像データを準備しました: {len(uploaded_images_info)}枚")
                for img_info in uploaded_images_info:
                    st.info(f"📷 画像{img_info['index']}: {img_info['filename']}")
                    st.caption(f"サイズ: {img_info['size']:,} bytes, 形式: {img_info['format']}")
                
                # 一時ディレクトリの状態確認
                st.write("🔧 Nova Canvasツール:")
                st.success(f"一時ディレクトリ: {TEMP_IMAGE_DIR}")
                st.caption("画像ファイルは一時的に保存されています")

        agent_stream = agent.stream_async(prompt=user_prompt)

        # ツール結果を収集するためのリスト
        collected_tool_results = []
        
        def on_tool_result(tool_result):
            """ツール結果を受信したときのコールバック"""
            collected_tool_results.append(tool_result)
        
        with st.chat_message("assistant"):
            # ストリーミングを表示（ツール結果コールバック付き）
            st.write_stream(streaming(agent_stream, on_tool_result=on_tool_result))
            
            # ストリーミング完了後、収集したツール結果から画像を表示
            for tool_result in collected_tool_results:
                display_tool_result_realtime(tool_result)

        with open(chat_history_file, mode="wt") as f:
            yaml.safe_dump(agent.messages, f, allow_unicode=True)


def handle_image_generation(bedrock_region):
    """
    専用画像生成タブでのNova Canvas Text-to-Image機能を提供する関数。
    
    この関数は、チャット機能とは独立した直感的な画像生成インターフェースを提供し、
    構造化プロンプト、詳細設定、バッチ生成などの高度な機能を簡単に利用できます。
    
    主要機能:
        - 6パラメータ構造化プロンプト作成（Subject, Environment, Action, Lighting, Camera, Style）
        - 10種類のプロンプトサンプルテンプレート
        - 5種類のネガティブプロンプトサンプル
        - 29種類のアスペクト比オプション
        - 品質設定（standard/premium）
        - CFGスケール調整（1.0-10.0）
        - バッチ生成（1-5枚同時）
        - シード値制御（ランダム/固定）
        - プロンプトプレビュー機能
        - 否定語検出とアドバイス
        - 生成時間計測
    
    引数:
        bedrock_region: AWS Bedrockのリージョン設定
    """
    st.header("🎨 Nova Canvas 画像生成")
    st.markdown("""
    Amazon Nova Canvasを使用して、テキストプロンプトから高品質な画像を生成します。
    構造化されたプロンプト作成、ネガティブプロンプト、詳細な設定オプションをサポートしています。
    """)
    
    # プロンプトサンプル選択
    st.subheader("プロンプトサンプル")
    sample_names = ["カスタムプロンプト"] + [sample["title"] for sample in PROMPT_SAMPLES]
    selected_sample_idx = st.selectbox(
        "プロンプトサンプルを選択",
        range(len(sample_names)),
        format_func=lambda x: sample_names[x],
        help="事前定義されたプロンプトサンプルから選択、またはカスタムプロンプトを作成します。"
    )
    
    # 選択されたサンプルのデータを取得
    if selected_sample_idx == 0:
        # カスタムプロンプト
        sample_data = {"subject": "", "environment": "", "action": "", "lighting": "", "camera": "", "style": ""}
    else:
        sample_data = PROMPT_SAMPLES[selected_sample_idx - 1]
    
    # 6つのプロンプトパラメータ入力フィールド
    st.subheader("プロンプトパラメータ")
    col1, col2 = st.columns(2)
    
    with col1:
        subject = st.text_input(
            "被写体 (Subject) *",
            value=sample_data["subject"],
            help="画像の主要な被写体を指定します。"
        )
        
        environment = st.text_input(
            "環境・背景 (Environment)",
            value=sample_data["environment"],
            help="画像の背景や設定を指定します。"
        )
        
        action = st.text_input(
            "アクション・ポーズ (Action)",
            value=sample_data["action"],
            help="被写体の動作、ポーズ、位置を指定します。"
        )
    
    with col2:
        lighting = st.text_input(
            "照明 (Lighting)",
            value=sample_data["lighting"],
            help="画像の照明条件を指定します。"
        )
        
        camera = st.text_input(
            "カメラアングル (Camera)",
            value=sample_data["camera"],
            help="カメラの位置、アングル、フレーミングを指定します。"
        )
        
        style = st.text_input(
            "スタイル (Style)",
            value=sample_data["style"],
            help="画像のビジュアルスタイルを指定します。"
        )
    
    # ネガティブプロンプトセクション
    st.subheader("ネガティブプロンプト")
    negative_sample_names = ["カスタム"] + [sample["title"] for sample in NEGATIVE_PROMPT_SAMPLES]
    selected_negative_idx = st.selectbox(
        "ネガティブプロンプトサンプルを選択",
        range(len(negative_sample_names)),
        format_func=lambda x: negative_sample_names[x],
        help="避けたい要素を指定するネガティブプロンプトを選択します。"
    )
    
    if selected_negative_idx == 0:
        default_negative = ""
    else:
        default_negative = NEGATIVE_PROMPT_SAMPLES[selected_negative_idx - 1]["text"]
    
    negative_prompt = st.text_area(
        "ネガティブプロンプト",
        value=default_negative,
        height=100,
        help="画像から除外したい要素を指定します。"
    )
    
    # 画像設定セクション
    st.subheader("画像設定")
    col1, col2 = st.columns(2)
    
    with col1:
        # アスペクト比選択
        aspect_ratio_keys = list(ASPECT_RATIO_OPTIONS.keys())
        selected_aspect = st.selectbox(
            "アスペクト比",
            aspect_ratio_keys,
            index=1,  # 1024x1024をデフォルトに
            help="画像のアスペクト比を選択します。"
        )
        
        width, height = ASPECT_RATIO_OPTIONS[selected_aspect]
        
        # 品質設定
        quality = st.selectbox(
            "画像品質",
            ["standard", "premium"],
            index=0,
            help="画像の品質を選択します。premiumはより高品質ですが、生成時間が長くなります。"
        )
        
        # 生成数
        number_of_images = st.slider(
            "生成する画像数",
            min_value=1,
            max_value=5,
            value=1,
            help="一度に生成する画像の数を選択します。"
        )
    
    with col2:
        # CFGスケール
        cfg_scale = st.slider(
            "CFGスケール",
            min_value=1.0,
            max_value=10.0,
            value=3.0,
            step=0.1,
            help="プロンプトの忠実度を制御します。高い値ほどプロンプトに忠実になります。"
        )
        
        # シード値
        use_random_seed = st.checkbox("ランダムシードを使用", value=True)
        
        if use_random_seed:
            import random
            seed = random.randint(0, 2147483647)
            st.info(f"ランダムシード: {seed}")
        else:
            seed = st.number_input(
                "シード値",
                min_value=0,
                max_value=2147483647,
                value=0,
                help="同じシード値で同じプロンプトを使用すると、似たような結果が得られます。"
            )
    
    # プロンプトプレビュー
    if st.button("プロンプトプレビュー"):
        try:
            from nova_canvas_tool import PromptStructure
            prompt_structure = PromptStructure(
                subject=subject,
                environment=environment,
                action=action,
                lighting=lighting,
                camera=camera,
                style=style
            )
            
            generated_prompt = prompt_structure.generate_prompt()
            
            st.text_area(
                "生成されたプロンプト",
                value=generated_prompt,
                height=150,
                disabled=True
            )
            
            # 否定語チェック
            negation_words = prompt_structure.check_negation_words(generated_prompt)
            if negation_words:
                st.warning(f"プロンプトに否定語が含まれています: {', '.join(negation_words)}")
                st.info("否定語はネガティブプロンプトに移動することを推奨します。")
            
        except Exception as e:
            st.error(f"プロンプト生成エラー: {str(e)}")
    
    # 画像生成ボタン
    if st.button("🎨 画像を生成する", type="primary", use_container_width=True):
        if not subject.strip():
            st.error("被写体(Subject)は必須入力です。")
            return
            
        try:
            # プロンプト構造を作成
            from nova_canvas_tool import PromptStructure
            prompt_structure = PromptStructure(
                subject=subject,
                environment=environment,
                action=action,
                lighting=lighting,
                camera=camera,
                style=style
            )
            
            generated_prompt = prompt_structure.generate_prompt()
            
            # 画像生成の実行
            with st.spinner("画像を生成中..."):
                import time
                start_time = time.time()
                
                result = nova_canvas_text_to_image(
                    prompt=generated_prompt,
                    negative_prompt=negative_prompt if negative_prompt.strip() else None,
                    width=width,
                    height=height,
                    number_of_images=number_of_images,
                    quality=quality,
                    cfg_scale=cfg_scale,
                    seed=seed,
                    aws_region=bedrock_region
                )
                
                end_time = time.time()
                generation_time = end_time - start_time
                
            # 結果の表示
            if result.get("success"):
                st.success(f"{result.get('message', '')}　生成時間: {generation_time:.2f}秒")
                
                # 生成された画像の表示
                if "images" in result:
                    for i, image_b64 in enumerate(result["images"]):
                        try:
                            import base64
                            image_data = base64.b64decode(image_b64)
                            st.image(image_data, caption=f"生成画像 {i+1}")
                        except Exception as e:
                            st.error(f"画像{i+1}の表示エラー: {str(e)}")
                
                # パラメータ情報の表示
                if "parameters" in result:
                    with st.expander("生成パラメータ詳細"):
                        st.json(result["parameters"])
                        
            else:
                st.error(f"画像生成に失敗しました: {result.get('message', '')}") 
                if "error" in result:
                    st.error(f"エラー詳細: {result['error']}")
                    
        except Exception as e:
            st.error(f"画像生成中にエラーが発生しました: {str(e)}")
            st.exception(e)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
