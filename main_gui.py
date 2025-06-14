import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QFileDialog, QMessageBox,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from qt_material import apply_stylesheet # qt-material 임포트

# 기존 모듈 임포트 (경로가 올바르다고 가정)
from logger import app_logger
from config_manager import config_manager
from app_service import ApplicationService
from exceptions import ApplicationBaseException, ConfigError, FileOperationError, OCRError, EpubProcessingError

class WorkerSignals(QObject):
    """
    백그라운드 스레드에서 GUI 스레드로 시그널을 보내기 위한 클래스.
    """
    finished = pyqtSignal()
    error = pyqtSignal(str, str) # 오류 제목, 오류 메시지
    success = pyqtSignal(str, str) # 성공 제목, 성공 메시지
    status_update = pyqtSignal(str)

class EpubCreatorAppPyQt(QMainWindow):
    def __init__(self):
        super().__init__()
        app_logger.info("EpubCreatorAppPyQt GUI 초기화 시작.")
        self.app_service = ApplicationService()
        self.init_ui()
        app_logger.info("EpubCreatorAppPyQt GUI 초기화 완료.")

    def init_ui(self):
        self.setWindowTitle("EPUB 생성기 (PDF/이미지 폴더)")
        self.setGeometry(100, 100, 700, 600) # 창 크기 조정

        # 중앙 위젯 및 기본 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 입력 타입 선택
        input_type_layout = QHBoxLayout()
        input_type_label = QLabel("입력 타입:")
        self.rb_pdf = QRadioButton("PDF 파일")
        self.rb_pdf.setChecked(True)
        self.rb_image_folder = QRadioButton("이미지 폴더")
        self.rb_pdf.toggled.connect(self.update_input_widgets_pyqt)
        self.rb_image_folder.toggled.connect(self.update_input_widgets_pyqt)
        input_type_layout.addWidget(input_type_label)
        input_type_layout.addWidget(self.rb_pdf)
        input_type_layout.addWidget(self.rb_image_folder)
        input_type_layout.addStretch()
        main_layout.addLayout(input_type_layout)

        # 입력 경로
        self.input_path_label = QLabel("입력 PDF 파일:")
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setToolTip("EPUB으로 변환할 PDF 파일 또는 이미지 폴더의 경로입니다.")
        self.input_path_edit.setPlaceholderText("EPUB으로 변환할 PDF 파일 또는 이미지 폴더 경로")
        self.input_path_button = QPushButton("PDF 찾기")
        self.input_path_button.clicked.connect(self.select_input_source_pyqt)
        self.input_path_button.setToolTip("입력 소스를 선택합니다.")
        input_path_layout = self.create_path_selection_layout(self.input_path_label, self.input_path_edit, self.input_path_button)
        main_layout.addLayout(input_path_layout)

        # EPUB 출력 파일
        output_path_label = QLabel("EPUB 출력 파일:")
        self.output_epub_path_edit = QLineEdit()
        self.output_epub_path_edit.setToolTip("생성될 EPUB 파일의 전체 경로입니다. (.epub)")
        self.output_epub_path_edit.setPlaceholderText("생성될 EPUB 파일의 전체 경로 (.epub)")
        output_path_button = QPushButton("저장 경로")
        output_path_button.clicked.connect(self.select_output_epub_file_pyqt)
        output_path_button.setToolTip("EPUB 저장 경로와 파일명을 선택합니다.")
        output_path_layout = self.create_path_selection_layout(output_path_label, self.output_epub_path_edit, output_path_button)
        main_layout.addLayout(output_path_layout)

        # 서비스 계정 JSON
        credentials_label = QLabel("서비스 계정 JSON:")
        self.credentials_edit = QLineEdit()
        self.credentials_edit.setPlaceholderText("Google Cloud Vision API 서비스 계정 JSON 파일 경로")
        self.credentials_edit.setToolTip("Google Cloud Vision API 서비스 계정 JSON 파일 경로입니다.")
        credentials_button = QPushButton("찾아보기")
        credentials_button.clicked.connect(self.select_credentials_file_pyqt)
        credentials_button.setToolTip("서비스 계정 JSON 파일을 선택합니다.")
        credentials_layout = self.create_path_selection_layout(credentials_label, self.credentials_edit, credentials_button)
        main_layout.addLayout(credentials_layout)

        # EPUB 옵션 프레임
        epub_options_frame = QFrame()
        epub_options_frame.setObjectName("epubOptionsFrame") # QSS 적용을 위해
        # epub_options_frame.setFrameShape(QFrame.Shape.StyledPanel) # 테마에 따라 불필요할 수 있음
        epub_options_layout = QGridLayout(epub_options_frame)
        
        self.epub_title_edit = QLineEdit(config_manager.get("default_epub_title"))
        self.epub_title_edit.setToolTip("생성될 EPUB 파일의 제목입니다.")
        self.epub_author_edit = QLineEdit(config_manager.get("default_epub_author"))
        self.epub_author_edit.setToolTip("생성될 EPUB 파일의 저자입니다.")
        self.epub_illust_pages_pdf_edit = QLineEdit()
        self.epub_illust_pages_pdf_edit.setPlaceholderText("예: 1,5,10")
        # 툴팁은 update_input_widgets_pyqt에서 동적으로 설정됩니다.
        self.epub_illust_images_external_edit = QLineEdit()
        # 툴팁은 update_input_widgets_pyqt에서 동적으로 설정됩니다.
        add_external_illust_button = QPushButton("파일 추가")
        add_external_illust_button.clicked.connect(self.select_external_illust_files_pyqt)
        add_external_illust_button.setToolTip("목록에 외부 일러스트 이미지 파일을 추가합니다.")

        epub_options_layout.addWidget(QLabel("EPUB 제목:"), 0, 0)
        epub_options_layout.addWidget(self.epub_title_edit, 0, 1)
        epub_options_layout.addWidget(QLabel("EPUB 저자:"), 1, 0)
        epub_options_layout.addWidget(self.epub_author_edit, 1, 1)
        
        self.pdf_illust_label = QLabel("일러스트 페이지 (PDF 내):")
        epub_options_layout.addWidget(self.pdf_illust_label, 2, 0)
        epub_options_layout.addWidget(self.epub_illust_pages_pdf_edit, 2, 1)

        self.external_illust_label = QLabel("외부 일러스트 파일:")
        epub_options_layout.addWidget(self.external_illust_label, 3, 0)
        external_illust_layout = QHBoxLayout()
        external_illust_layout.addWidget(self.epub_illust_images_external_edit)
        external_illust_layout.addWidget(add_external_illust_button)
        epub_options_layout.addLayout(external_illust_layout, 3, 1)
        
        main_layout.addWidget(epub_options_frame)

        # 처리 시작 버튼
        self.process_button = QPushButton("EPUB 생성 시작")
        self.process_button.setObjectName("primaryButton") # QSS 적용용
        self.process_button.setFixedHeight(40)
        self.process_button.setToolTip("입력된 정보를 바탕으로 EPUB 생성을 시작합니다.")
        self.process_button.clicked.connect(self.start_processing_thread_pyqt)
        main_layout.addWidget(self.process_button)

        # 상태 메시지 레이블
        self.status_label = QLabel("준비")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        main_layout.addStretch() # 하단 여백

        self.update_input_widgets_pyqt() # 초기 UI 상태 설정

    def create_path_selection_layout(self, label_widget, line_edit_widget, button_widget):
        layout = QHBoxLayout()
        label_widget.setFixedWidth(150) # 레이블 너비 고정
        layout.addWidget(label_widget)
        layout.addWidget(line_edit_widget)
        layout.addWidget(button_widget)
        return layout

    def update_input_widgets_pyqt(self):
        if self.rb_pdf.isChecked():
            self.input_path_label.setText("입력 PDF 파일:")
            self.input_path_button.setText("PDF 찾기")
            self.pdf_illust_label.show()
            self.epub_illust_pages_pdf_edit.show()
            self.external_illust_label.setText("외부 일러스트 파일:")
            self.epub_illust_pages_pdf_edit.setToolTip("PDF 내 일러스트 페이지 번호를 쉼표로 구분하여 입력 (예: 1,5,10)")
            self.epub_illust_images_external_edit.setToolTip("외부 일러스트 이미지 파일 경로 (본문 처리 후 추가됨). 쉼표로 구분하거나 찾아보기 사용.")
        else: # 이미지 폴더 선택
            self.input_path_label.setText("입력 이미지 폴더:")
            self.input_path_button.setText("폴더 찾기")
            self.pdf_illust_label.hide()
            self.epub_illust_pages_pdf_edit.hide()
            self.epub_illust_pages_pdf_edit.clear()
            self.external_illust_label.setText("일러스트 지정(폴더내):")
            self.epub_illust_images_external_edit.setToolTip("폴더 내 특정 이미지 파일을 일러스트로 지정 (OCR 제외). 쉼표로 구분하거나 찾아보기 사용.")
        self.input_path_edit.clear()

    def select_input_source_pyqt(self):
        if self.rb_pdf.isChecked():
            self.select_input_pdf_for_epub_pyqt()
        else:
            self.select_input_image_folder_pyqt()

    def select_input_pdf_for_epub_pyqt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "EPUB으로 만들 PDF 파일 선택", "", "PDF Files (*.pdf);;All Files (*)")
        if file_path:
            self.input_path_edit.setText(file_path)
            app_logger.info(f"EPUB 생성용 PDF 파일 선택됨: {file_path}")
            # EPUB 출력 경로 기본값 설정
            dir_name = os.path.dirname(file_path)
            base_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
            default_output_name = f"{base_name_without_ext}_ocr.epub"
            default_output_path = os.path.join(dir_name, default_output_name)
            self.output_epub_path_edit.setText(default_output_path)
            app_logger.info(f"EPUB 출력 경로 기본값 설정됨: {default_output_path}")

    def select_input_image_folder_pyqt(self):
        folder_path = QFileDialog.getExistingDirectory(self, "이미지 파일들이 있는 폴더 선택")
        if folder_path:
            self.input_path_edit.setText(folder_path)
            app_logger.info(f"입력 이미지 폴더 선택됨: {folder_path}")
            # EPUB 출력 경로 기본값 설정 (폴더의 부모 디렉토리에 폴더명_ocr.epub)
            parent_dir = os.path.dirname(folder_path)
            folder_name = os.path.basename(folder_path)
            default_output_name = f"{folder_name}_ocr.epub"
            default_output_path = os.path.normpath(os.path.join(parent_dir, default_output_name)) # 폴더와 같은 레벨에 생성하고 정규화
            self.output_epub_path_edit.setText(default_output_path)
            app_logger.info(f"EPUB 출력 경로 기본값 설정됨 (폴더 모드): {default_output_path}")

    def select_output_epub_file_pyqt(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "EPUB 파일로 저장", "", "EPUB Files (*.epub);;All Files (*)")
        if file_path:
            self.output_epub_path_edit.setText(file_path)
            app_logger.info(f"EPUB 출력 파일 선택됨: {file_path}")

    def select_credentials_file_pyqt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "서비스 계정 JSON 파일 선택", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            self.credentials_edit.setText(file_path)
            app_logger.info(f"서비스 계정 파일 선택됨: {file_path}")

    def select_external_illust_files_pyqt(self):
        files, _ = QFileDialog.getOpenFileNames(self, "외부 일러스트 이미지 파일 선택", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;All Files (*)")
        if files:
            current_paths = self.epub_illust_images_external_edit.text()
            existing_paths = [p.strip() for p in current_paths.split(',') if p.strip()] if current_paths else []
            new_paths = list(set(existing_paths + files)) # 중복 제거
            self.epub_illust_images_external_edit.setText(",".join(new_paths))
            app_logger.info(f"외부 일러스트 파일 추가됨: {files}")

    def start_processing_thread_pyqt(self):
        input_path = self.input_path_edit.text()
        output_path = self.output_epub_path_edit.text()
        credentials_file = self.credentials_edit.text()
        is_image_folder_mode = self.rb_image_folder.isChecked()

        # 유효성 검사 (tkinter 버전과 유사하게)
        if not input_path:
            QMessageBox.warning(self, "입력 오류", "입력 PDF 파일 또는 이미지 폴더를 선택해주세요.")
            return
        # ... (다른 유효성 검사 추가) ...

        self.process_button.setEnabled(False)
        self.status_label.setText("처리 중...")
        app_logger.info("EPUB 생성 스레드 시작 중...")

        # 스레드에서 실행될 작업 준비
        self.worker_signals = WorkerSignals()
        self.worker_signals.finished.connect(self.on_processing_finished)
        self.worker_signals.error.connect(self.on_processing_error)
        self.worker_signals.success.connect(self.on_processing_success)
        self.worker_signals.status_update.connect(self.status_label.setText)

        # 스레드 생성 및 시작
        # (기존 start_processing_thread의 로직을 별도 함수로 분리하여 스레드에서 실행)
        thread = threading.Thread(target=self.run_epub_creation_task, 
                                  args=(input_path, output_path, credentials_file, is_image_folder_mode, self.worker_signals))
        thread.daemon = True
        thread.start()

    def run_epub_creation_task(self, input_path, output_path, credentials_file, is_image_folder_mode, signals):
        try:
            epub_title = self.epub_title_edit.text()
            epub_author = self.epub_author_edit.text()
            illust_pages_pdf_str = self.epub_illust_pages_pdf_edit.text()
            illust_images_ext_str = self.epub_illust_images_external_edit.text()

            illust_pages_pdf = []
            if not is_image_folder_mode and illust_pages_pdf_str:
                try:
                    illust_pages_pdf = [int(p.strip()) for p in illust_pages_pdf_str.split(',') if p.strip().isdigit()]
                except ValueError:
                    signals.error.emit("입력 오류", "PDF 내 일러스트 페이지 번호는 숫자로, 쉼표로 구분하여 입력해주세요.")
                    return
            
            illust_images_ext = [p.strip() for p in illust_images_ext_str.split(',') if p.strip()] if illust_images_ext_str else []

            final_input_source = input_path
            if is_image_folder_mode:
                supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')
                try:
                    image_files = sorted([os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith(supported_extensions)])
                    if not image_files:
                        signals.error.emit("입력 오류", "선택한 폴더에 지원되는 이미지 파일이 없습니다.")
                        return
                    final_input_source = image_files
                except Exception as e_dir:
                    signals.error.emit("폴더 읽기 오류", f"이미지 폴더를 읽는 중 오류 발생: {e_dir}")
                    return
            
            success = self.app_service.create_epub_from_source(
                input_source=final_input_source,
                output_epub_path=output_path,
                title=epub_title, author=epub_author,
                illustration_pages_pdf=illust_pages_pdf,
                illustration_images_ext=illust_images_ext,
                is_image_folder_mode=is_image_folder_mode,
                credentials_path=credentials_file
            )
            if success:
                signals.success.emit("완료", f"EPUB 파일 '{os.path.basename(output_path)}' 생성이 완료되었습니다.")
        except (ConfigError, FileOperationError, OCRError, EpubProcessingError) as app_exc:
            signals.error.emit("처리 오류", app_exc.message)
        except ApplicationBaseException as base_exc:
            signals.error.emit("애플리케이션 오류", base_exc.message)
        except Exception as e:
            signals.error.emit("알 수 없는 오류", f"EPUB 생성 중 알 수 없는 오류가 발생했습니다: {e}")
        finally:
            signals.finished.emit()

    def on_processing_finished(self):
        self.process_button.setEnabled(True)
        # self.status_label.setText("준비 완료. 다른 파일을 처리할 수 있습니다.") # success/error 시그널에서 처리
        app_logger.info("EPUB 생성 스레드 종료.")

    def on_processing_error(self, title, message):
        self.status_label.setText(f"오류: {message}")
        QMessageBox.critical(self, title, message)
        app_logger.error(f"{title}: {message}")

    def on_processing_success(self, title, message):
        self.status_label.setText("EPUB 파일 생성 완료!")
        QMessageBox.information(self, title, message)
        app_logger.info(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Material Design 테마 적용 (예: dark_teal)
    # extra = {'density_scale': '0'} # 밀도 스케일 조정 (선택 사항)
    apply_stylesheet(app, theme='dark_teal.xml') #, extra=extra)
    
    window = EpubCreatorAppPyQt()
    window.show()
    sys.exit(app.exec())