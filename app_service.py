import os
from logger import app_logger
from epub_processor import EpubProcessor
# ocr_service는 epub_processor 내부에서 사용되므로 직접적인 의존성은 줄어들 수 있음
# 필요한 경우 ocr_service의 특정 기능(예: 환경변수 설정)만 가져올 수 있음
from ocr_service import os as ocr_os
from exceptions import ApplicationBaseException, ConfigError, FileOperationError, OCRError, EpubProcessingError # 사용자 정의 예외 임포트
from searchable_pdf_service import create_searchable_pdf

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

    def create_searchable_pdf_from_source(self, input_pdf_path, output_pdf_path, credentials_path, progress_callback=None, finished_callback=None):
        """
        스캔된 PDF로부터 검색 가능한 PDF를 생성합니다. (GUI 연동을 위한 콜백 포함)
        """
        app_logger.info(f"Searchable PDF 생성 요청: 입력='{input_pdf_path}', 출력='{output_pdf_path}'")
        try:
            if not self.set_google_credentials(credentials_path):
                raise ConfigError("Google Cloud 인증 정보가 설정되지 않았습니다.")

            # searchable_pdf_service의 함수를 직접 호출
            create_searchable_pdf(input_pdf_path, output_pdf_path)
            
            app_logger.info(f"Searchable PDF 생성 성공: {output_pdf_path}")
            if finished_callback:
                finished_callback(True, f"Searchable PDF 생성 완료: {os.path.basename(output_pdf_path)}")
            return True
        except (ConfigError, OCRError, FileOperationError) as app_exc:
            app_logger.error(f"Searchable PDF 생성 중 예외 발생: {app_exc.message}", exc_info=True)
            if finished_callback:
                finished_callback(False, f"오류: {app_exc.message}")
            raise
        except Exception as e:
            app_logger.error(f"Searchable PDF 생성 중 예상치 못한 오류 발생: {e}", exc_info=True)
            if finished_callback:
                finished_callback(False, f"예상치 못한 오류: {e}")
            raise ApplicationBaseException(f"Searchable PDF 생성 중 예상치 못한 오류: {e}")

    def create_document_from_source(self, input_source, output_path, title, author,
                                illustration_pages_pdf, illustration_images_ext,
                                 is_image_folder_mode, credentials_path=None,
                                 output_format="epub"):
        """
        주어진 소스(PDF 또는 이미지 폴더)로부터 EPUB 또는 TXT 파일을 생성합니다.

        Args:
            input_source (str or list): PDF 경로 또는 이미지 파일 경로 리스트.
            output_path (str): 생성될 파일 경로 (.epub 또는 .txt).
            title (str): EPUB 제목.
            author (str): EPUB 저자.
            illustration_pages_pdf (list): PDF 내 일러스트 페이지 번호.
            illustration_images_ext (list): 외부/지정 일러스트 이미지 파일 경로.
            is_image_folder_mode (bool): 입력이 이미지 폴더인지 여부.
            credentials_path (str, optional): Google Cloud 인증 파일 경로.
                                              OCR 수행 시 필요.
            output_format (str): 'epub' 또는 'txt'. Defaults to 'epub'.

        Returns:
            bool: 성공 여부.
        """
        app_logger.info(f"{output_format.upper()} 생성 요청: 입력='{input_source}', 출력='{output_path}', 이미지폴더={is_image_folder_mode}")

        # OCR이 필요한 경우 (일러스트가 아닌 이미지가 있을 경우)에만 인증 설정
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
                # output_path_for_epub은 EpubProcessor.__init__에서 선택 사항이거나
                # epub 전용 기본값으로 설정될 수 있습니다.
                # 포맷이 epub인 경우 output_path를 전달하고, 그렇지 않으면 None을 전달합니다.
                output_path_for_epub=output_path if output_format == "epub" else None,
                illustration_pages=illustration_pages_pdf,
                illustration_images=illustration_images_ext,
                is_image_folder=is_image_folder_mode
            )

            if output_format == "epub":
                processor.create_epub(output_epub_path=output_path, title=title, author=author)
                app_logger.info(f"EPUB 생성 성공: {output_path}")
            elif output_format == "txt":
                processor.create_txt(output_txt_path=output_path, title=title) # 저자 정보는 TXT 내용에 기본적으로 사용되지 않음
                app_logger.info(f"TXT 생성 성공: {output_path}")
            else:
                raise ValueError(f"지원되지 않는 출력 포맷입니다: {output_format}")

            return True
        except (ConfigError, OCRError, EpubProcessingError, FileOperationError) as app_exc:
            # 이미 정의된 애플리케이션 예외는 그대로 전달
            app_logger.error(f"애플리케이션 예외 발생: {app_exc.message}", exc_info=True)
            raise
        except Exception as e:
            # 예상치 못한 기타 예외는 ApplicationBaseException으로 감싸서 전달
            app_logger.error(f"문서 생성 중 ApplicationService에서 오류 발생 ({output_format}): {e}", exc_info=True)
            raise ApplicationBaseException(f"문서 생성 중 예상치 못한 오류 ({output_format}): {e}")

# 애플리케이션 서비스의 단일 인스턴스 (필요에 따라)
# app_service_instance = ApplicationService()