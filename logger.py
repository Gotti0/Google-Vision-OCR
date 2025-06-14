import logging
import os
from logging.handlers import RotatingFileHandler

# 로그 파일이 저장될 디렉토리 (예: 현재 작업 디렉토리 아래 'logs' 폴더)
LOG_DIR = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'app.log')

def setup_logger(name='ocr_app_logger', log_file=LOG_FILE, level=logging.INFO):
    """
    애플리케이션 로거를 설정합니다.

    Args:
        name (str): 로거의 이름.
        log_file (str): 로그 메시지를 저장할 파일 경로.
        level (int): 로깅 레벨 (예: logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: 설정된 로거 객체.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 이미 핸들러가 설정되어 있다면 중복 추가 방지
    if logger.hasHandlers():
        return logger

    # 콘솔 핸들러 설정 (선택 사항)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 설정 (RotatingFileHandler 사용)
    # 파일 크기가 5MB에 도달하면 새 파일 생성, 최대 5개 백업 파일 유지
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(level)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

# 기본 로거 인스턴스 (애플리케이션 전체에서 사용 가능)
app_logger = setup_logger()

if __name__ == '__main__':
    # 로거 테스트
    app_logger.info("로거 모듈 테스트 시작.")
    app_logger.debug("디버그 메시지 테스트.")
    app_logger.error("오류 메시지 테스트.")
    app_logger.info("로거 모듈 테스트 완료. 'logs/app.log' 파일을 확인하세요.")