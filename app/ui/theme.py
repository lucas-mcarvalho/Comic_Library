"""Tema escuro da aplicação."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BACKGROUND = "#121418"
SURFACE = "#1b1e24"
SURFACE_HOVER = "#262a32"
BORDER = "#2e333c"
TEXT = "#e8eaed"
TEXT_MUTED = "#8c939e"
ACCENT = "#e5484d"
ACCENT_HOVER = "#f2555a"
READER_BACKGROUND = "#0b0c0e"

STYLESHEET = f"""
QMainWindow, QStackedWidget {{ background: {BACKGROUND}; }}

QToolBar {{
    background: {SURFACE};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 10px;
    spacing: 6px;
}}
QToolBar#bottomBar {{ border-bottom: none; border-top: 1px solid {BORDER}; }}
QToolButton {{
    color: {TEXT};
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}}
QToolButton:hover {{ background: {SURFACE_HOVER}; }}
QToolButton:checked {{ background: {SURFACE_HOVER}; color: {ACCENT}; }}
QToolButton:disabled {{ color: {BORDER}; }}

QPushButton {{
    color: {TEXT};
    background: {SURFACE_HOVER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {TEXT_MUTED}; }}
QPushButton#primary {{
    color: white;
    background: {ACCENT};
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}

QLineEdit {{
    color: {TEXT};
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QListView {{ background: {BACKGROUND}; border: none; outline: none; }}
QScrollArea {{ background: {READER_BACKGROUND}; border: none; }}

QLabel#title {{ color: {TEXT}; font-size: 22px; font-weight: 600; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}

QStatusBar {{ background: {SURFACE}; color: {TEXT_MUTED}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {BORDER}; border-radius: 3px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {TEXT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QToolTip {{ color: {TEXT}; background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
QMessageBox {{ background: {SURFACE}; }}
"""


def apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")

    palette = QPalette()
    colors = {
        QPalette.Window: BACKGROUND,
        QPalette.WindowText: TEXT,
        QPalette.Base: SURFACE,
        QPalette.AlternateBase: SURFACE_HOVER,
        QPalette.Text: TEXT,
        QPalette.Button: SURFACE,
        QPalette.ButtonText: TEXT,
        QPalette.Highlight: ACCENT,
        QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: SURFACE,
        QPalette.ToolTipText: TEXT,
        QPalette.PlaceholderText: TEXT_MUTED,
        QPalette.Link: ACCENT,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        palette.setColor(QPalette.Disabled, role, QColor(TEXT_MUTED))

    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
