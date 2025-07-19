"""
Amazon Nova Canvas カスタムツール実装

AWS BedrockのNova Canvas APIを使用して、高度な画像生成・編集機能を提供します。
主な機能:
- Virtual try-on: 人物画像と商品画像を組み合わせた仮想試着
- Style generation: 8つのアーティスティックスタイルでの画像変換
- Options retrieval: 利用可能なスタイルオプションの取得

Strands Agent フレームワークのカスタムツールとして実装されており、
MCP経由ではなく、AWS Bedrock APIを直接呼び出すことで高いパフォーマンスを実現しています。
"""

import base64
import io
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Literal, Union, List, ClassVar
import boto3
from strands import tool
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()


# Amazon Nova Canvas で利用可能なスタイルオプション定義
# 8つのアーティスティックスタイルから選択可能
STYLE_OPTIONS = [
    "3D animated family film",     # 3Dアニメーション映画風
    "Design sketch",               # デザインスケッチ風
    "Flat vector illustration",    # フラットベクターイラスト風
    "Graphic novel",               # グラフィックノベル風
    "Maximalism",                  # マキシマリズムスタイル
    "Midcentury retro",            # ミッドセンチュリーレトロ風
    "Photorealism",                # フォトリアリズム
    "Soft digital painting"        # ソフトデジタルペインティング風
]

# 事前定義されたプロンプトサンプル（英語）
PROMPT_SAMPLES = [
    {
        "title": "油絵の猫",
        "subject": "Calico colored cat",
        "environment": "Cozy living room",
        "action": "Lounging on a sofa",
        "lighting": "Soft lighting",
        "camera": "High angle",
        "style": "Oil on canvas"
    },
    {
        "title": "先生のストック写真",
        "subject": "Female teacher with a warm smile",
        "environment": "Grade-school classroom with blackboard in background",
        "action": "Standing in front of a blackboard",
        "lighting": "Clean white light",
        "camera": "Eye-level facing the teacher, shallow depth of field, blurred background",
        "style": "Realistic editorial photo, stock photography, high-quality"
    },
    {
        "title": "船上の女性イラスト",
        "subject": "Woman in a large hat",
        "environment": "Boat deck with a railing and ocean view",
        "action": "Standing at the ship's railing, looking out across the ocean, left side of the frame",
        "lighting": "Golden hour light, setting sun",
        "camera": "Eye-level from behind the woman, looking out across the ocean",
        "style": "Ethereal soft-shaded, story, illustration"
    },
    {
        "title": "男性モデルのファッション写真",
        "subject": "Cool looking stylish man in an orange jacket, dark skin, wearing reflective glasses",
        "environment": "Aqua blue sleek building shapes in background",
        "action": "Standing in front of the building",
        "lighting": "Natural light",
        "camera": "Slightly low angle, face and chest in view",
        "style": "High-quality fashion photography, editorial, modern, sleek, sharp"
    },
    {
        "title": "ドラゴンイラスト",
        "subject": "Large, menacing dragon",
        "environment": "Medieval castle ruins",
        "action": "Roaring and breathing fire",
        "lighting": "Dark and moody",
        "camera": "Low angle, wide shot",
        "style": "Fantasy, epic, dark, detailed, illustration"
    },
    {
        "title": "LA交通渋滞のバットモービル",
        "subject": "The Batmobile from the Batman movies",
        "environment": "Los Angeles traffic",
        "action": "Stuck in Los Angeles traffic",
        "lighting": "rainy, wet, reflections",
        "camera": "wide shot",
        "style": "Impressionist painting, large broad brush strokes, impasto"
    },
    {
        "title": "西部カウボーイのティンタイプ",
        "subject": "Western cowboy, Caucasian, White, male, man",
        "environment": "Saloon background, 1880's, Old West",
        "action": "Looking off directly at camera",
        "lighting": "Soft, warm, tungsten, candlelight",
        "camera": "portrait, head and shoulder, narrow depth of field, blurred background",
        "style": "Tintype, vintage photograph, sepia tone, hand-made print, imperfections"
    },
    {
        "title": "日本風版画",
        "subject": "Brown-eared Bulbul perched on a cherry blossom branch",
        "environment": "Springtime cherry blossom tree",
        "action": "Bird and branch on right side of image, bird facing left",
        "lighting": "",
        "camera": "",
        "style": "Japanese-style, Katsushika Hokusai, woodblock print, ukiyo-e print, Edo period, handmade Washi paper"
    },
    {
        "title": "タンゴダンサーの油絵",
        "subject": "Man and woman both dressed in formal attire with the woman wearing a red dress",
        "environment": "Dark gray, creating an atmosphere of mystery and elegance",
        "action": "Dancing the tango",
        "lighting": "",
        "camera": "",
        "style": "Oil painting"
    },
    {
        "title": "レトロスタイルのラウンジシーン",
        "subject": "60's style, retro-inspired lounge",
        "environment": "Shaggy rugs, vintage stereo, mid-century furniture",
        "action": "",
        "lighting": "",
        "camera": "",
        "style": "60's illustration style, graphic, graphic art, flat color, color palette of teal, orange, brown"
    }
]

# 事前定義されたネガティブプロンプトサンプル
NEGATIVE_PROMPT_SAMPLES = [
    {
        "title": "一般的な画像品質の問題を回避",
        "text": "blurry, blur, censored, crop, cut off, draft, grainy, out of focus, out of frame, poorly lit, poor quality, shadow, worst quality"
    },
    {
        "title": "画像内のテキストを回避",
        "text": "annotations, artist name, autograph, caption, digits, error, initials, inscription, label, letters, logo, name, seal, signature, stamp, textual elements, trademark, typography, username, watermark, words, writing"
    },
    {
        "title": "歪んだ人物の特徴を回避",
        "text": "bad anatomy, bad body, bad eyes, bad face, bad hands, bad arms, bad legs, bad teeth, deformities, extra fingers, extra limbs, extra toes, missing limbs, missing fingers, mutated, malformed, mutilated, morbid, 3d character"
    },
    {
        "title": "写真品質の問題を回避",
        "text": "anime, asymmetrical, bad art, bad photography, bad photo, black and white, blur, blurry, cartoon, censored, CGI, copy, cut off, draft, duplicate, digital, double exposure, grainy, grayscale, low details, low-res, low quality, manga, out of frame, over-saturated, overexposed, poor photo, poor photography, poor quality, render, shadow"
    },
    {
        "title": "アーティスティックな問題を回避",
        "text": "abstract, amateur, childish, clumsy, disfigured, distorted, gross, horrible, kitsch, lowres, messy, monochrome, mutilated, ugly, unprofessional, poorly drawn"
    }
]

# 事前定義されたアスペクト比オプション
ASPECT_RATIO_OPTIONS = {
    "512 x 512 (1:1)": (512, 512),
    "1024 x 1024 (1:1)": (1024, 1024),
    "2048 x 2048 (1:1)": (2048, 2048),
    "1024 x 336 (3:1)": (1024, 336),
    "1024 x 512 (2:1)": (1024, 512),
    "1024 x 576 (16:9)": (1024, 576),
    "1024 x 672 (3:2)": (1024, 672),
    "1024 x 816 (5:4)": (1024, 816),
    "1280 x 720 (16:9)": (1280, 720),
    "2048 x 512 (4:1)": (2048, 512),
    "2288 x 1824 (5:4)": (2288, 1824),
    "2512 x 1664 (3:2)": (2512, 1664),
    "2720 x 1520 (16:9)": (2720, 1520),
    "2896 x 1440 (2:1)": (2896, 1440),
    "3536 x 1168 (3:1)": (3536, 1168),
    "4096 x 1024 (4:1)": (4096, 1024),
    "336 x 1024 (1:3)": (336, 1024),
    "512 x 1024 (1:2)": (512, 1024),
    "512 x 2048 (1:4)": (512, 2048),
    "576 x 1024 (9:16)": (576, 1024),
    "672 x 1024 (2:3)": (672, 1024),
    "720 x 1280 (9:16)": (720, 1280),
    "816 x 1024 (4:5)": (816, 1024),
    "1024 x 4096 (1:4)": (1024, 4096),
    "1168 x 3536 (1:3)": (1168, 3536),
    "1440 x 2896 (1:2)": (1440, 2896),
    "1520 x 2720 (9:16)": (1520, 2720),
    "1664 x 2512 (2:3)": (1664, 2512),
    "1824 x 2288 (4:5)": (1824, 2288)
}

# Virtual try-on機能で使用する身体部位の分類
# ガーメントマスキング時に指定する対象部位
GARMENT_CLASSES = [
    "UPPER_BODY",  # 上半身（シャツ、ジャケット等）
    "LOWER_BODY",  # 下半身（パンツ、スカート等）
    "FULL_BODY",   # 全身（ドレス、オーバーオール等）
    "FOOTWEAR"     # 靴類
]

# Virtual try-on機能で使用可能なマスキングタイプ
# 置換エリアを指定する3つの方法
MASK_TYPES = ["GARMENT", "PROMPT", "IMAGE"]

# テキストから画像生成の設定定数
MIN_PROMPT_LENGTH = 1  # プロンプトの最小文字数
MAX_PROMPT_LENGTH = 1024  # プロンプトの最大文字数
MIN_IMAGE_SIZE = 320  # 画像の最小サイズ（ピクセル）
MAX_IMAGE_SIZE = 4096  # 画像の最大サイズ（ピクセル）
MAX_PIXEL_COUNT = 4194304  # 最大ピクセル数
MAX_ASPECT_RATIO = 4  # 最大アスペクト比


def load_image_as_base64(image_data: Union[str, bytes]) -> str:
    """
    画像データをBase64エンコードして返すユーティリティ関数
    
    Nova Canvas APIでは画像データをBase64形式で送信する必要があるため、
    様々な形式の画像データを統一的にBase64エンコードします。
    Streamlitからのバイナリデータも適切に処理します。
    
    Args:
        image_data: 画像のバイナリデータまたはBase64文字列
        
    Returns:
        str: Base64エンコードされた画像データ（プレフィックスなし）
        
    Raises:
        ValueError: 画像データが無効な場合
    """
    if image_data is None:
        raise ValueError("画像データがNoneです")
    
    if isinstance(image_data, str):
        # 空文字列チェック
        if not image_data.strip():
            raise ValueError("画像データが空です")
            
        # 既にBase64エンコード済みの場合はそのまま返す
        if image_data.startswith('data:image/'):
            # data:image/...;base64, プレフィックスを除去してBase64データのみ抽出
            if ',' in image_data:
                base64_part = image_data.split(',', 1)[1]
                # Base64として有効性をチェック
                try:
                    base64.b64decode(base64_part)
                    return base64_part
                except Exception as e:
                    raise ValueError(f"無効なBase64データです: {str(e)}")
            else:
                raise ValueError("Data URLの形式が正しくありません")
        
        # プレフィックスなしのBase64文字列として処理
        try:
            base64.b64decode(image_data)
            return image_data
        except Exception:
            # Base64として無効な場合はエラー
            raise ValueError("Base64として解釈できない文字列です")
    
    elif isinstance(image_data, bytes):
        # バイナリデータの場合
        if len(image_data) == 0:
            raise ValueError("画像データが空です")
            
        # 画像形式の簡易チェック
        if not (image_data.startswith(b'\x89PNG') or image_data.startswith(b'\xff\xd8\xff')):
            # 警告はするが、処理は続行（他の画像形式の可能性もあるため）
            pass
            
        # バイナリデータの場合はBase64エンコードを実行
        try:
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Base64エンコードに失敗しました: {str(e)}")
    
    else:
        raise ValueError(f"サポートされていないデータ型です: {type(image_data)}")


# get_current_session_image関数は削除されました
# 画像データは直接ツール関数に渡されるようになりました


def extract_and_encode_image(image_data: Union[str, bytes, dict]) -> str:
    """
    Strands Agentから渡される様々な形式の画像データを処理してBase64エンコードします。
    
    Strands Agentフレームワークは、アップロードされた画像を以下の形式で渡すことがあります：
    - 単純な文字列（Base64）
    - バイナリデータ（bytes）
    - 辞書形式（{"source": {"bytes": <binary_data>}, "format": "png"}など）
    - 画像参照（"image_1", "image_2"など - 一時ファイルから取得）
    
    Args:
        image_data: 画像データ（文字列、バイナリ、または辞書）
        
    Returns:
        str: Base64エンコードされた画像データ
        
    Raises:
        ValueError: 画像データが無効または処理できない場合
    """
    # 画像参照の場合、一時ファイルから取得
    if isinstance(image_data, str) and image_data.startswith("image_"):
        # 一時ディレクトリから画像ファイルを検索
        import glob
        import os
        
        # 最新のnova_canvas_一時ディレクトリを検索
        temp_dirs = []
        
        # /tmpディレクトリを確認
        if os.path.exists("/tmp"):
            temp_dirs.extend(glob.glob("/tmp/nova_canvas_*"))
        
        # macOSの場合、/var/foldersも確認
        if os.path.exists("/var/folders"):
            temp_dirs.extend(glob.glob("/var/folders/*/*/T/nova_canvas_*"))
        
        # 最新のディレクトリを取得
        if temp_dirs:
            temp_dirs.sort(key=os.path.getmtime, reverse=True)
            latest_temp_dir = temp_dirs[0]
            
            # 画像ファイルを検索
            file_pattern = os.path.join(latest_temp_dir, f"{image_data}.*")
            files = glob.glob(file_pattern)
            
            if files:
                # ファイルを読み込んでBase64エンコード
                with open(files[0], 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
        
        raise ValueError(f"画像ファイル {image_data} が見つかりません。一時ディレクトリを確認してください。")
    if isinstance(image_data, dict):
        # Strands Agent形式の辞書データの処理
        if "source" in image_data and "bytes" in image_data["source"]:
            # {"source": {"bytes": <binary_data>}, "format": "..."}形式
            binary_data = image_data["source"]["bytes"]
            return load_image_as_base64(binary_data)
        elif "bytes" in image_data:
            # {"bytes": <binary_data>, "format": "..."}形式
            binary_data = image_data["bytes"]
            return load_image_as_base64(binary_data)
        elif "data" in image_data:
            # {"data": <base64_or_binary>, "format": "..."}形式
            data = image_data["data"]
            return load_image_as_base64(data)
        else:
            raise ValueError(f"辞書形式の画像データの構造が認識できません: {list(image_data.keys())}")
    else:
        # 文字列またはバイナリデータの場合
        return load_image_as_base64(image_data)


@dataclass(frozen=True)
class PromptStructure:
    """
    Amazon Nova Canvas用の構造化プロンプト生成クラス
    
    プロンプトを6つの要素に分解して、効果的な画像生成を支援します。
    """
    
    # インスタンス属性
    title: str = field(default="カスタムプロンプト")
    subject: str = field(default="")
    environment: Optional[str] = field(default="")
    action: Optional[str] = field(default="")
    lighting: Optional[str] = field(default="")
    camera: Optional[str] = field(default="")
    style: Optional[str] = field(default="")
    
    # 否定語の検出用定数
    NEGATION_WORDS: ClassVar[frozenset] = frozenset([
        "no", "not", "neither", "never", "no one", "nobody", "none", "nor",
        "nothing", "nowhere", "without", "barely", "hardly", "scarcely", "seldom"
    ])
    
    def check_negation_words(self, text: str) -> List[str]:
        """テキスト内の否定語を検出する関数"""
        found_words = []
        for word in self.NEGATION_WORDS:
            if re.search(r"\b" + word + r"\b", text.lower()):
                found_words.append(word)
        return found_words
    
    def generate_prompt(self) -> str:
        """構造化されたプロンプトを生成する関数"""
        fields = []
        
        if self.subject:
            fields.append(f"Subject: {self.subject.strip()}")
        if self.environment:
            fields.append(f"Environment: {self.environment.strip()}")
        if self.action:
            fields.append(f"Subject action, position, and pose: {self.action.strip()}")
        if self.lighting:
            fields.append(f"Lighting: {self.lighting.strip()}")
        if self.camera:
            fields.append(f"Camera position and framing: {self.camera.strip()}")
        if self.style:
            fields.append(f"Image style: {self.style.strip()}")
        
        prompt = ", \n".join(fields)
        
        # プロンプト検証
        if len(prompt) < MIN_PROMPT_LENGTH:
            raise ValueError(f"プロンプトは最低{MIN_PROMPT_LENGTH}文字以上である必要があります")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"プロンプトの長さ{len(prompt)}文字が最大{MAX_PROMPT_LENGTH}文字を超えています")
        if len(self.subject) < MIN_PROMPT_LENGTH:
            raise ValueError("Subject（被写体）は必須フィールドです")
            
        return prompt


@dataclass
class ImageGenerationConfig:
    """
    画像生成の設定パラメータを管理するクラス
    """
    
    width: int = 1024
    height: int = 1024
    number_of_images: int = 1
    quality: str = "standard"  # "standard" or "premium"
    cfg_scale: float = 3.0
    seed: int = 0
    
    def validate_dimensions(self) -> None:
        """画像寸法の検証を行う関数"""
        if self.width > MAX_IMAGE_SIZE or self.height > MAX_IMAGE_SIZE:
            raise ValueError(f"幅と高さは{MAX_IMAGE_SIZE}ピクセル以下である必要があります")
        
        if self.width < MIN_IMAGE_SIZE or self.height < MIN_IMAGE_SIZE:
            raise ValueError(f"幅と高さは{MIN_IMAGE_SIZE}ピクセル以上である必要があります")
        
        if self.width * self.height > MAX_PIXEL_COUNT:
            raise ValueError(f"総ピクセル数は{MAX_PIXEL_COUNT}未満である必要があります")
            
        aspect_ratio = max(self.width / self.height, self.height / self.width)
        if aspect_ratio > MAX_ASPECT_RATIO:
            raise ValueError(f"アスペクト比は{MAX_ASPECT_RATIO}:1以下である必要があります")
    
    def validate_parameters(self) -> None:
        """全パラメータの検証を行う関数"""
        self.validate_dimensions()
        
        if self.number_of_images < 1 or self.number_of_images > 5:
            raise ValueError("画像生成数は1から5の間である必要があります")
            
        if self.quality not in ["standard", "premium"]:
            raise ValueError("品質は'standard'または'premium'である必要があります")
            
        if self.cfg_scale < 1.0 or self.cfg_scale > 10.0:
            raise ValueError("CFGスケールは1.0から10.0の間である必要があります")
            
        if self.seed < 0:
            raise ValueError("シード値は0以上である必要があります")


def get_bedrock_client(region_name: str = "us-east-1"):
    """
    AWS Bedrock Runtime クライアントを取得する関数
    
    Nova Canvas APIを呼び出すためのBedrock Runtimeクライアントを初期化します。
    AWS認証情報は環境変数、IAMロール、またはAWSプロファイルから自動的に取得されます。
    
    Args:
        region_name: AWSリージョン（デフォルトは us-east-1）
        
    Returns:
        boto3.client: Bedrock Runtime クライアントオブジェクト
    """
    # デバッグ: 認証情報の確認
    import os
    if os.environ.get("DEV") == "true":
        print(f"[DEBUG] AWS_ACCESS_KEY_ID: {'設定済み' if os.environ.get('AWS_ACCESS_KEY_ID') else '未設定'}")
        print(f"[DEBUG] AWS_SECRET_ACCESS_KEY: {'設定済み' if os.environ.get('AWS_SECRET_ACCESS_KEY') else '未設定'}")
        print(f"[DEBUG] AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION', '未設定')}")
        print(f"[DEBUG] Using region: {region_name}")
    
    return boto3.client('bedrock-runtime', region_name=region_name)


@tool
def nova_canvas_virtual_tryout(
    source_image: Union[str, bytes, dict],
    reference_image: Union[str, bytes, dict],
    mask_type: Literal["GARMENT", "PROMPT", "IMAGE"] = "GARMENT",
    garment_class: Optional[Literal["UPPER_BODY", "LOWER_BODY", "FULL_BODY", "FOOTWEAR"]] = "UPPER_BODY",
    prompt_text: Optional[str] = None,
    mask_image: Optional[Union[str, bytes, dict]] = None,
    style: Optional[str] = None,
    aws_region: str = "us-east-1"
) -> dict:
    """
    Amazon Nova Canvas API を活用した高度なVirtual Try-on（仮想試着）カスタムツール。
    
    このStrands Agentカスタムツールは、AWS BedrockのNova Canvas APIを直接呼び出して、
    人物画像と商品画像を組み合わせた仮想試着機能を提供します。
    
    特徴:
        - 3つのマスキング方式をサポート（GARMENT/PROMPT/IMAGE）
        - 複数の画像形式に対応（Base64/bytes/Streamlitアップロード）
        - 高精度な置換処理で自然な仮想試着を実現
        - Context Window節約のため一時ファイル保存方式を採用
    
    マスキング方式の詳細:
        - GARMENT: 身体部位を指定した自動マスキング（推奨）
        - PROMPT: 自然言語での置換エリア指定
        - IMAGE: カスタム白黒マスク画像による精密制御
    
    引数:
        source_image: ソース画像（試着する人物または空間）
            - str: Base64エンコードされた画像データ
            - bytes: 生の画像バイナリデータ（自動Base64変換）
            - dict: Streamlit/Strands Agent形式の画像オブジェクト
        reference_image: 参照画像（試着させたい商品・アイテム）
            - str: Base64エンコードされた画像データ
            - bytes: 生の画像バイナリデータ（自動Base64変換）
            - dict: Streamlit/Strands Agent形式の画像オブジェクト
        mask_type: マスキング処理方式の選択
            - "GARMENT": ガーメントクラス指定（最も簡単で推奨）
            - "PROMPT": 自然言語による置換エリア指定
            - "IMAGE": カスタムマスク画像使用（最も精密）
        garment_class: 衣類カテゴリ（mask_type="GARMENT"時必須）
            - "UPPER_BODY": 上半身衣類（シャツ、ブラウス、ジャケット等）
            - "LOWER_BODY": 下半身衣類（パンツ、スカート、ショーツ等）
            - "FULL_BODY": 全身衣類（ドレス、オーバーオール、コート等）
            - "FOOTWEAR": 履物（靴、ブーツ、サンダル等）
        prompt_text: 置換エリア記述（mask_type="PROMPT"時必須）
            例: "replace the shirt with the reference item"
        mask_image: カスタムマスク画像（mask_type="IMAGE"時必須）
            白：置換エリア、黒：保持エリアの二値画像
        style: アーティスティックスタイル（任意）
            STYLE_OPTIONS から選択：Photorealism, Graphic novel等
        aws_region: AWS Bedrockのリージョン（デフォルト: us-east-1）
        
    戻り値:
        str: 処理結果（成功時は一時ファイルパス、エラー時はエラーメッセージ）
            - 成功: "SUCCESS: /path/to/generated_image.png"
            - エラー: "ERROR: 詳細なエラーメッセージ"
        
    使用例:
        # 上半身の服を試着
        nova_canvas_virtual_tryout(
            source_image="image_1",
            reference_image="image_2", 
            mask_type="GARMENT",
            garment_class="UPPER_BODY"
        )
    """
    try:
        # デバッグ情報の出力
        print(f"[DEBUG] Virtual Try-on開始:")
        print(f"  - source_image: {type(source_image).__name__} - {str(source_image)[:100] if isinstance(source_image, str) else 'binary data'}")
        print(f"  - reference_image: {type(reference_image).__name__} - {str(reference_image)[:100] if isinstance(reference_image, str) else 'binary data'}")
        print(f"  - mask_type: {mask_type}")
        print(f"  - garment_class: {garment_class}")
        
        # AWS Bedrock クライアントの初期化
        bedrock_client = get_bedrock_client(aws_region)
        
        # 入力画像データのBase64エンコード処理
        # Base64データのエンコード処理
        try:
            # 画像データは直接渡されるか、既にBase64エンコードされている
            source_b64 = extract_and_encode_image(source_image)
            reference_b64 = extract_and_encode_image(reference_image)
        except Exception as convert_error:
            # 詳細なエラー情報を提供
            error_details = str(convert_error)
            
            # 画像データの詳細情報を取得
            session_info = "画像データは直接渡される必要があります"
            
            return {
                "success": False,
                "error": f"画像データの変換に失敗しました: {error_details}",
                "error_type": "ImageExtractionError",
                "message": "画像データの取得または変換に失敗しました。",
                "debug_info": {
                    "source_image_type": str(type(source_image)),
                    "reference_image_type": str(type(reference_image)),
                    "source_image_value": str(source_image)[:100] + "..." if isinstance(source_image, str) else "非文字列",
                    "reference_image_value": str(reference_image)[:100] + "..." if isinstance(reference_image, str) else "非文字列",
                    "session_info": session_info
                },
                "troubleshooting": {
                    "step1": "画像を再度アップロードしてください",
                    "step2": "サイドバーで画像データの準備状況を確認してください",
                    "step3": "画像データが正しい形式で渡されているか確認してください"
                }
            }
        
        # Nova Canvas API用のリクエストパラメータ構築
        inference_params = {
            "taskType": "VIRTUAL_TRY_ON",
            "virtualTryOnParams": {
                "sourceImage": source_b64,
                "referenceImage": reference_b64,
                "maskType": mask_type
            }
        }
        
        # マスキングタイプに応じた追加パラメータ設定
        if mask_type == "GARMENT" and garment_class:
            # ガーメントベースマスク: 身体部位を指定して置換
            inference_params["virtualTryOnParams"]["garmentBasedMask"] = {
                "garmentClass": garment_class
            }
        elif mask_type == "PROMPT" and prompt_text:
            # プロンプトベースマスク: 自然言語で置換エリアを指定
            inference_params["virtualTryOnParams"]["promptBasedMask"] = {
                "prompt": prompt_text
            }
        elif mask_type == "IMAGE" and mask_image:
            # イメージベースマスク: カスタムマスク画像を使用して置換
            mask_b64 = extract_and_encode_image(mask_image)
            inference_params["virtualTryOnParams"]["imageBasedMask"] = {
                "maskImage": mask_b64
            }
        
        # スタイルオプションの設定（オプション、指定された場合のみ）
        if style and style in STYLE_OPTIONS:
            inference_params["virtualTryOnParams"]["style"] = style
        
        # Amazon Nova Canvas API の呼び出し実行
        print(f"[DEBUG] Nova Canvas API呼び出し:")
        print(f"  - モデル: amazon.nova-canvas-v1:0")
        print(f"  - タスク: {inference_params['taskType']}")
        
        response = bedrock_client.invoke_model(
            modelId="amazon.nova-canvas-v1:0",
            body=json.dumps(inference_params)
        )
        
        print(f"[DEBUG] API呼び出し成功")
        
        # APIレスポンスのパースと処理
        response_body = json.loads(response['body'].read())
        
        # レスポンスのデバッグ情報
        print(f"[DEBUG] APIレスポンス構造: {type(response_body)}")
        if isinstance(response_body, dict):
            print(f"[DEBUG] レスポンスキー: {list(response_body.keys())}")
        
        # APIレスポンスのエラーチェック
        if isinstance(response_body, dict) and "error" in response_body:
            error_message = response_body["error"]
            return {
                "success": False,
                "error": error_message,
                "message": f"Nova Canvas API でエラーが発生しました: {error_message}",
                "parameters": {
                    "mask_type": mask_type,
                    "garment_class": garment_class,
                    "prompt_text": prompt_text,
                    "style": style,
                    "region": aws_region
                }
            }
        
        # 成功時のレスポンスデータの構築
        # Nova Canvas APIのレスポンス形式を確認
        image_data = ""
        saved_image_path = None
        
        if isinstance(response_body, dict):
            # imagesキーがある場合
            if "images" in response_body and isinstance(response_body["images"], list) and len(response_body["images"]) > 0:
                first_image = response_body["images"][0]
                if isinstance(first_image, dict) and "image" in first_image:
                    image_data = first_image["image"]
                elif isinstance(first_image, str):
                    image_data = first_image
            # 直接imageキーがある場合
            elif "image" in response_body:
                image_data = response_body["image"]
        elif isinstance(response_body, str):
            # レスポンス全体が画像データの場合
            image_data = response_body
        
        # Context Window Overflow対策: 画像を一時ファイルに保存
        if image_data:
            try:
                import tempfile
                import base64
                
                # 一時ファイルを作成
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="nova_vto_result_") as temp_file:
                    # Base64デコードして保存
                    decoded_image = base64.b64decode(image_data)
                    temp_file.write(decoded_image)
                    saved_image_path = temp_file.name
                    
                print(f"[INFO] Virtual Try-on結果を一時ファイルに保存: {saved_image_path}")
                
                # 小さなサムネイルを作成してレスポンスに含める（オプション）
                from PIL import Image
                import io
                
                # 画像を開いてサムネイルを作成
                img = Image.open(io.BytesIO(decoded_image))
                thumbnail_size = (128, 128)
                img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
                
                # サムネイルをBase64エンコード
                thumb_buffer = io.BytesIO()
                img.save(thumb_buffer, format='PNG')
                thumbnail_b64 = base64.b64encode(thumb_buffer.getvalue()).decode('utf-8')
                
            except Exception as e:
                print(f"[ERROR] 画像の一時保存に失敗: {e}")
                saved_image_path = None
                thumbnail_b64 = None
        
        # シンプルなテキスト応答を構築
        if saved_image_path:
            # 成功時は一時ファイルパスをシンプルなテキストで返す
            print(f"[INFO] Context Window節約のため、画像ファイルパスのみを返します")
            return f"SUCCESS: {saved_image_path}"
        else:
            # フォールバック: エラーメッセージ
            return "ERROR: 画像ファイルの保存に失敗しました"
        
    except Exception as e:
        # 例外ハンドリング: AWS認証エラー、ネットワークエラー等を含む
        import traceback
        error_message = str(e)
        error_traceback = traceback.format_exc()
        
        print(f"[ERROR] Virtual try-on の実行中にエラーが発生しました:")
        print(f"  - エラータイプ: {type(e).__name__}")
        print(f"  - エラーメッセージ: {error_message}")
        print(f"  - トレースバック:\n{error_traceback}")
        
        # シンプルなエラーメッセージを返す
        return f"ERROR: Virtual try-on の実行中にエラーが発生しました: {error_message}"


@tool  
def nova_canvas_style_generation(
    source_image: Union[str, bytes, dict],
    style: str,
    prompt: Optional[str] = None,
    aws_region: str = "us-east-1"
) -> dict:
    """
    Amazon Nova Canvasを使用してスタイル変換機能を実行します。
    
    Args:
        source_image: ソース画像のBase64エンコードデータ
        style: アートスタイル（8つのオプションから選択）
        prompt: 追加のプロンプト（オプション）
        aws_region: AWSリージョン
        
    Returns:
        dict: 生成された画像のBase64データと実行結果
    """
    try:
        # スタイル検証
        if style not in STYLE_OPTIONS:
            return {
                "success": False,
                "error": f"無効なスタイルです。以下から選択してください: {', '.join(STYLE_OPTIONS)}",
                "message": "スタイルオプションが正しくありません"
            }
        
        # Bedrock クライアントの初期化
        bedrock_client = get_bedrock_client(aws_region)
        
        # Base64データのエンコード処理
        try:
            source_b64 = extract_and_encode_image(source_image)
        except Exception as convert_error:
            return {
                "success": False,
                "error": f"画像データの変換に失敗しました: {str(convert_error)}",
                "message": "画像データの形式を確認してください。PNG, JPEGファイルまたはBase64文字列が必要です。"
            }
        
        # リクエストパラメータの構築
        inference_params = {
            "taskType": "IMAGE_GENERATION",
            "imageGenerationParams": {
                "text": prompt or f"Apply {style} style to this image",
                "images": [source_b64],
                "style": style
            }
        }
        
        # Nova Canvas API の呼び出し
        response = bedrock_client.invoke_model(
            modelId="amazon.nova-canvas-v1:0",
            body=json.dumps(inference_params)
        )
        
        # レスポンスの処理
        response_body = json.loads(response['body'].read())
        
        if "error" in response_body:
            return {
                "success": False,
                "error": response_body["error"],
                "message": "Nova Canvas API でエラーが発生しました"
            }
        
        # 成功時のレスポンス
        return {
            "success": True,
            "image": response_body.get("images", [{}])[0].get("image", ""),
            "message": f"スタイル変換が正常に実行されました（スタイル: {style}）",
            "parameters": {
                "style": style,
                "prompt": prompt,
                "region": aws_region
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"スタイル変換の実行中にエラーが発生しました: {str(e)}"
        }


@tool
def nova_canvas_get_styles() -> dict:
    """
    利用可能なNova Canvasスタイルオプションを取得します。
    
    Returns:
        dict: 利用可能なスタイルオプション、ガーメントクラス、マスクタイプの一覧
    """
    return {
        "success": True,
        "styles": STYLE_OPTIONS,
        "garment_classes": GARMENT_CLASSES,
        "mask_types": MASK_TYPES,
        "message": "Nova Canvas の利用可能オプション一覧"
    }


@tool
def nova_canvas_debug_image_data(
    image_data: Union[str, bytes, dict],
    debug_info: str = "画像データの形式チェック"
) -> dict:
    """
    画像データの形式をデバッグするためのテスト関数
    
    Virtual try-on機能で問題が発生している場合に、
    画像データが適切な形式で渡されているかを確認するためのデバッグツールです。
    
    Args:
        image_data: 確認したい画像データ（Base64またはバイナリ）
        debug_info: デバッグ情報（何をテストしているかの説明）
        
    Returns:
        dict: デバッグ結果を含む辞書
            - success: 処理成功フラグ
            - image_info: 画像データの詳細情報
            - recommendations: 推奨される対処法
    """
    try:
        result = {
            "success": True,
            "debug_info": debug_info,
            "image_info": {},
            "recommendations": []
        }
        
        # 画像データの型を確認
        result["image_info"]["data_type"] = type(image_data).__name__
        
        # データサイズの計算（辞書の場合は含まれるデータのサイズ）
        if isinstance(image_data, dict):
            result["image_info"]["data_length"] = "dict"
            result["image_info"]["dict_keys"] = list(image_data.keys())
            # 実際の画像データを取得してサイズ計算
            try:
                extracted = extract_and_encode_image(image_data)
                result["image_info"]["extracted_data_length"] = len(extracted)
            except Exception as e:
                result["image_info"]["extraction_error"] = str(e)
        else:
            result["image_info"]["data_length"] = len(image_data) if image_data else 0
        
        if isinstance(image_data, str):
            # 文字列の場合の詳細チェック
            if image_data.startswith('data:image/'):
                result["image_info"]["format"] = "Data URL形式"
                result["image_info"]["has_prefix"] = True
                # Base64部分のサイズを確認
                if ',' in image_data:
                    base64_part = image_data.split(',', 1)[1]
                    result["image_info"]["base64_length"] = len(base64_part)
                else:
                    result["recommendations"].append("Data URLにコンマが見つかりません")
            else:
                result["image_info"]["format"] = "Base64文字列（プレフィックスなし）"
                result["image_info"]["has_prefix"] = False
                
                # Base64として有効かチェック
                try:
                    import base64
                    decoded = base64.b64decode(image_data)
                    result["image_info"]["base64_valid"] = True
                    result["image_info"]["decoded_size"] = len(decoded)
                    
                    # 画像フォーマットの推定
                    if decoded.startswith(b'\x89PNG'):
                        result["image_info"]["detected_format"] = "PNG"
                    elif decoded.startswith(b'\xff\xd8\xff'):
                        result["image_info"]["detected_format"] = "JPEG"
                    else:
                        result["image_info"]["detected_format"] = "Unknown"
                        result["recommendations"].append("画像形式がPNGまたはJPEGではない可能性があります")
                        
                except Exception as e:
                    result["image_info"]["base64_valid"] = False
                    result["image_info"]["base64_error"] = str(e)
                    result["recommendations"].append("Base64デコードに失敗しました")
                    
        elif isinstance(image_data, bytes):
            # バイナリデータの場合
            result["image_info"]["format"] = "バイナリデータ"
            result["image_info"]["binary_size"] = len(image_data)
            
            # 画像フォーマットの推定
            if image_data.startswith(b'\x89PNG'):
                result["image_info"]["detected_format"] = "PNG"
            elif image_data.startswith(b'\xff\xd8\xff'):
                result["image_info"]["detected_format"] = "JPEG"
            else:
                result["image_info"]["detected_format"] = "Unknown"
                result["recommendations"].append("画像形式がPNGまたはJPEGではない可能性があります")
                
            # Base64エンコードのテスト
            try:
                import base64
                encoded = base64.b64encode(image_data).decode('utf-8')
                result["image_info"]["can_encode_base64"] = True
                result["image_info"]["base64_length"] = len(encoded)
            except Exception as e:
                result["image_info"]["can_encode_base64"] = False
                result["image_info"]["encode_error"] = str(e)
        else:
            result["image_info"]["format"] = "不明な形式"
            result["recommendations"].append("画像データの形式が認識できません")
            
        # 推奨事項の追加
        data_length = result["image_info"].get("data_length", 0)
        extracted_length = result["image_info"].get("extracted_data_length", 0)
        
        if isinstance(image_data, dict):
            # 辞書の場合は抽出されたデータのサイズをチェック
            if extracted_length == 0:
                result["recommendations"].append("画像データが空です")
            elif extracted_length > 10 * 1024 * 1024:  # 10MB
                result["recommendations"].append("画像データが大きすぎる可能性があります（10MB以上）")
        else:
            # その他の場合は通常のサイズチェック
            if data_length == 0:
                result["recommendations"].append("画像データが空です")
            elif data_length > 10 * 1024 * 1024:  # 10MB
                result["recommendations"].append("画像データが大きすぎる可能性があります（10MB以上）")
            
        result["message"] = f"画像データのデバッグが完了しました（{debug_info}）"
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"画像データのデバッグ中にエラーが発生しました: {str(e)}",
            "debug_info": debug_info
        }


@tool
def nova_canvas_text_to_image(
    prompt: str,
    negative_prompt: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    number_of_images: int = 1,
    quality: str = "standard",
    cfg_scale: float = 3.0,
    seed: int = 0,
    aws_region: str = "us-east-1"
) -> dict:
    """
    Amazon Nova Canvas Text-to-Image機能による高品質画像生成カスタムツール。
    
    このStrands Agentカスタムツールは、詳細なプロンプト制御により
    プロフェッショナル品質の画像を生成します。構造化プロンプト、
    ネガティブプロンプト、詳細設定による高度な制御が可能です。
    
    主要機能:
        - テキストプロンプトからの直接画像生成
        - ネガティブプロンプトによる不要要素の除外
        - 豊富なアスペクト比オプション（320x320〜4096x4096）
        - バッチ生成機能（1-5枚同時）
        - 品質制御（standard/premium）
        - CFGスケールによるプロンプト忠実度調整
        - シード値制御による再現性確保
    
    引数:
        prompt: メイン画像生成プロンプト（英語推奨、詳細な記述ほど効果的）
        negative_prompt: 除外したい要素の指定（任意）
            例: "blurry, low quality, distorted"
        width: 画像幅（320-4096ピクセル、64の倍数）
        height: 画像高さ（320-4096ピクセル、64の倍数）
        number_of_images: 同時生成枚数（1-5枚）
        quality: 画像品質設定
            - "standard": 標準品質（高速）
            - "premium": 高品質（時間要）
        cfg_scale: プロンプト忠実度制御（1.0-10.0）
            - 低値: 創造的・多様性重視
            - 高値: プロンプト厳密遵守
        seed: 生成時の乱数シード（0以上、0=ランダム）
        aws_region: AWS Bedrockリージョン（デフォルト: us-east-1）
        
    戻り値:
        dict: 画像生成結果を含む辞書
            - success: 処理成功フラグ（True/False）
            - images: 生成画像のBase64エンコードデータリスト
            - message: 結果メッセージ（日本語）
            - parameters: 生成時使用パラメータの詳細
            
    使用例:
        # 基本的な画像生成
        nova_canvas_text_to_image(
            prompt="A serene mountain landscape at sunset",
            negative_prompt="blurry, low quality",
            width=1024,
            height=1024
        )
    """
    try:
        # 画像生成パラメータの検証と設定オブジェクト作成
        # dataclassによる型安全性とバリデーション機能を活用
        config = ImageGenerationConfig(
            width=width,                      # 画像幅
            height=height,                    # 画像高さ
            number_of_images=number_of_images,# 生成枚数
            quality=quality,                  # 品質設定
            cfg_scale=cfg_scale,             # CFGスケール
            seed=seed                        # シード値
        )
        config.validate_parameters()        # パラメータ妥当性検証
        
        # プロンプト文字列の長さとフォーマット検証
        if len(prompt) < MIN_PROMPT_LENGTH:
            raise ValueError(f"プロンプトは最低{MIN_PROMPT_LENGTH}文字以上である必要があります")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"プロンプトの長さ{len(prompt)}文字が最大{MAX_PROMPT_LENGTH}文字を超えています")
        
        # AWS Bedrock Runtime クライアントの初期化
        # 指定されたリージョンでNova Canvas APIにアクセス
        bedrock_client = get_bedrock_client(aws_region)
        
        # Nova Canvas API用のリクエストパラメータ構築
        text_to_image_params = {
            "text": prompt
        }
        
        # ネガティブプロンプトの追加（指定されている場合）
        if negative_prompt:
            text_to_image_params["negativeText"] = negative_prompt
        
        inference_params = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": text_to_image_params,
            "imageGenerationConfig": {
                "numberOfImages": number_of_images,
                "quality": quality,
                "height": height,
                "width": width,
                "cfgScale": cfg_scale,
                "seed": seed
            }
        }
        
        # Amazon Nova Canvas API の呼び出し実行
        response = bedrock_client.invoke_model(
            modelId="amazon.nova-canvas-v1:0",
            body=json.dumps(inference_params)
        )
        
        # APIレスポンスのパースと処理
        response_body = json.loads(response['body'].read())
        
        # APIレスポンスのエラーチェック
        if "error" in response_body:
            return {
                "success": False,
                "error": response_body["error"],
                "message": "Nova Canvas API でエラーが発生しました"
            }
        
        # 生成された画像データの取得
        images_data = response_body.get("images", [])
        if not images_data:
            return {
                "success": False,
                "error": "画像データが生成されませんでした",
                "message": "画像生成に失敗しました"
            }
        
        # 成功時のレスポンスデータの構築
        generated_images = []
        for img_data in images_data:
            if isinstance(img_data, str):
                # 文字列の場合はそのまま追加
                generated_images.append(img_data)
            elif isinstance(img_data, dict) and "image" in img_data:
                # 辞書の場合はimageキーから取得
                generated_images.append(img_data["image"])
        
        return {
            "success": True,
            "images": generated_images,
            "message": f"テキストから画像生成が正常に実行されました（{len(generated_images)}枚生成）",
            "parameters": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "number_of_images": number_of_images,
                "quality": quality,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "region": aws_region
            }
        }
        
    except Exception as e:
        # 例外ハンドリング: AWS認証エラー、パラメータエラー等を含む
        return {
            "success": False,
            "error": str(e),
            "message": f"テキストから画像生成の実行中にエラーが発生しました: {str(e)}"
        }