from dataclasses import dataclass, field
from typing import Optional, List, Any
from PIL.Image import Image as PILImage # PIL.Image.Image 타입을 명시적으로 사용

@dataclass
class PageDataSource:
    """
    EPUB 생성을 위한 원본 페이지/이미지 소스 정보를 담는 데이터 클래스.
    EpubProcessor의 _load_pages_from_pdf, _load_images_from_folder에서 생성됨.
    """
    path: str  # 원본 파일 경로 (PDF의 경우 "pdf_page_1" 등 내부 식별자, 이미지 폴더의 경우 실제 파일 경로)
    pil_image: PILImage # 로드된 PIL 이미지 객체
    original_index: int # 원본 리스트에서의 순서 (0부터 시작)

@dataclass
class OcrInputItem:
    """
    OCR 처리를 위해 ocr_service에 전달될 개별 이미지 정보를 담는 데이터 클래스.
    EpubProcessor의 _determine_ocr_and_illust_items에서 생성됨.
    """
    id: Any # 페이지 번호, 파일 경로 등 OCR 결과와 매칭할 수 있는 고유 식별자
    image: PILImage # OCR을 수행할 PIL 이미지 객체
    original_path: str # 원본 파일 경로 또는 식별자 (로깅 및 추적용)

@dataclass
class ProcessedPageItem:
    """
    OCR 또는 이미지 처리가 완료된 후 EPUB 챕터 생성을 위해 사용될 정보를 담는 데이터 클래스.
    EpubProcessor의 _extract_and_ocr_pages (내부적으로 _determine_ocr_and_illust_items 및 OCR 결과 조합)에서 생성됨.
    """
    type: str  # 'text' 또는 'image'
    page_num: int # EPUB 내에서의 순서 (1부터 시작)
    id: str # EPUB 아이템 ID (예: "page_1", "img_pdf_1")
    original_path: str # 원본 파일 경로 또는 식별자
    content: Optional[str] = None  # type이 'text'일 경우 OCR 결과 텍스트
    path: Optional[str] = None  # type이 'image'일 경우 임시 저장된 이미지 파일 경로