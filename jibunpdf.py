import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pypdf
import fitz  # PyMuPDF
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

ctk.set_appearance_mode("System")


class PDFEditorApp(ctk.CTk, TkinterDnD.DnDWrapper):

    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("PDFEditorApp - phase3.5 (Thumbnails & Zoom)")
        self.geometry("750x600")
        self.minsize(650, 450)

        self.pages_list = []
        self.setup_ui()

        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop_pdf)

    def setup_ui(self):
        """画面レイアウトの構築"""
        self.top_frame = ctk.CTkFrame(self, height=60)
        self.top_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.open_button = ctk.CTkButton(
            self.top_frame, text="open pdf", command=self.open_pdf
        )
        self.open_button.pack(side="left", padx=10, pady=10)

        self.file_label = ctk.CTkLabel(
            self.top_frame,
            text="ファイルを選択するか、下にドロップしてください",
            text_color="gray",
        )
        self.file_label.pack(side="left", padx=10, pady=10)

        self.list_frame = ctk.CTkScrollableFrame(
            self, label_text="Contents List (Drop PDF here)"
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.list_frame.drop_target_register(DND_FILES)
        self.list_frame.dnd_bind("<<Drop>>", self.drop_pdf)

        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.pack(fill="x", padx=20, pady=(10, 20))

        self.save_button = ctk.CTkButton(
            self.bottom_frame,
            text="save as looks",
            command=self.save_pdf,
            state="disabled",
        )
        self.save_button.pack(side="right", padx=10, pady=10)

    def open_pdf(self):
        """ボタンからPDFを開く"""
        file_path = filedialog.askopenfilename(
            title="choose file", filetypes=[("pdfs", "*.pdf")]
        )
        if not file_path:
            return
        self.pages_list = []
        self.add_pdf_to_list(file_path)

    def drop_pdf(self, event):
        """ファイルがドロップされたときの処理"""
        file_path = event.data.strip()
        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]

        file_paths = file_path.split(" ") if " " in file_path else [file_path]

        valid_files_added = False
        for path in file_paths:
            path = path.strip()
            if path.lower().endswith(".pdf"):
                self.add_pdf_to_list(path)
                valid_files_added = True

        if not valid_files_added:
            messagebox.showwarning(
                "警告", "有効なPDFファイルが検出されませんでした。"
            )

    def get_page_thumbnail(self, file_path, page_num, zoom_factor=1.0):
        """PyMuPDFを使用して指定ページのPIL Imageオブジェクトを返す"""
        doc = fitz.open(file_path)
        page = doc.load_page(page_num)
        
        # zoom_factorに応じてレンダリング解像度を変更
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pix = page.get_pixmap(matrix=mat)
        
        # fitzのpixmapからPIL Imageに変換
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return img

    def add_pdf_to_list(self, file_path):
        """データ構造に ImageTk オブジェクトをキャッシュするように拡張"""
        try:
            reader = pypdf.PdfReader(file_path)
            file_name = os.path.basename(file_path)
            total_pages = len(reader.pages)

            for i in range(total_pages):
                pil_img = self.get_page_thumbnail(file_path, i, zoom_factor=0.15)
                pil_img.thumbnail((80, 60))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                self.pages_list.append(
                    {
                        "file_path": file_path,
                        "page_num": i,
                        "label": f"{file_name} - {i + 1}ページ目",
                        "thumb_img": ctk_img,
                    }
                )

            self.file_label.configure(
                text=f"現在の総ページ数: {len(self.pages_list)} ページ",
                text_color="green",
            )
            self.save_button.configure(state="normal")
            self.refresh_page_list_ui()

        except Exception as e:
            messagebox.showerror(
                "エラー", f"PDFの処理に失敗しました:\n{e}"
            )

    def refresh_page_list_ui(self):
        """リスト内にサムネイル用ラベルを追加し、ダブルクリックイベントをバインド"""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        for index, page_info in enumerate(self.pages_list):
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.pack(fill="x", padx=5, pady=4)

            img_label = ctk.CTkLabel(row_frame, text="", image=page_info["thumb_img"])
            img_label.pack(side="left", padx=10, pady=2)
            
            img_label.bind("<Double-1>", lambda e, p=page_info: self.open_zoom_window(p))

            lbl = ctk.CTkLabel(row_frame, text=page_info["label"], anchor="w")
            lbl.pack(side="left", padx=10, fill="x", expand=True)
            lbl.bind("<Double-1>", lambda e, p=page_info: self.open_zoom_window(p))

            if index > 0:
                up_btn = ctk.CTkButton(
                    row_frame,
                    text="↑ 上へ",
                    width=60,
                    command=lambda i=index: self.move_page(i, -1),
                )
                up_btn.pack(side="right", padx=2)

            if index < len(self.pages_list) - 1:
                down_btn = ctk.CTkButton(
                    row_frame,
                    text="↓ 下へ",
                    width=60,
                    command=lambda i=index: self.move_page(i, 1),
                )
                down_btn.pack(side="right", padx=2)

    def open_zoom_window(self, page_info):
        """别ウィンドウを立ち上げて高解像度化したページプレビューを表示する"""
        zoom_window = ctk.CTkToplevel(self)
        zoom_window.title(f"拡大プレビュー - {page_info['label']}")
        
        zoom_window.attributes("-topmost", True)

        pil_large_img = self.get_page_thumbnail(
            page_info["file_path"], page_info["page_num"], zoom_factor=0.6
        )
        
        ctk_large_img = ctk.CTkImage(
            light_image=pil_large_img, dark_image=pil_large_img, size=pil_large_img.size
        )

        # 子ウィンドウ内にスクロール可能なフレームを配置
        scroll_canvas = ctk.CTkScrollableFrame(zoom_window, width=500, height=650)
        scroll_canvas.pack(fill="both", expand=True, padx=10, pady=10)

        display_label = ctk.CTkLabel(scroll_canvas, text="", image=ctk_large_img)
        display_label.image = ctk_large_img  # ガベージコレクション対策の参照保持
        display_label.pack(anchor="center", expand=True)

        # ウィンドウサイズを画像サイズに合わせて微調整
        zoom_window.geometry(f"{pil_large_img.width + 50}x{min(pil_large_img.height + 70, 750)}")

    def move_page(self, index, direction):
        """リスト内の要素を入れ替える"""
        target_index = index + direction
        if target_index < 0 or target_index >= len(self.pages_list):
            return
        self.pages_list[index], self.pages_list[target_index] = (
            self.pages_list[target_index],
            self.pages_list[index],
        )
        self.refresh_page_list_ui()

    def save_pdf(self):
        """保存処理"""
        if not self.pages_list:
            return

        save_path = filedialog.asksaveasfilename(
            title="別名で保存",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        try:
            writer = pypdf.PdfWriter()
            for page_info in self.pages_list:
                reader = pypdf.PdfReader(page_info["file_path"])
                page = reader.pages[page_info["page_num"]]
                writer.add_page(page)

            with open(save_path, "wb") as f:
                writer.write(f)
            messagebox.showinfo("成功", "PDFが正しく結合されました！")
        except Exception as e:
            messagebox.showerror(
                "エラー", f"ファイルの保存中にエラーが発生しました:\n{e}"
            )

    def refresh_page_list_ui(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        for index, page_info in enumerate(self.pages_list):
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.pack(fill="x", padx=5, pady=4)

            img_label = ctk.CTkLabel(row_frame, text="", image=page_info["thumb_img"])
            img_label.pack(side="left", padx=10, pady=2)
            img_label.bind("<Double-1>", lambda e, p=page_info: self.open_zoom_window(p))

            lbl = ctk.CTkLabel(row_frame, text=page_info["label"], anchor="w")
            lbl.pack(side="left", padx=10, fill="x", expand=True)
            lbl.bind("<Double-1>", lambda e, p=page_info: self.open_zoom_window(p))

            del_btn = ctk.CTkButton(
                row_frame,
                text="削除",
                width=65,
                fg_color="#A34949",
                hover_color="#BD5A5A",
                command=lambda i=index: self.delete_page(i),
            )
            del_btn.pack(side="right", padx=10)

            if index < len(self.pages_list) - 1:
                down_btn = ctk.CTkButton(
                    row_frame,
                    text="↓ 下へ",
                    width=60,
                    command=lambda i=index: self.move_page(i, 1),
                )
                down_btn.pack(side="right", padx=2)
            else:
                # レイアウト崩れ防止用の透明なダミースペース
                spacer_down = ctk.CTkLabel(row_frame, text="", width=60)
                spacer_down.pack(side="right", padx=2)

            if index > 0:
                up_btn = ctk.CTkButton(
                    row_frame,
                    text="↑ 上へ",
                    width=60,
                    command=lambda i=index: self.move_page(i, -1),
                )
                up_btn.pack(side="right", padx=2)
            else:
                # レイアウト崩れ防止用の透明なダミースペース
                spacer_up = ctk.CTkLabel(row_frame, text="", width=60)
                spacer_up.pack(side="right", padx=2)

    def delete_page(self, index):
        """リストから要素を削除し、ヘッダーの数字とUIを最新状態にする"""
        if 0 <= index < len(self.pages_list):
            self.pages_list.pop(index)
            self.update_ui_state()
            self.refresh_page_list_ui()
      

if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
