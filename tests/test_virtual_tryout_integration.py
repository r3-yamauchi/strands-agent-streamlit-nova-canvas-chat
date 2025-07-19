"""
Virtual Try-on機能の統合テスト

実際の画像を使用してVirtual Try-on機能が正しく動作することを確認します。
"""

import unittest
import base64
import json
import os
import sys
from io import BytesIO
from PIL import Image
import tempfile

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nova_canvas_tool import nova_canvas_virtual_tryout, extract_and_encode_image


class TestVirtualTryoutIntegration(unittest.TestCase):
    """Virtual Try-on機能の統合テストクラス"""
    
    @classmethod
    def setUpClass(cls):
        """テスト用画像の生成"""
        # 320x320のテスト画像を生成（最小サイズ要件を満たす）
        cls.test_image_size = (320, 320)
        
        # 人物画像（ソース画像）の生成
        source_img = Image.new('RGB', cls.test_image_size, color='blue')
        source_buffer = BytesIO()
        source_img.save(source_buffer, format='PNG')
        cls.source_image_bytes = source_buffer.getvalue()
        cls.source_image_base64 = base64.b64encode(cls.source_image_bytes).decode('utf-8')
        
        # 服画像（参照画像）の生成
        ref_img = Image.new('RGB', cls.test_image_size, color='red')
        ref_buffer = BytesIO()
        ref_img.save(ref_buffer, format='PNG')
        cls.reference_image_bytes = ref_buffer.getvalue()
        cls.reference_image_base64 = base64.b64encode(cls.reference_image_bytes).decode('utf-8')
        
        print(f"\n[テスト準備] テスト画像を生成しました")
        print(f"  - サイズ: {cls.test_image_size}")
        print(f"  - ソース画像サイズ: {len(cls.source_image_bytes):,} bytes")
        print(f"  - 参照画像サイズ: {len(cls.reference_image_bytes):,} bytes")
    
    def test_virtual_tryout_with_base64_images(self):
        """Base64形式の画像でVirtual Try-onテスト"""
        print("\n=== Base64画像でのVirtual Try-onテスト ===")
        
        # Virtual Try-on実行
        result = nova_canvas_virtual_tryout(
            source_image=self.source_image_base64,
            reference_image=self.reference_image_base64,
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
        
        # 結果の検証
        self.assertTrue(result['success'], f"Virtual Try-on失敗: {result.get('error', '')}")
        self.assertIn('image', result, "結果に画像が含まれていません")
        
        # 生成された画像を検証
        generated_image_b64 = result['image']
        try:
            generated_image_bytes = base64.b64decode(generated_image_b64)
            print(f"✓ 生成された画像サイズ: {len(generated_image_bytes):,} bytes")
            
            # 画像として読み込めるか確認
            generated_img = Image.open(BytesIO(generated_image_bytes))
            print(f"✓ 生成された画像サイズ: {generated_img.size}")
            
        except Exception as e:
            self.fail(f"生成された画像の処理に失敗: {e}")
    
    def test_virtual_tryout_with_temporary_files(self):
        """一時ファイル経由でのVirtual Try-onテスト（Streamlit統合用）"""
        print("\n=== 一時ファイル経由でのVirtual Try-onテスト ===")
        
        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix="nova_canvas_")
        print(f"一時ディレクトリ: {temp_dir}")
        
        try:
            # 画像を一時ファイルに保存
            source_path = os.path.join(temp_dir, "image_1.png")
            with open(source_path, 'wb') as f:
                f.write(self.source_image_bytes)
            
            ref_path = os.path.join(temp_dir, "image_2.png")
            with open(ref_path, 'wb') as f:
                f.write(self.reference_image_bytes)
            
            print(f"✓ ソース画像保存: {source_path}")
            print(f"✓ 参照画像保存: {ref_path}")
            
            # Virtual Try-on実行（画像参照形式）
            result = nova_canvas_virtual_tryout(
                source_image="image_1",
                reference_image="image_2",
                mask_type="GARMENT",
                garment_class="UPPER_BODY"
            )
            
            # 結果の検証
            self.assertTrue(result['success'], f"Virtual Try-on失敗: {result.get('error', '')}")
            self.assertIn('image', result, "結果に画像が含まれていません")
            
            print("✓ 一時ファイル経由でのVirtual Try-on成功")
            
        finally:
            # クリーンアップ
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"✓ 一時ディレクトリをクリーンアップしました")
    
    def test_virtual_tryout_all_garment_classes(self):
        """すべてのガーメントクラスでのテスト"""
        print("\n=== すべてのガーメントクラスのテスト ===")
        
        garment_classes = ["UPPER_BODY", "LOWER_BODY", "FULL_BODY", "FOOTWEAR"]
        
        for garment_class in garment_classes:
            with self.subTest(garment_class=garment_class):
                print(f"\nテスト中: {garment_class}")
                
                result = nova_canvas_virtual_tryout(
                    source_image=self.source_image_base64,
                    reference_image=self.reference_image_base64,
                    mask_type="GARMENT",
                    garment_class=garment_class
                )
                
                if result['success']:
                    print(f"  ✓ {garment_class}: 成功")
                else:
                    print(f"  ✗ {garment_class}: 失敗 - {result.get('error', '')}")
                
                self.assertTrue(result['success'], 
                               f"{garment_class}でのVirtual Try-on失敗")
    
    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        print("\n=== エラーハンドリングのテスト ===")
        
        # 無効な画像データでテスト
        result = nova_canvas_virtual_tryout(
            source_image="invalid_base64_data",
            reference_image="invalid_base64_data",
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
        
        # エラーが適切に処理されることを確認
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('error_type', result)
        
        print(f"✓ エラーハンドリング正常: {result['error_type']}")
        print(f"  エラーメッセージ: {result['error']}")


if __name__ == '__main__':
    print("=" * 60)
    print("Virtual Try-on機能の統合テスト")
    print("=" * 60)
    
    # 統合テストを実行するかどうかを確認
    if os.environ.get("SKIP_INTEGRATION_TESTS", "false").lower() == "true":
        print("統合テストはスキップされました（SKIP_INTEGRATION_TESTS=true）")
    else:
        unittest.main(verbosity=2)