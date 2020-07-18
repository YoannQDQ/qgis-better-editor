from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, QPoint

SCROLL_STYLESHEET = """
QScrollBar:vertical {
    border: None;
    width: 8px;
    background: #eee;
    margin: 0 0 0 0;
}
QScrollBar::handle {
  background: #aaa;
}
QScrollBar::handle:hover {
  background: #888;
}
QScrollBar::add-line {
  border: None;
}
QScrollBar::sub-line {
  border: None;
}
"""


class CallTips(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#fff"))
        self.setPalette(palette)
        self.setWindowFlags(Qt.ToolTip)

        self.line = QFrame(self)
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.title_label = QLabel()
        self.title_label.setMinimumWidth(300)
        self.title_label.setFont(parent.font())
        self.docstring_textedit = QTextEdit(self)
        self.docstring_textedit.setReadOnly(True)
        self.docstring_textedit.setFont(parent.font())

        palette = self.docstring_textedit.palette()
        palette.setColor(QPalette.WindowText, QColor("#888"))
        palette.setColor(QPalette.Text, QColor("#888"))
        self.docstring_textedit.setPalette(palette)
        self.docstring_textedit.setFrameShape(QFrame.NoFrame)
        self.docstring_textedit.document().setDocumentMargin(0)
        self.title_label.setPalette(palette)

        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.line)
        layout.addWidget(self.docstring_textedit)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)

    @staticmethod
    def signature_to_string(signature):
        name = signature.name
        params = []
        for i, param in enumerate(signature.params):
            try:
                type_hint = param.get_type_hint()
            except TypeError:
                type_hint = None

            if signature.index == i:
                if type_hint:
                    params.append(
                        f'<b><u><font color="royalblue">{param.name}</font></u></b>: {type_hint}'
                    )
                else:
                    params.append(
                        f'<b><u><font color="royalblue">{param.name}</font></u></b>'
                    )

            else:
                if type_hint:
                    params.append(f"{param.name}: {type_hint}")
                else:
                    params.append(param.name)
        html = f'{name}({", ".join(params)})'

        docstring = ""
        if signature.docstring(True, True):
            docstring = signature.docstring(True, True).replace("\n", "<br>")

        return html, docstring

    def show_signatures(self, signatures, pos: QPoint):
        signature = signatures[0]

        text, docstring = self.signature_to_string(signature)

        self.title_label.setText(text)
        if not docstring:
            self.docstring_textedit.hide()
            self.line.hide()
        else:
            self.docstring_textedit.show()
            self.line.show()
            self.docstring_textedit.setHtml(docstring)
            self.docstring_textedit.document().adjustSize()
            height = self.docstring_textedit.document().size().height()
            self.docstring_textedit.setFixedHeight(min(150, height))

        point = self.parent().mapToGlobal(
            QPoint(pos.x(), pos.y() - self.sizeHint().height() - 2)
        )
        self.show()
        self.move(point.x(), point.y())

        self.docstring_textedit.setStyleSheet(SCROLL_STYLESHEET)
