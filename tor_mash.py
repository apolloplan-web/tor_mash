import os
import sys
import re
import shutil
import tempfile
import fitz  # PyMuPDF
import pypdf
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, colorchooser
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ZoomEditWindow(ctk.CTkToplevel):
    """
    書き換え君2のUI・機能を統合したズームアップ編集ウィンドウ
    サムネイルのダブルクリックから呼び出され、ページのテキスト・画像編集を行う。
    """
    def __init__(self, parent, temp_pdf_path, page_idx, on_close_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.temp_pdf_path = temp_pdf_path
        self.current_page_idx = page_idx
        self.on_close_callback = on_close_callback

        self.title(f"書き換え君2 - ズームアップ編集 (ページ {self.current_page_idx + 1})")
        self.geometry("1100x800")
        self.attributes("-topmost", True)

        # PDFドキュメント読み込み
        self.doc = fitz.open(self.temp_pdf_path)
        self.zoom = 1.6  # ズーム倍率

        # 編集モード
        self.current_mode = None  # "add_text", "delete_text", "add_image", "delete_image"

        # テキスト設定
        self.current_fontsize = 14
        self.current_fontcolor_rgb = (0.0, 0.0, 0.0)  # (R, G, B) float 0~1
        self.current_fontcolor_hex = "#000000"

        # キャンバスドラッグ用
        self.start_x = None
        self.start_y = None
        self.rect_id = None

        self.setup_ui()
        self.render_page()

        # ウィンドウを閉じる際のリフレッシュ処理
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # メインレイアウト: 左側コントロールパネル、右側キャンバス
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 左側：コントロールパネル ---
        self.ctrl_frame = ctk.CTkFrame(self, width=250)
        self.ctrl_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # モード表示ラベル
        self.lbl_mode = ctk.CTkLabel(
            self.ctrl_frame, 
            text="モード: 未選択", 
            font=("Arial", 14, "bold"),
            text_color="#1f538d"
        )
        self.lbl_mode.pack(pady=(15, 10), padx=10, fill="x")

        # --- テキスト編集セクション ---
        lbl_sec1 = ctk.CTkLabel(self.ctrl_frame, text="【機能1：テキスト編集】", font=("Arial", 12, "bold"))
        lbl_sec1.pack(anchor="w", padx=10, pady=(10, 5))

        # フォントサイズ
        size_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        size_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(size_frame, text="サイズ:").pack(side="left")
        self.size_entry = ctk.CTkEntry(size_frame, width=60)
        self.size_entry.insert(0, str(self.current_fontsize))
        self.size_entry.pack(side="right")

        # 例: ZoomEditWindow.setup_ui() のテキスト設定セクションに追加するコード
        # 「フォント選択」UI を作成し、選択変更を受け取るハンドラを設定します。

        # --- フォント選択（システムフォント一覧） ---
        font_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        font_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(font_frame, text="フォント:").pack(side="left")

        # tkinter の低レベル呼び出しでフォント一覧を取得（追加インポート不要）
        try:
            fonts = list(self.tk.call('font', 'families'))
            fonts = sorted(set(fonts))
        except Exception:
            fonts = []

        # CTkOptionMenu を使って表示（customtkinter のバージョンによっては OptionMenu が無ければ別の選択ウィジェットへ）
        self.combo_font = ctk.CTkOptionMenu(font_frame, values=fonts, command=self.on_font_changed)
        if fonts:
            self.current_font_family = fonts[0]
            self.combo_font.set(self.current_font_family)
        else:
            self.current_font_family = None
            self.combo_font.pack(side="right", fill="x", expand=True)

        # そしてクラスに以下のメソッドを追加：
        def on_font_changed(self, value):
            """フォント選択が変わったときのコールバック"""
            self.current_font_family = value
        
        # 文字色
        color_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        color_frame.pack(fill="x", padx=10, pady=5)
        self.btn_color = ctk.CTkButton(color_frame, text="文字色選択", width=100, command=self.choose_color)
        self.btn_color.pack(side="left")
        self.color_preview = ctk.CTkFrame(color_frame, width=24, height=24, fg_color=self.current_fontcolor_hex)
        self.color_preview.pack(side="right", padx=5)

        self.btn_add_text = ctk.CTkButton(
            self.ctrl_frame, text="テキスト追加 (位置指定)", command=lambda: self.set_mode("add_text")
        )
        self.btn_add_text.pack(fill="x", padx=10, pady=4)

        self.btn_del_text = ctk.CTkButton(
            self.ctrl_frame, text="テキスト削除 (範囲選択)", command=lambda: self.set_mode("delete_text")
        )
        self.btn_del_text.pack(fill="x", padx=10, pady=4)

        # --- 画像編集セクション ---
        lbl_sec2 = ctk.CTkLabel(self.ctrl_frame, text="【機能2：画像編集】", font=("Arial", 12, "bold"))
        lbl_sec2.pack(anchor="w", padx=10, pady=(15, 5))

        self.btn_add_img = ctk.CTkButton(
            self.ctrl_frame, text="画像追加 (位置指定)", command=lambda: self.set_mode("add_image")
        )
        self.btn_add_img.pack(fill="x", padx=10, pady=4)

        self.btn_del_img = ctk.CTkButton(
            self.ctrl_frame, text="画像削除 (範囲選択)", command=lambda: self.set_mode("delete_image")
        )
        self.btn_del_img.pack(fill="x", padx=10, pady=4)

        # --- ページ操作ナビゲーション ---
        lbl_sec3 = ctk.CTkLabel(self.ctrl_frame, text="【ページ操作】", font=("Arial", 12, "bold"))
        lbl_sec3.pack(anchor="w", padx=10, pady=(20, 5))

        nav_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=5)
        self.btn_prev = ctk.CTkButton(nav_frame, text="前へ", width=70, command=self.prev_page)
        self.btn_prev.pack(side="left", padx=2)
        self.btn_next = ctk.CTkButton(nav_frame, text="次へ", width=70, command=self.next_page)
        self.btn_next.pack(side="right", padx=2)

        self.lbl_page_info = ctk.CTkLabel(self.ctrl_frame, text="", font=("Arial", 11))
        self.lbl_page_info.pack(pady=5)

        # 閉じるボタン
        self.btn_close = ctk.CTkButton(
            self.ctrl_frame, text="完了して閉じる", fg_color="#2b8a3e", hover_color="#237032", command=self.on_close
        )
        self.btn_close.pack(side="bottom", fill="x", padx=10, pady=15)

        # --- 右側：ビューア・キャンバスエリア ---
        self.canvas_container = ctk.CTkScrollableFrame(self)
        self.canvas_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.canvas = tk.Canvas(self.canvas_container, bg="#555555", highlightthickness=0)
        self.canvas.pack(anchor="center", expand=True)

        # キャンバスバインド
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

    def set_mode(self, mode):
        self.current_mode = mode
        modes = {
            "add_text": "テキスト追加 (PDF上をクリック)",
            "delete_text": "テキスト削除 (削除エリアをドラッグ)",
            "add_image": "画像追加 (PDF上をクリック)",
            "delete_image": "画像削除 (削除エリアをドラッグ)"
        }
        self.lbl_mode.configure(text=f"モード: {modes.get(mode, 'なし')}")

    def choose_color(self):
        color = colorchooser.askcolor(title="文字色を選択", color=self.current_fontcolor_hex)
        if color[1]:
            self.current_fontcolor_hex = color[1]
            rgb = color[0]
            self.current_fontcolor_rgb = (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            self.color_preview.configure(fg_color=self.current_fontcolor_hex)

    def render_page(self):
        if not self.doc or self.current_page_idx >= len(self.doc):
            return

        page = self.doc[self.current_page_idx]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.config(width=pix.width, height=pix.height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        self.lbl_page_info.configure(text=f"ページ: {self.current_page_idx + 1} / {len(self.doc)}")
        self.title(f"書き換え君2 - ズームアップ編集 (ページ {self.current_page_idx + 1}/{len(self.doc)})")

    def prev_page(self):
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self.render_page()

    def next_page(self):
        if self.current_page_idx < len(self.doc) - 1:
            self.current_page_idx += 1
            self.render_page()

    def save_doc_changes(self):
        """変更を一時ファイルに上書き保存"""
        try:
            self.doc.save(self.temp_pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        except Exception:
            # 増分保存が失敗した場合は一括保存
            fd, tmp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            self.doc.save(tmp_out)
            self.doc.close()
            shutil.move(tmp_out, self.temp_pdf_path)
            self.doc = fitz.open(self.temp_pdf_path)

    def on_canvas_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.current_mode in ["delete_text", "delete_image"]:
            self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2, dash=(4, 4)
            )

    def on_canvas_drag(self, event):
        if self.rect_id and self.current_mode in ["delete_text", "delete_image"]:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_canvas_release(self, event):
        end_x, end_y = event.x, event.y

        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

        if self.start_x is None or not self.doc:
            return

        dist = ((end_x - self.start_x) ** 2 + (end_y - self.start_y) ** 2) ** 0.5

        # クリック動作 (距離が短い)
        if dist < 5:
            self.handle_click(self.start_x, self.start_y)
        else:
            self.handle_drag(self.start_x, self.start_y, end_x, end_y)

        self.start_x = None
        self.start_y = None

    def handle_click(self, x, y):
        pdf_x = x / self.zoom
        pdf_y = y / self.zoom
        page = self.doc[self.current_page_idx]

        if self.current_mode == "add_text":
            text = simpledialog.askstring("テキスト追加", "挿入する文字を入力してください:", parent=self)
            if text:
                try:
                    sz = int(self.size_entry.get())
                except ValueError:
                    sz = self.current_fontsize

                try:
                    page.insert_text(
                        (pdf_x, pdf_y),
                        text,
                        fontsize=sz,
                        color=self.current_fontcolor_rgb,
                        fontname="japan"
                    )
                except Exception as e:
                    messagebox.showerror("エラー", f"テキスト挿入エラー:{e}", parent=self)

                self.save_doc_changes()
                self.render_page()

        elif self.current_mode == "add_image":
            img_path = filedialog.askopenfilename(
                title="画像を選択",
                filetypes=[("画像ファイル", "*.png *.jpg *.jpeg *.bmp")],
                parent=self
            )
            if img_path:
                rect = fitz.Rect(pdf_x, pdf_y, pdf_x + 150, pdf_y + 100)
                page.insert_image(rect, filename=img_path)
                self.save_doc_changes()
                self.render_page()

    def handle_drag(self, x1, y1, x2, y2):
        if self.current_mode not in ["delete_text", "delete_image"]:
            return

        px1, py1 = min(x1, x2) / self.zoom, min(y1, y2) / self.zoom
        px2, py2 = max(x1, x2) / self.zoom, max(y1, y2) / self.zoom
        pdf_rect = fitz.Rect(px1, py1, px2, py2)
        page = self.doc[self.current_page_idx]

        if self.current_mode == "delete_text":
            page.add_redact_annot(pdf_rect)
            page.apply_redactions()
            self.save_doc_changes()
            self.render_page()
            messagebox.showinfo("完了", "指定エリアのテキストを削除・隠蔽しました。", parent=self)

        elif self.current_mode == "delete_image":
            images = page.get_images(full=True)
            deleted = False
            for img_info in images:
                xref = img_info[0]
                rects = page.get_image_rects(xref)
                for r in rects:
                    if pdf_rect.intersects(r):
                        page.delete_image(xref)
                        deleted = True
                        break

            if not deleted:
                # 該当画像オブジェクトが直接消せなかった場合はRedactionで消去
                page.add_redact_annot(pdf_rect)
                page.apply_redactions()

            self.save_doc_changes()
            self.render_page()
            messagebox.showinfo("完了", "指定エリアの画像を削除しました。", parent=self)

    def on_close(self):
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()


class JibunPDFApp(ctk.CTk, TkinterDnD.DnDWrapper):
    """
    jibunpdf UIベースのメインアプリケーション
    一時ファイル管理、横4列サムネイル表示、複数選択＆ドラッグ入れ替え、別名保存を行う
    """
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("jibunpdf + 書き換え君2 マッシュアップ Editor")
        self.geometry("980x750")
        self.minsize(800, 550)

        # 一時ファイルおよびデータ管理
        self.temp_pdf_path = None
        self.pages_order = []  # [{ "page_num": int, "selected": bool }, ...]
        self.drag_start_index = None

        self.setup_ui()

        # DND登録
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop_pdf)

    def setup_ui(self):
        # ヘッダーエリア
        self.top_frame = ctk.CTkFrame(self, height=60)
        self.top_frame.pack(fill="x", padx=15, pady=(15, 10))

        self.open_button = ctk.CTkButton(
            self.top_frame, text="PDFを開く", command=self.open_pdf_dialog
        )
        self.open_button.pack(side="left", padx=10, pady=10)

        self.file_label = ctk.CTkLabel(
            self.top_frame,
            text="PDFファイルを選択するか、ここにドロップしてください",
            text_color="gray",
            font=("Arial", 12)
        )
        self.file_label.pack(side="left", padx=10, pady=10)

        # 複数選択操作ボタン群
        self.btn_select_all = ctk.CTkButton(
            self.top_frame, text="全選択", width=65, command=self.select_all_pages
        )
        self.btn_select_all.pack(side="right", padx=5, pady=10)

        self.btn_deselect_all = ctk.CTkButton(
            self.top_frame, text="全解除", width=65, command=self.deselect_all_pages
        )
        self.btn_deselect_all.pack(side="right", padx=5, pady=10)

        # メイン領域：サムネイル一覧（横4列 × 縦スクロール）
        self.list_frame = ctk.CTkScrollableFrame(
            self, label_text="ページサムネイル (横4列表示 / ドラッグ＆ドロップで入れ替え・ファイルドロップで追加)"
        )
        self.list_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.list_frame.drop_target_register(DND_FILES)
        self.list_frame.dnd_bind("<<Drop>>", self.drop_pdf)

        # フッターコントロールエリア
        self.bottom_frame = ctk.CTkFrame(self, height=70)
        self.bottom_frame.pack(fill="x", padx=15, pady=(10, 15))

        # 選択ページ移動・削除ツール
        self.lbl_ops = ctk.CTkLabel(self.bottom_frame, text="選択ページの操作:")
        self.lbl_ops.pack(side="left", padx=(10, 5), pady=10)

        self.btn_move_up = ctk.CTkButton(
            self.bottom_frame, text="← 前へ移動", width=90, command=lambda: self.move_selected_pages(-1)
        )
        self.btn_move_up.pack(side="left", padx=3, pady=10)

        self.btn_move_down = ctk.CTkButton(
            self.bottom_frame, text="次へ移動 →", width=90, command=lambda: self.move_selected_pages(1)
        )
        self.btn_move_down.pack(side="left", padx=3, pady=10)

        self.btn_delete = ctk.CTkButton(
            self.bottom_frame, text="選択ページを削除", width=120, fg_color="#A34949", hover_color="#BD5A5A", command=self.delete_selected_pages
        )
        self.btn_delete.pack(side="left", padx=10, pady=10)

        # 保存ボタン
        self.save_button = ctk.CTkButton(
            self.bottom_frame,
            text="保存 (別名で保存)",
            fg_color="#1f538d",
            font=("Arial", 13, "bold"),
            command=self.save_pdf,
            state="disabled",
            width=150
        )
        self.save_button.pack(side="right", padx=15, pady=10)

    def open_pdf_dialog(self):
        file_path = filedialog.askopenfilename(
            title="PDFファイルを選択", filetypes=[("PDF Files", "*.pdf")]
        )
        if file_path:
            self.load_pdf(file_path)

    def drop_pdf(self, event):
        """
        ファイルドロップ処理
        未読み込み時：新規読み込み
        既にPDF読み込み時：末尾にページ追加（追加機能要件1）
        """
        try:
            raw = event.data
            file_paths = self._parse_dnd_paths(raw)
            pdf_paths = [p.strip() for p in file_paths if p.strip().lower().endswith(".pdf") and os.path.exists(p.strip())]

            if not pdf_paths:
                return

            if self.temp_pdf_path is None or not os.path.exists(self.temp_pdf_path):
                # 最初のPDFを開く
                self.load_pdf(pdf_paths[0])
                # 複数ドロップされていた場合は2個目以降を追加
                for path in pdf_paths[1:]:
                    self.append_pdf(path)
            else:
                # 既存PDFにドロップされたPDFを追記・追加するのだ
                for path in pdf_paths:
                    self.append_pdf(path)

        except Exception as e:
            messagebox.showerror("ドロップエラー", f"ファイルの読み込みに失敗しました:{e}")

    def append_pdf(self, append_path):
        """要件1: 既存のPDFの後ろにファイル（PDF）を追加するのだ"""
        try:
            target_doc = fitz.open(self.temp_pdf_path)
            append_doc = fitz.open(append_path)

            start_page_idx = len(target_doc)
            append_count = len(append_doc)

            target_doc.insert_pdf(append_doc)
            
            # 一時ファイルへ保存
            fd, tmp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            target_doc.save(tmp_out)
            target_doc.close()
            append_doc.close()

            if os.path.exists(self.temp_pdf_path):
                try:
                    os.remove(self.temp_pdf_path)
                except Exception:
                    pass
            shutil.move(tmp_out, self.temp_pdf_path)

            # 新規ページのインデックスを追加
            for i in range(append_count):
                self.pages_order.append({
                    "page_num": start_page_idx + i,
                    "selected": False
                })

            total_pages = len(self.pages_order)
            self.file_label.configure(
                text=f"ファイル: 追加済み (全 {total_pages} ページ)",
                text_color="#2b8a3e"
            )
            self.refresh_thumbnails()

        except Exception as e:
            messagebox.showerror("追加エラー", f"ページの追加に失敗しました:{e}")

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

    def load_pdf(self, src_path):
        """初期化要件: 一時ファイルにPDFをコピーし、一時ファイルに対して処理を行う"""
        try:
            # 既存の一時ファイルがあればクリーンアップ
            if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
                try:
                    os.remove(self.temp_pdf_path)
                except Exception:
                    pass

            # 新しい一時ファイルにコピー
            fd, self.temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            shutil.copyfile(src_path, self.temp_pdf_path)

            # PyMuPDFで読み込み
            doc = fitz.open(self.temp_pdf_path)
            total_pages = len(doc)
            doc.close()

            self.pages_order = []
            for i in range(total_pages):
                self.pages_order.append({
                    "page_num": i,
                    "selected": False
                })

            self.file_label.configure(
                text=f"ファイル: {os.path.basename(src_path)} (全 {total_pages} ページ)",
                text_color="#2b8a3e"
            )
            self.save_button.configure(state="normal")

            self.refresh_thumbnails()

        except Exception as e:
            messagebox.showerror("読み込みエラー", f"PDFの読み込みに失敗しました:{e}")

    def get_page_thumbnail(self, page_num, zoom_factor=0.2):
        """一時ファイルから指定ページのサムネイル画像を生成"""
        if not self.temp_pdf_path or not os.path.exists(self.temp_pdf_path):
            return None
        doc = fitz.open(self.temp_pdf_path)
        if page_num >= len(doc):
            doc.close()
            return None
        page = doc.load_page(page_num)
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        img.thumbnail((160, 200))
        return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

    def refresh_thumbnails(self):
        """UI要件: サムネイルを横4ページ×縦スクロールで表示"""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not self.temp_pdf_path:
            return

        # 4列のグリッド配置の設定
        for c in range(4):
            self.list_frame.grid_columnconfigure(c, weight=1, pad=10)

        self.cards_list = []  # 各カードの参照保持用

        for index, page_info in enumerate(self.pages_order):
            row = index // 4
            col = index % 4

            # 各サムネイルカードの枠
            card = ctk.CTkFrame(
                self.list_frame, 
                fg_color="#333333" if page_info["selected"] else "#2b2b2b",
                border_width=2,
                border_color="#1f538d" if page_info["selected"] else "#444444"
            )
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.cards_list.append(card)

            # チェックボックス（複数選択用）
            chk_var = tk.BooleanVar(value=page_info["selected"])
            chk = ctk.CTkCheckBox(
                card, 
                text=f"P. {index + 1} (元:{page_info['page_num'] + 1})",
                variable=chk_var,
                command=lambda idx=index, v=chk_var: self.toggle_page_selection(idx, v.get()),
                font=("Arial", 11, "bold")
            )
            chk.pack(anchor="w", padx=8, pady=(6, 4))

            # サムネイル画像表示
            ctk_img = self.get_page_thumbnail(page_info["page_num"])
            if ctk_img:
                img_label = ctk.CTkLabel(card, text="", image=ctk_img)
                img_label.pack(padx=8, pady=4, expand=True)

                # ダブルクリックイベント -> 書き換え君2 UI 起動 (ズームアップ)
                img_label.bind("<Double-1>", lambda e, p_idx=page_info["page_num"]: self.open_zoom_editor(p_idx))

                # ドラッグ＆ドロップ用イベントバインド（要件2: ページ入れ替え）
                img_label.bind("<ButtonPress-1>", lambda e, idx=index: self.on_drag_start(idx))
                img_label.bind("<ButtonRelease-1>", lambda e, idx=index: self.on_drag_end(e, idx))
                
                card.bind("<ButtonPress-1>", lambda e, idx=index: self.on_drag_start(idx))
                card.bind("<ButtonRelease-1>", lambda e, idx=index: self.on_drag_end(e, idx))

    def toggle_page_selection(self, index, is_selected):
        self.pages_order[index]["selected"] = is_selected
        self.refresh_thumbnails()

    def select_all_pages(self):
        for item in self.pages_order:
            item["selected"] = True
        self.refresh_thumbnails()

    def deselect_all_pages(self):
        for item in self.pages_order:
            item["selected"] = False
        self.refresh_thumbnails()

    def on_drag_start(self, index):
        self.drag_start_index = index

    def on_drag_end(self, event, start_idx):
        """要件2: ドラッグ＆ドロップによるページ入れ替え機能"""
        if self.drag_start_index is None:
            return

        # マウスリリース位置からドロップ先ウィジェットを検索
        x, y = self.winfo_pointerxy()
        target_widget = self.winfo_containing(x, y)

        target_idx = None
        if hasattr(self, 'cards_list'):
            for index, card in enumerate(self.cards_list):
                # ドロップ先がカード自身、またはカードの子ウィジェットであるか判定
                w = target_widget
                while w is not None:
                    if w == card:
                        target_idx = index
                        break
                    w = getattr(w, 'master', None)
                if target_idx is not None:
                    break

        if target_idx is not None and target_idx != start_idx:
            # 選択中のアイテムがあればまとめて移動、無ければドラッグ対象のみ移動するのだ
            selected_indices = [i for i, item in enumerate(self.pages_order) if item["selected"]]

            if start_idx not in selected_indices:
                selected_indices = [start_idx]

            # 移動アイテムの取り出し
            moving_items = [self.pages_order[i] for i in selected_indices]
            for item in moving_items:
                self.pages_order.remove(item)

            # 挿入インデックスの計算
            insert_pos = target_idx
            if insert_pos > len(self.pages_order):
                insert_pos = len(self.pages_order)

            for i, item in enumerate(moving_items):
                self.pages_order.insert(insert_pos + i, item)

            self.refresh_thumbnails()

        self.drag_start_index = None

    def move_selected_pages(self, direction):
        """選択された複数ページを一括で移動 (-1: 前へ, 1: 次へ)"""
        selected_indices = [i for i, item in enumerate(self.pages_order) if item["selected"]]
        if not selected_indices:
            messagebox.showinfo("案内", "移動するページを選択してください。")
            return

        if direction == -1:
            if min(selected_indices) == 0:
                return
            for idx in selected_indices:
                self.pages_order[idx], self.pages_order[idx - 1] = self.pages_order[idx - 1], self.pages_order[idx]
        elif direction == 1:
            if max(selected_indices) == len(self.pages_order) - 1:
                return
            for idx in reversed(selected_indices):
                self.pages_order[idx], self.pages_order[idx + 1] = self.pages_order[idx + 1], self.pages_order[idx]

        self.refresh_thumbnails()

    def delete_selected_pages(self):
        selected_indices = [i for i, item in enumerate(self.pages_order) if item["selected"]]
        if not selected_indices:
            messagebox.showinfo("案内", "削除するページを選択してください。")
            return

        if messagebox.askyesno("確認", f"選択した {len(selected_indices)} ページを削除しますか？"):
            self.pages_order = [item for i, item in enumerate(self.pages_order) if not item["selected"]]
            self.refresh_thumbnails()

    def open_zoom_editor(self, page_num):
        """
        サムネイルをダブルクリックすると書き換え君2のUIが開く→ズームアップ
        ズームアップを閉じると、サムネイルのビューがリフレッシュされる
        """
        ZoomEditWindow(
            parent=self,
            temp_pdf_path=self.temp_pdf_path,
            page_idx=page_num,
            on_close_callback=self.refresh_thumbnails
        )

    def save_pdf(self):
        """
        終了処理: 「保存」ボタンが押されたら、一時ファイルの内容を別名保存する
        """
        if not self.temp_pdf_path or not self.pages_order:
            messagebox.showwarning("警告", "保存対象のデータがありません。")
            return

        save_path = filedialog.asksaveasfilename(
            title="別名で保存",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not save_path:
            return

        try:
            src_doc = fitz.open(self.temp_pdf_path)
            new_doc = fitz.open()

            # 現在の並び順に従ってページを再構築
            for page_info in self.pages_order:
                p_num = page_info["page_num"]
                if p_num < len(src_doc):
                    new_doc.insert_pdf(src_doc, from_page=p_num, to_page=p_num)

            new_doc.save(save_path)
            new_doc.close()
            src_doc.close()

            messagebox.showinfo("完了", f"ファイルが正常に保存されました:{save_path}")
        except Exception as e:
            messagebox.showerror("保存エラー", f"保存処理中にエラーが発生しました:{e}")

    def destroy(self):
        # アプリ終了時に一時ファイルを確実に削除
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except Exception:
                pass
        super().destroy()


if __name__ == "__main__":
    app = JibunPDFApp()
    app.mainloop()
