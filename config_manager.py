import json
import os
from logger import app_logger

CONFIG_FILE_NAME = "config.json"
DEFAULT_CONFIG = {
    "default_epub_title": "제목 없음",
    "default_epub_author": "저자 미상",
    "default_epub_language": "jp",
    "max_ocr_workers": 4, # OCR 병렬 처리 시 최대 워커 수
    "temp_dir_base": None, # None이면 시스템 기본 임시 폴더 사용, 경로 지정 가능
    "log_level": "INFO" # 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
}

class ConfigManager:
    def __init__(self, config_file_path=None):
        if config_file_path is None:
            # 실행 파일과 같은 디렉토리에 config.json을 기본으로 사용
            self.config_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE_NAME)
        else:
            self.config_file_path = config_file_path
        
        self.config = self._load_config()
        app_logger.info(f"설정 관리자 초기화됨. 설정 파일: {self.config_file_path}")

    def _load_config(self):
        """설정 파일에서 설정을 로드합니다. 파일이 없으면 기본 설정을 사용하고 파일을 생성합니다."""
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 기본 설정에 없는 키가 파일에 있을 수 있으므로, 기본 설정을 기준으로 업데이트
                    # 기본 설정에 있는 키가 파일에 없으면 기본값 사용
                    final_config = DEFAULT_CONFIG.copy()
                    final_config.update(config)
                    return final_config
            except json.JSONDecodeError:
                app_logger.error(f"설정 파일 ({self.config_file_path}) 파싱 오류. 기본 설정을 사용합니다.")
                self._save_config(DEFAULT_CONFIG) # 오류 발생 시 기본 설정으로 덮어쓰기 또는 백업 후 생성
                return DEFAULT_CONFIG.copy()
            except Exception as e:
                app_logger.error(f"설정 파일 로드 중 알 수 없는 오류 발생: {e}. 기본 설정을 사용합니다.")
                return DEFAULT_CONFIG.copy()
        else:
            app_logger.info(f"설정 파일({self.config_file_path})을 찾을 수 없습니다. 기본 설정으로 새로 생성합니다.")
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

    def _save_config(self, config_data):
        """현재 설정을 파일에 저장합니다."""
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            app_logger.info(f"설정이 파일에 저장됨: {self.config_file_path}")
        except Exception as e:
            app_logger.error(f"설정 파일 저장 중 오류 발생: {e}")

    def get(self, key, default_value=None):
        """지정된 키에 해당하는 설정 값을 반환합니다. 없으면 기본값을 반환합니다."""
        return self.config.get(key, default_value if default_value is not None else DEFAULT_CONFIG.get(key))

# 애플리케이션 전체에서 사용할 단일 ConfigManager 인스턴스
config_manager = ConfigManager()

if __name__ == '__main__':
    # ConfigManager 테스트
    print(f"기본 EPUB 제목: {config_manager.get('default_epub_title')}")
    print(f"최대 OCR 워커 수: {config_manager.get('max_ocr_workers')}")
    print(f"없는 키 테스트 (기본값 None): {config_manager.get('non_existent_key')}")
    print(f"없는 키 테스트 (지정된 기본값): {config_manager.get('non_existent_key_with_default', 'my_default')}")
    
    # 예시: 설정 파일이 없다면 logs 폴더와 같은 위치에 config.json이 생성됨
    # DEFAULT_CONFIG 내용으로 생성되며, 수동으로 수정하여 테스트 가능