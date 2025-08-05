# searchable_pdf_service.py

import io
import time
from PIL import Image
from pdf2image import convert_from_path, pdfinfo_from_path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from logger import app_logger
from ocr_service import detect_text_with_bounds
from exceptions import OCRError, FileOperationError

# 이 파일은 스캔된 PDF를 검색 가능한 PDF로 변환하는 로직을 담당합니다.

def _process_page(page_task_data):
    """
    Helper function to process a single page in a fully parallel manner.
    It handles both image conversion and OCR for one page.
    
    Args:
        page_task_data (tuple): A tuple containing page index and the input PDF path.
        
    Returns:
        tuple: A tuple containing the page index, the processed PIL image, and the OCR annotations.
    """
    page_index, input_pdf_path = page_task_data
    page_num = page_index + 1
    app_logger.debug(f"페이지 {page_num}: 처리 시작 (이미지 변환 + OCR).")
    
    try:
        # 1. Convert a single page to an image
        # first_page and last_page are 1-based
        pil_images = convert_from_path(input_pdf_path, first_page=page_num, last_page=page_num)
        if not pil_images:
            raise FileOperationError(f"페이지 {page_num}를 이미지로 변환할 수 없습니다.")
        image = pil_images[0]
        
        # 2. Convert image to byte data for OCR
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        # 3. Get text and bounds via OCR service
        text_annotations = detect_text_with_bounds(image_data)
        app_logger.debug(f"페이지 {page_num}: 처리 완료.")
        return page_index, image, text_annotations
    except Exception as e:
        app_logger.error(f"페이지 {page_num} 처리 중 오류 발생: {e}", exc_info=True)
        # On failure, return index, a placeholder for the image, and None for annotations
        return page_index, None, None

def create_searchable_pdf(input_pdf_path, output_pdf_path):
    """
    Converts a scanned PDF file into a searchable PDF using parallel processing
    for both image conversion and OCR. It supports mathematical symbols by using a fallback font.
    """
    try:
        app_logger.info(f"Searchable PDF 변환 시작: {input_pdf_path}")

        # 1. 폰트 등록
        # 기본 한글 폰트
        font_name = 'Helvetica' # 기본 폴백 폰트
        try:
            malgun_path = r"C:\Windows\Fonts\malgun.ttf"
            if os.path.exists(malgun_path):
                pdfmetrics.registerFont(TTFont('MalgunGothic', malgun_path))
                font_name = 'MalgunGothic'
                app_logger.info(f"기본 폰트로 '{font_name}'를 등록했습니다.")
            else:
                app_logger.warning(f"맑은 고딕 폰트를 찾을 수 없어 기본 '{font_name}' 폰트를 사용합니다. 한글이 깨질 수 있습니다.")
        except Exception as e:
            app_logger.error(f"기본 폰트 등록 중 오류 발생: {e}")

        # 수학/기호용 폴백 폰트
        symbol_font_name = None
        try:
            segoe_path = r"C:\Windows\Fonts\seguisym.ttf"
            if os.path.exists(segoe_path):
                pdfmetrics.registerFont(TTFont('SymbolFont', segoe_path))
                symbol_font_name = 'SymbolFont'
                app_logger.info(f"기호 폰트로 '{symbol_font_name}' (Segoe UI Symbol)을 등록했습니다.")
            else:
                app_logger.warning("기호 폰트(Segoe UI Symbol)를 찾을 수 없습니다. 일부 기호가 표시되지 않을 수 있습니다.")
        except Exception as e:
            app_logger.error(f"기호 폰트 등록 중 오류 발생: {e}")

        # 2. Get PDF info and process pages in parallel
        pdf_info = pdfinfo_from_path(input_pdf_path)
        total_pages = pdf_info['Pages']
        app_logger.info(f"PDF 정보 확인 완료. 총 {total_pages} 페이지.")

        page_results = [None] * total_pages
        app_logger.info(f"총 {total_pages} 페이지에 대한 병렬 처리를 시작합니다.")

        with ThreadPoolExecutor() as executor:
            future_to_index = {executor.submit(_process_page, (i, input_pdf_path)): i for i in range(total_pages)}
            
            processed_count = 0
            for future in as_completed(future_to_index):
                page_index = future_to_index[future]
                processed_count += 1
                try:
                    _, image, annotations = future.result()
                    if image is None:
                        app_logger.error(f'페이지 {page_index + 1} 처리에 실패하여 결과가 없습니다.')
                        page_results[page_index] = "failed"
                    else:
                        page_results[page_index] = (image, annotations)
                    app_logger.info(f"페이지 {page_index + 1}/{total_pages} 처리 완료. ({processed_count}/{total_pages})")
                except Exception as exc:
                    app_logger.error(f'페이지 {page_index + 1} 처리 중 예외 발생: {exc}', exc_info=True)
                    page_results[page_index] = "failed"

        # 3. Create the final PDF from the results
        app_logger.info("모든 페이지 처리 완료. PDF 파일 작성을 시작합니다.")
        pdf_canvas = canvas.Canvas(output_pdf_path)

        for i, result in enumerate(page_results):
            page_num = i + 1
            if result is None or result == "failed":
                app_logger.error(f"페이지 {page_num}의 처리 결과가 없어 PDF에 빈 페이지를 추가합니다.")
                from reportlab.lib.pagesizes import A4
                pdf_canvas.setPageSize(A4)
                pdf_canvas.showPage()
                continue

            image, text_annotations = result
            
            app_logger.debug(f"{page_num} 페이지 PDF 작성 시작.")
            
            image_width, image_height = image.size
            pdf_canvas.setPageSize((image_width, image_height))
            
            pdf_canvas.drawImage(ImageReader(image), 0, 0, width=image_width, height=image_height)
            
            if text_annotations:
                text_object = pdf_canvas.beginText()
                text_object.setTextRenderMode(3) # Invisible text
                
                primary_font = pdfmetrics.getFont(font_name)
                symbol_font = pdfmetrics.getFont(symbol_font_name) if symbol_font_name else None

                for annotation in text_annotations[1:]:
                    word = annotation.description
                    vertices = annotation.bounding_poly.vertices
                    
                    x = vertices[0].x
                    y = image_height - vertices[3].y
                    height = vertices[3].y - vertices[0].y
                    font_size = height * 0.8
                    
                    text_object.setTextOrigin(x, y)

                    if not symbol_font or not word:
                        text_object.setFont(font_name, font_size)
                        text_object.textLine(word)
                        continue
                    
                    # --- Corrected logic to handle multiple fonts ---
                    def has_char(font, char):
                        return ord(char) in font.face.charToGlyph

                    current_chunk = ""
                    try:
                        first_char = word[0]
                        if has_char(primary_font, first_char):
                            last_font_name = font_name
                        elif symbol_font and has_char(symbol_font, first_char):
                            last_font_name = symbol_font_name
                        else:
                            last_font_name = font_name # Default fallback
                    except IndexError: # Empty word
                        continue

                    text_object.setFont(last_font_name, font_size)

                    for char in word:
                        char_font_name = font_name
                        if not has_char(primary_font, char):
                            if symbol_font and has_char(symbol_font, char):
                                char_font_name = symbol_font_name
                        
                        if char_font_name == last_font_name:
                            current_chunk += char
                        else:
                            if current_chunk:
                                text_object.textOut(current_chunk)
                            last_font_name = char_font_name
                            text_object.setFont(last_font_name, font_size)
                            current_chunk = char
                    
                    if current_chunk:
                        text_object.textOut(current_chunk)
                    # --- End of corrected logic ---

                pdf_canvas.drawText(text_object)

            pdf_canvas.showPage()
            app_logger.debug(f"{page_num} 페이지 PDF 작성 완료.")

        pdf_canvas.save()
        app_logger.info(f"Searchable PDF 생성 완료: {output_pdf_path}")

    except FileNotFoundError:
        app_logger.error(f"입력 파일을 찾을 수 없음: {input_pdf_path}")
        raise FileOperationError(f"입력 파일을 찾을 수 없음: {input_pdf_path}")
    except Exception as e:
        app_logger.error(f"Searchable PDF 생성 중 오류 발생: {e}", exc_info=True)
        raise OCRError(f"Searchable PDF 생성 중 오류: {e}")


if __name__ == '__main__':
    app_logger.info("searchable_pdf_service.py 직접 실행 (테스트 코드 없음).")
