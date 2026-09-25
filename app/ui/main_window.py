"""Janela principal: biblioteca com as capas das HQs encontradas."""

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QRunnable, QSettings, QSize, QStandardPaths, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
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

from app.database.database import ComicRecord, Library
from app.library import online
from app.library.metadata import Metadata
from app.library.scanner import Comic, scan_folder
from app.reader.document import read_details
from app.ui import theme
from app.ui.details_page import DetailsPage, describe_progress
from app.ui.metadata_dialog import MetadataDialog
from app.ui.reader_window import ReaderWindow
from app.ui.settings_dialog import SettingsDialog

COVER_SIZE = QSize(160, 240)
# Largura com que a capa é guardada no banco: nítida no cartão e na tela de detalhes
STORED_COVER_WIDTH = 400
CARD_PADDING = 10
TITLE_LINES = 2
PROGRESS_ROLE = Qt.UserRole + 1
# Segundos de pausa entre uma HQ e outra no "Buscar descrições"
LOOKUP_DELAY = 2.0


def database_path() -> Path:
    data_dir = QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
    return Path(data_dir) / "ComicLibrary" / "library.db"


class DetailsSignals(QObject):
    loaded = Signal(int, str, bytes, int, object)


class DetailsLoader(QRunnable):
    """Extrai capa, total de páginas e metadados fora da thread da interface."""

    def __init__(self, generation: int, comic: Comic):
        super().__init__()
        self.generation = generation
        self.comic = comic
        self.signals = DetailsSignals()

    def run(self):
        try:
            cover, page_count, metadata = read_details(self.comic.path, max_width=STORED_COVER_WIDTH)
        except Exception:
            return  # arquivo corrompido ou ilegível: mantém sem capa
        self.signals.loaded.emit(self.generation, str(self.comic.path), cover, page_count, metadata)


class LookupSignals(QObject):
    found = Signal(str, object)  # caminho, OnlineResult ou None (não encontrada)
    failed = Signal(str, str, bool)  # caminho, mensagem, se a busca inteira parou por causa do erro
    progress = Signal(int, int)  # concluídas, total
    finished = Signal()


@dataclass
class LookupJob:
    path: Path
    metadata: Metadata
    cover: bytes | None  # capa do arquivo, para escolher a edição certa entre séries de mesmo nome


class LookupWorker(QRunnable):
    """Busca descrição e capa online de uma ou várias HQs, uma de cada vez, sem travar a interface."""

    def __init__(self, jobs: list[LookupJob], comicvine_key: str, gcd_login: tuple[str, str] | None):
        super().__init__()
        self.jobs = jobs
        self.comicvine_key = comicvine_key
        self.gcd_login = gcd_login
        self.cancelled = threading.Event()
        self.signals = LookupSignals()

    def run(self):
        for done, job in enumerate(self.jobs):
            # Pausa entre buscas para respeitar os limites do GCD e do ComicVine
            if self.cancelled.is_set() or (done and self.cancelled.wait(LOOKUP_DELAY)):
                break
            try:
                result = online.lookup(
                    job.metadata.series,
                    job.metadata.number,
                    job.metadata.year,
                    job.cover,
                    self.comicvine_key,
                    self.gcd_login,
                )
            except (online.RateLimitError, online.InvalidKeyError, online.InvalidLoginError) as error:
                self.signals.failed.emit(str(job.path), str(error), True)
                break
            except online.OnlineError as error:
                self.signals.failed.emit(str(job.path), str(error), len(self.jobs) == 1)
            except Exception as error:
                self.signals.failed.emit(str(job.path), f"Erro inesperado: {error}", len(self.jobs) == 1)
            else:
                self.signals.found.emit(str(job.path), result)
            self.signals.progress.emit(done + 1, len(self.jobs))
        self.signals.finished.emit()


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
        progress = index.data(PROGRESS_ROLE) or 0.0
        if progress > 0:
            bar = QRect(cover.left(), cover.bottom() - 4, cover.width(), 5)
            painter.fillRect(bar, QColor(0, 0, 0, 170))
            painter.fillRect(bar.adjusted(0, 0, -round(bar.width() * (1 - progress)), 0), QColor(theme.ACCENT))
        painter.setClipping(False)

        if selected:
            painter.setPen(QPen(QColor(theme.ACCENT), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cover.adjusted(1, 1, -1, -1), 6, 6)

        self._paint_badge(painter, cover, comic.path.suffix[1:].upper())
        if progress >= 1:
            self._paint_badge(painter, cover, "LIDA", left=True)

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

    def _paint_badge(self, painter: QPainter, cover: QRect, label: str, left: bool = False):
        painter.save()
        font = QFont(painter.font())
        font.setPointSizeF(font.pointSizeF() * 0.75)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(label) + 10
        x = cover.left() + 6 if left else cover.right() - width - 6
        badge = QRect(x, cover.top() + 6, width, painter.fontMetrics().height() + 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(QColor("white"))
        painter.drawText(badge, Qt.AlignCenter, label)
        painter.restore()


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
        self.library = Library(database_path())
        self.records: dict[Path, ComicRecord] = {}
        self.items: dict[Path, QListWidgetItem] = {}
        self.current: Comic | None = None  # HQ aberta na tela de detalhes
        self.lookup_worker: LookupWorker | None = None
        self.lookup_pending: set[Path] = set()  # HQs na fila da busca online em andamento
        self.lookup_single = False
        self.lookup_errors: list[str] = []
        self.lookup_found_count = 0

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
        self.comic_list.itemClicked.connect(lambda item: self.show_details(item.data(Qt.UserRole)))
        self.comic_list.itemActivated.connect(lambda item: self.show_details(item.data(Qt.UserRole)))

        self.details = DetailsPage()
        self.details.back_requested.connect(self.show_library)
        self.details.read_requested.connect(lambda from_start: self.open_comic(self.current, from_start))
        self.details.lookup_requested.connect(self.lookup_current)
        self.details.edit_requested.connect(self.edit_current)
        self.details.cover_choice_changed.connect(self.set_use_online_cover)

        self.stack = QStackedWidget()
        self.empty_page = self._build_empty_page()
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.comic_list)
        self.stack.addWidget(self.details)
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

        self.lookup_all_button = QPushButton("Buscar descrições")
        self.lookup_all_button.setToolTip("Busca online a descrição e a capa das HQs que ainda não têm descrição")
        self.lookup_all_button.clicked.connect(self.toggle_lookup_all)
        toolbar.addWidget(self.lookup_all_button)

        settings_button = QPushButton("Configurações")
        settings_button.setToolTip("Login do Grand Comics Database e chave do ComicVine")
        settings_button.clicked.connect(self.open_settings)
        toolbar.addWidget(settings_button)

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

    # ---------- biblioteca ----------

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
        # Capas e buscas de uma pasta anterior que ainda estejam em andamento são descartadas
        self.cover_generation += 1
        self.stop_lookup()
        self.thread_pool.clear()
        self.comic_list.clear()
        self.items.clear()
        self.current = None
        self.search.clear()
        self.records = self.library.sync(comics)

        for comic in comics:
            item = QListWidgetItem(comic.title)
            item.setData(Qt.UserRole, comic)
            self.comic_list.addItem(item)
            self.items[comic.path] = item

            record = self.records[comic.path]
            self._refresh_item(item, record)
            if record.needs_scan:
                loader = DetailsLoader(self.cover_generation, comic)
                loader.signals.loaded.connect(self.save_details)
                self.thread_pool.start(loader)

        if comics:
            self.stack.setCurrentWidget(self.comic_list)
        else:
            self.empty_title.setText("Nenhuma HQ encontrada")
            self.empty_subtitle.setText(f"Não há arquivos PDF, CBR ou CBZ em {self.folder}")
            self.stack.setCurrentWidget(self.empty_page)
        self.update_status()

    def save_details(self, generation: int, path: str, cover: bytes, page_count: int, metadata: Metadata):
        if generation != self.cover_generation:
            return
        path = Path(path)
        self.library.save_scan(path, cover, page_count, metadata)
        self._reload_record(path)

    def _refresh_item(self, item: QListWidgetItem, record: ComicRecord):
        item.setData(PROGRESS_ROLE, record.progress)
        comic: Comic = item.data(Qt.UserRole)
        item.setToolTip(f"{comic.path}\n{describe_progress(record)}")
        if record.display_cover is not None:
            item.setData(Qt.DecorationRole, self._card_cover(record.display_cover))

    def _card_cover(self, data: bytes) -> QPixmap:
        source = QPixmap()
        source.loadFromData(data)
        ratio = self.devicePixelRatioF()
        target = COVER_SIZE * ratio
        # Preenche o cartão todo, cortando as sobras e mantendo o topo da capa
        scaled = source.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        cover = scaled.copy((scaled.width() - target.width()) // 2, 0, target.width(), target.height())
        cover.setDevicePixelRatio(ratio)
        return cover

    def _reload_record(self, path: Path):
        record = self.library.get(path)
        if record is None:
            return
        self.records[path] = record
        if path in self.items:
            self._refresh_item(self.items[path], record)
        if self.current is not None and self.current.path == path:
            self.update_details()

    def filter_comics(self, text: str):
        if text and self.stack.currentWidget() is self.details:
            self.show_library()
        query = text.strip().lower()
        for row in range(self.comic_list.count()):
            item = self.comic_list.item(row)
            item.setHidden(query not in item.text().lower())
        self.update_status()

    def update_status(self):
        if self.lookup_worker is not None:
            return  # a busca online mostra o próprio progresso
        total = self.comic_list.count()
        visible = sum(not self.comic_list.item(row).isHidden() for row in range(total))
        count = f"{total} HQ(s)" if visible == total else f"{visible} de {total} HQ(s)"
        self.statusBar().showMessage(f"{count}  •  {self.folder}")

    # ---------- tela de detalhes ----------

    def show_details(self, comic: Comic):
        self.current = comic
        self.update_details()
        self.details.scroll_to_top()
        self.stack.setCurrentWidget(self.details)
        self.details.setFocus()

    def update_details(self):
        if self.current is None:
            return
        self.details.show_comic(self.current, self.records.get(self.current.path))
        self.details.set_looking_up(self.current.path in self.lookup_pending)

    def show_library(self):
        self.stack.setCurrentWidget(self.comic_list)
        if self.current is not None and self.current.path in self.items:
            self.comic_list.setCurrentItem(self.items[self.current.path])
            self.comic_list.scrollToItem(self.items[self.current.path])
        self.comic_list.setFocus()

    def edit_current(self):
        record = self.records.get(self.current.path) if self.current else None
        if record is None:
            return
        dialog = MetadataDialog(self.current.title, record.metadata, self)
        if dialog.exec() == QDialog.Accepted:
            self.library.save_metadata(self.current.path, dialog.metadata(), "manual")
            self._reload_record(self.current.path)

    def set_use_online_cover(self, use: bool):
        if self.current is not None:
            self.library.set_use_online_cover(self.current.path, use)
            self._reload_record(self.current.path)

    # ---------- leitura ----------

    def open_comic(self, comic: Comic | None, from_start: bool = False):
        if comic is None:
            return
        # Continua de onde parou, a não ser que a HQ já tenha sido lida até o fim
        record = self.records.get(comic.path)
        start_page = 0 if from_start or record is None or record.finished else record.last_page

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            reader = ReaderWindow(comic, start_page)
        except Exception as error:
            QMessageBox.warning(self, "Erro ao abrir", f"Não foi possível abrir {comic.title}:\n{error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if self.reader is not None:
            self.reader.close()
        self.reader = reader
        self.reader.page_changed.connect(self.save_progress)
        self.save_progress(comic, reader.page_index, reader.document.page_count)
        self.reader.show()

    def save_progress(self, comic: Comic, page: int, page_count: int):
        self.library.save_progress(comic.path, page, page_count)
        self._reload_record(comic.path)

    # ---------- busca online ----------

    def open_settings(self):
        SettingsDialog(self.settings, self).exec()

    def _credentials(self) -> tuple[str, tuple[str, str] | None]:
        key = self.settings.value("comicvine/api_key") or os.environ.get("COMICVINE_API_KEY", "")
        user, password = self.settings.value("gcd/user", ""), self.settings.value("gcd/password", "")
        return key, (user, password) if user and password else None

    def _job(self, path: Path) -> LookupJob:
        record = self.records[path]
        return LookupJob(path, record.metadata, record.cover)

    def lookup_current(self):
        record = self.records.get(self.current.path) if self.current else None
        if record is None or self.lookup_worker is not None:
            return
        if not record.metadata.series or not record.metadata.number:
            QMessageBox.information(
                self, "Buscar online", "Informe a série e o número da HQ em “Editar” para poder buscar."
            )
            return
        self.start_lookup([self._job(self.current.path)])

    def toggle_lookup_all(self):
        if self.lookup_worker is not None:
            self.stop_lookup()
            return

        # Só as que nunca foram buscadas, não foram editadas à mão e ainda não têm descrição
        paths = [
            path
            for path, record in self.records.items()
            if record.looked_up_at is None
            and record.metadata_source not in (None, "manual")
            and not record.metadata.summary
            and record.metadata.series
            and record.metadata.number
        ]
        if not paths:
            QMessageBox.information(
                self,
                "Buscar descrições",
                "Todas as HQs já têm descrição ou já foram buscadas.\n"
                "Para buscar uma HQ de novo, abra a tela dela e use “Buscar online”.",
            )
            return
        self.start_lookup([self._job(path) for path in sorted(paths, key=lambda path: path.name.lower())])

    def start_lookup(self, jobs: list[LookupJob]):
        comicvine_key, gcd_login = self._credentials()
        worker = LookupWorker(jobs, comicvine_key, gcd_login)
        worker.signals.found.connect(self.lookup_found)
        worker.signals.failed.connect(self.lookup_failed)
        worker.signals.progress.connect(self.lookup_progress)
        worker.signals.finished.connect(self.lookup_finished)
        self.lookup_worker = worker
        self.lookup_single = len(jobs) == 1
        self.lookup_pending = {job.path for job in jobs}
        self.lookup_errors = []
        self.lookup_found_count = 0
        self.update_details()
        self.lookup_progress(0, len(jobs))
        self.thread_pool.start(worker)

    def stop_lookup(self):
        if self.lookup_worker is not None:
            self.lookup_worker.cancelled.set()
            self.lookup_all_button.setText("Parando…")

    def lookup_progress(self, done: int, total: int):
        if self.lookup_single:
            name = next(iter(self.lookup_pending), Path()).stem
            self.statusBar().showMessage(f"Buscando “{name}” online…")
        else:
            self.lookup_all_button.setText(f"Parar busca ({done}/{total})")
            self.statusBar().showMessage(f"Buscando descrições online: {done} de {total}…")

    def lookup_found(self, path: str, result: online.OnlineResult | None):
        path = Path(path)
        self.lookup_pending.discard(path)
        record = self.records.get(path)
        if record is None:
            return
        if result is None:
            self.library.mark_looked_up(path)
            if self.lookup_single:
                QMessageBox.information(
                    self,
                    "Buscar online",
                    f"Nada encontrado para “{record.metadata.series} #{record.metadata.number}”.\n"
                    "Confira a série, o número e o ano em “Editar” e tente de novo.",
                )
        else:
            # Campos que a fonte online não trouxe mantêm o que já existia
            found, old = result.metadata, record.metadata
            found.writer = found.writer or old.writer
            found.publisher = found.publisher or old.publisher
            found.summary = found.summary or old.summary
            self.library.save_online(path, found, result.source, result.source_url, result.cover)
            self.lookup_found_count += 1
        self._reload_record(path)

    def lookup_failed(self, path: str, message: str, stops: bool):
        self.lookup_pending.discard(Path(path))
        if stops:
            self.lookup_errors.append(message)
        if self.current is not None and self.current.path == Path(path):
            self.update_details()

    def lookup_finished(self):
        single, errors, found = self.lookup_single, self.lookup_errors, self.lookup_found_count
        self.lookup_worker = None
        self.lookup_pending.clear()
        self.lookup_all_button.setText("Buscar descrições")
        self.update_details()
        self.update_status()

        if errors:
            text = errors[0]
            if "GCD" in text or "Grand Comics" in text or "ComicVine" in text:
                text += "\n\nO login do GCD e a chave do ComicVine ficam em Configurações."
            if not single:
                text = f"Busca interrompida depois de {found} descrição(ões) encontrada(s).\n\n{text}"
            QMessageBox.warning(self, "Buscar online", text)
        elif not single:
            self.statusBar().showMessage(f"Busca concluída: {found} HQ(s) atualizada(s).", 8000)

    def closeEvent(self, event):
        # Descarta as capas na fila e espera as tarefas que já estão rodando
        self.stop_lookup()
        self.thread_pool.clear()
        self.thread_pool.waitForDone()
        if self.reader is not None:
            self.reader.close()
        self.library.close()
        super().closeEvent(event)
