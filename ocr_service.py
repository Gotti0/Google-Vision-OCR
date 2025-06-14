import os
import io
import numpy as np
from PIL import Image
import cv2
from google.cloud import vision
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import app_logger # 로거 임포트
from config_manager import config_manager # ConfigManager 임포트
from dtos import OcrInputItem # OcrInputItem DTO 임포트

# The environment variable for Google Vision API credentials
# will be set by the GUI (ocr_gui.py) or should be set in the system environment.
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'' # 사용자에게 GUI를 통해 입력받도록 변경됨

def detect_text_from_image(image_data):
    """
    Detects text in an image file using Google Vision API and returns it.
    
    Args:
        image_data (bytes): The image data in bytes format.
        
    Returns:
        str: The detected text.
    """
    try:
        app_logger.debug("Google Vision API 클라이언트 생성 시도.")
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_data)
        app_logger.debug("텍스트 감지 수행 중...")
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if texts:
            app_logger.info("텍스트 감지 성공.")
            return texts[0].description
        else:
            app_logger.info("감지된 텍스트 없음.")
            return ""
    except Exception as e:
        app_logger.error(f"Google Vision API 텍스트 감지 중 오류: {e}", exc_info=True)
        raise

def preprocess_image(image):
    """
    Preprocesses the image to enhance OCR accuracy by converting it to grayscale.
    
    Args:
        image (PIL.Image.Image): The image to preprocess.
        
    Returns:
        PIL.Image.Image: The preprocessed image.
    """
    try:
        app_logger.debug("이미지 전처리 시작 (그레이스케일 변환).")
        image_np = np.array(image)
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        processed_image = Image.fromarray(gray)
        app_logger.debug("이미지 전처리 완료.")
        return processed_image
    except Exception as e:
        app_logger.error(f"이미지 전처리 중 오류: {e}", exc_info=True)
        raise

def process_page(page, page_number):
    """
    Processes a single page of PDF: converts to image, preprocesses, performs OCR, and returns the extracted text.
    
    Args:
        page (PIL.Image.Image): The PDF page as a PIL image.
        page_number (int): The page number.
        
    Returns:
        tuple: A tuple containing the page number and extracted text.
    """
    try:
        app_logger.info(f"{page_number} 페이지 처리 시작.")
        buffer = io.BytesIO()
        processed_page = preprocess_image(page) # 전처리된 이미지 사용
        processed_page.save(buffer, format="PNG")
        image_data = buffer.getvalue()

        extracted_text = detect_text_from_image(image_data)
        app_logger.info(f"{page_number} 페이지 텍스트 추출 완료.")
        return (page_number, extracted_text)
    except Exception as e:
        app_logger.error(f"{page_number} 페이지 처리 중 오류: {e}", exc_info=True)
        # 오류 발생 시 빈 텍스트와 함께 페이지 번호 반환 또는 예외를 다시 발생시켜 상위에서 처리
        return (page_number, f"Error processing page {page_number}: {e}")
        
def process_pdf(pdf_path, output_folder):
    """
    Processes each page in a PDF file and performs OCR.
    
    Args:
        pdf_path (str): The path to the PDF file.
        output_folder (str): The folder where the output text file will be saved.
    """
    app_logger.info(f"PDF 처리 시작: {pdf_path}")
    try:
        pages = convert_from_path(pdf_path)
        app_logger.info(f"PDF를 이미지로 변환 완료. 총 {len(pages)} 페이지.")

        output_text_file = os.path.join(output_folder, f"{os.path.basename(pdf_path)}.txt")
        
        with open(output_text_file, 'w', encoding='utf-8') as text_file:
            with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor: # CPU 코어 수만큼 워커 사용
                app_logger.debug(f"ThreadPoolExecutor 생성 (max_workers={executor._max_workers}). 페이지 처리 시작.")
                futures = [executor.submit(process_page, page, page_number)
                           for page_number, page in enumerate(pages, start=1)]
                results = sorted([future.result() for future in as_completed(futures)], key=lambda x: x[0])
            
            app_logger.info("모든 페이지 처리 완료. 파일에 결과 작성 중...")
            for page_number, text in results:
                text_file.write(f"\n--- Page {page_number} ---\n")
                text_file.write(text)
                text_file.write("\n\n")
        app_logger.info(f"PDF 처리 완료. 결과 저장: {output_text_file}")
    except Exception as e:
        app_logger.error(f"PDF 처리 중 오류 ({pdf_path}): {e}", exc_info=True)
        # GUI에서 이 오류를 잡아서 사용자에게 알릴 수 있도록 raise
        raise
        
def process_images_in_folder(input_folder, output_folder):
    """
    Processes all image files (png, jpg, jpeg, bmp, tiff, gif) in the input folder
    and stores the results in the output folder.
    
    Args:
        input_folder (str): The folder containing image files.
        output_folder (str): The folder where the output text files will be saved.
    """
    app_logger.info(f"폴더 내 이미지 일괄 처리 시작: {input_folder}")
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            app_logger.info(f"출력 폴더 생성됨: {output_folder}")

        supported_image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')
        image_files_processed = 0
        for file_name in os.listdir(input_folder):
            if file_name.lower().endswith(supported_image_extensions):
                image_path = os.path.join(input_folder, file_name)
                process_single_image_file(image_path, output_folder)
                image_files_processed += 1
        app_logger.info(f"폴더 내 이미지 일괄 처리 완료. 총 {image_files_processed}개 파일 처리됨: {input_folder}")
    except Exception as e:
        app_logger.error(f"폴더 내 이미지 일괄 처리 중 오류 ({input_folder}): {e}", exc_info=True)
        raise
        
def process_single_image_file(image_path, output_folder):
    """
    Processes a single image file, performs OCR, and saves the text.

    Args:
        image_path (str): The path to the image file.
        output_folder (str): The folder where the output text file will be saved.
    """
    app_logger.info(f"단일 이미지 파일 처리 시작: {image_path}")
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            app_logger.info(f"출력 폴더 생성됨: {output_folder}")

        img = Image.open(image_path)
        app_logger.debug(f"이미지 로드 완료: {image_path}")

        # 이미지 전처리 (그레이스케일 변환 등) - 필요시 활성화
        # img = preprocess_image(img)

        buffer = io.BytesIO()
        img_format = img.format if img.format in ["PNG", "JPEG", "BMP", "TIFF"] else "PNG"
        img.save(buffer, format=img_format)
        image_data = buffer.getvalue()
        app_logger.debug(f"이미지를 바이트 데이터로 변환 완료 (포맷: {img_format}).")

        extracted_text = detect_text_from_image(image_data)
        
        base_name = os.path.basename(image_path)
        text_file_name = os.path.splitext(base_name)[0] + ".txt"
        output_text_file = os.path.join(output_folder, text_file_name)

        with open(output_text_file, 'w', encoding='utf-8') as text_file:
            text_file.write(extracted_text)
        app_logger.info(f"텍스트 추출 완료 및 저장: {output_text_file}")
    except FileNotFoundError:
        app_logger.error(f"이미지 파일을 찾을 수 없음: {image_path}")
        raise
    except Exception as e:
        app_logger.error(f"단일 이미지 파일 처리 중 오류 ({image_path}): {e}", exc_info=True)
        raise

def ocr_pil_images_batch(pil_images_with_identifiers):
    """
    여러 PIL 이미지에 대해 OCR을 수행하고, 각 이미지의 식별자와 함께 텍스트 결과를 반환합니다.
    ThreadPoolExecutor를 사용하여 병렬 처리합니다.

    Args:
        pil_images_with_identifiers (List[OcrInputItem]): OCR을 수행할 OcrInputItem 객체 리스트.
                                                          id는 페이지 번호, 파일 경로 등이 될 수 있습니다.

    Returns:
        list: 각 요소가 {'id': 식별자, 'text': 추출된 텍스트} 형태인 딕셔너리 리스트.
              오류 발생 시 text 필드에 오류 메시지가 포함될 수 있습니다.
    """
    app_logger.info(f"총 {len(pil_images_with_identifiers)}개 이미지에 대한 배치 OCR 시작.")
    results = []
    
    # process_page 함수는 (identifier, text)를 반환하도록 수정하거나,
    # 여기서 identifier를 process_page에 전달하고 결과를 매핑해야 합니다.
    # 현재 process_page는 (page_number, text)를 반환하므로, id를 page_number로 사용합니다.
    
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
        future_to_id = {executor.submit(process_page, item.image, item.id): item.id for item in pil_images_with_identifiers}
        for future in as_completed(future_to_id):
            identifier = future_to_id[future]
            try:
                _, text_content = future.result() # process_page는 (id, text) 반환
                results.append({'id': identifier, 'text': text_content})
                app_logger.debug(f"이미지 ID '{identifier}' OCR 완료.")
            except Exception as exc:
                app_logger.error(f"이미지 ID '{identifier}' 처리 중 오류: {exc}", exc_info=True)
                results.append({'id': identifier, 'text': f"Error processing image ID {identifier}: {exc}"})
    app_logger.info("배치 OCR 처리 완료.")
    return results

if __name__ == "__main__":
    app_logger.info("ocr_service.py 직접 실행 (테스트 코드 없음).")
