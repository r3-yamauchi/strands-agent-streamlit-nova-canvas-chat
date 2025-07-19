"""
Nova Canvas APIの直接テスト

実際のAWS Bedrock Nova Canvas APIとの通信をテストし、
レスポンス形式を確認します。
"""

import unittest
import json
import boto3
import base64
import os
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError


class TestNovaCanvasAPI(unittest.TestCase):
    """Nova Canvas APIの統合テストクラス"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラスの初期化"""
        # テスト用の小さな画像データ（1x1の透明PNG）
        cls.test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        # AWS設定
        cls.region = os.environ.get("AWS_REGION", "us-east-1")
        cls.skip_integration = os.environ.get("SKIP_INTEGRATION_TESTS", "false").lower() == "true"
    
    def setUp(self):
        """各テストの前処理"""
        if self.skip_integration:
            self.skipTest("統合テストはスキップされました（SKIP_INTEGRATION_TESTS=true）")
    
    def test_nova_canvas_api_response_format(self):
        """Nova Canvas APIのレスポンス形式を確認するテスト"""
        # Bedrockクライアントの作成
        client = boto3.client("bedrock-runtime", region_name=self.region)
        
        # Virtual Try-on用のリクエストボディ
        request_body = {
            "taskType": "VIRTUAL_TRY_ON",
            "virtualTryOnParams": {
                "sourceImage": self.test_image_base64,
                "referenceImage": self.test_image_base64,
                "maskType": "GARMENT",
                "garmentBasedMask": {
                    "garmentClass": "UPPER_BODY"
                }
            }
        }
        
        try:
            # API呼び出し
            response = client.invoke_model(
                modelId="amazon.nova-canvas-v1:0",
                body=json.dumps(request_body)
            )
            
            # レスポンスの解析
            response_body = json.loads(response["body"].read())
            
            # レスポンス構造の確認
            self.assertIsInstance(response_body, dict, "レスポンスは辞書型である必要があります")
            
            # デバッグ情報を出力
            print(f"\n[TEST] Nova Canvas APIレスポンス構造:")
            print(f"  - Type: {type(response_body)}")
            print(f"  - Keys: {list(response_body.keys())}")
            
            # imagesキーの存在確認
            if "images" in response_body:
                self.assertIsInstance(response_body["images"], list, "imagesは配列である必要があります")
                if len(response_body["images"]) > 0:
                    first_image = response_body["images"][0]
                    print(f"  - First image type: {type(first_image)}")
                    
                    # 画像データの形式を確認
                    if isinstance(first_image, dict):
                        print(f"  - First image keys: {list(first_image.keys())}")
                        if "image" in first_image:
                            # Base64データか確認
                            image_data = first_image["image"]
                            self.assertIsInstance(image_data, str, "画像データは文字列である必要があります")
                            # Base64デコードできるか確認
                            try:
                                base64.b64decode(image_data)
                                print("  - 画像データは有効なBase64形式です")
                            except Exception:
                                self.fail("画像データが有効なBase64形式ではありません")
                    elif isinstance(first_image, str):
                        # 直接Base64データの場合
                        try:
                            base64.b64decode(first_image)
                            print("  - 画像データは有効なBase64形式です（直接文字列）")
                        except Exception:
                            self.fail("画像データが有効なBase64形式ではありません")
            
            # エラーレスポンスでないことを確認
            self.assertNotIn("error", response_body, f"APIエラー: {response_body.get('error', '')}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            # 既知のエラーの場合は詳細情報を提供
            if error_code == "ValidationException":
                self.fail(f"ValidationException: {error_message}\n"
                         f"考えられる原因:\n"
                         f"- モデルIDが正しくない\n"
                         f"- リージョンでNova Canvasが利用できない\n"
                         f"- リクエスト形式が正しくない")
            elif error_code == "AccessDeniedException":
                self.fail(f"AccessDeniedException: {error_message}\n"
                         f"Nova Canvas APIへのアクセス権限がありません。\n"
                         f"IAMポリシーを確認してください。")
            else:
                self.fail(f"AWS API Error ({error_code}): {error_message}")
        
        except Exception as e:
            self.fail(f"予期しないエラー: {type(e).__name__}: {e}")
    
    def test_nova_canvas_model_availability(self):
        """Nova Canvasモデルが利用可能か確認するテスト"""
        client = boto3.client("bedrock", region_name=self.region)
        
        try:
            # 利用可能なモデルをリスト
            response = client.list_foundation_models()
            
            # Nova Canvasモデルを検索
            nova_canvas_models = [
                model for model in response['modelSummaries'] 
                if 'nova-canvas' in model['modelId'].lower()
            ]
            
            # Nova Canvasモデルが存在することを確認
            self.assertGreater(len(nova_canvas_models), 0, 
                             "Nova Canvasモデルが見つかりません")
            
            # モデル情報を出力
            print(f"\n[TEST] 利用可能なNova Canvasモデル:")
            for model in nova_canvas_models:
                print(f"  - {model['modelId']} ({model['modelName']})")
                
                # 正しいモデルIDを確認
                if model['modelId'] == "amazon.nova-canvas-v1:0":
                    print("  ✓ 期待されるモデルIDが確認されました")
        
        except ClientError as e:
            self.fail(f"モデルリストの取得に失敗: {e}")


class TestNovaCanvasAPIMock(unittest.TestCase):
    """Nova Canvas APIのモックテストクラス"""
    
    @patch('boto3.client')
    def test_api_response_handling(self, mock_boto_client):
        """様々なAPIレスポンス形式を処理できることを確認"""
        # モッククライアントの設定
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        # テストケース: 正常なレスポンス（images配列形式）
        test_cases = [
            # ケース1: 標準的なレスポンス形式
            {
                "response": {"images": [{"image": "base64_data_here"}]},
                "expected_image": "base64_data_here"
            },
            # ケース2: imagesが文字列配列の場合
            {
                "response": {"images": ["base64_data_here"]},
                "expected_image": "base64_data_here"
            },
            # ケース3: 直接imageキーがある場合
            {
                "response": {"image": "base64_data_here"},
                "expected_image": "base64_data_here"
            },
            # ケース4: エラーレスポンス
            {
                "response": {"error": "Something went wrong"},
                "expected_error": True
            }
        ]
        
        from nova_canvas_tool import nova_canvas_virtual_tryout
        
        for i, test_case in enumerate(test_cases):
            with self.subTest(case=i):
                # モックレスポンスの設定
                mock_response = {
                    'body': MagicMock(
                        read=lambda: json.dumps(test_case["response"]).encode('utf-8')
                    )
                }
                mock_client.invoke_model.return_value = mock_response
                
                # 関数の実行
                result = nova_canvas_virtual_tryout(
                    source_image="test_base64",
                    reference_image="test_base64",
                    mask_type="GARMENT",
                    garment_class="UPPER_BODY"
                )
                
                # 結果の検証
                if test_case.get("expected_error"):
                    self.assertFalse(result["success"])
                    self.assertIn("error", result)
                else:
                    self.assertTrue(result["success"])
                    self.assertEqual(result["image"], test_case["expected_image"])


if __name__ == '__main__':
    # 統合テストを実行するかどうかを環境変数で制御
    # SKIP_INTEGRATION_TESTS=true python -m unittest tests.test_nova_canvas_api
    unittest.main(verbosity=2)