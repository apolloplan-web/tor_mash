import os, re, shutil,tempfile, pypdf, fitz
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

ctk.set_appearance_mode("System")


class PDFEditorApp(ctk.CTk, TkinterDnD.DnDWrapper):

    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("PDFEditorApp - phase4 (shuffle & annotation)")
        self.geometry("750x600")
        self.minsize(650, 450)

        self.pages_list = []
        self.annotation_mode = None
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
            self, label_text="Contents List (PDFをDrag&Drop)"
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.list_frame.drop_target_register(DND_FILES)
        self.list_frame.dnd_bind("<<Drop>>", self.drop_pdf)

        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.pack(fill="x", padx=20, pady=(10, 20))

        self.save_button = ctk.CTkButton(
            self.bottom_frame,
            text="この並び順で名前を付けて保存",
            command=self.save_pdf,
            state="disabled",
        )
        self.save_button.pack(side="right", padx=10, pady=10)

    def open_pdf(self):
        """ボタンからPDFを開く"""
        file_path = filedialog.askopenfilename(
            title="ファイルを選択", filetypes=[("pdfs", "*.pdf")]
        )
        if not file_path:
            return
        self.pages_list = []
        self.add_pdf_to_list(file_path)

    def _parse_dnd_paths(self, data_str: str):
        if not isinstance(data_str, str):
            return []
        matches = re.findall(r'\{([^}]*)\}|([^ ]+)', data_str)
        paths = []
        for g1, g2 in matches:
            token = g1 or g2
            if token:
                paths.append(token)
        return paths

    
    def drop_pdf(self, event):
        try:
            raw = event.data
            file_paths = self._parse_dnd_paths(raw)
            valid_files_added = False
            for path in file_paths:
                path = path.strip()
                if path.lower().endswith(".pdf") and os.path.exists(path):
                    self.add_pdf_to_list(path)
                    valid_files_added = True

            if not valid_files_added:
                messagebox.showwarning(
                    "警告", "有効なPDFファイルが検出されませんでした"
                )
        except Exception as e:
            messagebox.showerror("ドロップエラー", f"ドロップ処理中に例外が発生しました:\n{e}")
    
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
            self.update_ui_state()
            self.refresh_page_list_ui()

        except Exception as e:
            messagebox.showerror(
                "エラー", f"PDFの処理に失敗しました:\n{e}"
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


    def open_zoom_window(self, page_info):
        """别ウィンドウを立ち上げて高解像度化したページプレビューを表示する"""
        zoom_window = ctk.CTkToplevel(self)
        zoom_window.title(f"拡大プレビュー - {page_info['label']}")
        zoom_window.attributes("-topmost", True)
        zoom_factor = 0.9

        pil_large_img = self.get_page_thumbnail(
            page_info["file_path"], page_info["page_num"], zoom_factor = zoom_factor
        )
        # toolbar
        toolbar = ctk.CTkFrame(zoom_window)
        toolbar.pack(fill="x", padx=8, pady=(8, 0)) 
        text_annot_btn = ctk.CTkButton(toolbar, text="テキスト注釈", command=lambda: self.toggle_annotation_mode('text', text_annot_btn))
        text_annot_btn.pack(side="left", padx=6)
        list_ann_btn = ctk.CTkButton(toolbar, text="注釈一覧", command=lambda p=page_info: self.show_annotations(p))
        list_ann_btn.pack(side="left", padx=6)
        close_btn = ctk.CTkButton(toolbar, text="閉じる", command=zoom_window.destroy)
        close_btn.pack(side="right", padx=6)

        # Canvas を使って画像描画し、クリック座標を拾う
        canvas_frame = tk.Frame(zoom_window)  # tk.Frame を使ってスクロール等を後で追加しやすく
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        canvas = tk.Canvas(canvas_frame, width=pil_large_img.width, height=pil_large_img.height)
        canvas.pack(fill="both", expand=True)
        tk_img = ImageTk.PhotoImage(pil_large_img)
        canvas.image = tk_img
        canvas.create_image(0, 0, anchor="nw", image=tk_img)

        # クリックで注釈追加（モードが 'text' の時のみ）
        def on_canvas_click(event):
            if self.annotation_mode == 'text':
                # テキスト入力ダイアログ
                text = simpledialog.askstring("注釈テキスト", "注釈内容を入力してください:") 
                if text:
                    # canvas のピクセル座標 -> PDF 座標へ変換
                    pdf_x = event.x / zoom_factor
                    pdf_y = event.y / zoom_factor
                    self.add_text_annotation(page_info, pdf_x, pdf_y, text)
                    # 注釈を追加したらサムネイルを更新して UI を再描画
                    self.refresh_page_list_ui()

        canvas.bind("<Button-1>", on_canvas_click)

        # ウィンドウサイズを画像サイズに合わせて微調整
        zoom_window.geometry(f"{pil_large_img.width + 50}x{min(pil_large_img.height + 70, 900)}")

    def add_text_annotation(self, page_info, pdf_x, pdf_y, text):
        """指定ページにテキスト注釈を追加してファイルを書き換え、サムネイルを更新する"""
        file_path = page_info["file_path"]
        page_num = page_info["page_num"]
        try:
            doc = fitz.open(file_path)
            page = doc.load_page(page_num)
            # PyMuPDF の Rect を使ってフリーテキスト注釈を追加
            rect = fitz.Rect(pdf_x, pdf_y, pdf_x +200, pdf_y+50) 
            page.add_freetext_annot(rect, text, fontsize=14, fontname="cjk", text_color=(0, 0, 0))

            # 一時ファイルに保存して元ファイルを置換（安全なフロー）
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            doc.save(tmp_path)
            doc.close()

            shutil.move(tmp_path, file_path)
            # 変更後のサムネイルを更新
            self._update_thumbnail_for_file_page(file_path, page_num)
            messagebox.showinfo("注釈追加", "注釈を追加しました。")
        except Exception as e:
            messagebox.showerror("注釈エラー", f"注釈の追加に失敗しました:\n{e}")

    def show_annotations(self, page_info):
        """指定ページの注釈一覧を表示し、個別削除を可能にする"""
        file_path = page_info["file_path"]
        page_num = page_info["page_num"]
        try:
            doc = fitz.open(file_path)
            page = doc.load_page(page_num)
            annots = list(page.annots() or [])
            if not annots:
                doc.close()
                messagebox.showinfo("注釈一覧", "このページに注釈はありません。")
                return

            # 別ウィンドウで一覧を表示
            ann_win = ctk.CTkToplevel(self)
            ann_win.title(f"注釈一覧 - {page_info['label']}")
            ann_win.geometry("400x300")
            container = ctk.CTkScrollableFrame(ann_win)
            container.pack(fill="both", expand=True, padx=8, pady=8)

            # 注釈を表示（内容と削除ボタン）
            for annot in annots:
                info = annot.info or {}
                content = info.get("content") or info.get("title") or str(info)
                frame = ctk.CTkFrame(container)
                frame.pack(fill="x", padx=6, pady=6)
                lbl = ctk.CTkLabel(frame, text=content, anchor="w")
                lbl.pack(side="left", fill="x", expand=True, padx=(6, 8))
                def _delete(a=annot):
                    try:
                        # 再取得して削除（）
                        page.delete_annot(a)
                        # 保存して置換
                        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
                        os.close(fd)
                        doc.save(tmp_path)
                        doc.close()
                        shutil.move(tmp_path, file_path)
                        messagebox.showinfo("削除", "注釈を削除しました。")
                        ann_win.destroy()
                        # 更新
                        self._update_thumbnail_for_file_page(file_path, page_num)
                    except Exception as e:
                        messagebox.showerror("削除エラー", f"注釈の削除に失敗しました:\n{e}")
                del_btn = ctk.CTkButton(frame, text="削除", width=80, command=_delete)
                del_btn.pack(side="right", padx=6)
            # doc は削除処理の中で閉じる設計なのでここでは閉じない
        except Exception as e:
            messagebox.showerror("注釈一覧エラー", f"注釈一覧を取得できませんでした:\n{e}")
    
    def _update_thumbnail_for_file_page(self, file_path, page_num):
        """単一ページのサムネイルを再生成して pages_list に反映させる"""
        try:
            pil_img = self.get_page_thumbnail(file_path, page_num, zoom_factor=0.15)
            pil_img.thumbnail((80, 60))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            # pages_list 内の一致するエントリを更新
            for entry in self.pages_list:
                if entry["file_path"] == file_path and entry["page_num"] == page_num:
                    entry["thumb_img"] = ctk_img
            self.update_ui_state()
        except Exception:
            # サムネイル更新は致命ではないのでログ的に無視
            pass

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
            newdoc = fitz.open()
            for page_info in self.pages_list:
                src = fitz.open(page_info["file_path"])
                # 指定ページだけを挿入（注釈を含めてコピーされます）
                newdoc.insert_pdf(src, from_page=page_info["page_num"], to_page=page_info["page_num"])
                src.close()
            newdoc.save(save_path)
            newdoc.close()
            messagebox.showinfo("成功", "PDFが正しく結合・保存されました！")
        except Exception as e:
            messagebox.showerror(
                "エラー", f"ファイルの保存中にエラーが発生しました:\n{e}"
            )

    def update_ui_state(self):
        """ヘッダーのラベルや保存ボタンの状態を更新"""
        if self.pages_list:
            self.file_label.configure(
                text=f"現在の総ページ数: {len(self.pages_list)} ページ",
                text_color="green",
            )
            self.save_button.configure(state="normal")
        else:
            self.file_label.configure(
                text="ファイルを選択するか、下にドロップしてください",
                text_color="gray",
            )
            self.save_button.configure(state="disabled")

    def delete_page(self, index):
        """リストから要素を削除し、ヘッダーの数字とUIを最新状態にする"""
        if 0 <= index < len(self.pages_list):
            self.pages_list.pop(index)
            self.update_ui_state()
            self.refresh_page_list_ui()
      
    def toggle_annotation_mode(self, mode, button_widget):
        """注釈モードのトグル（UI ボタンの状態を視覚的に切り替え）"""
        if self.annotation_mode == mode:
            self.annotation_mode = None
            try:
                button_widget.configure(fg_color=None)
            except Exception:
                pass
        else:
            self.annotation_mode = mode
            try:
                button_widget.configure(fg_color="#318216")
            except Exception:
                pass

if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
