"""Diálogo para editar à mão os metadados e a descrição de uma HQ."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox

from app.library.metadata import Metadata


class MetadataDialog(QDialog):
    def __init__(self, title: str, metadata: Metadata, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editar — {title}")
        self.resize(520, 480)

        self.series = QLineEdit(metadata.series)
        self.number = QLineEdit(metadata.number)
        self.year = QSpinBox()
        self.year.setRange(0, 2100)
        self.year.setSpecialValueText("—")  # 0 = sem ano
        self.year.setValue(metadata.year or 0)
        self.writer = QLineEdit(metadata.writer)
        self.publisher = QLineEdit(metadata.publisher)
        self.summary = QPlainTextEdit(metadata.summary)

        form = QFormLayout(self)
        form.addRow("Série", self.series)
        form.addRow("Número", self.number)
        form.addRow("Ano", self.year)
        form.addRow("Roteiro", self.writer)
        form.addRow("Editora", self.publisher)
        form.addRow("Descrição", self.summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def metadata(self) -> Metadata:
        return Metadata(
            series=self.series.text().strip(),
            number=self.number.text().strip(),
            year=self.year.value() or None,
            writer=self.writer.text().strip(),
            publisher=self.publisher.text().strip(),
            summary=self.summary.toPlainText().strip(),
        )
