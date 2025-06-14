import os
import shutil
import tempfile
from ebooklib import epub
from PIL import Image
from pdf2image import convert_from_path
from logger import app_logger
from config_manager import config_manager # ConfigManager 임포트
from ocr_service import ocr_pil_images_batch # 새로운 배치 OCR 함수 사용

class EpubProcessor:
    def __init__(self, input_source, output_epub_path, illustration_pages=None, illustration_images=None, is_image_folder=False, language=None):
        """
        EPUB 생성기 초기화

        Args:
            input_source (str or list): 원본 PDF 파일 경로 또는 이미지 파일 경로 리스트
            output_epub_path (str): 생성될 EPUB 파일 경로
            illustration_pages (list, optional): PDF 내 일러스트 페이지 번호 목록 (1부터 시작). Defaults to None.
            illustration_images (list, optional): 별도 일러스트 이미지 파일 경로 목록. Defaults to None.
            is_image_folder (bool): input_source가 이미지 파일 리스트인지 여부. Defaults to False.
        """
        self.language = language if language else config_manager.get("default_epub_language")
        self.input_source = input_source
        self.output_epub_path = output_epub_path
        self.illustration_pages = set(illustration_pages) if illustration_pages else set()
        self.illustration_images = illustration_images if illustration_images else []
        self.is_image_folder = is_image_folder
        self.temp_dir = tempfile.mkdtemp()
        app_logger.info(f"EpubProcessor 초기화: 입력='{input_source}', EPUB='{output_epub_path}', 임시폴더='{self.temp_dir}', 이미지폴더모드={is_image_folder}")
        app_logger.info(f"일러스트 페이지 (PDF 내): {self.illustration_pages}")
        app_logger.info(f"일러스트 이미지 (외부 파일): {self.illustration_images}")

    def _extract_and_ocr_pages(self):
        """
        입력 소스(PDF 또는 이미지 리스트)에서 페이지를 처리.
        PDF인 경우: 페이지를 추출하고, 일러스트가 아닌 페이지만 OCR 수행. 일러스트 페이지는 이미지로 저장.
        이미지 리스트인 경우: 각 이미지를 그대로 사용 (OCR 없음).
        """
        processed_content = [] # (타입, 데이터, 페이지번호) - 타입: 'text' 또는 'image'
        source_pages_pil = [] # PIL Image 객체 리스트

        if not self.is_image_folder: # PDF 처리
            app_logger.info(f"'{self.input_source}' (PDF)에서 페이지 추출 및 OCR 시작...")
            source_pages_pil = convert_from_path(self.input_source, output_folder=self.temp_dir, fmt='jpeg', paths_only=False)
        else: # 이미지 폴더(리스트) 처리
            app_logger.info(f"이미지 리스트에서 페이지 처리 시작 (총 {len(self.input_source)}개)...")
            # self.input_source는 이미지 파일 경로의 리스트여야 함
            for img_path in self.input_source:
                try:
                    source_pages_pil.append(Image.open(img_path))
                except Exception as e:
                    app_logger.error(f"이미지 파일 로드 실패 '{img_path}': {e}")
                    continue # 다음 이미지로
        images_for_ocr = [] # OCR을 수행할 이미지와 해당 식별자(페이지 번호)를 저장

        for i, page_pil_data in enumerate(source_pages_pil):
            page_number = i + 1 # 내부 처리용 순차 번호
            page_pil = page_pil_data['pil']
            original_file_path = page_pil_data.get('path', f"unknown_source_{page_number}")

            page_image_filename = f"page_{page_number}.jpg"
            page_image_path = os.path.join(self.temp_dir, page_image_filename)
            page_pil.save(page_image_path, "JPEG")

            # PDF 모드에서는 illustration_pages 사용, 이미지 폴더 모드에서는 illustration_images 사용
            is_designated_illust = False
            if not self.is_image_folder and page_number in self.illustration_pages:
                is_designated_illust = True
            elif self.is_image_folder and original_file_path in self.illustration_images:
                is_designated_illust = True

            if is_designated_illust:
                app_logger.info(f"페이지 {page_number} ('{original_file_path}')는 일러스트로 처리. 이미지 저장: {page_image_path}")
                item_id_prefix = "img_pdf_" if not self.is_image_folder else "img_folder_designated_"
                processed_content.append({
                    'type': 'image', 'path': page_image_path, 
                    'id': f'{item_id_prefix}{page_number}', 
                    'page_num': page_number, 'original_path': original_file_path
                })
            else:
                app_logger.info(f"페이지 {page_number} ('{original_file_path}') OCR 대상으로 추가.")
                images_for_ocr.append({'id': page_number, 'image': page_pil, 'original_path': original_file_path})

        if images_for_ocr:
            ocr_results = ocr_pil_images_batch(images_for_ocr)
            for result in ocr_results:
                # images_for_ocr에서 original_path를 찾아 매핑
                original_path_for_text = next((item['original_path'] for item in images_for_ocr if item['id'] == result['id']), "Unknown")
                processed_content.append({'type': 'text', 'content': result['text'], 'page_num': result['id'], 'original_path': original_path_for_text})

        # 외부 일러스트 이미지 추가
        for idx, img_path in enumerate(self.illustration_images):
            if os.path.exists(img_path):
                base_name = os.path.basename(img_path)
                dest_path = os.path.join(self.temp_dir, base_name)
                shutil.copy(img_path, dest_path)
                app_logger.info(f"외부 일러스트 이미지 추가: {img_path} -> {dest_path}")
                # 외부 이미지는 PDF 페이지 번호와 직접적인 연관이 없으므로, PDF 페이지 이후에 순차적으로 배치하거나
                # 별도의 삽입 로직이 필요할 수 있습니다. 여기서는 PDF 페이지 이후 순서로 가정합니다.
                # 페이지 번호는 PDF 페이지 수 이후로 할당하거나, None으로 두고 순서대로 처리합니다.
                processed_content.append({'type': 'image', 'path': dest_path, 'id': f'img_ext_{idx}', 'page_num': len(source_pages_pil) + idx + 1})
            else:
                app_logger.warning(f"외부 일러스트 이미지 파일을 찾을 수 없음: {img_path}")

        # 페이지 번호 기준으로 정렬
        processed_content.sort(key=lambda x: x['page_num'])
        return processed_content

    def create_epub(self, title="Sample Ebook", author="Unknown Author"):
        """
        추출된 텍스트와 이미지를 사용하여 EPUB 파일을 생성
        """
        app_logger.info(f"EPUB 생성 시작: '{self.output_epub_path}'")
        book = epub.EpubBook()
        book.set_identifier('id123456') # 고유 ID 설정 필요
        book.set_title(title)
        book.set_language(self.language)
        book.add_author(author)

        extracted_data = self._extract_and_ocr_pages()
        
        chapters = []
        spine = ['nav'] # 목차(nav)를 가장 먼저 추가

        for i, item_data in enumerate(extracted_data):
            item_id = item_data.get('id', f"item_{i}")
            page_num_for_title = item_data.get('page_num', i + 1)

            if item_data['type'] == 'text':
                chapter_title = f'Page {page_num_for_title}'
                # HTML 형식으로 변환 (간단한 예시)
                html_content = f"<h1>{chapter_title}</h1><pre>{item_data['content']}</pre>"
                
                # EpubHtml 객체 생성
                # 파일명은 고유해야 하므로 item_id 사용
                epub_chapter = epub.EpubHtml(title=chapter_title, file_name=f'{item_id}.xhtml', lang='ko')
                epub_chapter.content = html_content
                book.add_item(epub_chapter)
                chapters.append(epub_chapter)
                spine.append(epub_chapter)
                app_logger.debug(f"텍스트 챕터 추가: {chapter_title} ({item_id}.xhtml)")

            elif item_data['type'] == 'image':
                try:
                    img_pil = Image.open(item_data['path'])
                    # EPUB에 이미지 추가 시 파일명(href)은 EPUB 내부 경로가 됨
                    # item_id를 파일명으로 사용하고, 실제 파일 확장자를 유지
                    img_filename_epub = f"{item_id}{os.path.splitext(item_data['path'])[1]}"
                    
                    epub_image = epub.EpubImage()
                    epub_image.file_name = f'images/{img_filename_epub}' # EPUB 내 이미지 폴더 경로
                    epub_image.media_type = Image.MIME[img_pil.format]
                    with open(item_data['path'], 'rb') as f_img:
                        epub_image.content = f_img.read()
                    book.add_item(epub_image)
                    app_logger.debug(f"이미지 아이템 추가: {epub_image.file_name}")

                    # 이미지를 보여주는 XHTML 챕터 생성
                    image_chapter_title = f'Illustration (Page {page_num_for_title})'
                    # 파일명은 고유해야 하므로 item_id 사용 (텍스트 챕터와 구분)
                    image_xhtml_filename = f'img_page_{item_id}.xhtml'
                    epub_img_chapter = epub.EpubHtml(title=image_chapter_title, file_name=image_xhtml_filename, lang='ko')
                    epub_img_chapter.content = f'<h1>{image_chapter_title}</h1><div><img src="images/{img_filename_epub}" alt="{image_chapter_title}" style="max-width:100%;"/></div>'
                    epub_img_chapter.add_item(epub_image) # 이미지 아이템을 이 챕터에 연결
                    book.add_item(epub_img_chapter)
                    chapters.append(epub_img_chapter) # 목차용
                    spine.append(epub_img_chapter) # 읽기 순서용
                    app_logger.debug(f"이미지 챕터 추가: {image_chapter_title} ({image_xhtml_filename})")
                except Exception as e_img:
                    app_logger.error(f"이미지 처리 중 오류 ({item_data['path']}): {e_img}", exc_info=True)

        book.toc = chapters # 목차 설정
        book.spine = spine # 읽기 순서 설정
        book.add_item(epub.EpubNcx()) # NCX (목차) 파일 생성
        book.add_item(epub.EpubNav()) # Nav (탐색) 문서 생성

        epub.write_epub(self.output_epub_path, book, {})
        app_logger.info(f"EPUB 파일 생성 완료: '{self.output_epub_path}'")
        self._cleanup()

    def _cleanup(self):
        """임시 파일 및 폴더 정리"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            app_logger.info(f"임시 폴더 삭제 완료: {self.temp_dir}")

if __name__ == '__main__':
    # 테스트용 예시 (실제 사용 시 GUI 등에서 경로를 받아와야 함)
    # 이 테스트를 실행하려면 ocr_service.py, logger.py가 필요하고,
    # GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되어 있어야 합니다.
    # 또한, 테스트용 PDF 파일 (test.pdf)과 이미지 파일 (test_illust.jpg)이 필요합니다.
    
    # if os.path.exists("test.epub"): os.remove("test.epub") # 기존 테스트 파일 삭제
    # if not os.path.exists("test.pdf"): open("test.pdf", "w").write("dummy pdf content for test") # 더미 PDF
    # if not os.path.exists("test_illust.jpg"): Image.new('RGB', (60, 30), color = 'red').save("test_illust.jpg") # 더미 이미지

    # processor = EpubProcessor(
    #     pdf_path="test.pdf", # 실제 PDF 파일 경로로 변경
    #     output_epub_path="test.epub",
    #     illustration_pages=[1], # 예: 1페이지를 일러스트로 간주 (PDF 내)
    #     illustration_images=["test_illust.jpg"] # 예: 외부 일러스트 이미지 파일
    # )
    # processor.create_epub(title="나의 테스트 Ebook", author="홍길동")
    app_logger.info("epub_processor.py 테스트 완료 (주석 처리된 예시 실행 필요).")