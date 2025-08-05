# searchable_pdf_service.py

import io
import time
from PIL import Image
from pdf2image import convert_from_path
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

def create_searchable_pdf(input_pdf_path, output_pdf_path):
    """
    Converts a scanned PDF file into a searchable PDF.

    Args:
        input_pdf_path (str): The path to the input scanned PDF file.
        output_pdf_path (str): The path where the output searchable PDF will be saved.
    """
    try:
        app_logger.info(f"Searchable PDF 변환 시작: {input_pdf_path}")

        # 한글 지원 폰트 등록
        font_path = r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('MalgunGothic', font_path))
            font_name = 'MalgunGothic'
            app_logger.info(f"'{font_name}' 폰트 등록 성공.")
        else:
            font_name = 'Helvetica' # 폴백 폰트
            app_logger.warning(f"맑은 고딕 폰트를 찾을 수 없어 기본 '{font_name}' 폰트를 사용합니다. 한글이 깨질 수 있습니다.")

        # 1. PDF를 페이지별 이미지로 변환
        pil_images = convert_from_path(input_pdf_path)
        app_logger.info(f"PDF를 이미지로 변환 완료. 총 {len(pil_images)} 페이지.")

        # 2. ReportLab Canvas 생성 (결과 PDF 파일)
        pdf_canvas = canvas.Canvas(output_pdf_path)

        # 3. 페이지 루프 시작
        for i, image in enumerate(pil_images):
            page_num = i + 1
            app_logger.debug(f"{page_num} 페이지 처리 시작.")
            
            image_width, image_height = image.size
            
            # 페이지 크기를 원본 이미지와 동일하게 설정
            pdf_canvas.setPageSize((image_width, image_height))
            
            # 이미지를 바이트 데이터로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            
            # ocr_service를 통해 텍스트와 좌표 정보 가져오기
            text_annotations = detect_text_with_bounds(image_data)
            
            # 원본 이미지를 PDF 페이지 배경에 그리기
            pdf_canvas.drawImage(ImageReader(image), 0, 0, width=image_width, height=image_height)
            
            if text_annotations:
                # 텍스트 객체 생성
                text_object = pdf_canvas.beginText()
                # 렌더링 모드 3: 투명 (텍스트 선택/검색은 가능하지만 보이지 않음)
                text_object.setTextRenderMode(3)
                
                # 첫 번째 annotation은 전체 텍스트이므로 건너뛰고, 개별 단어부터 처리
                for annotation in text_annotations[1:]:
                    word = annotation.description
                    vertices = annotation.bounding_poly.vertices
                    
                    # 좌표계 변환: 이미지(좌상단 0,0) -> PDF(좌하단 0,0)
                    x = vertices[0].x
                    y = image_height - vertices[3].y
                    
                    # 단어 너비를 기반으로 폰트 크기 대략적으로 계산
                    width = vertices[1].x - vertices[0].x
                    height = vertices[3].y - vertices[0].y
                    
                    font_size = height * 0.8
                    
                    text_object.setFont(font_name, font_size)
                    text_object.setTextOrigin(x, y)
                    text_object.textLine(word)

                # 텍스트 객체를 캔버스에 그리기
                pdf_canvas.drawText(text_object)

            # 현재 페이지 작업 완료 후 다음 페이지로 이동
            pdf_canvas.showPage()
            app_logger.debug(f"{page_num} 페이지 처리 완료.")

        # 최종 PDF 파일 저장
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
