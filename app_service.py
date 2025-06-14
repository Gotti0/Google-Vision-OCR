import os
from logger import app_logger
from epub_processor import EpubProcessor
# ocr_service는 epub_processor 내부에서 사용되므로 직접적인 의존성은 줄어들 수 있음
# 필요한 경우 ocr_service의 특정 기능(예: 환경변수 설정)만 가져올 수 있음
from ocr_service import os as ocr_os
from exceptions import ApplicationBaseException, ConfigError, FileOperationError, OCRError, EpubProcessingError # 사용자 정의 예외 임포트

class ApplicationService:
    def __init__(self):
        app_logger.info("ApplicationService 초기화됨.")

    def set_google_credentials(self, credentials_path):
        """Google Cloud 인증 정보를 환경 변수에 설정합니다."""
        if credentials_path and ocr_os.path.exists(credentials_path):
            ocr_os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            app_logger.info(f"GOOGLE_APPLICATION_CREDENTIALS 환경 변수 설정됨: {credentials_path}")
            return True
        elif not credentials_path:
            app_logger.warning("Google Cloud 인증 정보 경로가 제공되지 않았습니다.")
            return False
        else:
            app_logger.error(f"Google Cloud 인증 파일을 찾을 수 없음: {credentials_path}")
            raise FileOperationError(f"Google Cloud 인증 파일을 찾을 수 없음: {credentials_path}")

    def create_epub_from_source(self, input_source, output_epub_path, title, author,
                                illustration_pages_pdf, illustration_images_ext,
                                is_image_folder_mode, credentials_path=None):
        """
        주어진 소스(PDF 또는 이미지 폴더)로부터 EPUB 파일을 생성합니다.

        Args:
            input_source (str or list): PDF 경로 또는 이미지 파일 경로 리스트.
            output_epub_path (str): 생성될 EPUB 파일 경로.
            title (str): EPUB 제목.
            author (str): EPUB 저자.
            illustration_pages_pdf (list): PDF 내 일러스트 페이지 번호.
            illustration_images_ext (list): 외부/지정 일러스트 이미지 파일 경로.
            is_image_folder_mode (bool): 입력이 이미지 폴더인지 여부.
            credentials_path (str, optional): Google Cloud 인증 파일 경로.
                                              OCR 수행 시 필요.

        Returns:
            bool: 성공 여부.
        """
        app_logger.info(f"EPUB 생성 요청 수신: 입력='{input_source}', 출력='{output_epub_path}', 이미지폴더={is_image_folder_mode}")

        # OCR이 필요한 경우 (PDF 모드 또는 이미지 폴더 모드에서 일러스트가 아닌 이미지)에만 인증 설정
        # EpubProcessor 내부에서 OCR 호출 시점에 인증이 설정되어 있어야 함.
        if not is_image_folder_mode or (is_image_folder_mode and len(input_source) > len(illustration_images_ext)):
            if not self.set_google_credentials(credentials_path):
                # set_google_credentials에서 FileOperationError가 발생할 수 있음
                # 또는 여기서 직접 FileOperationError를 발생시킬 수도 있음
                # 여기서는 set_google_credentials가 False를 반환하면 (경고만 로깅된 경우)
                # 추가적인 오류를 발생시키지 않고 진행하도록 둠 (EpubProcessor에서 OCR 시도 시 오류 발생 가능)
                pass
        try:
            processor = EpubProcessor(
                input_source=input_source,
                output_epub_path=output_epub_path,
                illustration_pages=illustration_pages_pdf,
                illustration_images=illustration_images_ext,
                is_image_folder=is_image_folder_mode
            )
            processor.create_epub(title=title, author=author)
            app_logger.info(f"EPUB 생성 성공: {output_epub_path}")
            return True
        except (ConfigError, OCRError, EpubProcessingError, FileOperationError) as app_exc:
            # 이미 정의된 애플리케이션 예외는 그대로 전달
            app_logger.error(f"애플리케이션 예외 발생: {app_exc.message}", exc_info=True)
            raise
        except Exception as e:
            # 예상치 못한 기타 예외는 ApplicationBaseException으로 감싸서 전달
            app_logger.error(f"EPUB 생성 중 ApplicationService에서 오류 발생: {e}", exc_info=True)
            raise ApplicationBaseException(f"EPUB 생성 중 예상치 못한 오류: {e}")

# 애플리케이션 서비스의 단일 인스턴스 (필요에 따라)
# app_service_instance = ApplicationService()