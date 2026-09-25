import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import apply_dark_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Comic Library")
    apply_dark_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
