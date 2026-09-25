"""Janela de leitura de uma HQ, página por página."""

from collections import OrderedDict
from enum import Enum

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QScrollArea, QSizePolicy, QSlider, QToolBar, QWidget

from app.library.scanner import Comic
from app.reader.document import open_document

CACHE_SIZE = 6
ZOOM_STEP = 1.25
MIN_ZOOM, MAX_ZOOM = 0.1, 8.0


class FitMode(Enum):
    PAGE = "page"
    WIDTH = "width"
    ZOOM = "zoom"


class ReaderWindow(QMainWindow):
    # (hq, página atual, total de páginas): emitido a cada troca de página, para salvar o progresso
    page_changed = Signal(object, int, int)

    def __init__(self, comic: Comic, start_page: int = 0):
        super().__init__()
        self.comic = comic
        self.setWindowTitle(f"{comic.title} — Comic Library")
        self.resize(1000, 900)

        self.document = open_document(comic.path)
        if self.document.page_count == 0:
            raise ValueError("o arquivo não tem páginas")

        self.page_index = 0
        self.fit_mode = FitMode.PAGE
        self.zoom = 1.0
        self.wheel_delta = 0
        self.closed = False
        self.cache: OrderedDict[int, QImage] = OrderedDict()

        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignCenter)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.page_label)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        self.scroll.viewport().installEventFilter(self)
        self.setCentralWidget(self.scroll)

        # Reescala a página só quando o redimensionamento da janela termina
        self.resize_timer = QTimer(self, singleShot=True, interval=40)
        self.resize_timer.timeout.connect(self.display_page)

        self._build_actions()
        self._build_top_bar(comic.title)
        self._build_bottom_bar()
        self.set_fit_mode(FitMode.PAGE)
        self.go_to_page(start_page)

    # ---------- construção da interface ----------

    def _action(self, text, slot, shortcuts=(), checkable=False, tip=None) -> QAction:
        action = QAction(text, self)
        action.setShortcuts([QKeySequence(key) for key in shortcuts])
        action.setCheckable(checkable)
        keys = ", ".join(QKeySequence(key).toString() for key in shortcuts)
        action.setToolTip(f"{tip or text} ({keys})" if keys else tip or text)
        action.triggered.connect(slot)
        # Adicionadas à janela para que os atalhos funcionem em tela cheia, com as barras ocultas
        self.addAction(action)
        return action

    def _build_actions(self):
        self.prev_action = self._action(
            "‹ Anterior", self.previous_page, [Qt.Key_Left, Qt.Key_PageUp, Qt.Key_Backspace], tip="Página anterior"
        )
        self.next_action = self._action(
            "Próxima ›", self.next_page, [Qt.Key_Right, Qt.Key_PageDown, Qt.Key_Space], tip="Próxima página"
        )
        self._action("Primeira", lambda: self.go_to_page(0), [Qt.Key_Home])
        self._action("Última", lambda: self.go_to_page(self.document.page_count - 1), [Qt.Key_End])

        self.fit_page_action = self._action(
            "Página inteira", lambda: self.set_fit_mode(FitMode.PAGE), [Qt.Key_P], checkable=True
        )
        self.fit_width_action = self._action(
            "Largura", lambda: self.set_fit_mode(FitMode.WIDTH), [Qt.Key_W], checkable=True, tip="Ajustar à largura"
        )

        self.zoom_out_action = self._action("−", lambda: self.change_zoom(1 / ZOOM_STEP), [Qt.Key_Minus], tip="Diminuir zoom")
        self.zoom_in_action = self._action(
            "+", lambda: self.change_zoom(ZOOM_STEP), [Qt.Key_Plus, Qt.Key_Equal], tip="Aumentar zoom"
        )
        self.fullscreen_action = self._action(
            "Tela cheia", self.toggle_fullscreen, [Qt.Key_F11, Qt.Key_F], checkable=True
        )
        self._action("Sair", self.escape, [Qt.Key_Escape])

    def _build_top_bar(self, title: str):
        self.top_bar = QToolBar("Leitor")
        self.top_bar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.top_bar)

        self.top_bar.addAction(self._action("← Biblioteca", self.close, tip="Voltar para a biblioteca"))

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600; padding: 0 12px;")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_label.setMinimumWidth(0)
        self.top_bar.addWidget(title_label)

        self.top_bar.addAction(self.fit_page_action)
        self.top_bar.addAction(self.fit_width_action)
        self.top_bar.addSeparator()
        self.top_bar.addAction(self.zoom_out_action)
        self.zoom_label = QLabel()
        self.zoom_label.setObjectName("muted")
        self.zoom_label.setFixedWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.top_bar.addWidget(self.zoom_label)
        self.top_bar.addAction(self.zoom_in_action)
        self.top_bar.addSeparator()
        self.top_bar.addAction(self.fullscreen_action)

    def _build_bottom_bar(self):
        self.bottom_bar = QToolBar("Páginas")
        self.bottom_bar.setObjectName("bottomBar")
        self.bottom_bar.setMovable(False)
        self.addToolBar(Qt.BottomToolBarArea, self.bottom_bar)

        self.bottom_bar.addAction(self.prev_action)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, self.document.page_count)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.valueChanged.connect(lambda value: self.go_to_page(value - 1))
        self.bottom_bar.addWidget(self.slider)

        self.page_counter = QLabel()
        self.page_counter.setObjectName("muted")
        self.page_counter.setMinimumWidth(80)
        self.page_counter.setAlignment(Qt.AlignCenter)
        self.bottom_bar.addWidget(self.page_counter)

        self.bottom_bar.addAction(self.next_action)

    # ---------- páginas ----------

    def page_image(self, index: int) -> QImage:
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]

        image = QImage.fromData(self.document.page(index))
        self.cache[index] = image
        if len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)
        return image

    def go_to_page(self, index: int):
        index = max(0, min(index, self.document.page_count - 1))
        self.page_index = index
        self.display_page()
        self.scroll.verticalScrollBar().setValue(0)
        self.scroll.horizontalScrollBar().setValue(0)

        total = self.document.page_count
        self.page_counter.setText(f"{index + 1} / {total}")
        self.slider.blockSignals(True)
        self.slider.setValue(index + 1)
        self.slider.blockSignals(False)
        self.prev_action.setEnabled(index > 0)
        self.next_action.setEnabled(index < total - 1)
        self.page_changed.emit(self.comic, index, total)

        # Deixa a próxima página pronta depois que a atual já foi exibida
        if index + 1 < total:
            QTimer.singleShot(0, self, lambda: self._preload(index + 1))

    def _preload(self, index: int):
        if not self.closed:
            self.page_image(index)

    def next_page(self):
        self.go_to_page(self.page_index + 1)

    def previous_page(self):
        self.go_to_page(self.page_index - 1)

    def display_page(self):
        if self.closed:
            return
        image = self.page_image(self.page_index)
        if image.isNull():
            self.page_label.setText("Não foi possível exibir esta página.")
            return

        viewport = self.scroll.viewport().size()
        if self.fit_mode is FitMode.PAGE:
            factor = min(viewport.width() / image.width(), viewport.height() / image.height())
        elif self.fit_mode is FitMode.WIDTH:
            factor = viewport.width() / image.width()
        else:
            factor = self.zoom
        self.zoom = factor

        ratio = self.devicePixelRatioF()
        scaled = image.scaled(
            max(1, round(image.width() * factor * ratio)),
            max(1, round(image.height() * factor * ratio)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        pixmap = QPixmap.fromImage(scaled)
        pixmap.setDevicePixelRatio(ratio)
        self.page_label.setPixmap(pixmap)
        self.page_label.resize(pixmap.deviceIndependentSize().toSize())
        self.zoom_label.setText(f"{round(factor * 100)}%")

    # ---------- zoom e modos ----------

    def set_fit_mode(self, mode: FitMode):
        self.fit_mode = mode
        self.fit_page_action.setChecked(mode is FitMode.PAGE)
        self.fit_width_action.setChecked(mode is FitMode.WIDTH)

        # Barras fixas evitam que a página "pule" quando a rolagem aparece ou some
        vertical = {
            FitMode.PAGE: Qt.ScrollBarAlwaysOff,
            FitMode.WIDTH: Qt.ScrollBarAlwaysOn,
            FitMode.ZOOM: Qt.ScrollBarAsNeeded,
        }[mode]
        self.scroll.setVerticalScrollBarPolicy(vertical)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded if mode is FitMode.ZOOM else Qt.ScrollBarAlwaysOff)
        self.display_page()

    def change_zoom(self, step: float):
        self.zoom = max(MIN_ZOOM, min(self.zoom * step, MAX_ZOOM))
        self.set_fit_mode(FitMode.ZOOM)

    def toggle_fullscreen(self):
        fullscreen = not self.isFullScreen()
        self.top_bar.setVisible(not fullscreen)
        self.bottom_bar.setVisible(not fullscreen)
        self.fullscreen_action.setChecked(fullscreen)
        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def escape(self):
        if self.isFullScreen():
            self.toggle_fullscreen()
        else:
            self.close()

    # ---------- eventos ----------

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport():
            if event.type() == QEvent.Wheel:
                return self._handle_wheel(event)
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                # Clique no terço esquerdo volta; no resto, avança
                if event.position().x() < watched.width() / 3:
                    self.previous_page()
                else:
                    self.next_page()
                return True
        return super().eventFilter(watched, event)

    def _handle_wheel(self, event) -> bool:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            self.change_zoom(ZOOM_STEP if delta > 0 else 1 / ZOOM_STEP)
            return True
        if self.fit_mode is not FitMode.PAGE:
            return False  # rolagem normal

        # Com a página inteira visível, a roda vira páginas (acumulando para touchpads)
        self.wheel_delta += delta
        if abs(self.wheel_delta) >= 120:
            self.previous_page() if self.wheel_delta > 0 else self.next_page()
            self.wheel_delta = 0
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode is not FitMode.ZOOM:
            self.resize_timer.start()

    def closeEvent(self, event):
        self.closed = True
        self.resize_timer.stop()
        self.cache.clear()
        self.document.close()
        super().closeEvent(event)
