# EPUB 생성기 (PDF 및 이미지 폴더 지원)

## 개요

이 프로젝트는 PDF 파일 또는 이미지 파일들이 들어있는 폴더로부터 텍스트를 추출(OCR)하고, 사용자가 지정한 일러스트와 조합하여 EPUB 파일을 생성하는 GUI 애플리케이션입니다. Google Cloud Vision API를 사용하여 OCR 기능을 수행하며, `ebooklib` 라이브러리를 통해 EPUB 파일을 생성합니다.

## 주요 기능

- **입력 소스 다양성**:
    - PDF 파일 입력 지원
    - 이미지 파일들이 포함된 폴더 입력 지원
- **OCR 기능**:
    - Google Cloud Vision API를 사용한 고품질 텍스트 추출
    - 이미지 전처리(그레이스케일 변환)를 통한 OCR 정확도 향상 (선택 사항)
    - 병렬 처리를 통한 OCR 속도 향상
- **일러스트 처리**:
    - PDF 입력 시: 특정 페이지 번호를 일러스트로 지정 가능
    - 이미지 폴더 입력 시: 폴더 내 특정 이미지 파일을 일러스트로 지정 가능
    - 외부 이미지 파일을 일러스트로 추가 가능
- **EPUB 생성**:
    - 추출된 텍스트와 지정된 일러스트를 조합하여 EPUB 파일 생성
    - EPUB 제목, 저자, 언어 설정 가능
- **사용자 친화적 GUI**:
    - `tkinter`를 사용한 그래픽 사용자 인터페이스 제공
    - 파일/폴더 선택, 옵션 설정, 처리 시작 등의 기능을 GUI를 통해 쉽게 사용 가능
    - 마우스 오버 툴팁 제공
- **설정 관리**:
    - `config.json` 파일을 통해 기본 EPUB 제목, 저자, 언어, OCR 워커 수 등의 설정을 외부에서 관리
- **로깅**:
    - `logs/app.log` 파일에 애플리케이션 실행 및 오류 로그 기록
- **사용자 정의 예외 처리**:
    - 각 모듈별 특화된 예외 클래스를 정의하여 오류 상황을 명확히 구분하고 처리

## 시스템 요구사항

- Python 3.7 이상
- **필수 Python 패키지**:
    - `google-cloud-vision`
    - `pdf2image`
    - `Pillow`
    - `numpy`
    - `opencv-python`
    - `ebooklib`
    - (기타 `concurrent.futures` 등 표준 라이브러리)
- **Poppler (Windows 사용자)**: `pdf2image`가 PDF 처리를 위해 필요합니다. Poppler 공식 사이트에서 다운로드 후 `bin` 폴더를 시스템 `Path` 환경 변수에 추가해야 합니다.

## 설치 및 설정

1.  **저장소 복제 (Clone Repository)**:
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **가상 환경 생성 및 활성화 (권장)**:
    ```bash
    python -m venv .venv
    # Windows PowerShell
    .\.venv\Scripts\Activate.ps1
    # Windows Command Prompt
    .\.venv\Scripts\activate.bat
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **의존성 패키지 설치**:
    ```bash
    pip install google-cloud-vision pdf2image Pillow numpy opencv-python ebooklib
    ```

4.  **Google Cloud Vision API 설정**:
    - Google Cloud Platform (GCP) 프로젝트를 생성하고 Vision API를 활성화합니다.
    - 서비스 계정을 생성하고 "Cloud Vision API 사용자" 역할을 부여합니다.
    - 서비스 계정의 JSON 키 파일을 다운로드합니다.
    - **중요**: 다운로드한 JSON 키 파일의 경로를 프로그램 실행 시 GUI를 통해 지정해야 합니다. (또는 `ocr_service.py`에서 환경 변수를 직접 설정할 수도 있었으나, 현재는 GUI를 통해 입력받습니다.)

5.  **설정 파일 (`config.json`)**:
    - 프로그램 첫 실행 시, `config_manager.py`와 동일한 디렉토리에 `config.json` 파일이 기본값으로 자동 생성됩니다.
    - 필요에 따라 이 파일을 수정하여 기본 EPUB 제목, 저자, 언어, OCR 워커 수 등을 변경할 수 있습니다.

## 실행 방법

1.  필요한 모든 설정이 완료되었는지 확인합니다.
2.  프로젝트 루트 디렉토리에서 다음 명령어를 실행합니다:
    ```bash
    python main_gui.py
    ```

## GUI 사용법

1.  **입력 타입 선택**: "PDF 파일" 또는 "이미지 폴더" 중 하나를 선택합니다.
2.  **입력 경로 지정**: 선택한 타입에 따라 PDF 파일 또는 이미지 폴더를 지정합니다.
3.  **EPUB 출력 파일 지정**: 생성될 EPUB 파일의 저장 경로와 파일명을 지정합니다.
4.  **서비스 계정 JSON 파일 지정**: Google Cloud Vision API 서비스 계정의 JSON 키 파일을 선택합니다. (PDF 또는 이미지 폴더 내 OCR 수행 시 필요)
5.  **EPUB 옵션 설정**:
    - EPUB 제목 및 저자를 입력합니다.
    - **PDF 모드 시**: PDF 내 일러스트로 처리할 페이지 번호를 쉼표로 구분하여 입력합니다 (예: `1,5,10`).
    - **이미지 폴더 모드 시**: "일러스트 페이지 (PDF 내)" 필드는 비활성화됩니다. 대신 "일러스트 지정(폴더내)" 필드(기존 "외부 일러스트 파일" 필드)를 사용하여 폴더 내 특정 이미지 파일을 일러스트로 지정할 수 있습니다. 이 필드에 지정되지 않은 이미지들은 OCR 대상이 됩니다.
    - **공통**: "외부 일러스트 파일" (또는 "일러스트 지정(폴더내)") 필드를 통해 폴더 외부의 이미지 파일을 일러스트로 추가하거나, 폴더 내 이미지를 일러스트로 명시적으로 지정할 수 있습니다. "파일 추가" 버튼으로 여러 파일을 선택할 수 있습니다.
6.  **EPUB 생성 시작**: 모든 설정을 완료한 후 "EPUB 생성 시작" 버튼을 클릭합니다.
7.  **상태 확인**: 처리 과정 및 결과는 창 하단의 상태 메시지를 통해 확인할 수 있습니다. 오류 발생 시 해당 내용이 표시됩니다.

## 로그

- 애플리케이션 실행 중 발생하는 주요 이벤트 및 오류는 프로젝트 루트 디렉토리의 `logs/app.log` 파일에 기록됩니다.

## 아키텍처

애플리케이션은 다음과 같은 주요 모듈로 구성되어 계층화된 아키텍처를 따릅니다:

- **`main_gui.py`**: 프레젠테이션 계층 (사용자 인터페이스)
- **`app_service.py`**: 애플리케이션 서비스 계층 (GUI와 핵심 로직 간의 중재)
- **`epub_processor.py`**: 도메인/서비스 계층 (EPUB 생성 핵심 로직)
- **`ocr_service.py`**: 유틸리티/인프라 계층 (OCR 및 관련 이미지 처리)
- **`config_manager.py`**: 공통 서비스 (설정 관리)
- **`logger.py`**: 공통 서비스 (로깅)
- **`dtos.py`**: 데이터 전송 객체 (계층 간 데이터 전달 구조 정의)
- **`exceptions.py`**: 사용자 정의 예외 (오류 처리 일관성)

## 기여

버그 수정, 기능 개선 등에 대한 기여를 환영합니다. 이슈를 생성하거나 풀 리퀘스트를 보내주세요.

## 라이선스

이 프로젝트는 [라이선스 이름] 라이선스 하에 배포됩니다. (라이선스를 명시해주세요)