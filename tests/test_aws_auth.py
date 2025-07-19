"""
AWS認証とNova Canvas APIアクセスの診断テスト

このテストスイートは以下を検証します：
1. .envファイルからの環境変数読み込み
2. AWS認証情報の有効性
3. Bedrockサービスへのアクセス権限
4. Nova Canvasモデルの利用可能性
"""

import unittest
import os
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
import sys

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAWSAuthentication(unittest.TestCase):
    """AWS認証の診断テストクラス"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラスの初期化"""
        # .envファイルの読み込み
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(env_path)
        
        print(f"\n[診断] .envファイルパス: {env_path}")
        print(f"[診断] .envファイル存在: {os.path.exists(env_path)}")
    
    def test_env_file_loaded(self):
        """環境変数が正しく読み込まれているか確認"""
        print("\n=== 環境変数の確認 ===")
        
        # 必要な環境変数のチェック
        required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION']
        
        for var in required_vars:
            value = os.environ.get(var)
            if value:
                if var == 'AWS_ACCESS_KEY_ID':
                    print(f"✓ {var}: {value[:10]}...{value[-4:]}")  # 部分的に表示
                elif var == 'AWS_SECRET_ACCESS_KEY':
                    print(f"✓ {var}: {'*' * 20}")  # 秘密情報はマスク
                else:
                    print(f"✓ {var}: {value}")
            else:
                print(f"✗ {var}: 未設定")
                self.fail(f"{var}が設定されていません")
    
    def test_aws_credentials_valid(self):
        """AWS認証情報が有効か確認"""
        print("\n=== AWS認証情報の検証 ===")
        
        try:
            # STSを使用して認証情報を確認
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            
            print(f"✓ AWS アカウントID: {identity['Account']}")
            print(f"✓ ARN: {identity['Arn']}")
            print(f"✓ ユーザーID: {identity['UserId']}")
            
            # 認証成功
            self.assertIsNotNone(identity)
            
        except NoCredentialsError:
            self.fail("AWS認証情報が見つかりません。.envファイルの設定を確認してください。")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidClientTokenId':
                self.fail("AWS Access Key IDが無効です。")
            elif error_code == 'SignatureDoesNotMatch':
                self.fail("AWS Secret Access Keyが無効です。")
            else:
                self.fail(f"AWS認証エラー: {e}")
        except Exception as e:
            self.fail(f"予期しないエラー: {e}")
    
    def test_bedrock_access(self):
        """Bedrockサービスへのアクセスを確認"""
        print("\n=== Bedrockサービスアクセスの確認 ===")
        
        try:
            # Bedrockクライアントの作成
            bedrock = boto3.client('bedrock', region_name='us-east-1')
            
            # 利用可能なモデルをリスト
            response = bedrock.list_foundation_models()
            
            all_models = response.get('modelSummaries', [])
            print(f"✓ 利用可能なモデル総数: {len(all_models)}")
            
            # Nova関連モデルを検索
            nova_models = [m for m in all_models if 'nova' in m['modelId'].lower()]
            print(f"✓ Novaモデル数: {len(nova_models)}")
            
            # Nova Canvasモデルを確認
            nova_canvas_found = False
            for model in nova_models:
                print(f"  - {model['modelId']} ({model['modelName']})")
                if model['modelId'] == 'amazon.nova-canvas-v1:0':
                    nova_canvas_found = True
                    print(f"    ✓ Nova Canvasモデルが見つかりました！")
                    print(f"    プロバイダー: {model['providerName']}")
                    print(f"    ステータス: {model.get('modelLifecycle', {}).get('status', 'N/A')}")
            
            self.assertTrue(nova_canvas_found, "Nova Canvasモデルが見つかりません")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                self.fail("Bedrockサービスへのアクセスが拒否されました。IAMポリシーを確認してください。")
            else:
                self.fail(f"Bedrockアクセスエラー: {e}")
        except Exception as e:
            self.fail(f"予期しないエラー: {e}")
    
    def test_nova_canvas_invoke(self):
        """Nova Canvas APIを実際に呼び出してテスト"""
        print("\n=== Nova Canvas API呼び出しテスト ===")
        
        try:
            # Bedrock Runtimeクライアントの作成
            bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            # テスト用の小さな画像（1x1 透明PNG）
            test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            
            # Virtual Try-onテストリクエスト
            request_body = {
                "taskType": "VIRTUAL_TRY_ON",
                "virtualTryOnParams": {
                    "sourceImage": test_image,
                    "referenceImage": test_image,
                    "maskType": "GARMENT",
                    "garmentBasedMask": {
                        "garmentClass": "UPPER_BODY"
                    }
                }
            }
            
            print("✓ リクエストボディを準備しました")
            print(f"  モデルID: amazon.nova-canvas-v1:0")
            print(f"  タスクタイプ: VIRTUAL_TRY_ON")
            
            # API呼び出し
            response = bedrock_runtime.invoke_model(
                modelId="amazon.nova-canvas-v1:0",
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # レスポンスの解析
            response_body = json.loads(response['body'].read())
            
            print("✓ Nova Canvas APIの呼び出しに成功しました！")
            print(f"  レスポンスキー: {list(response_body.keys())}")
            
            # 画像が返されたか確認
            if 'images' in response_body:
                print(f"  生成された画像数: {len(response_body['images'])}")
                
                # 画像データの形式を確認
                if response_body['images']:
                    first_image = response_body['images'][0]
                    if isinstance(first_image, dict) and 'image' in first_image:
                        print("  画像形式: オブジェクト形式 {'image': 'base64_data'}")
                    elif isinstance(first_image, str):
                        print("  画像形式: 文字列形式（Base64データ直接）")
            
            self.assertIn('images', response_body, "レスポンスに画像が含まれていません")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'ValidationException':
                # ValidationExceptionの詳細を解析
                if 'invalid model identifier' in error_message.lower():
                    self.fail(f"モデルIDが無効です: {error_message}\n"
                             "Nova Canvasへのアクセス権限がない可能性があります。")
                else:
                    self.fail(f"リクエスト形式エラー: {error_message}")
            elif error_code == 'AccessDeniedException':
                self.fail(f"Nova Canvas APIへのアクセスが拒否されました: {error_message}\n"
                         "Bedrockコンソールでモデルアクセスをリクエストしてください。")
            else:
                self.fail(f"API呼び出しエラー ({error_code}): {error_message}")
        except Exception as e:
            self.fail(f"予期しないエラー: {type(e).__name__}: {e}")
    
    def test_region_configuration(self):
        """リージョン設定の確認"""
        print("\n=== リージョン設定の確認 ===")
        
        # 環境変数から設定されたリージョン
        env_region = os.environ.get('AWS_DEFAULT_REGION', '未設定')
        print(f"環境変数のリージョン: {env_region}")
        
        # Nova Canvasが利用可能なリージョンの確認
        nova_canvas_regions = ['us-east-1', 'us-west-2']  # 利用可能なリージョン
        
        if env_region in nova_canvas_regions:
            print(f"✓ {env_region}はNova Canvasが利用可能なリージョンです")
        else:
            print(f"⚠️ Nova Canvasは以下のリージョンで利用可能です: {', '.join(nova_canvas_regions)}")
            if env_region != 'us-east-1':
                print("  → us-east-1の使用を推奨します")


if __name__ == '__main__':
    print("=" * 60)
    print("AWS認証とNova Canvasアクセスの診断テスト")
    print("=" * 60)
    
    # 詳細な出力でテストを実行
    unittest.main(verbosity=2)