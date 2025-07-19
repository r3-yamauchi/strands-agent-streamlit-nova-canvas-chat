"""
実際の画像を使用したVirtual Try-on機能のテスト

ユーザーが提供した画像を使用して、Virtual Try-on機能が正しく動作することを確認します。
画像1: 赤いTシャツを着た男性
画像2: グレーのAWSパーカー
"""

import unittest
import base64
import json
import os
import sys
from PIL import Image
from io import BytesIO

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nova_canvas_tool import nova_canvas_virtual_tryout


class TestVirtualTryoutRealImages(unittest.TestCase):
    """実際の画像を使用したVirtual Try-on統合テストクラス"""
    
    @classmethod
    def setUpClass(cls):
        """テスト用画像の準備"""
        # 画像ファイルのパス
        cls.source_image_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "nova-canvas-source-image1.png"
        )
        cls.reference_image_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "nova-canvas-source-image2.png"
        )
        
        # 画像の存在確認
        if not os.path.exists(cls.source_image_path):
            raise FileNotFoundError(f"ソース画像が見つかりません: {cls.source_image_path}")
        if not os.path.exists(cls.reference_image_path):
            raise FileNotFoundError(f"参照画像が見つかりません: {cls.reference_image_path}")
        
        print(f"\n[テスト準備] 画像ファイルを確認しました")
        print(f"  - ソース画像: {cls.source_image_path}")
        print(f"  - 参照画像: {cls.reference_image_path}")
        
        # 画像をBase64エンコード
        with open(cls.source_image_path, 'rb') as f:
            cls.source_image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        with open(cls.reference_image_path, 'rb') as f:
            cls.reference_image_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        # 画像情報を表示
        source_img = Image.open(cls.source_image_path)
        ref_img = Image.open(cls.reference_image_path)
        
        print(f"\n[画像情報]")
        print(f"  ソース画像:")
        print(f"    - サイズ: {source_img.size}")
        print(f"    - フォーマット: {source_img.format}")
        print(f"    - Base64サイズ: {len(cls.source_image_base64):,} 文字")
        print(f"  参照画像:")
        print(f"    - サイズ: {ref_img.size}")
        print(f"    - フォーマット: {ref_img.format}")
        print(f"    - Base64サイズ: {len(cls.reference_image_base64):,} 文字")
    
    def test_virtual_tryout_upper_body(self):
        """男性の赤いTシャツをAWSパーカーに置き換えるテスト"""
        print("\n=== Virtual Try-on: 赤いTシャツ → AWSパーカー ===")
        
        # Virtual Try-on実行
        result = nova_canvas_virtual_tryout(
            source_image=self.source_image_base64,
            reference_image=self.reference_image_base64,
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
        
        # 結果の検証
        print(f"\n[実行結果]")
        print(f"  成功: {result.get('success', False)}")
        
        if result.get('success'):
            print(f"  メッセージ: {result.get('message', '')}")
            
            # 生成された画像を保存
            if 'image' in result:
                output_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "virtual_tryout_result.png"
                )
                
                try:
                    # Base64デコードして保存
                    image_data = base64.b64decode(result['image'])
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                    print(f"  ✓ 結果画像を保存しました: {output_path}")
                    
                    # 画像情報を表示
                    result_img = Image.open(BytesIO(image_data))
                    print(f"  生成画像サイズ: {result_img.size}")
                    
                except Exception as e:
                    print(f"  ✗ 画像保存エラー: {e}")
                    
            # パラメータ情報を表示
            if 'parameters' in result:
                print(f"\n[実行パラメータ]")
                for key, value in result['parameters'].items():
                    print(f"  {key}: {value}")
                    
        else:
            print(f"  ✗ エラー: {result.get('error', 'Unknown error')}")
            print(f"  エラータイプ: {result.get('error_type', 'Unknown')}")
            print(f"  メッセージ: {result.get('message', '')}")
            
            # デバッグ情報を表示
            if 'debug_info' in result:
                print(f"\n[デバッグ情報]")
                for key, value in result['debug_info'].items():
                    print(f"  {key}: {value}")
            
            # トラブルシューティング情報
            if 'troubleshooting' in result:
                print(f"\n[トラブルシューティング]")
                for key, value in result['troubleshooting'].items():
                    print(f"  - {value}")
        
        # アサーション
        self.assertTrue(result['success'], 
                       f"Virtual Try-on失敗: {result.get('error', '')}")
    
    def test_virtual_tryout_with_file_paths(self):
        """ファイルパスを直接使用したテスト"""
        print("\n=== Virtual Try-on: ファイルパス直接指定 ===")
        
        # Virtual Try-on実行（ファイルパスを使用）
        result = nova_canvas_virtual_tryout(
            source_image=self.source_image_path,
            reference_image=self.reference_image_path,
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
        
        # 結果の表示
        print(f"\n[実行結果]")
        print(f"  成功: {result.get('success', False)}")
        
        if not result.get('success'):
            print(f"  エラー: {result.get('error', '')}")
            print(f"  メッセージ: {result.get('message', '')}")
    
    def test_virtual_tryout_with_image_references(self):
        """Streamlitスタイルの画像参照を使用したテスト"""
        print("\n=== Virtual Try-on: Streamlit画像参照スタイル ===")
        
        # Streamlitでの使用を想定した画像参照
        result = nova_canvas_virtual_tryout(
            source_image="image_1",  # Streamlitで使用される参照形式
            reference_image="image_2",
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
        
        # 結果の表示
        print(f"\n[実行結果]")
        print(f"  成功: {result.get('success', False)}")
        
        if not result.get('success'):
            print(f"  エラー: {result.get('error', '')}")
            print(f"  メッセージ: {result.get('message', '')}")
            print("\n  注: Streamlitアプリ内でのみ動作する参照形式です")


if __name__ == '__main__':
    print("=" * 60)
    print("実際の画像を使用したVirtual Try-onテスト")
    print("=" * 60)
    
    # テストを実行
    unittest.main(verbosity=2)