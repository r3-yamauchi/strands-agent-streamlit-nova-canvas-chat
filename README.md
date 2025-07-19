# Strands Agent Streamlit Nova Canvas チャットアプリ

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/strands-agent-streamlit-nova-canvas-chat)

Amazon Nova Canvas の Virtual try-on 機能のサンプルです。
Streamlit と Strands Agents SDK を使用しています。

## 前提条件

- **Python**: 3.12以上（uvの使用を推奨します）
- **AWS認証**: Bedrockアクセス権限を持つAWSアカウント

## インストール

### 1. リポジトリクローン
```bash
git clone https://github.com/r3-yamauchi/strands-agent-streamlit-nova-canvas-chat.git
cd strands-agent-streamlit-nova-canvas-chat
```

### 2. 環境変数設定（.envファイルを作成してください）
```bash
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-access-key>
AWS_DEFAULT_REGION=us-east-1
```

## 使用方法

### 1. アプリケーション起動
```bash
uv run streamlit run app.py
```

### 2. Nova Canvas機能の使用

#### Virtual Try-on（チャットタブ）
```
image1.png の男性に image2.png の上着を着せた画像を生成して
```

## Amazon Nova Canvas機能詳細

### Virtual Try-on機能
- **ソース画像**: 人物または空間の画像
- **参照画像**: 試着させたい商品の画像
- **マスキング方式**:
  - **GARMENT**: 身体部位指定（上半身、下半身、全身、靴）
  - **PROMPT**: 自然言語での置換エリア指定
  - **IMAGE**: 白黒マスク画像使用

## チャット履歴管理

### 保存形式
チャット履歴は`chat_history/`ディレクトリにYAMLファイルとして保存されます。

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

## トラブルシューティング

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
