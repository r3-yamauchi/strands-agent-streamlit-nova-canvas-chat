# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

AWS BedrockのLLMモデルを使用したエンタープライズグレードのチャットアプリケーション。Strands agentフレームワークとMCP（Model Context Protocol）ツールシステムを統合し、高度な対話型AIインターフェースを提供。

## 開発環境のセットアップ

### 前提条件
- Python 3.12以上
- AWS アカウントとBedrock アクセス権限
- AWS認証情報の適切な設定（~/.aws/credentials または環境変数）
- Docker（一部MCPツール用）

### インストールと実行

```bash
# 依存関係のインストール
pip install -e .
# または uv を使用
uv pip install -e .

# Streamlitアプリケーションの起動
streamlit run app.py

# 環境変数の設定（必要に応じて）
export DEV=true  # 開発モード有効化
```

## アーキテクチャ詳細

### コア技術スタック

- **Streamlit**: WebUIフレームワーク
- **Strands Agent Framework**: LLMインタラクションとツール管理
- **AWS Bedrock**: LLMプロバイダー（Claude、Amazon Nova）
- **MCP（Model Context Protocol）**: 外部ツール統合プロトコル
- **nest_asyncio**: 同期環境での非同期処理実現

### アプリケーションフロー

1. **初期化フェーズ**
   - 設定ファイル（config/*.json）の読み込み
   - 環境変数とAWS認証の検証
   - Streamlit UIの構築

2. **ユーザーインタラクションフェーズ**
   - サイドバーでのモデル/ツール選択
   - チャット履歴の管理（読み込み/保存）
   - テキスト/画像入力の処理

3. **処理フェーズ**
   - MCPツールの動的ロード（ExitStackパターン）
   - エージェントの初期化と実行
   - ストリーミングレスポンスの処理

4. **結果表示フェーズ**
   - リアルタイムレスポンス表示
   - ツール使用の可視化
   - チャット履歴の更新と保存

### 重要な実装パターン

#### 非同期処理の統合
```python
# app.pyでの実装
import nest_asyncio
nest_asyncio.apply()  # Streamlitの制約を回避

async def streaming(stream):
    async for chunk in stream:
        # ストリーミング処理
```

#### MCPクライアント管理
```python
with ExitStack() as stack:
    for server_name, server_config in selected_mcp.items():
        # クライアントの動的ロードと管理
        client = stack.enter_context(StdioClient(server_name, server_config["command"]))
```

#### プロンプトキャッシング最適化
```python
def convert_messages(messages, enable_cache):
    # 最新2つのユーザーターンにキャッシュポイントを追加
    # パフォーマンス向上のための重要機能
```

## 設定ファイル詳細

### config/config.json
```json
{
    "chat_history_dir": "chat_history",      // チャット履歴保存先
    "mcp_config_file": "config/mcp.json",    // MCPツール設定
    "bedrock_region": "ap-northeast-1",      // AWS リージョン
    "models": {
        "<model-id>": {
            "cache_support": ["system", "messages", "tools"],  // キャッシュ可能要素
            "image_support": true/false                        // 画像入力対応
        }
    }
}
```

### config/mcp.json
```json
{
    "mcpServers": {
        "server-name": {
            "command": "実行コマンド",
            "args": ["引数"]
        }
    }
}
```

## チャット履歴フォーマット

YAMLファイルとして保存（例：chat_history/1747940369.yaml）：
```yaml
- content:
  - text: "ユーザーメッセージ"
  - image: {data: "base64エンコードデータ", format: "png"}  # 画像の場合
  role: user
- content:
  - text: "アシスタントの応答"
  - toolUse:
      input: {...}
      name: tool_name
      toolUseId: "unique-id"
  role: assistant
```

## UI/UX仕様

### サイドバー機能
- **モデル選択**: ドロップダウンでモデル切り替え
- **プロンプトキャッシュ**: パフォーマンス最適化のトグル
- **MCPツール選択**: 複数選択可能なチェックボックス
- **チャット履歴**: 最新20件の履歴表示と選択
- **新規チャット**: 新しい会話の開始

### メインチャット領域
- **入力エリア**: テキスト入力とファイルアップロード
- **画像プレビュー**: 対応モデルでの画像表示
- **レスポンス表示**: ストリーミング対応のマークダウン表示
- **ツール使用表示**: エキスパンダーでJSON形式表示

## エラーハンドリングとバリデーション

### 画像サポート検証
```python
if not model_config.get("image_support", False) and uploaded_file:
    st.warning("このモデルは画像はサポートしていません。画像は使用されません。")
```

### ファイル存在確認
```python
if Path(chat_history_file).exists():
    # 安全な読み込み処理
```

## 開発時の注意事項

### AWS認証
- Bedrock APIアクセスには適切なIAMロールまたは認証情報が必要
- デフォルトリージョンは `ap-northeast-1`（東京）

### MCPツール実行
- 一部のツールはDockerが必要（例：cdatakintone）
- ツール実行時のタイムアウトやエラーハンドリングに注意

### パフォーマンス最適化
- プロンプトキャッシングを有効化して応答速度を向上
- 大きな画像ファイルは自動的にbase64エンコード

### デバッグ
- `DEV`環境変数を設定してデバッグモードを有効化
- Streamlitのエラーメッセージは画面上に表示される
