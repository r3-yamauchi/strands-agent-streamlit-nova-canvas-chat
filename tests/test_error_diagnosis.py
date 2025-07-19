"""
Nova Canvas エラー診断テスト

発生しているエラーの原因を特定するためのテストスイート
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from io import BytesIO


class TestErrorDiagnosis(unittest.TestCase):
    """エラー診断用のテストクラス"""
    
    def test_response_format_error_reproduction(self):
        """'str' object has no attribute 'get' エラーを再現するテスト"""
        
        # 様々なレスポンス形式をテスト
        test_responses = [
            # ケース1: response_body全体が文字列の場合
            '"base64_image_data_here"',
            
            # ケース2: imagesが文字列の配列の場合
            '{"images": ["base64_image_data_here"]}',
            
            # ケース3: imagesの中身が文字列の場合
            '{"images": "base64_image_data_here"}',
            
            # ケース4: 正常な形式
            '{"images": [{"image": "base64_image_data_here"}]}',
            
            # ケース5: 空のレスポンス
            '{}',
            
            # ケース6: エラーレスポンス
            '{"error": "Invalid request"}',
        ]
        
        for i, response_str in enumerate(test_responses):
            with self.subTest(case=i):
                print(f"\n[TEST CASE {i+1}] レスポンス: {response_str[:50]}...")
                
                try:
                    # レスポンスをパース
                    response_body = json.loads(response_str)
                    print(f"  パース成功: type={type(response_body)}")
                    
                    # 元のコードで発生したエラーを再現
                    try:
                        # エラーが発生した行をシミュレート
                        result = response_body.get("images", [{}])[0].get("image", "")
                        print(f"  元のコード: 成功 - result={result[:20] if result else 'empty'}...")
                    except AttributeError as e:
                        print(f"  元のコード: AttributeError発生 - {e}")
                        
                        # どこでエラーが発生したか診断
                        if isinstance(response_body, str):
                            print(f"    → response_bodyが文字列です")
                        elif "images" in response_body:
                            images = response_body["images"]
                            print(f"    → imagesの型: {type(images)}")
                            if isinstance(images, list) and len(images) > 0:
                                first_item = images[0]
                                print(f"    → images[0]の型: {type(first_item)}")
                                if isinstance(first_item, str):
                                    print(f"    → images[0]が文字列なので.get()できません")
                                    
                except json.JSONDecodeError as e:
                    print(f"  JSONパースエラー: {e}")
    
    @patch('boto3.client')
    def test_nova_canvas_error_handling(self, mock_boto_client):
        """Nova Canvasツールのエラーハンドリングをテスト"""
        from nova_canvas_tool import extract_and_encode_image
        
        # モッククライアントの設定
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        # ケース1: imagesが文字列配列の場合のレスポンス
        mock_response = Mock()
        mock_response_body = BytesIO(json.dumps({"images": ["base64_data"]}).encode('utf-8'))
        mock_response.__getitem__ = lambda self, key: {"body": mock_response_body}[key]
        
        mock_client.invoke_model.return_value = mock_response
        
        # extract_and_encode_image関数のモック
        with patch('nova_canvas_tool.extract_and_encode_image') as mock_extract:
            mock_extract.return_value = "test_base64_data"
            
            from nova_canvas_tool import nova_canvas_virtual_tryout
            
            result = nova_canvas_virtual_tryout(
                source_image="test",
                reference_image="test",
                mask_type="GARMENT",
                garment_class="UPPER_BODY"
            )
            
            print(f"\n[TEST] 結果: success={result.get('success')}")
            if not result.get('success'):
                print(f"  エラー: {result.get('error')}")
                print(f"  エラータイプ: {result.get('error_type')}")
    
    def test_access_denied_diagnosis(self):
        """AccessDeniedExceptionの診断テスト"""
        import boto3
        from botocore.exceptions import ClientError
        
        print("\n[診断] Nova Canvas APIアクセス権限チェック")
        
        # 1. 現在の認証情報を確認
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"  AWS アカウントID: {identity['Account']}")
            print(f"  ARN: {identity['Arn']}")
        except Exception as e:
            print(f"  認証情報の取得失敗: {e}")
        
        # 2. Bedrockモデルアクセスの確認
        try:
            bedrock = boto3.client('bedrock', region_name='us-east-1')
            models = bedrock.list_foundation_models()
            
            nova_models = [m for m in models['modelSummaries'] if 'nova' in m['modelId'].lower()]
            print(f"\n  利用可能なNovaモデル数: {len(nova_models)}")
            
            # Nova Canvasが含まれているか確認
            nova_canvas = [m for m in nova_models if 'nova-canvas' in m['modelId']]
            if nova_canvas:
                print(f"  ✓ Nova Canvasモデルがリストに含まれています")
            else:
                print(f"  ✗ Nova Canvasモデルがリストに含まれていません")
                print(f"  → モデルアクセスをリクエストする必要があります")
                
        except ClientError as e:
            print(f"  Bedrockモデルリストの取得失敗: {e}")
            
        print("\n[推奨対処法]")
        print("  1. AWS Bedrockコンソールでモデルアクセスをリクエスト")
        print("  2. IAMポリシーに以下の権限があることを確認:")
        print("     - bedrock:InvokeModel")
        print("     - bedrock:InvokeModelWithResponseStream")
        print("  3. 正しいリージョンを使用していることを確認")


if __name__ == '__main__':
    unittest.main(verbosity=2)