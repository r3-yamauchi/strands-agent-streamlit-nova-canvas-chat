# CLAUDE.md

このファイルは、Claude Code (claude.ai/code) がこのリポジトリのコードを操作する際のガイダンスを提供します。

## プロジェクト概要

AWS BedrockのLLMモデルとAmazon Nova Canvasを統合したエンタープライズグレードのチャットアプリケーション。Strands Agentフレームワークを使用し、MCP（Model Context Protocol）に依存しない直接的なカスタムツール実装により、高度な対話型AIインターフェースと画像生成・編集機能を提供します。

## 技術スタックと主要アーキテクチャ

### コアテクノロジー
- **Streamlit**: WebUIフレームワーク
- **Strands Agent Framework**: LLMインタラクションとツール管理
- **AWS Bedrock**: LLMプロバイダー（Claude、Amazon Nova）
- **Amazon Nova Canvas**: 画像生成・編集API
- **nest_asyncio**: 同期環境での非同期処理実現

### 実装パターン
- **@tool デコレータ**: Strands Agent カスタムツール実装
- **Direct API Integration**: MCP経由ではなく直接AWS API呼び出し
- **Base64エンコーディング**: 画像データ処理
- **プロンプトキャッシング**: パフォーマンス最適化

### アーキテクチャの特徴
- **MCP非依存**: 外部プロトコルに依存しない安定した動作
- **高速化**: 直接API呼び出しによる大幅な性能向上
- **簡素化**: 複雑な依存関係を排除した保守性の向上
- **カスタマイズ**: 特化した機能実装が容易

## 開発環境のセットアップ

### 前提条件
- Python 3.12以上
- AWS アカウントとBedrock アクセス権限
- AWS認証情報の適切な設定（~/.aws/credentials または環境変数）

### インストールと実行

```bash
# 依存関係のインストール
uv pip install -e .
# または
pip install -e .

# Streamlitアプリケーションの起動
streamlit run app.py

# 環境変数の設定（必要に応じて）
export DEV=true  # 開発モード有効化
export AWS_PROFILE=your-profile  # AWSプロファイル指定
export AWS_REGION=us-east-1  # AWSリージョン指定
```

## アプリケーションアーキテクチャ詳細

### アプリケーションフロー

1. **初期化フェーズ**
   - 設定ファイル（config/config.json）の読み込み
   - 環境変数とAWS認証の検証
   - Streamlit UIの構築

2. **ユーザーインタラクションフェーズ**
   - サイドバーでのモデル選択
   - チャット履歴の管理（読み込み/保存）
   - テキスト/画像入力の処理

3. **処理フェーズ**
   - Nova Canvasカスタムツールの実行
   - エージェントの初期化と実行
   - ストリーミングレスポンスの処理

4. **結果表示フェーズ**
   - リアルタイムレスポンス表示
   - ツール使用の可視化
   - 画像生成結果の表示
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

#### プロンプトキャッシング最適化
```python
def convert_messages(messages, enable_cache):
    # 最新2つのユーザーターンにキャッシュポイントを追加
    # パフォーマンス向上のための重要機能
```

#### カスタムツール実装
```python
@tool
def nova_canvas_virtual_tryout(source_image: str, reference_image: str, ...):
    # AWS Bedrock Nova Canvas APIの直接呼び出し
    # MCP経由ではなく、カスタムツールとして実装
```

#### エラーハンドリングの強化
```python
try:
    result_data = json.loads(result_content["text"])
    # JSON形式の場合の処理
except json.JSONDecodeError:
    # JSON形式でない場合は通常のテキストとして表示
    st.text(result_content["text"])
```

## 設定ファイル詳細

### config/config.json
```json
{
    "chat_history_dir": "chat_history",      // チャット履歴保存先
    "mcp_config_file": "config/mcp.json",    // 従来の互換性のために保持（未使用）
    "bedrock_region": "us-east-1",           // AWS リージョン
    "models": {
        "<model-id>": {
            "cache_support": ["system", "messages", "tools"],  // キャッシュ可能要素
            "image_support": true/false                         // 画像入力対応
        }
    }
}
```

### config/mcp.json
```json
{
    "mcpServers": {
        "awslabs.nova-canvas-mcp-server": {
            "command": "uvx",
            "args": ["awslabs.nova-canvas-mcp-server@latest"],
            "env": {
                "AWS_PROFILE": "プロファイル名",
                "AWS_REGION": "リージョン名"
            },
            "disabled": true  // 現在は無効化されている
        }
    }
}
```

**注意**: `config/mcp.json`は従来の互換性のために保持されていますが、現在のバージョンでは使用されていません。

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
  - toolResult:
      content: [{text: "ツール実行結果"}]
      toolUseId: "unique-id"
  role: assistant
```

## Amazon Nova Canvas統合

### カスタムツール実装（nova_canvas_tool.py）

#### 実装済み機能
1. **nova_canvas_virtual_tryout**: Virtual try-on機能
2. **nova_canvas_style_generation**: スタイル変換機能  
3. **nova_canvas_get_styles**: 利用可能オプション取得

#### Virtual Try-on機能
- **3つのマスキングタイプ**：
  - `GARMENT`: 身体部位指定（上半身、下半身、全身、靴）
  - `PROMPT`: 自然言語での置換エリア指定
  - `IMAGE`: 白黒マスク画像使用

#### スタイル変換機能
- **8つのアーティスティックスタイル**：
  - 3D animated family film, Design sketch
  - Flat vector illustration, Graphic novel
  - Maximalism, Midcentury retro
  - Photorealism, Soft digital painting

#### 技術実装詳細
```python
# AWS Bedrock Nova Canvas APIの直接呼び出し
response = bedrock_client.invoke_model(
    modelId="amazon.nova-canvas-v1:0",
    body=json.dumps(inference_params)
)
```

### MCP機能無効化の理由
1. **パフォーマンス向上**: 直接API呼び出しによる高速化
2. **安定性確保**: 外部プロトコルに依存しない信頼性
3. **保守性向上**: シンプルな依存関係とエラーハンドリング
4. **カスタマイズ容易性**: 特化した機能実装が可能

### 画像データ処理の最新実装（v0.4.0）
- **カスタムツールラッパー**: Strands Agentのツール実行時に画像参照を実際のデータに置換
- **セッション状態の問題を解決**: ツールが別コンテキストで実行される問題に対応
- **直接データ注入**: "image_1", "image_2"のような参照を自動的にBase64データに変換
- **デバッグ機能強化**: ツールラッパーでの詳細なログ出力

## UI/UX仕様

### サイドバー機能
- **モデル選択**: ドロップダウンでモデル切り替え
- **プロンプトキャッシュ**: パフォーマンス最適化のトグル
- **ツール状態表示**: Nova Canvasカスタムツール使用中の情報表示
- **チャット履歴**: 最新20件の履歴表示と選択
- **新規チャット**: 新しい会話の開始

### メインチャット領域
- **入力エリア**: テキスト入力とファイルアップロード
- **画像プレビュー**: 対応モデルでの画像表示
- **レスポンス表示**: ストリーミング対応のマークダウン表示
- **ツール使用表示**: エキスパンダーでJSON形式表示
- **画像生成結果**: Nova Canvas生成画像の自動表示

## エラーハンドリングとバリデーション

### 安全なツール結果解析（v0.4.1最新機能）
```python
def safe_parse_tool_result(text: str) -> dict:
    """
    ツール結果のテキストを安全にPython辞書として解析する関数。
    
    JSON形式、Python辞書文字列形式、またはプレーンテキストを適切に処理します。
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
```

### 堅牢なツール結果表示処理
```python
# 最新のツール結果表示（display_tool_result_realtime、display_tool_result）
try:
    result_data = safe_parse_tool_result(result_content["text"])
    
    # プレーンテキストの場合
    if result_data.get("is_plain_text"):
        st.text(result_data["text"])
        return
    
    # Nova Canvas ツールの成功結果のみ処理
    if result_data.get("success", False):
        # 画像表示処理...
except Exception as ex:
    # 解析エラーの場合（safe_parse_tool_result内でハンドリング済み）
    print(f"[ERROR] 予期しないエラー: {str(ex)}")
    st.error(f"ツール結果の処理中にエラーが発生しました: {str(ex)}")
    st.text(result_content["text"])
```

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

### Nova Canvas ツール結果表示
```python
if ("success" in result_data and result_data["success"] and 
    "image" in result_data and result_data["image"]):
    # Base64画像の表示処理
    image_data = base64.b64decode(result_data["image"])
    st.image(image_data, caption="Generated by Nova Canvas")
```

### JSON解析エラーの完全解決
v0.4.1では、以下の問題を根本的に解決しました：
- **Python辞書文字列**: `{'success': True, 'message': '...'}`形式の自動変換
- **JSONDecodeError**: 3段階のフォールバック処理で完全回避
- **アプリケーション停止**: エラー時でも安定した動作を保証
- **デバッグ情報**: 詳細なログ出力でトラブルシューティングを支援

## 開発時の注意事項

### AWS認証
- Bedrock APIアクセスには適切なIAMロールまたは認証情報が必要
- デフォルトリージョンは `us-east-1`
- Nova Canvas利用には追加の権限が必要

### カスタムツール開発
- `@tool` デコレータを使用してStrands Agent統合
- 型ヒントとdocstringの適切な記述が重要
- エラーハンドリングの包括的な実装
- JSON形式でない結果に対する適切な処理

### パフォーマンス最適化
- プロンプトキャッシングを有効化して応答速度を向上
- 大きな画像ファイルは自動的にbase64エンコード
- ストリーミング処理でリアルタイム表示
- MCP初期化処理の削除による起動時間短縮

### デバッグ
- `DEV=true`環境変数でデバッグモードを有効化
- Streamlitのエラーメッセージは画面上に表示される
- カスタムツールのインポートエラーに注意
- JSON形式でないツール結果のエラーハンドリング

## ファイル構成と責務

```
strands-agent-streamlit-nova-canvas-chat/
├── app.py                    # メインアプリケーション（MCP機能無効化済み）
├── nova_canvas_tool.py       # Nova Canvas カスタムツール
├── config/
│   ├── config.json          # メイン設定
│   └── mcp.json             # MCP設定（未使用、互換性のため保持）
├── chat_history/            # チャット履歴（YAML）
├── docs/                    # ドキュメント・画像
├── pyproject.toml          # Python プロジェクト設定
├── README.md               # プロジェクト説明
└── CLAUDE.md               # Claude Code向けガイド
```

## 主要開発コマンド

### 開発用コマンド
```bash
# 開発モードでの起動
export DEV=true && streamlit run app.py

# 依存関係の確認
uv pip list

# カスタムツールのテスト
python -c "import nova_canvas_tool; print('OK')"

# 構文チェック
python -m py_compile nova_canvas_tool.py
python -m py_compile app.py
```

### トラブルシューティング
```bash
# AWS認証の確認
aws sts get-caller-identity

# Bedrockモデルの確認
aws bedrock list-foundation-models --region us-east-1

# Streamlitログの確認
streamlit run app.py --logger.level debug
```

## 重要な実装上の考慮事項

### セキュリティ
- AWS認証情報の適切な管理
- チャット履歴のローカル保存
- 画像データの一時処理

### パフォーマンス
- プロンプトキャッシングの活用
- ストリーミング処理の最適化
- 画像データの効率的な処理
- MCP初期化処理の削除による高速化

### 拡張性
- 新しいカスタムツールの追加が容易
- 外部プロトコルに依存しない安定した基盤
- 複数のAWS Bedrockモデル対応

### 保守性
- 型ヒントの適切な使用
- 包括的なエラーハンドリング
- コードコメントの日本語化
- シンプルな依存関係

## テスト戦略

### 単体テスト
```python
# Nova Canvasツールのテスト例
def test_nova_canvas_get_styles():
    result = nova_canvas_get_styles()
    assert result["success"] == True
    assert len(result["styles"]) == 8
```

### 統合テスト
```python
# アプリケーション全体のテスト
def test_app_startup():
    # Streamlitアプリの起動テスト
    # カスタムツールの読み込み確認
    pass
```

## 重要な注意事項

### 必須事項
- 既存ファイルの編集を優先し、不要な新規ファイル作成を避ける
- ドキュメントファイル（*.md）の作成は明示的に要求された場合のみ
- コード内での絵文字使用は明示的に要求された場合のみ

### 開発指針
- 要求されたことのみを実行し、それ以上でもそれ以下でもない
- 既存のコードベースとの一貫性を保つ
- 日本語でのコメントと文書化を徹底
- MCP機能は無効化されているため、カスタムツールのみを使用

### 現在のアーキテクチャの利点
- **高速化**: MCP経由の間接通信を排除
- **安定性**: 外部プロトコル依存を削除
- **保守性**: シンプルな依存関係構造
- **拡張性**: 新しいカスタムツールの追加が容易
- **ユーザビリティ**: タブ形式UIによる直感的な操作
- **高機能性**: 構造化プロンプトと詳細設定による高度な画像生成制御

## 最新の実装状況

### v0.4.1 安定性とエラーハンドリングの大幅改善
- **JSON解析エラー完全解決**: `safe_parse_tool_result`関数による安全なデータ解析
- **Python辞書文字列対応**: シングルクォート形式からJSONへの自動変換
- **3段階フォールバック**: JSON → Python辞書変換 → ast.literal_eval → プレーンテキスト
- **アプリケーション安定性向上**: JSONDecodeErrorによる停止問題を根本解決
- **エラーハンドリング強化**: 包括的な例外処理とログ出力改善

### v0.4.0 新機能と改善
- **カスタムツールラッパー**: 画像参照の自動データ注入機能
- **Virtual Try-on修正**: セッション状態アクセス問題の根本的解決
- **デバッグ機能強化**: ツール実行時の詳細ログ出力

### v0.3.0 新機能
- **テキストから画像生成**: nova_canvas_text_to_image カスタムツール
- **構造化プロンプト**: 6つのパラメータによる詳細制御
- **プロンプトサンプル**: 10種類の事前定義テンプレート
- **ネガティブプロンプト**: 5種類のカテゴリー別サンプル
- **アスペクト比オプション**: 29種類の豊富な選択肢
- **バッチ生成**: 1-5枚の同時生成
- **プロンプトプレビュー**: 生成前の確認機能
- **否定語検出**: プロンプト最適化支援
- **生成時間計測**: パフォーマンス監視

### 技術的改善（最新版）
- **堅牢なデータ解析**: 複数形式のツール結果に対応する安全な解析システム
- **正規表現パターンマッチング**: Python辞書からJSONへの正確な変換処理
- **タブ形式UI**: 機能分離による使いやすさ向上
- **エラーハンドリング**: JSON/非JSON/Python辞書の3形式対応
- **型安全性**: dataclassとバリデーション機能
- **日本語UI**: 全要素の日本語化（API通信は英語）
- **コメント**: 全ソースコードの日本語コメント化
- **ツール実行の安定化**: Strands Agentフレームワークとの統合改善

### 信頼性向上のための実装
- **safe_parse_tool_result関数**: 多様な入力形式に対応する安全な解析
- **正規表現による文字列変換**: `'key': 'value'` → `"key": "value"` の自動変換
- **ast.literal_eval活用**: 安全なPython辞書評価による信頼性確保
- **包括的フォールバック**: 解析失敗時の適切なテキスト表示

この実装により、MCP（Model Context Protocol）に依存しない高速で安定した包括的なAmazon Nova Canvas統合チャットアプリケーションが実現されています。特にv0.4.1では、ツール結果の解析における信頼性が大幅に向上し、アプリケーションの停止や例外発生がほぼ完全に解消されました。