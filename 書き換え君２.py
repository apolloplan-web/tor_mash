import os
import sys
import fitz  # PyMuPDF
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QImage, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PDFEditorApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF GUI Editor (PyMuPDF & PyQt6)")
        self.setGeometry(100, 100, 1050, 750)

        # PDFデータ管理用変数
        self.doc = None
        self.current_page_idx = 0
        self.zoom = 1.5  # 編集しやすいように少し拡大表示

        # 編集モード状態
        self.current_mode = (
            None  # "add_text", "delete_text", "add_image", "delete_image"
        )

        # テキスト属性のデフォルト設定
        self.current_fontsize = 12
        self.current_fontcolor = QColor(0, 0, 0)  # BLACK
        self.current_font_family = ""

        self.init_ui()

    def init_ui(self):
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- 左側：コントロールパネル ---
        control_panel = QVBoxLayout()

        self.btn_open = QPushButton("PDFを開く")
        self.btn_open.clicked.connect(self.open_pdf)
        control_panel.addWidget(self.btn_open)

        # 状態表示ラベル
        self.lbl_status = QLabel("PDFを選択してください")
        self.lbl_status.setWordWrap(True)
        control_panel.addWidget(self.lbl_status)

        control_panel.addSpacing(15)
        control_panel.addWidget(QLabel("【機能1：テキスト編集】"))

        # --- フォント設定エリア ---
        # 1. フォント選択（システムフォント一覧）
        control_panel.addWidget(QLabel("フォント:"))
        self.combo_font = QComboBox()
        system_fonts = QFontDatabase.families()
        self.combo_font.addItems(system_fonts)
        if system_fonts:
            self.current_font_family = system_fonts[0]
        self.combo_font.currentTextChanged.connect(self.on_font_changed)
        control_panel.addWidget(self.combo_font)

        # 2. フォントサイズ（デフォルト: 12）
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("サイズ:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 200)
        self.spin_size.setValue(12)  # デフォルト値 12
        self.spin_size.valueChanged.connect(self.on_size_changed)
        size_layout.addWidget(self.spin_size)
        control_panel.addLayout(size_layout)

        # 3. フォントカラー（デフォルト: BLACK）
        color_layout = QHBoxLayout()
        self.btn_color = QPushButton("文字色を選択")
        self.btn_color.clicked.connect(self.choose_color)
        color_layout.addWidget(self.btn_color)

        self.lbl_color_preview = QLabel()
        self.lbl_color_preview.setFixedSize(24, 24)
        self.update_color_preview()
        color_layout.addWidget(self.lbl_color_preview)
        control_panel.addLayout(color_layout)

        control_panel.addSpacing(10)

        self.btn_add_text = QPushButton("テキストを追加 (位置指定)")
        self.btn_add_text.clicked.connect(self.set_add_text_mode)
        control_panel.addWidget(self.btn_add_text)

        self.btn_del_text = QPushButton("テキストを削除 (エリア選択)")
        self.btn_del_text.clicked.connect(self.set_delete_text_mode)
        control_panel.addWidget(self.btn_del_text)

        control_panel.addSpacing(15)
        control_panel.addWidget(QLabel("【機能2：画像編集】"))

        self.btn_add_img = QPushButton("画像を追加 (位置指定)")
        self.btn_add_img.clicked.connect(self.set_add_image_mode)
        control_panel.addWidget(self.btn_add_img)

        self.btn_del_img = QPushButton("画像を削除 (エリア選択)")
        self.btn_del_img.clicked.connect(self.set_delete_image_mode)
        control_panel.addWidget(self.btn_del_img)

        control_panel.addSpacing(15)
        control_panel.addWidget(QLabel("【ページ操作・保存】"))

        # ページ移動
        page_nav = QHBoxLayout()
        self.btn_prev = QPushButton("前へ")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("次へ")
        self.btn_next.clicked.connect(self.next_page)
        page_nav.addWidget(self.btn_prev)
        page_nav.addWidget(self.btn_next)
        control_panel.addLayout(page_nav)

        self.lbl_page = QLabel("ページ: 0 / 0")
        control_panel.addWidget(self.lbl_page)

        control_panel.addSpacing(15)
        self.btn_save = QPushButton("PDFを別名で保存")
        self.btn_save.clicked.connect(self.save_pdf)
        control_panel.addWidget(self.btn_save)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

        # --- 右側：PDFプレビュー・編集エリア ---
        self.view = EventGraphicsView(self)
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        main_layout.addWidget(self.view, stretch=4)

    # --- フォント設定イベントハンドラ ---
    def on_font_changed(self, font_name):
        self.current_font_family = font_name

    def on_size_changed(self, value):
        self.current_fontsize = value

    def choose_color(self):
        color = QColorDialog.getColor(
            self.current_fontcolor, self, "文字色の選択"
        )
        if color.isValid():
            self.current_fontcolor = color
            self.update_color_preview()

    def update_color_preview(self):
        """カラープレビューラベルの背景色を更新"""
        self.lbl_color_preview.setStyleSheet(
            f"background-color: {self.current_fontcolor.name()}; border: 1px solid #888;"
        )

    # --- モード切り替え関数 ---
    def set_add_text_mode(self):
        self.current_mode = "add_text"
        self.lbl_status.setText(
            "モード: テキスト追加\nPDF上をクリックして文字を入力してください。"
        )

    def set_delete_text_mode(self):
        self.current_mode = "delete_text"
        self.lbl_status.setText(
            "モード: テキスト削除\n消したい文字をドラッグして囲んでください。"
        )

    def set_add_image_mode(self):
        self.current_mode = "add_image"
        self.lbl_status.setText(
            "モード: 画像追加\nPDF上をクリックして挿入する画像を選んでください。"
        )

    def set_delete_image_mode(self):
        self.current_mode = "delete_image"
        self.lbl_status.setText(
            "モード: 画像削除\n消したい画像をドラッグして囲んでください。"
        )

    # --- PDF処理ロジック ---
    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "PDFファイルを開く", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.doc = fitz.open(file_path)
            self.current_page_idx = 0
            self.render_page()
            self.lbl_status.setText(
                "PDFを読み込みました。操作を選択してください。"
            )

    def render_page(self):
        if not self.doc:
            return

        self.scene.clear()
        page = self.doc[self.current_page_idx]

        # 画面表示用にPDFを画像化
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)

        fmt = (
            QImage.Format.Format_RGBA8888
            if pix.alpha
            else QImage.Format.Format_RGB888
        )
        qimg = QImage(
            pix.samples, pix.width, pix.height, pix.stride, fmt
        ).copy()
        qpixmap = QPixmap.fromImage(qimg)

        self.scene.addPixmap(qpixmap)
        self.scene.setSceneRect(0, 0, pix.width, pix.height)

        self.lbl_page.setText(
            f"ページ: {self.current_page_idx + 1} / {len(self.doc)}"
        )

    def prev_page(self):
        if self.doc and self.current_page_idx > 0:
            self.current_page_idx -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.current_page_idx < len(self.doc) - 1:
            self.current_page_idx += 1
            self.render_page()

    def get_font_file_path(self, font_family):
        """システム上のフォントファイルパスを検索するヘルパー関数"""
        search_dirs = []
        if sys.platform == "win32":
            search_dirs.append(
                os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
            )
        elif sys.platform == "darwin":
            search_dirs.extend(
                [
                    "/System/Library/Fonts",
                    "/Library/Fonts",
                    os.path.expanduser("~/Library/Fonts"),
                ]
            )
        else:
            search_dirs.extend(
                [
                    "/usr/share/fonts",
                    "/usr/local/share/fonts",
                    os.path.expanduser("~/.fonts"),
                    os.path.expanduser("~/.local/share/fonts"),
                ]
            )

        clean_name = font_family.lower().replace(" ", "")
        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for root, _, files in os.walk(d):
                for file in files:
                    if file.lower().endswith((".ttf", ".otf", ".ttc")):
                        if clean_name in file.lower().replace(" ", ""):
                            return os.path.join(root, file)
        return None

    # --- キャンバス上でのクリック・ドラッグ確定イベント ---
    def handle_canvas_click(self, x, y):
        """クリック位置（表示座標）に要素を追加する処理"""
        if not self.doc:
            return

        pdf_x = x / self.zoom
        pdf_y = y / self.zoom
        page = self.doc[self.current_page_idx]

        if self.current_mode == "add_text":
            text, ok = QInputDialog.getText(
                self, "テキスト追加", "追加する文字列を入力してください:"
            )
            if ok and text:
                # RGB色(0~255)を PyMuPDF 用の float(0.0~1.0) に変換
                r = self.current_fontcolor.red() / 255.0
                g = self.current_fontcolor.green() / 255.0
                b = self.current_fontcolor.blue() / 255.0
                color_tuple = (r, g, b)

                # 選択されたフォントのファイルパスを取得
                font_path = self.get_font_file_path(self.current_font_family)

                try:
                    if font_path and os.path.exists(font_path):
                        page.insert_text(
                            (pdf_x, pdf_y),
                            text,
                            fontfile=font_path,
                            fontsize=self.current_fontsize,
                            color=color_tuple,
                        )
                    else:
                        # システムフォントが見つからない場合は日本語組み込みフォントにフォールバック
                        page.insert_text(
                            (pdf_x, pdf_y),
                            text,
                            fontname="japan",
                            fontsize=self.current_fontsize,
                            color=color_tuple,
                        )
                except Exception:
                    # フォント読み込みエラー時の安全策
                    page.insert_text(
                        (pdf_x, pdf_y),
                        text,
                        fontname="japan",
                        fontsize=self.current_fontsize,
                        color=color_tuple,
                    )

                self.render_page()

        elif self.current_mode == "add_image":
            img_path, _ = QFileDialog.getOpenFileName(
                self, "画像を選択", "", "Images (*.png *.jpg *.jpeg)"
            )
            if img_path:
                rect = fitz.Rect(pdf_x, pdf_y, pdf_x + 150, pdf_y + 100)
                page.insert_image(rect, filename=img_path)
                self.render_page()

    def handle_canvas_rect(self, start_pos, end_pos):
        """ドラッグした領域（表示座標）を元に要素を削除する処理"""
        if not self.doc:
            return

        page = self.doc[self.current_page_idx]

        x1, y1 = start_pos.x() / self.zoom, start_pos.y() / self.zoom
        x2, y2 = end_pos.x() / self.zoom, end_pos.y() / self.zoom

        pdf_rect = fitz.Rect(
            min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        )

        if self.current_mode == "delete_text":
            page.add_redact_annot(pdf_rect)
            page.apply_redactions()
            self.render_page()
            QMessageBox.information(
                self, "完了", "指定エリアのテキストを削除しました。"
            )

        elif self.current_mode == "delete_image":
            image_list = page.get_images(full=True)
            deleted_any = False

            for img in image_list:
                xref = img[0]
                rects = page.get_image_rects(xref)
                for r in rects:
                    if pdf_rect.intersects(r):
                        page.delete_image(xref)
                        deleted_any = True
                        break

            if deleted_any:
                self.render_page()
                QMessageBox.information(
                    self, "完了", "選択エリアの画像を削除しました。"
                )
            else:
                page.add_redact_annot(pdf_rect)
                page.apply_redactions()
                self.render_page()
                QMessageBox.information(
                    self, "完了", "指定エリアの画像を隠蔽削除しました。"
                )

    def save_pdf(self):
        if not self.doc:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "PDFを保存", "", "PDF Files (*.pdf)"
        )
        if save_path:
            self.doc.save(save_path)
            QMessageBox.information(
                self, "成功", "PDFを別名で保存しました。"
            )


class EventGraphicsView(QGraphicsView):
    """プレビュー画面でのマウス操作を検知・処理するカスタムクラス"""

    def __init__(self, editor_app):
        super().__init__()
        self.editor = editor_app
        self.start_pos = None
        self.rect_item = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.mapToScene(event.position().toPoint())
            if self.editor.current_mode in ["delete_text", "delete_image"]:
                self.rect_item = QGraphicsRectItem()
                self.rect_item.setPen(
                    QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine)
                )
                self.editor.scene.addItem(self.rect_item)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_pos and self.rect_item:
            current_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.rect_item.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos:
            end_pos = self.mapToScene(event.position().toPoint())

            distance = (end_pos - self.start_pos).manhattanLength()
            if distance < 5:
                self.editor.handle_canvas_click(
                    self.start_pos.x(), self.start_pos.y()
                )
            else:
                if self.editor.current_mode in ["delete_text", "delete_image"]:
                    self.editor.handle_canvas_rect(self.start_pos, end_pos)

            if self.rect_item:
                self.editor.scene.removeItem(self.rect_item)
                self.rect_item = None
                self.start_pos = None

        super().mouseReleaseEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = PDFEditorApp()
    editor.show()
    sys.exit(app.exec())
