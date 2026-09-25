"""Tela de detalhes: capa grande e descrição da HQ, com o progresso e o botão de leitura."""

import html

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database.database import ComicRecord
from app.library.online import SOURCE_NAMES
from app.library.scanner import Comic
from app.ui import theme

COVER_SIZE = QSize(300, 450)
TEXT_MAX_WIDTH = 720
BACKDROP_HEIGHT = 440


def describe_progress(record: ComicRecord | None) -> str:
    if record is None or not record.started:
        return "Não iniciada"
    if record.finished:
        return "Lida"
    return f"Página {record.last_page + 1} de {record.page_count}"


def describe_source(record: ComicRecord) -> str:
    """Crédito da descrição em HTML; o GCD exige atribuição (CC BY-SA 4.0)."""
    source = record.metadata_source or ""
    if source == "manual":
        return "Editada por você"
    names = [SOURCE_NAMES[part] for part in source.split("+") if part in SOURCE_NAMES]
    if not names:
        return ""
    text = "Fonte: " + " e ".join(names)
    if "gcd" in source:
        text += " (CC BY-SA 4.0)"
    if record.source_url:
        text += f' · <a href="{html.escape(record.source_url)}" style="color: {theme.ACCENT};">ver no site</a>'
    return text


def summary_html(summary: str) -> str:
    paragraphs = [html.escape(part.strip()).replace("\n", "<br>") for part in summary.split("\n\n") if part.strip()]
    return "".join(f'<p style="line-height: 145%; margin-bottom: 12px;">{part}</p>' for part in paragraphs)


def rounded(pixmap: QPixmap, radius: float) -> QPixmap:
    result = QPixmap(pixmap.size())
    result.setDevicePixelRatio(pixmap.devicePixelRatio())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.deviceIndependentSize().width(), pixmap.deviceIndependentSize().height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return result


class DetailsPage(QWidget):
    back_requested = Signal()
    read_requested = Signal(bool)  # True = recomeçar da primeira página
    lookup_requested = Signal()
    edit_requested = Signal()
    cover_choice_changed = Signal(bool)  # True = usar a capa online

    def __init__(self):
        super().__init__()
        self.backdrop = QPixmap()
        self.backdrop_scaled = QPixmap()

        scroll = QScrollArea()
        scroll.setObjectName("detailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        self.scroll = scroll
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("detailsContent")
        page = QVBoxLayout(content)
        page.setContentsMargins(40, 24, 40, 40)
        page.setSpacing(24)
        scroll.setWidget(content)

        back = QPushButton("← Biblioteca")
        back.setObjectName("flat")
        back.setToolTip("Voltar para a biblioteca (Esc)")
        back.clicked.connect(self.back_requested)
        page.addWidget(back, alignment=Qt.AlignLeft)

        body = QHBoxLayout()
        body.setSpacing(40)
        page.addLayout(body)
        page.addStretch()

        # ---------- coluna da capa ----------
        cover_column = QVBoxLayout()
        cover_column.setSpacing(12)
        self.cover = QLabel()
        self.cover.setFixedSize(COVER_SIZE)
        self.cover.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        shadow = QGraphicsDropShadowEffect(blurRadius=40, xOffset=0, yOffset=12, color=QColor(0, 0, 0, 180))
        self.cover.setGraphicsEffect(shadow)
        cover_column.addWidget(self.cover)

        self.cover_choice = QWidget()
        choice_layout = QHBoxLayout(self.cover_choice)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(0)
        self.file_cover_button = QPushButton("Capa do arquivo")
        self.online_cover_button = QPushButton("Capa online")
        group = QButtonGroup(self)
        for position, button in (("left", self.file_cover_button), ("right", self.online_cover_button)):
            button.setObjectName("segment")
            button.setProperty("position", position)
            button.setCheckable(True)
            group.addButton(button)
            choice_layout.addWidget(button)
        self.online_cover_button.toggled.connect(self._cover_toggled)
        cover_column.addWidget(self.cover_choice)
        cover_column.addStretch()
        body.addLayout(cover_column)

        # ---------- coluna do texto ----------
        info = QVBoxLayout()
        info.setSpacing(10)
        body.addLayout(info, 1)

        self.title = self._label("detailsTitle")
        self.subtitle = self._label("detailsMeta")
        self.writer = self._label("muted")
        info.addWidget(self.title)
        info.addWidget(self.subtitle)
        info.addWidget(self.writer)
        info.addSpacing(8)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(220)
        self.progress_label = self._label("muted")
        self.progress_label.setWordWrap(False)
        progress_row.addWidget(self.progress)
        progress_row.addWidget(self.progress_label)
        progress_row.addStretch()
        info.addLayout(progress_row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.read_button = QPushButton()
        self.read_button.setObjectName("primary")
        self.read_button.setMinimumHeight(38)
        self.read_button.clicked.connect(lambda: self.read_requested.emit(False))
        self.restart_button = QPushButton("Ler do início")
        self.restart_button.setMinimumHeight(38)
        self.restart_button.clicked.connect(lambda: self.read_requested.emit(True))
        buttons.addWidget(self.read_button)
        buttons.addWidget(self.restart_button)
        buttons.addStretch()
        info.addLayout(buttons)
        info.addSpacing(18)

        info.addWidget(self._label("section", "DESCRIÇÃO"))
        self.summary = self._label("summary")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary.setMaximumWidth(TEXT_MAX_WIDTH)
        info.addWidget(self.summary)

        self.source = self._label("muted")
        self.source.setTextFormat(Qt.RichText)
        self.source.setOpenExternalLinks(True)
        info.addWidget(self.source)
        info.addSpacing(6)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.lookup_button = QPushButton("Buscar online")
        self.lookup_button.setToolTip("Busca descrição e capa no Grand Comics Database (e no ComicVine, se configurado)")
        self.lookup_button.clicked.connect(self.lookup_requested)
        edit_button = QPushButton("Editar")
        edit_button.clicked.connect(self.edit_requested)
        actions.addWidget(self.lookup_button)
        actions.addWidget(edit_button)
        actions.addStretch()
        info.addLayout(actions)
        info.addStretch()

        for keys, slot in (
            ((Qt.Key_Escape, Qt.Key_Backspace), self.back_requested.emit),
            ((Qt.Key_Return, Qt.Key_Enter), lambda: self.read_requested.emit(False)),
        ):
            for key in keys:
                QShortcut(QKeySequence(key), self, slot, context=Qt.WidgetWithChildrenShortcut)

    @staticmethod
    def _label(name: str = "", text: str = "") -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        if name:
            label.setObjectName(name)
        return label

    # ---------- conteúdo ----------

    def show_comic(self, comic: Comic, record: ComicRecord | None):
        metadata = record.metadata if record else None
        self.title.setText(comic.title)

        meta = []
        if metadata and metadata.number:
            meta.append(f"{metadata.series} #{metadata.number}")
        elif metadata and metadata.series and metadata.series != comic.title:
            meta.append(metadata.series)
        if metadata and metadata.year:
            meta.append(str(metadata.year))
        if metadata and metadata.publisher:
            meta.append(metadata.publisher)
        if record and record.page_count:
            meta.append(f"{record.page_count} páginas")
        self.subtitle.setText("  •  ".join(meta))
        self.subtitle.setVisible(bool(meta))
        self.writer.setText(f"Roteiro: {metadata.writer}" if metadata and metadata.writer else "")
        self.writer.setVisible(bool(metadata and metadata.writer))

        started = bool(record and record.started)
        self.progress.setValue(round((record.progress if record else 0) * 100))
        self.progress.setVisible(started)
        self.progress_label.setText(describe_progress(record))
        if record and record.finished:
            self.read_button.setText("Ler novamente")
        elif started:
            self.read_button.setText(f"Continuar lendo  ·  pág. {record.last_page + 1}")
        else:
            self.read_button.setText("Começar a ler")
        self.restart_button.setVisible(started and not record.finished)

        if metadata and metadata.summary:
            self.summary.setText(summary_html(metadata.summary))
            self.summary.setProperty("empty", False)
        else:
            self.summary.setText("Esta HQ ainda não tem descrição. Use “Buscar online” ou “Editar” para adicionar uma.")
            self.summary.setProperty("empty", True)
        self.summary.style().polish(self.summary)
        source = describe_source(record) if record else ""
        self.source.setText(source)
        self.source.setVisible(bool(source))

        has_online = bool(record and record.online_cover)
        self.cover_choice.setVisible(has_online)
        self.online_cover_button.blockSignals(True)
        (self.online_cover_button if record and record.use_online_cover else self.file_cover_button).setChecked(True)
        self.online_cover_button.blockSignals(False)
        self._show_cover(record.display_cover if record else None)

    def scroll_to_top(self):
        self.scroll.verticalScrollBar().setValue(0)

    def _cover_toggled(self, use_online: bool):
        self.cover_choice_changed.emit(use_online)

    def _show_cover(self, data: bytes | None):
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            self.cover.setPixmap(QPixmap())
            self.cover.setText("Carregando capa…")
            self.backdrop = QPixmap()
            self._scale_backdrop()
            return

        ratio = self.devicePixelRatioF()
        scaled = pixmap.scaled(COVER_SIZE * ratio, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        self.cover.setPixmap(rounded(scaled, 8))
        # Uma versão minúscula da capa, ampliada depois, vira um fundo desfocado
        self.backdrop = pixmap.scaled(24, 36, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self._scale_backdrop()

    def set_looking_up(self, busy: bool):
        self.lookup_button.setEnabled(not busy)
        self.lookup_button.setText("Buscando…" if busy else "Buscar online")

    # ---------- fundo ----------

    def _scale_backdrop(self):
        if self.backdrop.isNull():
            self.backdrop_scaled = QPixmap()
        else:
            size = QSize(self.width(), BACKDROP_HEIGHT)
            self.backdrop_scaled = self.backdrop.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_backdrop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BACKGROUND))
        if self.backdrop_scaled.isNull():
            return
        area = QRect(0, 0, self.width(), BACKDROP_HEIGHT)
        source = QRect(
            (self.backdrop_scaled.width() - area.width()) // 2,
            (self.backdrop_scaled.height() - area.height()) // 3,
            area.width(),
            area.height(),
        )
        painter.setOpacity(0.35)
        painter.drawPixmap(area, self.backdrop_scaled, source)
        painter.setOpacity(1)
        fade = QLinearGradient(0, 0, 0, BACKDROP_HEIGHT)
        fade.setColorAt(0, QColor(0, 0, 0, 0))
        fade.setColorAt(1, QColor(theme.BACKGROUND))
        painter.fillRect(area, fade)
