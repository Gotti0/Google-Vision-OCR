import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os

# ocr_service 모듈이 같은 디렉토리에 있다고 가정합니다.
# 그렇지 않은 경우, sys.path를 수정하거나 ocr_service.py의 경로를 정확히 명시해야 합니다.
try:
    from ocr_service import process_all_pdfs, process_pdf, process_single_image_file, os as ocr_os
except ImportError:
    messagebox.showerror("오류", "ocr_service.py를 찾을 수 없습니다. 같은 디렉토리에 있는지 확인하세요.")
    exit()

# GUI에서 직접 경로를 설정하므로, 시작 시 경고는 제거하거나 수정할 수 있습니다.
# if not ocr_os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
#     messagebox.showwarning("경고", "GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다. "
#                                   "이 창에서 직접 설정하거나, ocr_service.py 또는 시스템 환경 변수로 설정해주세요.")

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF OCR 처리기")
        self.root.geometry("550x380") # 창 크기 조정

        self.input_mode = tk.StringVar(value="folder")
        self.input_path_var = tk.StringVar()
        self.output_folder_path = tk.StringVar()
        self.credentials_path_var = tk.StringVar()

        # 입력 모드 선택 섹션
        tk.Label(root, text="입력 방식:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        tk.Radiobutton(root, text="폴더 일괄 처리", variable=self.input_mode, value="folder", command=self.update_input_widgets).grid(row=0, column=1, sticky="w", padx=5)
        tk.Radiobutton(root, text="단일 파일 처리", variable=self.input_mode, value="file", command=self.update_input_widgets).grid(row=0, column=1, sticky="e", padx=5)

        # 입력 경로 섹션 (동적 변경)
        self.input_path_label = tk.Label(root, text="입력 폴더:")
        self.input_path_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.input_path_entry = tk.Entry(root, textvariable=self.input_path_var, width=40)
        self.input_path_entry.grid(row=1, column=1, padx=10, pady=10)
        self.input_path_button = tk.Button(root, text="폴더 찾기")
        self.input_path_button.grid(row=1, column=2, padx=10, pady=10)

        # 출력 폴더 섹션
        tk.Label(root, text="텍스트 출력 폴더:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        tk.Entry(root, textvariable=self.output_folder_path, width=40).grid(row=2, column=1, padx=10, pady=10)
        tk.Button(root, text="찾아보기", command=self.select_output_folder).grid(row=2, column=2, padx=10, pady=10)

        # 서비스 계정 JSON 파일 섹션
        tk.Label(root, text="서비스 계정 JSON:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        tk.Entry(root, textvariable=self.credentials_path_var, width=40).grid(row=3, column=1, padx=10, pady=10)
        tk.Button(root, text="찾아보기", command=self.select_credentials_file).grid(row=3, column=2, padx=10, pady=10)

        # 처리 시작 버튼
        self.process_button = tk.Button(root, text="OCR 처리 시작", command=self.start_processing_thread)
        self.process_button.grid(row=4, column=0, columnspan=3, pady=20)

        # 상태 메시지 레이블
        self.status_label = tk.Label(root, text="")
        self.status_label.grid(row=5, column=0, columnspan=3, pady=10)

        self.update_input_widgets() # 초기 위젯 상태 설정

    def update_input_widgets(self):
        mode = self.input_mode.get()
        if mode == "folder":
            self.input_path_label.config(text="입력 폴더:")
            self.input_path_button.config(text="폴더 찾기", command=self.select_input_folder)
        elif mode == "file":
            self.input_path_label.config(text="입력 파일:")
            self.input_path_button.config(text="파일 찾기", command=self.select_input_file)
        self.input_path_var.set("") # 모드 변경 시 입력 경로 초기화

    def select_input_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_path_var.set(folder_selected)

    def select_output_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_folder_path.set(folder_selected)

    def select_credentials_file(self):
        file_selected = filedialog.askopenfilename(
            title="서비스 계정 JSON 파일 선택",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if file_selected:
            self.credentials_path_var.set(file_selected)

    def select_input_file(self):
        file_selected = filedialog.askopenfilename(
            title="입력 파일 선택",
            filetypes=(
                ("지원되는 파일", "*.pdf *.png *.jpg *.jpeg *.bmp *.tiff *.gif"),
                ("PDF files", "*.pdf"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"),
                ("All files", "*.*")
            )
        )
        if file_selected:
            self.input_path_var.set(file_selected)

    def start_processing_thread(self):
        input_path = self.input_path_var.get()
        output_folder = self.output_folder_path.get()
        credentials_file = self.credentials_path_var.get()
        mode = self.input_mode.get()

        if not input_path:
            if mode == "folder":
                messagebox.showerror("오류", "입력 폴더를 선택해주세요.")
            else: # mode == "file"
                messagebox.showerror("오류", "입력 파일을 선택해주세요.")
            return

        if not output_folder:
            messagebox.showerror("오류", "출력 폴더를 선택해주세요.")
            return

        if not credentials_file:
            messagebox.showerror("오류", "서비스 계정 JSON 파일을 선택해주세요.")
            return

        if not ocr_os.path.exists(input_path):
            if mode == "folder":
                messagebox.showerror("오류", f"입력 폴더를 찾을 수 없습니다: {input_path}")
            else: # mode == "file"
                messagebox.showerror("오류", f"입력 파일을 찾을 수 없습니다: {input_path}")
            return

        if not ocr_os.path.exists(credentials_file):
            messagebox.showerror("오류", f"서비스 계정 JSON 파일을 찾을 수 없습니다: {credentials_file}")
            return

        ocr_os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_file

        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="처리 중...")

        thread = threading.Thread(target=self.run_ocr_processing, args=(mode, input_path, output_folder))
        thread.daemon = True
        thread.start()

    def run_ocr_processing(self, mode, input_path, output_folder):
        try:
            if mode == "folder":
                process_all_pdfs(input_path, output_folder)
                self.status_label.config(text="폴더 내 모든 PDF 처리 완료!")
                messagebox.showinfo("완료", f"폴더 '{input_path}' 내의 모든 PDF 파일 처리가 완료되었습니다.\n결과는 '{output_folder}' 폴더에 저장되었습니다.")
            elif mode == "file":
                file_extension = ocr_os.path.splitext(input_path)[1].lower()
                if file_extension == ".pdf":
                    process_pdf(input_path, output_folder)
                    self.status_label.config(text="PDF 파일 처리 완료!")
                    messagebox.showinfo("완료", f"PDF 파일 '{ocr_os.path.basename(input_path)}' 처리가 완료되었습니다.\n결과는 '{output_folder}' 폴더에 저장되었습니다.")
                elif file_extension in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"]:
                    process_single_image_file(input_path, output_folder)
                    self.status_label.config(text="이미지 파일 처리 완료!")
                    messagebox.showinfo("완료", f"이미지 파일 '{ocr_os.path.basename(input_path)}' 처리가 완료되었습니다.\n결과는 '{output_folder}' 폴더에 저장되었습니다.")
                else:
                    self.status_label.config(text="지원하지 않는 파일 형식")
                    messagebox.showerror("오류", f"지원하지 않는 파일 형식입니다: {file_extension}\nPDF 또는 이미지 파일을 선택해주세요.")
        except Exception as e:
            self.status_label.config(text=f"오류 발생: {e}")
            messagebox.showerror("처리 오류", f"OCR 처리 중 오류가 발생했습니다: {e}")
        finally:
            self.process_button.config(state=tk.NORMAL)
            self.root.after(0, self.update_gui_after_processing)

    def update_gui_after_processing(self):
        if "완료" in self.status_label.cget("text"):
             self.status_label.config(text="준비 완료. 다른 파일을 처리할 수 있습니다.")
        elif "오류" in self.status_label.cget("text"):
            pass


if __name__ == "__main__":

    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()