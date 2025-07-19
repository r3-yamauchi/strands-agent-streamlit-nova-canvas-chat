# Strands Agent Streamlit Nova Canvas チャットアプリ

AWS BedrockのLLMモデルとAmazon Nova Canvasを活用したエンタープライズグレードのチャットアプリケーション。Strands Agentフレームワークを使用し、高度な画像生成・編集機能を提供します。

![](docs/image01.png)

## 概要

このアプリケーションは、AWS Bedrockを通じて様々な大規模言語モデル（LLM）と対話し、さらにAmazon Nova Canvasの画像生成機能を統合したチャットインターフェースを提供します。MCP（Model Context Protocol）に依存せず、直接的なカスタムツール実装により高速で安定した動作を実現しています。

## 主要機能

### 🤖 多様なAIモデル対応
- **Amazon Nova シリーズ**: Premier, Pro, Lite, Micro
- **Anthropic Claude シリーズ**: Sonnet 4, 3.7 Sonnet, 3.5 Sonnet, 3.5 Haiku, 3 Haiku
- **画像入力サポート**: 対応モデルでの画像アップロード・処理

### 🎨 Amazon Nova Canvas統合
- **テキストから画像生成**: 構造化プロンプトによる高品質画像生成
- **Virtual Try-on機能**: 人物画像と商品画像を組み合わせた仮想試着
- **スタイル変換**: 8つのアーティスティックスタイルでの画像変換
- **3つのマスキング方式**: ガーメント、プロンプト、画像マスク

### ⚙️ 高度な機能
- **タブ形式UI**: チャット機能と画像生成機能の統合インターフェース
- **構造化プロンプト**: 6つのパラメータによる詳細な画像生成制御
- **プロンプトキャッシング**: パフォーマンス最適化のためのキャッシュ機能
- **チャット履歴管理**: YAML形式での会話履歴保存・読み込み
- **リアルタイム表示**: ストリーミング対応のレスポンス表示
- **ツール使用可視化**: 実行されたツールの詳細表示

## 前提条件

- **Python**: 3.12以上
- **AWS認証**: Bedrockアクセス権限を持つAWSアカウント
- **認証情報**: 適切に設定されたAWS認証情報（~/.aws/credentials または環境変数）

## インストール

### 1. リポジトリクローン
```bash
git clone https://github.com/r3-yamauchi/strands-agent-streamlit-nova-canvas-chat.git
cd strands-agent-streamlit-nova-canvas-chat
```

### 2. 依存関係インストール
```bash
# uvを使用（推奨）
uv pip install -e .

# または標準pip
pip install -e .
```

### 3. 環境変数設定（オプション）
```bash
export DEV=true  # 開発モード有効化
export AWS_PROFILE=your-profile  # AWSプロファイル指定
export AWS_REGION=us-east-1  # AWSリージョン指定
```

## 設定

### メイン設定ファイル (`config/config.json`)

```json
{
    "chat_history_dir": "chat_history",
    "mcp_config_file": "config/mcp.json",
    "bedrock_region": "us-east-1",
    "models": {
        "us.amazon.nova-premier-v1:0": {
            "cache_support": [],
            "image_support": true
        },
        "us.anthropic.claude-sonnet-4-20250514-v1:0": {
            "cache_support": ["system", "messages", "tools"],
            "image_support": true
        }
    }
}
```

**注意**: `mcp_config_file`は従来の互換性のために設定に残されていますが、現在は使用されていません。

## 使用方法

### 1. アプリケーション起動
```bash
streamlit run app.py
```

### 2. Webインターフェース操作

#### サイドバー機能
- **モデル選択**: ドロップダウンでAIモデルを選択
- **プロンプトキャッシュ**: パフォーマンス最適化のオン/オフ
- **ツール状態表示**: Nova Canvasカスタムツール使用中の表示
- **チャット履歴**: 最新20件の履歴表示と選択
- **新規チャット**: 新しい会話の開始

#### メインインターフェース
- **🗨️ チャットタブ**: 従来のチャット機能とツール実行
  - **テキスト入力**: メッセージとプロンプト入力
  - **画像アップロード**: 複数画像の同時アップロード対応
  - **リアルタイム表示**: ストリーミング対応のレスポンス表示
  - **ツール実行表示**: JSON形式での詳細情報表示
- **🎨 画像生成タブ**: 専用の画像生成インターフェース
  - **構造化プロンプト入力**: 6つのパラメータによる詳細制御
  - **プロンプト・ネガティブプロンプトサンプル**: 事前定義テンプレート
  - **画像設定**: アスペクト比、品質、CFGスケール、シード値
  - **バッチ生成**: 最大5枚の同時生成

### 3. Nova Canvas機能の使用

#### テキストから画像生成（画像生成タブ）
1. **🎨 画像生成タブ**を選択
2. **プロンプトサンプル**から選択するか、カスタムプロンプト作成
3. **6つのパラメータ**を入力:
   - 被写体 (Subject): 必須項目
   - 環境・背景 (Environment)
   - アクション・ポーズ (Action)
   - 照明 (Lighting)
   - カメラアングル (Camera)
   - スタイル (Style)
4. **ネガティブプロンプト**を選択（任意）
5. **画像設定**を調整:
   - アスペクト比（29種類から選択）
   - 品質（standard/premium）
   - CFGスケール（1.0-10.0）
   - 生成枚数（1-5枚）
   - シード値（ランダム/固定）
6. **🎨 画像を生成する**ボタンをクリック

#### Virtual Try-on（チャットタブ）
```
人物の画像と服の画像をアップロードして、仮想試着を実行してください。
上半身の服を試着させたいです。
```

#### スタイル変換（チャットタブ）
```
この画像をPhotorealismスタイルで変換してください。
```

#### 利用可能オプション確認（チャットタブ）
```
Nova Canvasで利用可能なスタイルオプションを教えてください。
```

## Amazon Nova Canvas機能詳細

### テキストから画像生成機能
- **構造化プロンプト**: 6つのパラメータによる詳細制御
  - **Subject**: 被写体・人物の詳細（必須）
  - **Environment**: 背景・環境設定
  - **Action**: 動作・ポーズ・位置
  - **Lighting**: 照明設定
  - **Camera**: カメラ位置・フレーミング
  - **Style**: 画像スタイル
- **プロンプトサンプル**: 10種類の事前定義テンプレート
  - 油絵の猫、先生のストック写真、船上の女性イラスト
  - 男性モデルのファッション写真、ドラゴンイラスト
  - LAの交通渋滞のバットモービル、西部カウボーイのティンタイプ
  - 日本風版画、タンゴダンサーの油絵、レトロスタイルのラウンジシーン
- **ネガティブプロンプト**: 5つのカテゴリー別テンプレート
  - 一般的な画像品質の問題を回避
  - 画像内のテキストを回避
  - 歪んだ人物の特徴を回避
  - 写真品質の問題を回避
  - アーティスティックな問題を回避
- **画像設定**:
  - **29種類のアスペクト比**: 正方形、横長、縦長の豊富なオプション
  - **品質制御**: 標準/高品質（プレミアム）
  - **CFGスケール**: 1.0-10.0（プロンプト忠実度）
  - **シード値**: ランダム/固定値指定
  - **バッチ生成**: 1-5枚同時生成

### Virtual Try-on機能
- **ソース画像**: 人物または空間の画像
- **参照画像**: 試着させたい商品の画像
- **マスキング方式**:
  - **GARMENT**: 身体部位指定（上半身、下半身、全身、靴）
  - **PROMPT**: 自然言語での置換エリア指定
  - **IMAGE**: 白黒マスク画像使用

### スタイル変換機能
8つのアーティスティックスタイル:
- 3D animated family film
- Design sketch
- Flat vector illustration
- Graphic novel
- Maximalism
- Midcentury retro
- Photorealism
- Soft digital painting

## チャット履歴管理

### 保存形式
チャット履歴は`chat_history/`ディレクトリにYAMLファイルとして保存されます。

```yaml
- content:
  - text: "ユーザーメッセージ"
  - image: {data: "base64エンコードデータ", format: "png"}
  role: user
- content:
  - text: "アシスタントの応答"
  - toolUse:
      input: {...}
      name: tool_name
      toolUseId: "unique-id"
  role: assistant
```

### 履歴操作
- **新規チャット**: 「New Chat」ボタンでタイムスタンプ付きファイル作成
- **履歴読み込み**: サイドバーでファイル名クリック
- **自動保存**: 各メッセージ交換後に自動保存

## 利用可能ツール

### Nova Canvas Custom Tools
- `nova_canvas_text_to_image`: テキストから画像生成機能
- `nova_canvas_virtual_tryout`: Virtual try-on機能
- `nova_canvas_style_generation`: スタイル変換機能
- `nova_canvas_get_styles`: 利用可能オプション取得

### Built-in Tools
- `current_time`: 現在時刻取得
- `http_request`: HTTP リクエスト実行

## 技術アーキテクチャ

### コアテクノロジー
- **Streamlit**: WebUIフレームワーク
- **Strands Agent Framework**: LLMインタラクションとツール管理
- **AWS Bedrock**: LLMプロバイダー
- **Amazon Nova Canvas**: 画像生成・編集API
- **nest_asyncio**: 同期環境での非同期処理

### 実装パターン
- **@tool デコレータ**: Strands Agent カスタムツール実装
- **Direct API Integration**: MCP経由ではなく直接AWS API呼び出し
- **Base64エンコーディング**: 画像データ処理
- **プロンプトキャッシング**: パフォーマンス最適化

### アーキテクチャの利点
- **高速化**: MCP経由での間接的な通信を排除
- **安定性**: 外部プロトコルに依存しない直接統合
- **保守性**: シンプルな依存関係とエラーハンドリング
- **拡張性**: 新しいカスタムツールの追加が容易

## 開発・デバッグ

### 開発モード
```bash
export DEV=true
streamlit run app.py
```

### 依存関係の確認
```bash
uv pip list  # インストール済みパッケージ一覧
python -c "import nova_canvas_tool; print('OK')"  # カスタムツールの動作確認
```

### 構文チェック
```bash
python -m py_compile app.py
python -m py_compile nova_canvas_tool.py
```

## トラブルシューティング

### よくある問題

1. **AWS認証エラー**
   - AWS認証情報の設定を確認
   - Bedrockアクセス権限の確認

2. **画像が表示されない**
   - モデルの画像サポート確認
   - 画像ファイル形式の確認（PNG, JPEG）

3. **ツールが実行されない**
   - カスタムツールのインポート確認
   - AWS認証情報の設定確認

4. **JSONDecodeError**
   - ツール結果の形式確認
   - エラーハンドリングが適切に動作しているか確認

### ログ確認
```bash
# Streamlitのログを確認
streamlit run app.py --logger.level debug
```

## パフォーマンス最適化

### プロンプトキャッシング
- **system**: システムプロンプトキャッシュ
- **messages**: メッセージ履歴キャッシュ
- **tools**: ツール定義キャッシュ

### 画像処理最適化
- 最大4.1M画素（2048x2048）
- Base64エンコーディング最適化
- 自動リサイズ機能

### 起動時間短縮
- MCP初期化処理を削除することで起動時間を大幅短縮
- 軽量な依存関係による高速な初期化

## セキュリティ

### データ保護
- チャット履歴のローカル保存
- AWS認証情報の安全な管理
- 画像データの一時処理

### アクセス制御
- AWS IAMによるBedrock アクセス制限
- 環境変数による設定管理

## 設計思想

### なぜMCPを使用しないのか
1. **パフォーマンス**: 直接API呼び出しによる高速化
2. **安定性**: 外部プロトコルに依存しない安定した動作
3. **保守性**: シンプルな依存関係とエラーハンドリング
4. **カスタマイズ**: 特化した機能実装が容易

### カスタムツールの利点
- **型安全性**: 厳密な型ヒント付きの実装
- **エラーハンドリング**: 包括的なエラー処理
- **ドキュメント**: 詳細なdocstringによる説明
- **テスト容易性**: 単体テストが容易

## ライセンス

このプロジェクトはApache License 2.0のもとでライセンスされています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 謝辞

- [Strands Agents Framework](https://github.com/strandsdev/strands-agents)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [Amazon Nova Canvas](https://aws.amazon.com/bedrock/nova/)
- [Streamlit](https://streamlit.io/)

## 貢献

プロジェクトへの貢献を歓迎します。Issue報告やPull Request提出前に、開発ガイドラインを確認してください。

## 重要な機能改善

### JSON解析エラー修正（v0.4.1）
JSON解析エラーが発生してアプリケーションが停止する問題を根本的に解決しました：

- **安全な解析機能**: `safe_parse_tool_result`関数でPython辞書文字列をJSON形式に自動変換
- **複数形式対応**: JSON、Python辞書、プレーンテキストの3つの形式に対応
- **エラーハンドリング強化**: JSONDecodeErrorを完全に排除し、フォールバック処理を改善
- **アプリケーション安定性向上**: ツール実行結果の表示で例外が発生しなくなりました

### カスタムツールラッパー（v0.4.0）
画像参照問題を解決し、Virtual Try-on機能を安定化：

- **画像データ自動注入**: "image_1", "image_2"の参照を実際のBase64データに自動変換
- **セッション状態問題解決**: Strands Agentツール実行時の画像アクセス問題を根本解決
- **デバッグ機能強化**: ツール実行時の詳細ログ出力でトラブルシューティングを向上

## アーキテクチャの特徴（最新版）

### 信頼性の高いエラーハンドリング
- **3段階の解析プロセス**: JSON → Python辞書変換 → ast.literal_eval → プレーンテキスト
- **正規表現による文字列変換**: シングルクォートからダブルクォートへの安全な変換
- **包括的なフォールバック**: 解析に失敗した場合でもアプリケーションが停止しない

### パフォーマンス最適化
- **Context Window節約**: 大きな画像データをファイルシステムで管理
- **自動画像リサイズ**: 512x512px以下への自動縮小（環境変数で制御可能）
- **プロンプトキャッシング**: AWS Bedrockの高速化機能を活用

## 更新履歴

- **v0.4.1**: JSON解析エラー修正と安定性向上
  - `safe_parse_tool_result`関数の追加
  - Python辞書文字列のJSON変換機能
  - エラーハンドリング強化とフォールバック処理改善
  - アプリケーション停止問題の根本解決
- **v0.4.0**: カスタムツールラッパーと画像処理改善
  - 画像参照の自動データ注入機能
  - Virtual Try-on修正とセッション状態問題解決
  - デバッグ機能強化と詳細ログ出力
- **v0.3.0**: テキストから画像生成機能追加
  - 構造化プロンプト作成システム
  - タブ形式UI（チャット/画像生成）
  - 10種類のプロンプトサンプル
  - 5種類のネガティブプロンプトサンプル
  - 29種類のアスペクト比オプション
  - バッチ生成機能（1-5枚同時）
  - プロンプトプレビュー機能
  - 否定語検出機能
- **v0.2.0**: MCP機能無効化、カスタムツール特化
  - MCP Server依存を削除
  - Nova Canvas直接統合
  - パフォーマンス改善
  - UI簡素化
- **v0.1.0**: 初期リリース
  - 基本チャット機能
  - Amazon Nova Canvas統合
  - Virtual Try-on機能
  - カスタムツール実装