import tkinter as tk
from tkinter import filedialog, messagebox
from logger import app_logger # 로거 임포트
import threading
import sys # sys 모듈 임포트


import os

# ocr_service 모듈이 같은 디렉토리에 있다고 가정합니다.
# 그렇지 않은 경우, sys.path를 수정하거나 ocr_service.py의 경로를 정확히 명시해야 합니다.
try:
    # epub_processor 모듈 임포트
    from epub_processor import EpubProcessor
    from ocr_service import os as ocr_os # ocr_service에서 os만 가져오도록 수정
except ImportError as e:
    if "epub_processor" in str(e).lower():
        err_msg = "epub_processor.py를 찾을 수 없습니다. 같은 디렉토리에 있는지 확인하세요."

    app_logger.error(f"{err_msg} - 상세 오류: {e}", exc_info=True)
    print(f"ImportError: {e}") # 콘솔에도 상세 오류 출력
    messagebox.showerror("오류", err_msg)
    exit()

# GUI에서 직접 경로를 설정하므로, 시작 시 경고는 제거하거나 수정할 수 있습니다.
# if not ocr_os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
#     messagebox.showwarning("경고", "GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다. "
#                                   "이 창에서 직접 설정하거나, ocr_service.py 또는 시스템 환경 변수로 설정해주세요.")

class ToolTip:
    """
    Create a tooltip for a given widget.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class OCRApp:
    def __init__(self, root):
        self.root = root
        app_logger.info("OCRApp GUI 초기화 시작.")
        self.root.title("EPUB 생성기 (PDF 기반)")
        self.root.geometry("600x400") # 창 크기 조정

        self.input_path_var = tk.StringVar()
        self.output_epub_path_var = tk.StringVar() # EPUB 출력용
        self.credentials_path_var = tk.StringVar()

        # EPUB 관련 변수
        self.epub_title_var = tk.StringVar(value="제목 없음")
        self.epub_author_var = tk.StringVar(value="저자 미상")
        self.epub_illust_pages_pdf_var = tk.StringVar() # PDF 내 일러스트 페이지
        self.epub_illust_images_external_var = tk.StringVar() # 외부 일러스트 파일

        # 입력 PDF 파일 섹션
        self.input_path_label = tk.Label(root, text="입력 PDF 파일:")
        self.input_path_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.input_path_entry = tk.Entry(root, textvariable=self.input_path_var, width=40)
        self.input_path_entry.grid(row=1, column=1, padx=10, pady=10)
        ToolTip(self.input_path_entry, "처리할 파일 또는 폴더의 경로입니다.")
        self.input_path_button = tk.Button(root, text="PDF 찾기", command=self.select_input_pdf_for_epub)
        self.input_path_button.grid(row=1, column=2, padx=10, pady=10)
        ToolTip(self.input_path_button, "파일 또는 폴더를 선택합니다.")

        # EPUB 출력 파일 섹션
        self.output_path_label = tk.Label(root, text="EPUB 출력 파일:")
        self.output_path_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.output_path_entry = tk.Entry(root, textvariable=self.output_epub_path_var, width=40)
        self.output_path_entry.grid(row=2, column=1, padx=10, pady=10)
        ToolTip(self.output_path_entry, "생성될 EPUB 파일의 전체 경로입니다. (.epub)")
        self.output_path_button = tk.Button(root, text="저장 경로", command=self.select_output_epub_file)
        self.output_path_button.grid(row=2, column=2, padx=10, pady=10)
        ToolTip(self.output_path_button, "EPUB 저장 경로와 파일명을 선택합니다.")

        # 서비스 계정 JSON 파일 섹션
        credentials_label = tk.Label(root, text="서비스 계정 JSON:")
        credentials_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        credentials_entry = tk.Entry(root, textvariable=self.credentials_path_var, width=40)
        credentials_entry.grid(row=3, column=1, padx=10, pady=10)
        ToolTip(credentials_entry, "Google Cloud Vision API 서비스 계정 JSON 파일 경로입니다.")
        credentials_button = tk.Button(root, text="찾아보기", command=self.select_credentials_file)
        credentials_button.grid(row=3, column=2, padx=10, pady=10)
        ToolTip(credentials_button, "서비스 계정 JSON 파일을 선택합니다.")

        # EPUB 생성 옵션 섹션 (동적 표시)
        self.epub_options_frame = tk.Frame(root)
        self.epub_options_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="ew") # 항상 표시

        tk.Label(self.epub_options_frame, text="EPUB 제목:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(self.epub_options_frame, textvariable=self.epub_title_var, width=30).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(self.epub_options_frame.winfo_children()[1], "생성될 EPUB 파일의 제목입니다.")

        tk.Label(self.epub_options_frame, text="EPUB 저자:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(self.epub_options_frame, textvariable=self.epub_author_var, width=30).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(self.epub_options_frame.winfo_children()[3], "생성될 EPUB 파일의 저자입니다.")

        tk.Label(self.epub_options_frame, text="일러스트 페이지 (PDF 내):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        tk.Entry(self.epub_options_frame, textvariable=self.epub_illust_pages_pdf_var, width=30).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ToolTip(self.epub_options_frame.winfo_children()[5], "PDF 내 일러스트 페이지 번호를 쉼표로 구분하여 입력 (예: 1,5,10)")

        tk.Label(self.epub_options_frame, text="외부 일러스트 파일:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.external_illust_entry = tk.Entry(self.epub_options_frame, textvariable=self.epub_illust_images_external_var, width=22)
        self.external_illust_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ToolTip(self.external_illust_entry, "외부 일러스트 이미지 파일 경로를 쉼표로 구분하여 입력하거나 찾아보기 사용")
        tk.Button(self.epub_options_frame, text="파일 추가", command=self.select_external_illust_files).grid(row=3, column=1, padx=5, pady=5, sticky="e")


        # 처리 시작 버튼
        self.process_button = tk.Button(root, text="EPUB 생성 시작", command=self.start_processing_thread)
        self.process_button.grid(row=6, column=0, columnspan=3, pady=20) # row 변경
        ToolTip(self.process_button, "입력된 정보를 바탕으로 EPUB 생성을 시작합니다.")

        # 상태 메시지 레이블
        self.status_label = tk.Label(root, text="")
        self.status_label.grid(row=7, column=0, columnspan=3, pady=10) # row 변경

        app_logger.info("OCRApp GUI 초기화 완료.")


    def select_output_epub_file(self):
        file_selected = filedialog.asksaveasfilename(
            title="EPUB 파일로 저장",
            defaultextension=".epub",
            filetypes=(("EPUB files", "*.epub"), ("All files", "*.*"))
        )
        if file_selected:
            self.output_epub_path_var.set(file_selected)
            app_logger.info(f"EPUB 출력 파일 선택됨: {file_selected}")

    def select_credentials_file(self):
        file_selected = filedialog.askopenfilename(
            title="서비스 계정 JSON 파일 선택",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if file_selected:
            self.credentials_path_var.set(file_selected)
            app_logger.info(f"서비스 계정 파일 선택됨: {file_selected}")

    def select_input_pdf_for_epub(self):
        file_selected = filedialog.askopenfilename(
            title="EPUB으로 만들 PDF 파일 선택",
            filetypes=(("PDF files", "*.pdf"), ("All files", "*.*"))
        )
        if file_selected:
            self.input_path_var.set(file_selected)
            app_logger.info(f"EPUB 생성용 PDF 파일 선택됨: {file_selected}")

    def select_external_illust_files(self):
        files_selected = filedialog.askopenfilenames(
            title="외부 일러스트 이미지 파일 선택",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"), ("All files", "*.*"))
        )
        if files_selected:
            current_paths = self.epub_illust_images_external_var.get()
            new_paths = list(files_selected)
            if current_paths:
                updated_paths = current_paths.split(',') + new_paths
            else:
                updated_paths = new_paths
            self.epub_illust_images_external_var.set(",".join(list(set(updated_paths)))) # 중복 제거
            app_logger.info(f"외부 일러스트 파일 추가됨: {files_selected}")

    def start_processing_thread(self):
        input_path = self.input_path_var.get()
        output_path = self.output_epub_path_var.get()
        credentials_file = self.credentials_path_var.get()

        app_logger.info(f"EPUB 생성 시작 요청. 입력 PDF: {input_path}, 출력 EPUB: {output_path}, 인증파일: {credentials_file}")

        if not input_path:
            err_msg = "입력 PDF 파일을 선택해주세요."
            app_logger.warning(f"입력 경로 누락: {err_msg}")
            messagebox.showerror("오류", err_msg)
            return

        if not output_path:
            err_msg = "EPUB 출력 파일을 선택해주세요."
            app_logger.warning(f"출력 경로 누락: {err_msg}")
            messagebox.showerror("오류", err_msg)
            return

        if not credentials_file:
            err_msg = "서비스 계정 JSON 파일을 선택해주세요."
            app_logger.warning(f"서비스 계정 파일 누락: {err_msg}") # 이 부분은 유지 (인증은 필요)
            messagebox.showerror("오류", err_msg)
            return

        if not ocr_os.path.exists(input_path): # 입력 PDF 파일 존재 여부 확인
            err_msg = f"입력 PDF 파일을 찾을 수 없습니다: {input_path}"
            app_logger.error(err_msg)
            messagebox.showerror("오류", err_msg)
            return

        if not ocr_os.path.exists(credentials_file):
            err_msg = f"서비스 계정 JSON 파일을 찾을 수 없습니다: {credentials_file}"
            app_logger.error(err_msg)
            messagebox.showerror("오류", err_msg)
            return

        ocr_os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_file
        app_logger.info(f"GOOGLE_APPLICATION_CREDENTIALS 환경 변수 설정됨: {credentials_file}")

        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="처리 중...")
        app_logger.info("EPUB 생성 스레드 시작 중...")

        epub_title = self.epub_title_var.get()
        epub_author = self.epub_author_var.get()
        illust_pages_pdf_str = self.epub_illust_pages_pdf_var.get()
        illust_images_ext_str = self.epub_illust_images_external_var.get()

        illust_pages_pdf = []
        if illust_pages_pdf_str:
            try:
                illust_pages_pdf = [int(p.strip()) for p in illust_pages_pdf_str.split(',') if p.strip().isdigit()]
            except ValueError:
                messagebox.showerror("오류", "PDF 내 일러스트 페이지 번호는 숫자로, 쉼표로 구분하여 입력해주세요.")
                self.process_button.config(state=tk.NORMAL)
                self.status_label.config(text="준비")
                return
        
        illust_images_ext = [p.strip() for p in illust_images_ext_str.split(',') if p.strip()] if illust_images_ext_str else []

        thread = threading.Thread(target=self.run_epub_processing,
                                    args=(input_path, output_path, epub_title, epub_author, illust_pages_pdf, illust_images_ext))
        
        thread.daemon = True
        thread.start()

    def run_epub_processing(self, pdf_path, epub_output_path, title, author, illust_pages_pdf, illust_images_ext):
        app_logger.info(f"EPUB 생성 스레드 실행. PDF: {pdf_path}, EPUB: {epub_output_path}")
        try:
            processor = EpubProcessor(
                pdf_path=pdf_path,
                output_epub_path=epub_output_path,
                illustration_pages=illust_pages_pdf,
                illustration_images=illust_images_ext
            )
            processor.create_epub(title=title, author=author)
            self.status_label.config(text="EPUB 파일 생성 완료!")
            messagebox.showinfo("완료", f"EPUB 파일 '{os.path.basename(epub_output_path)}' 생성이 완료되었습니다.")
            app_logger.info(f"EPUB 파일 생성 완료: {epub_output_path}")
        except Exception as e:
            self.status_label.config(text=f"EPUB 생성 오류: {e}")
            messagebox.showerror("EPUB 생성 오류", f"EPUB 생성 중 오류가 발생했습니다: {e}")
            app_logger.error(f"EPUB 생성 중 오류 발생: {e}", exc_info=True)
        finally:
            self.process_button.config(state=tk.NORMAL)
            self.root.after(0, self.update_gui_after_processing)
            app_logger.info("EPUB 생성 스레드 종료.")

    def update_gui_after_processing(self):
        if "완료" in self.status_label.cget("text"):
             self.status_label.config(text="준비 완료. 다른 파일을 처리할 수 있습니다.")
        elif "오류" in self.status_label.cget("text"):
            pass


if __name__ == "__main__":
    app_logger.info("애플리케이션 시작.")
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()
    app_logger.info("애플리케이션 종료.")