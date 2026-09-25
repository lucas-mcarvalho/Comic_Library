"""Janela principal: biblioteca com as capas das HQs encontradas."""

import os

from PySide6.QtCore import QObject, QRect, QRunnable, QSettings, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.library.scanner import Comic, scan_folder
from app.reader.document import render_cover
from app.ui import theme
from app.ui.reader_window import ReaderWindow

COVER_SIZE = QSize(160, 240)
CARD_PADDING = 10
TITLE_LINES = 2


class CoverSignals(QObject):
    loaded = Signal(int, int, bytes)


class CoverLoader(QRunnable):
    """Renderiza a capa fora da thread da interface."""

    def __init__(self, generation: int, row: int, comic: Comic):
        super().__init__()
        self.generation = generation
        self.row = row
        self.comic = comic
        self.signals = CoverSignals()

    def run(self):
        try:
            png = render_cover(self.comic.path, max_width=COVER_SIZE.width() * 2)
        except Exception:
            return  # arquivo corrompido ou ilegível: mantém sem capa
        self.signals.loaded.emit(self.generation, self.row, png)


class ComicCardDelegate(QStyledItemDelegate):
    """Desenha cada HQ como um cartão: capa arredondada, formato e título."""

    def sizeHint(self, option, index):
        title_height = option.fontMetrics.lineSpacing() * TITLE_LINES
        return QSize(
            COVER_SIZE.width() + CARD_PADDING * 2,
            COVER_SIZE.height() + title_height + CARD_PADDING * 3,
        )

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        card = option.rect.adjusted(4, 4, -4, -4)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.SURFACE_HOVER))
            painter.drawRoundedRect(card, 10, 10)

        cover = QRect(
            card.center().x() - COVER_SIZE.width() // 2,
            card.top() + CARD_PADDING - 4,
            COVER_SIZE.width(),
            COVER_SIZE.height(),
        )
        clip = QPainterPath()
        clip.addRoundedRect(cover, 6, 6)
        painter.setClipPath(clip)

        comic: Comic = index.data(Qt.UserRole)
        pixmap = index.data(Qt.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            painter.drawPixmap(cover, pixmap)
        else:
            painter.fillRect(cover, QColor(theme.SURFACE))
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(cover, Qt.AlignCenter, "Carregando…")
        painter.setClipping(False)

        if selected:
            painter.setPen(QPen(QColor(theme.ACCENT), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cover.adjusted(1, 1, -1, -1), 6, 6)

        self._paint_badge(painter, cover, comic.path.suffix[1:].upper())

        title = QRect(
            cover.left(),
            cover.bottom() + 8,
            cover.width(),
            option.fontMetrics.lineSpacing() * TITLE_LINES,
        )
        painter.setPen(QColor(theme.TEXT))
        painter.setFont(option.font)
        painter.drawText(title, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, comic.title)
        painter.restore()

    def _paint_badge(self, painter: QPainter, cover: QRect, label: str):
        font = QFont(painter.font())
        font.setPointSizeF(font.pointSizeF() * 0.75)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(label) + 10
        badge = QRect(cover.right() - width - 6, cover.top() + 6, width, painter.fontMetrics().height() + 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(QColor("white"))
        painter.drawText(badge, Qt.AlignCenter, label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Library")
        self.resize(1100, 750)

        self.settings = QSettings("ComicLibrary", "ComicLibrary")
        self.thread_pool = QThreadPool.globalInstance()
        self.cover_generation = 0
        self.folder = ""
        self.reader: ReaderWindow | None = None

        self._build_toolbar()

        self.comic_list = QListWidget()
        self.comic_list.setViewMode(QListView.IconMode)
        self.comic_list.setResizeMode(QListView.Adjust)
        self.comic_list.setMovement(QListView.Static)
        self.comic_list.setUniformItemSizes(True)
        self.comic_list.setSpacing(6)
        self.comic_list.setMouseTracking(True)
        self.comic_list.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.comic_list.setItemDelegate(ComicCardDelegate(self.comic_list))
        self.comic_list.itemActivated.connect(self.open_comic)

        self.stack = QStackedWidget()
        self.empty_page = self._build_empty_page()
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.comic_list)
        self.setCentralWidget(self.stack)

        self.statusBar().showMessage("Selecione uma pasta com HQs (PDF, CBR, CBZ).")

        # COMIC_LIBRARY_FOLDER define a pasta inicial quando nenhuma foi escolhida ainda (usado no Docker)
        last_folder = self.settings.value("library/folder") or os.environ.get("COMIC_LIBRARY_FOLDER")
        if last_folder:
            self.load_folder(last_folder)

    def _build_toolbar(self):
        toolbar = QToolBar("Biblioteca")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        title = QLabel("Comic Library")
        title.setStyleSheet("font-size: 16px; font-weight: 700; padding: 0 8px;")
        toolbar.addWidget(title)

        open_button = QPushButton("Abrir pasta")
        open_button.setObjectName("primary")
        open_button.clicked.connect(self.select_folder)
        toolbar.addWidget(open_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar HQ…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.filter_comics)
        toolbar.addWidget(self.search)

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self.empty_title = QLabel("Sua biblioteca está vazia")
        self.empty_title.setObjectName("title")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_subtitle = QLabel("Escolha uma pasta com HQs em PDF, CBR ou CBZ.")
        self.empty_subtitle.setObjectName("muted")
        self.empty_subtitle.setAlignment(Qt.AlignCenter)

        button = QPushButton("Selecionar pasta")
        button.setObjectName("primary")
        button.clicked.connect(self.select_folder)

        layout.addWidget(self.empty_title)
        layout.addWidget(self.empty_subtitle)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        return page

    def select_folder(self):
        start = self.settings.value("library/folder", "")
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta de HQs", start)
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder: str):
        try:
            comics = scan_folder(folder)
        except OSError as error:
            QMessageBox.warning(self, "Erro", str(error))
            return

        self.settings.setValue("library/folder", folder)
        self.folder = folder
        self.show_comics(comics)

    def show_comics(self, comics: list[Comic]):
        # Capas de uma pasta anterior que ainda estejam carregando são descartadas
        self.cover_generation += 1
        self.thread_pool.clear()
        self.comic_list.clear()
        self.search.clear()

        for row, comic in enumerate(comics):
            item = QListWidgetItem(comic.title)
            item.setData(Qt.UserRole, comic)
            item.setToolTip(str(comic.path))
            self.comic_list.addItem(item)

            loader = CoverLoader(self.cover_generation, row, comic)
            loader.signals.loaded.connect(self.set_cover)
            self.thread_pool.start(loader)

        if comics:
            self.stack.setCurrentWidget(self.comic_list)
        else:
            self.empty_title.setText("Nenhuma HQ encontrada")
            self.empty_subtitle.setText(f"Não há arquivos PDF, CBR ou CBZ em {self.folder}")
            self.stack.setCurrentWidget(self.empty_page)
        self.update_status()

    def set_cover(self, generation: int, row: int, png: bytes):
        item = self.comic_list.item(row)
        if generation != self.cover_generation or item is None:
            return

        source = QPixmap()
        source.loadFromData(png, "PNG")
        ratio = self.devicePixelRatioF()
        target = COVER_SIZE * ratio
        # Preenche o cartão todo, cortando as sobras e mantendo o topo da capa
        scaled = source.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        cover = scaled.copy((scaled.width() - target.width()) // 2, 0, target.width(), target.height())
        cover.setDevicePixelRatio(ratio)
        item.setData(Qt.DecorationRole, cover)

    def filter_comics(self, text: str):
        query = text.strip().lower()
        for row in range(self.comic_list.count()):
            item = self.comic_list.item(row)
            item.setHidden(query not in item.text().lower())
        self.update_status()

    def update_status(self):
        total = self.comic_list.count()
        visible = sum(not self.comic_list.item(row).isHidden() for row in range(total))
        count = f"{total} HQ(s)" if visible == total else f"{visible} de {total} HQ(s)"
        self.statusBar().showMessage(f"{count}  •  {self.folder}")

    def open_comic(self, item: QListWidgetItem):
        comic: Comic = item.data(Qt.UserRole)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            reader = ReaderWindow(comic)
        except Exception as error:
            QMessageBox.warning(self, "Erro ao abrir", f"Não foi possível abrir {comic.title}:\n{error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if self.reader is not None:
            self.reader.close()
        self.reader = reader
        self.reader.show()

    def closeEvent(self, event):
        # Descarta as capas na fila e espera as que já estão sendo geradas
        self.thread_pool.clear()
        self.thread_pool.waitForDone()
        if self.reader is not None:
            self.reader.close()
        super().closeEvent(event)
