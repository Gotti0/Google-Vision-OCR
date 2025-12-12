import os
import shutil
import io
import time
import tempfile
import uuid # 고유 ID 생성을 위해 추가
from datetime import datetime # 메타데이터 날짜를 위해 추가
from ebooklib import epub
from PIL import Image
from pdf2image import convert_from_path

from logger import app_logger
from config_manager import config_manager
from ocr_service import ocr_pil_images_batch
from exceptions import EpubProcessingError, FileOperationError, OCRError
from dtos import PageDataSource, OcrInputItem, ProcessedPageItem

class EpubProcessor:
    def __init__(self, input_source, output_path_for_epub=None, illustration_pages=None, illustration_images=None, is_image_folder=False, language=None):
        self.language = language if language else config_manager.get("default_epub_language")
        self.input_source = input_source
        self.output_path_for_epub = output_path_for_epub
        self.illustration_pages = set(illustration_pages) if illustration_pages else set()
        self.illustration_images = [os.path.normpath(p) for p in illustration_images] if illustration_images else []
        self.is_image_folder = is_image_folder
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="epub_proc_")
        except Exception as e:
            app_logger.error(f"임시 디렉토리 생성 실패: {e}", exc_info=True)
            raise FileOperationError(f"임시 디렉토리 생성에 실패했습니다: {e}")
        app_logger.info(f"Processor 초기화: 입력='{self.input_source}', EPUB용 기본경로='{self.output_path_for_epub}', 임시폴더='{self.temp_dir}', 이미지폴더모드={is_image_folder}")
        app_logger.info(f"일러스트 페이지 (PDF 내): {self.illustration_pages}")
        app_logger.info(f"일러스트 이미지 (외부 파일): {self.illustration_images}")

    def _load_pages_from_pdf(self):
        """
        PDF 파일에서 페이지들을 PIL 이미지 객체 리스트로 로드합니다.
        """
        app_logger.info(f"'{self.input_source}' (PDF)에서 페이지 추출 시작...")
        try:
            pil_images = convert_from_path(self.input_source, output_folder=self.temp_dir, fmt='jpeg', paths_only=False)
            return [PageDataSource(path=f"pdf_page_{i+1}", pil_image=pil_img, original_index=i) for i, pil_img in enumerate(pil_images)]
        except Exception as e:
            app_logger.error(f"PDF '{self.input_source}' 페이지 추출 중 오류: {e}", exc_info=True)
            raise FileOperationError(f"PDF '{self.input_source}'에서 페이지를 추출하는 중 오류가 발생했습니다: {e}")

    def _load_images_from_folder(self):
        """
        이미지 폴더(self.input_source가 경로 리스트일 경우)에서 이미지들을 로드합니다.
        """
        app_logger.info(f"이미지 리스트에서 페이지 처리 시작 (총 {len(self.input_source)}개)...")
        loaded_images = []
        for i, img_path in enumerate(self.input_source): # self.input_source는 이미지 파일 경로 리스트
            try:
                normalized_path = os.path.normpath(img_path)
                loaded_images.append(PageDataSource(path=normalized_path, pil_image=Image.open(normalized_path), original_index=i))
            except FileNotFoundError:
                app_logger.error(f"이미지 파일 로드 실패 (파일 없음): '{img_path}'")
                raise FileOperationError(f"이미지 파일 '{img_path}'를 찾을 수 없습니다.")
            except Exception as e:
                app_logger.error(f"이미지 파일 로드 실패 '{img_path}': {e}", exc_info=True)
                raise FileOperationError(f"이미지 파일 '{img_path}'을 로드하는 중 오류가 발생했습니다: {e}")
        return loaded_images

    def _determine_ocr_and_illust_items(self, source_page_data_list: list[PageDataSource]) -> tuple[list[OcrInputItem], list[ProcessedPageItem]]:
        """
        로드된 페이지/이미지 리스트를 기반으로 OCR 대상과 일러스트 아이템을 결정합니다.
        결정된 아이템들은 임시 폴더에 이미지로 저장됩니다.
        """
        ocr_target_items = []
        processed_items_list = [] # ProcessedPageItem 리스트

        for i, page_data in enumerate(source_page_data_list):
            page_number_for_processing = i + 1 # EPUB 내 순서 및 ID 생성을 위한 내부 번호
            pil_image = page_data.pil_image
            original_path = page_data.path # 이미 _load_images_from_folder 또는 _load_pages_from_pdf 에서 정규화된 경로 또는 내부 식별자

            # 임시 폴더에 이미지 저장 (모든 페이지/이미지에 대해)
            temp_image_filename = f"page_{page_number_for_processing}.jpg"
            temp_image_path = os.path.join(self.temp_dir, temp_image_filename)
            try:
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                pil_image.save(temp_image_path, "JPEG")
            except Exception as e:
                app_logger.error(f"임시 이미지 파일 저장 실패 '{temp_image_path}': {e}", exc_info=True)
                raise FileOperationError(f"임시 이미지 파일 '{temp_image_filename}' 저장 중 오류: {e}")

            is_designated_illust = False
            item_id_prefix = "page_" # 기본 ID 접두사
            if not self.is_image_folder and page_number_for_processing in self.illustration_pages:
                is_designated_illust = True
                item_id_prefix = "img_pdf_"
            elif self.is_image_folder and original_path in self.illustration_images:
                is_designated_illust = True
                item_id_prefix = "img_folder_designated_"

            if is_designated_illust:
                app_logger.info(f"아이템 {page_number_for_processing} ('{original_path}')는 일러스트로 처리.")
                processed_items_list.append(ProcessedPageItem(
                    type='image', path=temp_image_path,
                    id=f'{item_id_prefix}{page_number_for_processing}',
                    page_num=page_number_for_processing, original_path=original_path
                ))
            else:
                app_logger.info(f"아이템 {page_number_for_processing} ('{original_path}') OCR 대상으로 추가.")
                ocr_target_items.append(OcrInputItem(id=page_number_for_processing, image=pil_image, original_path=original_path))
        
        return ocr_target_items, processed_items_list

    def _extract_and_ocr_pages(self) -> list[ProcessedPageItem]:
        """
        입력 소스에서 페이지를 로드하고, OCR을 수행하며, 최종 컨텐츠 리스트를 준비합니다.
        """
        if not self.is_image_folder:
            source_page_data_list = self._load_pages_from_pdf()
        else:
            source_page_data_list = self._load_images_from_folder()

        try:
            ocr_input_items, processed_page_items = self._determine_ocr_and_illust_items(source_page_data_list)
        except FileOperationError: # _determine_ocr_and_illust_items 내부에서 발생한 FileOperationError는 그대로 전달
            raise
        except Exception as e:
            app_logger.error(f"OCR/일러스트 아이템 결정 중 오류: {e}", exc_info=True)
            raise EpubProcessingError(f"페이지 처리 중 오류 발생: {e}")

        if ocr_input_items:
            try:
                ocr_results = ocr_pil_images_batch(ocr_input_items) # [{'id': 식별자, 'text': 추출된 텍스트}] 반환
            except OCRError: # ocr_service에서 발생한 OCRError는 그대로 전달
                raise
            except Exception as e: # ocr_pil_images_batch의 예상치 못한 다른 오류
                app_logger.error(f"배치 OCR 호출 중 예상치 못한 오류: {e}", exc_info=True)
                raise OCRError(f"배치 OCR 처리 중 오류: {e}")
                
            for result in ocr_results:
                # ocr_input_items에서 original_path를 찾아 매핑
                ocr_item_origin = next((item for item in ocr_input_items if item.id == result['id']), None)
                original_path_for_text = ocr_item_origin.original_path if ocr_item_origin else "Unknown"
                
                processed_page_items.append(ProcessedPageItem(
                    type='text', content=result['text'],
                    page_num=result['id'], id=f'page_{result["id"]}', # 텍스트 페이지 ID 규칙
                    original_path=original_path_for_text
                ))

        # 외부 일러스트 이미지 추가
        for idx, img_path in enumerate(self.illustration_images):
            # 경로의 앞뒤 공백과 따옴표를 제거하여 경로 문제 방지
            cleaned_path = img_path.strip().strip('"')
            if os.path.exists(cleaned_path):
                normalized_img_path = os.path.normpath(cleaned_path)
                # 이미지 폴더 모드에서 이미 폴더 내 일러스트로 지정된 경우 중복 방지
                if self.is_image_folder and normalized_img_path in [item.original_path for item in processed_page_items if item.type == 'image']:
                    app_logger.info(f"외부 일러스트 '{cleaned_path}'는 이미 폴더 내 지정 일러스트로 처리됨. 중복 추가 안함.")
                    continue
                
                temp_ext_img_name = f"ext_illust_{idx}{os.path.splitext(cleaned_path)[1]}"
                temp_ext_img_path = os.path.join(self.temp_dir, temp_ext_img_name)
                try:
                    shutil.copy(cleaned_path, temp_ext_img_path)
                    app_logger.info(f"외부 일러스트 이미지 추가: {cleaned_path} -> {temp_ext_img_path}")
                    processed_page_items.append(ProcessedPageItem(
                        type='image', path=temp_ext_img_path,
                        id=f'img_ext_{idx}', page_num=len(source_page_data_list) + idx + 1, # 페이지 번호는 기존 페이지 수 이후로
                        original_path=normalized_img_path # 정규화된 경로 저장
                    ))
                except Exception as e:
                    app_logger.warning(f"외부 일러스트 파일 복사 실패 '{cleaned_path}': {e}")
                    # 오류를 발생시키지 않고 경고만 로깅 후 계속 진행할 수 있음
            else:
                app_logger.error(f"외부 일러스트 이미지 파일을 찾을 수 없음: {img_path}")
                raise FileOperationError(f"외부 일러스트 이미지 파일을 찾을 수 없음: {img_path}")

        # 페이지 번호 기준으로 정렬
        processed_page_items.sort(key=lambda item: item.page_num)
        return processed_page_items
        
    def _create_css(self):
        """EPUB 표준 스타일시트 생성"""
        css_content = """
        @namespace epub "http://www.idpf.org/2007/ops";
        body {
            font-family: sans-serif, "Malgun Gothic", "Apple SD Gothic Neo";
            margin: 1em;
            background-color: #ffffff;
        }
        p {
            line-height: 1.6;
            margin-bottom: 1em;
            text-align: justify;
            text-indent: 0.5em; 
        }
        h1, h2, h3 {
            text-align: center;
            font-weight: bold;
            color: #333333;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
        }
        .page-break {
            page-break-after: always;
        }
        """
        return epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=css_content)

    def _convert_text_to_html_paragraphs(self, text):
        """
        단순 텍스트를 HTML <p> 태그로 변환합니다.
        <pre> 태그 대신 사용하여 Reflowable 기능을 지원합니다.
        """
        if not text:
            return ""
        
        # 줄바꿈 문자를 기준으로 문단을 나눕니다.
        # OCR 결과가 문장 중간에 줄바꿈이 되어 있다면 line_break_fixer 로직을
        # 여기에 통합하거나 사전에 처리해야 더 깔끔한 결과가 나옵니다.
        paragraphs = text.split('\n')
        html_parts = []
        for p in paragraphs:
            stripped = p.strip()
            if stripped:
                # HTML 특수문자 이스케이프 처리 필요 (간단한 예시)
                stripped = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_parts.append(f"<p>{stripped}</p>")
        return "\n".join(html_parts)

    def create_epub(self, output_epub_path=None, title="Sample Ebook", author="Unknown Author"):
        """
        추출된 텍스트와 이미지를 사용하여 표준 준수 EPUB 파일을 생성
        """
        final_output_path = output_epub_path or self.output_path_for_epub
        if not final_output_path:
            raise ValueError("EPUB 출력 경로가 지정되지 않았습니다.")
        
        app_logger.info(f"EPUB 생성 시작 (표준 준수 모드): '{final_output_path}'")
        
        book = epub.EpubBook()
        
        # 1. 메타데이터 설정 (표준 필수 항목)
        book.set_identifier(str(uuid.uuid4())) # 고유 UUID 설정
        book.set_title(title)
        book.set_language(self.language)
        book.add_author(author)
        # 더블린 코어(Dublin Core) 메타데이터 추가 가능 (날짜 등)
        book.add_metadata('DC', 'date', datetime.utcnow().isoformat())

        # 2. CSS 스타일시트 추가
        css_item = self._create_css()
        book.add_item(css_item)

        extracted_data = self._extract_and_ocr_pages() #

        new_chapters_for_toc = []
        new_spine_order = ['nav'] 

        current_text_group_content_html = []
        current_text_group_start_item = None

        def add_merged_text_chapter_to_book(start_item, content_list):
            if not start_item or not content_list:
                return

            merged_content_html = "".join(content_list)
            merged_chapter_title = f'Text Section {start_item.page_num}'
            merged_item_id = start_item.id 
            
            # 3. HTML 구조 개선 (XHTML 호환)
            epub_merged_chapter = epub.EpubHtml(title=merged_chapter_title, file_name=f'{merged_item_id}.xhtml', lang=self.language)
            
            # CSS 링크 연결
            epub_merged_chapter.add_item(css_item) 
            
            # 본문 내용 구성 (HTML5/XHTML)
            epub_merged_chapter.content = f"""
                <head><link rel="stylesheet" href="style/nav.css" type="text/css" /></head>
                <body>
                    <h2>{merged_chapter_title}</h2>
                    {merged_content_html}
                </body>
            """
            
            book.add_item(epub_merged_chapter)
            new_chapters_for_toc.append(epub_merged_chapter)
            new_spine_order.append(epub_merged_chapter)

        # 4. 표지(Cover) 이미지 처리 (첫 번째 이미지를 표지로 사용하고 싶은 경우)
        # 로직: 추출된 데이터 중 첫 번째가 이미지라면 표지로 설정
        # cover_set = False 

        for item_data in extracted_data:
            if item_data.type == 'text':
                if not current_text_group_start_item:
                    current_text_group_start_item = item_data
                
                # <pre> 대신 <p> 태그 변환 사용
                html_paragraphs = self._convert_text_to_html_paragraphs(item_data.content)
                # 페이지 구분을 위한 주석 또는 보이지 않는 마커 추가 가능
                html_for_this_page = f"""
                <div class="original-page" id="page_{item_data.page_num}">
                    {html_paragraphs}
                </div>
                """
                current_text_group_content_html.append(html_for_this_page)
            
            elif item_data.type == 'image':
                add_merged_text_chapter_to_book(current_text_group_start_item, current_text_group_content_html)
                current_text_group_content_html = []
                current_text_group_start_item = None
                
                img_pil = None
                try:
                    if item_data.path and os.path.exists(item_data.path):
                        img_pil = Image.open(item_data.path)
                        img_filename_epub = f"{item_data.id}{os.path.splitext(item_data.path)[1]}"
                        
                        epub_image = epub.EpubImage()
                        epub_image.file_name = f'images/{img_filename_epub}'
                        epub_image.media_type = Image.MIME.get(img_pil.format, 'image/jpeg')
                        with open(item_data.path, 'rb') as f_img:
                            epub_image.content = f_img.read()
                        
                        book.add_item(epub_image)

                        # 이미지 챕터 생성
                        image_chapter_title = f'Illustration {item_data.page_num}'
                        image_xhtml_filename = f'img_page_{item_data.id}.xhtml'
                        epub_img_chapter = epub.EpubHtml(title=image_chapter_title, file_name=image_xhtml_filename, lang=self.language)
                        epub_img_chapter.add_item(css_item) # CSS 추가
                        
                        # 이미지 중앙 정렬 및 반응형 처리 (CSS 클래스 활용)
                        epub_img_chapter.content = f"""
                            <head><link rel="stylesheet" href="style/nav.css" type="text/css" /></head>
                            <body>
                                <div class="image-container">
                                    <img src="images/{img_filename_epub}" alt="Illustration on page {item_data.page_num}" />
                                </div>
                            </body>
                        """
                        
                        book.add_item(epub_img_chapter)
                        new_chapters_for_toc.append(epub_img_chapter)
                        new_spine_order.append(epub_img_chapter)
                        
                        # (선택 사항) 첫 번째 이미지를 책 표지로 설정
                        # if not cover_set:
                        #     book.set_cover(img_filename_epub, epub_image.content)
                        #     cover_set = True
                            
                    else:
                        app_logger.warning(f"이미지 파일 경로를 찾을 수 없음: {item_data.path}")
                except Exception as e_img:
                    app_logger.error(f"이미지 처리 중 오류 ({item_data.path}): {e_img}", exc_info=True)
                finally:
                    if img_pil:
                        img_pil.close()

        add_merged_text_chapter_to_book(current_text_group_start_item, current_text_group_content_html)

        book.toc = new_chapters_for_toc
        book.spine = new_spine_order
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub.write_epub(final_output_path, book, {})
        app_logger.info(f"Standard EPUB 파일 생성 완료: '{final_output_path}'")
        self._cleanup()

    def create_txt(self, output_txt_path, title="Text Output"):
        """
        추출된 텍스트를 사용하여 TXT 파일을 생성합니다.

        Args:
            output_txt_path (str): 생성될 TXT 파일 경로.
            title (str): TXT 파일의 제목 (주로 로깅 및 메타데이터용).
        """
        app_logger.info(f"TXT 생성 시작: '{output_txt_path}', 제목: '{title}'")
        if not output_txt_path:
            raise ValueError("TXT 출력 경로가 지정되지 않았습니다.")

        extracted_data = self._extract_and_ocr_pages()

        full_text_content = io.StringIO()
        full_text_content.write(f"제목: {title}\n\n")

        for item_data in extracted_data: # ProcessedPageItem 객체
            if item_data.type == 'text':
                full_text_content.write(item_data.content if item_data.content else "")
                full_text_content.write("\n\n")
            elif item_data.type == 'image':
                full_text_content.write(f"[이미지 파일: {os.path.basename(item_data.path)}]\n\n")

        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(full_text_content.getvalue())

        app_logger.info(f"TXT 파일 생성 완료: '{output_txt_path}'")
        self._cleanup() # 임시 파일 정리

    def _cleanup(self):
        """임시 파일 및 폴더 정리"""
        if not (self.temp_dir and os.path.exists(self.temp_dir)):
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                shutil.rmtree(self.temp_dir)
                app_logger.info(f"임시 폴더 삭제 완료: {self.temp_dir}")
                return # 성공 시 함수 종료
            except PermissionError as e:
                app_logger.warning(f"임시 폴더 삭제 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # 1초 대기 후 재시도
                else:
                    app_logger.error(f"임시 폴더 삭제 최종 실패 후에도 폴더가 남아있을 수 있습니다: {self.temp_dir}. 오류: {e}")
                    # 여기서 오류를 다시 발생시키거나, 사용자에게 알리는 등의 추가 조치를 취할 수 있습니다.
            except Exception as e: # 다른 예외 처리 (예: FileNotFoundError 등)
                app_logger.error(f"임시 폴더 삭제 중 예상치 못한 오류 발생: {e}", exc_info=True)
                break # 예상치 못한 오류 시 재시도 중단

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
