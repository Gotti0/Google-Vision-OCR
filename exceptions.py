"""
애플리케이션에서 사용될 사용자 정의 예외 클래스들을 정의합니다.
"""

class ApplicationBaseException(Exception):
    """애플리케이션의 모든 사용자 정의 예외에 대한 기본 클래스입니다."""
    def __init__(self, message="애플리케이션 오류가 발생했습니다."):
        self.message = message
        super().__init__(self.message)

class ConfigError(ApplicationBaseException):
    """설정 관련 오류 발생 시 사용됩니다."""
    def __init__(self, message="설정 파일 처리 중 오류가 발생했습니다."):
        super().__init__(message)

class OCRError(ApplicationBaseException):
    """OCR 처리 중 오류 발생 시 사용됩니다."""
    def __init__(self, message="OCR 처리 중 오류가 발생했습니다."):
        super().__init__(message)

class EpubProcessingError(ApplicationBaseException):
    """EPUB 생성 처리 중 오류 발생 시 사용됩니다."""
    def __init__(self, message="EPUB 생성 중 오류가 발생했습니다."):
        super().__init__(message)

class FileOperationError(ApplicationBaseException):
    """파일 입출력 또는 경로 관련 오류 발생 시 사용됩니다."""
    def __init__(self, message="파일 또는 디렉토리 작업 중 오류가 발생했습니다."):
        super().__init__(message)