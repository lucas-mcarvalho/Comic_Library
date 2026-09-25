"""Configurações das buscas online: login do GCD (opcional) e chave do ComicVine (opcional)."""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit

GCD_SIGNUP_URL = "https://www.comics.org/accounts/register/"
COMICVINE_KEY_URL = "https://comicvine.gamespot.com/api/"


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Buscas online")
        self.setMinimumWidth(520)

        form = QFormLayout(self)
        form.setVerticalSpacing(10)

        form.addRow(self._note(
            "<b>Grand Comics Database</b> — usado por padrão, grátis e sem cadastro. "
            "Sem login, o GCD permite poucas buscas por hora; com uma "
            f'<a href="{GCD_SIGNUP_URL}">conta gratuita</a> o limite é maior.'
        ))
        self.gcd_user = QLineEdit(settings.value("gcd/user", ""))
        self.gcd_user.setPlaceholderText("opcional")
        self.gcd_password = QLineEdit(settings.value("gcd/password", ""))
        self.gcd_password.setEchoMode(QLineEdit.Password)
        self.gcd_password.setPlaceholderText("opcional")
        form.addRow("E-mail do GCD", self.gcd_user)
        form.addRow("Senha do GCD", self.gcd_password)
        form.addRow(self._note(
            "A senha fica salva sem criptografia nas preferências do app. Use uma senha exclusiva para o GCD.",
            muted=True,
        ))

        form.addRow(self._note(
            "<br><b>ComicVine</b> — opcional. Usado quando o GCD não tem a sinopse. "
            f'Pegue uma chave gratuita em <a href="{COMICVINE_KEY_URL}">comicvine.gamespot.com/api</a>.'
        ))
        self.comicvine_key = QLineEdit(settings.value("comicvine/api_key", ""))
        self.comicvine_key.setPlaceholderText("opcional")
        form.addRow("Chave do ComicVine", self.comicvine_key)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _note(text: str, muted: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        if muted:
            label.setObjectName("muted")
        return label

    def save(self):
        for key, field in (
            ("gcd/user", self.gcd_user),
            ("gcd/password", self.gcd_password),
            ("comicvine/api_key", self.comicvine_key),
        ):
            value = field.text().strip()
            if value:
                self.settings.setValue(key, value)
            else:
                self.settings.remove(key)
        self.accept()
