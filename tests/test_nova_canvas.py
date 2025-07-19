"""
Nova Canvas Virtual Try-on機能のユニットテスト

一時ファイルを使用した画像データ共有の動作確認を行います。
"""

import unittest
import tempfile
import shutil
import os
import base64
import json
from unittest.mock import patch, MagicMock

from nova_canvas_tool import extract_and_encode_image, nova_canvas_virtual_tryout, nova_canvas_get_styles
from app import builtin_tools


class TestNovaCanvasTools(unittest.TestCase):
    """Nova Canvasツールのテストクラス"""
    
    def setUp(self):
        """各テストの前に実行される準備処理"""
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp(prefix='nova_canvas_')
        
        # テスト用の画像データ（小さなPNGファイル）
        self.test_image_data = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        )
        
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_tool_registration(self):
        """すべてのNova Canvasツールが正しく登録されているかテスト"""
        # builtin_toolsに含まれるツールを確認
        tool_names = [getattr(tool, 'tool_name', None) for tool in builtin_tools]
        
        # 必要なツールが含まれていることを確認
        self.assertIn('nova_canvas_virtual_tryout', tool_names)
        self.assertIn('nova_canvas_style_generation', tool_names)
        self.assertIn('nova_canvas_get_styles', tool_names)
        self.assertIn('nova_canvas_text_to_image', tool_names)
        
        # すべてのツールがDecoratedFunctionTool型であることを確認
        for tool in builtin_tools:
            if hasattr(tool, 'tool_name') and 'nova_canvas' in tool.tool_name:
                self.assertEqual(type(tool).__name__, 'DecoratedFunctionTool')
    
    def test_extract_and_encode_image_from_temp_file(self):
        """一時ファイルからの画像データ取得テスト"""
        # テスト画像ファイルを作成
        test_file_1 = os.path.join(self.temp_dir, 'image_1.png')
        test_file_2 = os.path.join(self.temp_dir, 'image_2.jpg')
        
        with open(test_file_1, 'wb') as f:
            f.write(self.test_image_data)
        with open(test_file_2, 'wb') as f:
            f.write(self.test_image_data)
        
        # 画像参照からBase64データを取得
        result1 = extract_and_encode_image('image_1')
        result2 = extract_and_encode_image('image_2')
        
        # 正しくBase64エンコードされていることを確認
        expected_base64 = base64.b64encode(self.test_image_data).decode('utf-8')
        self.assertEqual(result1, expected_base64)
        self.assertEqual(result2, expected_base64)
    
    def test_extract_and_encode_image_not_found(self):
        """存在しない画像参照のエラーハンドリングテスト"""
        # 存在しない画像参照でエラーが発生することを確認
        with self.assertRaises(ValueError) as context:
            extract_and_encode_image('image_99')
        
        self.assertIn('画像ファイル image_99 が見つかりません', str(context.exception))
    
    def test_extract_and_encode_image_direct_base64(self):
        """直接Base64文字列が渡された場合のテスト"""
        # Base64文字列を直接渡す
        base64_string = base64.b64encode(self.test_image_data).decode('utf-8')
        result = extract_and_encode_image(base64_string)
        
        # そのまま返されることを確認
        self.assertEqual(result, base64_string)
    
    def test_extract_and_encode_image_bytes_data(self):
        """バイナリデータが渡された場合のテスト"""
        # バイナリデータを渡す
        result = extract_and_encode_image(self.test_image_data)
        
        # 正しくBase64エンコードされることを確認
        expected_base64 = base64.b64encode(self.test_image_data).decode('utf-8')
        self.assertEqual(result, expected_base64)
    
    def test_nova_canvas_get_styles(self):
        """nova_canvas_get_styles関数のテスト"""
        result = nova_canvas_get_styles()
        
        # 成功フラグを確認
        self.assertTrue(result['success'])
        
        # スタイルオプションが含まれていることを確認
        self.assertIn('styles', result)
        self.assertEqual(len(result['styles']), 8)
        
        # ガーメントクラスが含まれていることを確認
        self.assertIn('garment_classes', result)
        self.assertEqual(len(result['garment_classes']), 4)
    
    @patch('boto3.client')
    def test_nova_canvas_virtual_tryout_with_mock(self, mock_boto_client):
        """Virtual Try-on機能のモックテスト"""
        # Bedrockクライアントのモックを設定
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # モックレスポンスを設定
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'images': [{'image': 'mock_base64_image_data'}]
            }).encode('utf-8'))
        }
        mock_bedrock.invoke_model.return_value = mock_response
        
        # テスト画像ファイルを作成
        test_file_1 = os.path.join(self.temp_dir, 'image_1.png')
        test_file_2 = os.path.join(self.temp_dir, 'image_2.png')
        
        with open(test_file_1, 'wb') as f:
            f.write(self.test_image_data)
        with open(test_file_2, 'wb') as f:
            f.write(self.test_image_data)
        
        # Virtual Try-onを実行
        result = nova_canvas_virtual_tryout(
            source_image='image_1',
            reference_image='image_2',
            mask_type='GARMENT',
            garment_class='UPPER_BODY'
        )
        
        # 成功することを確認
        self.assertTrue(result['success'])
        self.assertEqual(result['image'], 'mock_base64_image_data')
        
        # Bedrock APIが呼び出されたことを確認
        mock_bedrock.invoke_model.assert_called_once()


if __name__ == '__main__':
    # ユニットテストを実行
    unittest.main(verbosity=2)