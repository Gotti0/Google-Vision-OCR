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
import pypdf # Changed to pypdf
from pypdf import PdfWriter, PdfReader, Transformation

from logger import app_logger
from ocr_service import detect_text_with_bounds
from exceptions import OCRError, FileOperationError

# 이 파일은 스캔된 PDF를 검색 가능한 PDF로 변환하는 로직을 담당합니다.

def _process_page(page_task_data):
    """
    Helper function to process a single page for OCR.
    
    Args:
        page_task_data (tuple): A tuple containing page index and the input PDF path.
        
    Returns:
        tuple: (page_index, image_size, text_annotations)
               image_size is (width, height) in pixels.
    """
    page_index, input_pdf_path = page_task_data
    page_num = page_index + 1
    app_logger.debug(f"페이지 {page_num}: OCR 처리 시작.")
    
    try:
        # 1. Convert a single page to an image
        # Using default 200 DPI for balance between speed and OCR accuracy
        pil_images = convert_from_path(input_pdf_path, first_page=page_num, last_page=page_num)
        if not pil_images:
            raise FileOperationError(f"페이지 {page_num}를 이미지로 변환할 수 없습니다.")
        image = pil_images[0]
        image_size = image.size
        
        # 2. Convert image to byte data for OCR
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        # 3. Get text and bounds via OCR service
        text_annotations = detect_text_with_bounds(image_data)
        app_logger.debug(f"페이지 {page_num}: OCR 완료.")
        return page_index, image_size, text_annotations
    except Exception as e:
        app_logger.error(f"페이지 {page_num} 처리 중 오류 발생: {e}", exc_info=True)
        # On failure, return index, None size, None annotations
        return page_index, None, None

def _create_text_layer_pdf(image_size, text_annotations, font_name, symbol_font_name):
    """
    Creates a transparent PDF page containing the OCR text, matching the image dimensions.
    """
    image_width, image_height = image_size
    buffer = io.BytesIO()
    
    # Create canvas with the same size as the image
    pdf_canvas = canvas.Canvas(buffer, pagesize=(image_width, image_height))
    
    if text_annotations:
        text_object = pdf_canvas.beginText()
        text_object.setTextRenderMode(3)  # Invisible text
        
        primary_font = pdfmetrics.getFont(font_name)
        symbol_font = pdfmetrics.getFont(symbol_font_name) if symbol_font_name else None

        for annotation in text_annotations[1:]:
            word = annotation.description
            vertices = annotation.bounding_poly.vertices
            
            # Coordinates in image space (origin top-left)
            # ReportLab origin is bottom-left
            x = vertices[0].x
            
            # Calculate font size based on bounding box height
            # vertices[3] is bottom-left, vertices[0] is top-left in standard upright text
            # But OCR vertices order: 0:TL, 1:TR, 2:BR, 3:BL
            box_height = vertices[3].y - vertices[0].y
            
            # Y coordinate conversion: image_height - bottom_y
            y = image_height - vertices[3].y
            
            font_size = box_height * 0.8  # Heuristic adjustment
            
            text_object.setTextOrigin(x, y)

            if not symbol_font or not word:
                text_object.setFont(font_name, font_size)
                text_object.textLine(word)
                continue
            
            # --- Logic to handle multiple fonts (same as before) ---
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
                    last_font_name = font_name
            except IndexError:
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
            # --- End of logic ---

        pdf_canvas.drawText(text_object)

    pdf_canvas.showPage()
    pdf_canvas.save()
    buffer.seek(0)
    return buffer.getvalue()

def create_searchable_pdf(input_pdf_path, output_pdf_path):
    """
    Converts a scanned PDF file into a searchable PDF by overlaying OCR text.
    Preserves original PDF quality and reduces file size expansion.
    """
    try:
        app_logger.info(f"Searchable PDF 변환 시작 (Overlay 방식): {input_pdf_path}")

        # 1. 폰트 등록
        font_name = 'Helvetica'
        try:
            malgun_path = r"C:\Windows\Fonts\malgun.ttf"
            if os.path.exists(malgun_path):
                pdfmetrics.registerFont(TTFont('MalgunGothic', malgun_path))
                font_name = 'MalgunGothic'
                app_logger.info(f"기본 폰트로 '{font_name}'를 등록했습니다.")
            else:
                app_logger.warning(f"맑은 고딕 폰트를 찾을 수 없어 기본 '{font_name}' 폰트를 사용합니다.")
        except Exception as e:
            app_logger.error(f"기본 폰트 등록 중 오류 발생: {e}")

        symbol_font_name = None
        try:
            segoe_path = r"C:\Windows\Fonts\seguisym.ttf"
            if os.path.exists(segoe_path):
                pdfmetrics.registerFont(TTFont('SymbolFont', segoe_path))
                symbol_font_name = 'SymbolFont'
                app_logger.info(f"기호 폰트로 '{symbol_font_name}'을 등록했습니다.")
        except Exception as e:
            app_logger.error(f"기호 폰트 등록 중 오류 발생: {e}")

        # 2. Get PDF info
        pdf_info = pdfinfo_from_path(input_pdf_path)
        total_pages = pdf_info['Pages']
        app_logger.info(f"PDF 정보 확인 완료. 총 {total_pages} 페이지.")

        page_data_map = {} # index -> (image_size, annotations)
        
        # 3. Parallel OCR processing
        app_logger.info(f"총 {total_pages} 페이지에 대한 병렬 OCR 처리를 시작합니다.")
        with ThreadPoolExecutor() as executor:
            future_to_index = {executor.submit(_process_page, (i, input_pdf_path)): i for i in range(total_pages)}
            
            processed_count = 0
            for future in as_completed(future_to_index):
                page_index = future_to_index[future]
                processed_count += 1
                try:
                    _, image_size, annotations = future.result()
                    if image_size is None:
                        app_logger.error(f'페이지 {page_index + 1} 처리에 실패했습니다.')
                    else:
                        page_data_map[page_index] = (image_size, annotations)
                    app_logger.info(f"페이지 {page_index + 1}/{total_pages} OCR 완료. ({processed_count}/{total_pages})")
                except Exception as exc:
                    app_logger.error(f'페이지 {page_index + 1} OCR 중 예외 발생: {exc}', exc_info=True)

        # 4. Create final PDF with overlays
        app_logger.info("모든 페이지 OCR 완료. PDF 병합(Overlay)을 시작합니다.")
        
        try:
            reader = PdfReader(input_pdf_path)
            writer = PdfWriter()
            
            for i, page in enumerate(reader.pages):
                if i not in page_data_map:
                    # OCR failed or processed, just add original page
                    writer.add_page(page)
                    app_logger.warning(f"페이지 {i+1}: OCR 결과 없음, 원본 유지.")
                    continue
                
                image_size, annotations = page_data_map[i]
                
                # Generate text-only PDF layer
                text_layer_bytes = _create_text_layer_pdf(image_size, annotations, font_name, symbol_font_name)
                
                # Load text layer
                text_layer_reader = PdfReader(io.BytesIO(text_layer_bytes))
                text_page = text_layer_reader.pages[0]
                
                # Calculate scale
                # Original page dimensions
                orig_width = float(page.mediabox.width)
                orig_height = float(page.mediabox.height)
                
                # Text layer dimensions (image size)
                text_width = float(text_page.mediabox.width)
                text_height = float(text_page.mediabox.height)
                
                # prevent divide by zero
                if text_width > 0 and text_height > 0:
                    scale_x = orig_width / text_width
                    scale_y = orig_height / text_height
                    
                    # Apply transformation to text page to fit original page
                    op = Transformation().scale(scale_x, scale_y)
                    text_page.add_transformation(op)
                    
                    # Merge text page onto original page (original is background)
                    page.merge_page(text_page)
                
                writer.add_page(page)

            with open(output_pdf_path, "wb") as f_out:
                writer.write(f_out)
                
            app_logger.info(f"Searchable PDF 생성 완료: {output_pdf_path}")
            
        except Exception as e:
            app_logger.error(f"PDF 병합 중 오류 발생: {e}", exc_info=True)
            raise OCRError(f"PDF 병합 중 오류: {e}")

    except FileNotFoundError:
        app_logger.error(f"입력 파일을 찾을 수 없음: {input_pdf_path}")
        raise FileOperationError(f"입력 파일을 찾을 수 없음: {input_pdf_path}")
    except Exception as e:
        app_logger.error(f"Searchable PDF 생성 중 오류 발생: {e}", exc_info=True)
        raise OCRError(f"Searchable PDF 생성 중 오류: {e}")


if __name__ == '__main__':
    app_logger.info("searchable_pdf_service.py 직접 실행 (테스트 코드 없음).")
