# pylint: disable=no-member

import os
import subprocess
import tempfile

from PyQt5.QtCore import (
    QSettings,
    Qt,
    QPoint,
    QRect,
    QAbstractListModel,
    QModelIndex,
    QSize,
    QEvent,
)
from PyQt5.QtGui import QPalette, QColor, QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QDialog,
    QCompleter,
    QLabel,
    QFrame,
    QStackedWidget,
    QVBoxLayout,
    QTextEdit,
    QListView,
)
from PyQt5.Qsci import QsciScintilla

from qgis.utils import iface

from .dependencies import check_module
from .indicatorsutils import check_syntax
from .monkeypatch import unpatched
from .resourcebrowserimpl import ResourceBrowser


class MonkeyEditorTab:
    def save(self, filename=""):
        editor = self.newEditor
        settings = QSettings()
        settings.beginGroup("plugins/bettereditor")
        if settings.value("format_on_save", True, bool):
            editor.format_file()
        return unpatched().save(filename)


class MonkeyEditor:
    def syntaxCheck(self, filename=None, fromContextMenu=True):
        if not check_module("jedi", "0.17"):
            return unpatched().syntaxCheck(filename, fromContextMenu)
        return check_syntax(self, filename, fromContextMenu)

    def format_file(self):

        if not check_module("black"):
            return

        # Check there's no syntax errors before calling black
        if not self.syntaxCheck():
            return

        old_pos = self.getCursorPosition()
        old_scroll_value = self.verticalScrollBar().value()

        myfile = tempfile.mkstemp(".py")
        filepath = myfile[1]
        os.close(myfile[0])
        with open(filepath, "w") as out:
            out.write(self.text().replace("\r\n", "\n"))

        settings = QSettings()
        settings.beginGroup("plugins/bettereditor")
        line_length = settings.value("max_line_length", 88, int)

        cmd = ["python3", "-m", "black", filepath, "-l", str(line_length)]
        # Prevents the call to black from spawning an console on Windows.
        try:
            completed_process = subprocess.run(
                cmd, check=False, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except (AttributeError, TypeError):
            completed_process = subprocess.run(cmd, check=False)

        if completed_process.returncode == 0:
            with open(filepath) as out:
                content = out.read()
            self.beginUndoAction()
            self.selectAll()
            self.removeSelectedText()
            self.insert(content)
            self.setCursorPosition(*old_pos)
            self.verticalScrollBar().setValue(old_scroll_value)
            self.endUndoAction()

        os.remove(filepath)

    def toggle_comment(self):

        self.beginUndoAction()
        if self.hasSelectedText():
            start_line, start_pos, end_line, end_pos = self.getSelection()
        else:
            start_line, start_pos = self.getCursorPosition()
            end_line, end_pos = start_line, start_pos

        # Special case, only empty lines
        if not any(self.text(line).strip() for line in range(start_line, end_line + 1)):
            return

        all_commented = all(
            self.text(line).strip().startswith("#")
            for line in range(start_line, end_line + 1)
            if self.text(line).strip()
        )
        min_indentation = min(
            self.indentation(line)
            for line in range(start_line, end_line + 1)
            if self.text(line).strip()
        )

        for line in range(start_line, end_line + 1):
            # Empty line
            if not self.text(line).strip():
                continue

            delta = 0

            if not all_commented:
                self.insertAt("# ", line, min_indentation)
                delta = -2
            else:
                if not self.text(line).strip().startswith("#"):
                    continue
                if self.text(line).strip().startswith("# "):
                    delta = 2
                else:
                    delta = 1

                self.setSelection(
                    line, self.indentation(line), line, self.indentation(line) + delta,
                )
                self.removeSelectedText()

        self.endUndoAction()

        self.setSelection(start_line, start_pos - delta, end_line, end_pos - delta)

    def insert_resource(self):
        dialog = ResourceBrowser(iface.mainWindow())
        res = dialog.exec()
        if res == QDialog.Accepted:

            line, offset = self.getCursorPosition()
            old_selection = self.getSelection()
            if old_selection == (-1, -1, -1, -1):
                selection = (line, offset - 1, line, offset + 1)
            else:
                selection = (
                    old_selection[0],
                    old_selection[1] - 1,
                    old_selection[2],
                    old_selection[3] + 1,
                )

            self.setSelection(*selection)
            selected_text = self.selectedText()

            if selected_text and not (
                selected_text[-1] == selected_text[0]
                and selected_text[-1] in ("'", '"')
            ):
                self.setSelection(*old_selection)
                if old_selection == (-1, -1, -1, -1):
                    self.setCursorPosition(line, offset)
            self.removeSelectedText()
            ressource_path = f'"{dialog.icon}"'
            self.insert(ressource_path)

            line, offset = self.getCursorPosition()
            self.setCursorPosition(line, offset + len(ressource_path))

    def event(self, e):
        if e.type() in (QEvent.FocusOut, QEvent.MouseButtonPress):
            if hasattr(self, "hintToolTip"):
                self.hintToolTip.hide()
        if e.type() == QEvent.ShortcutOverride:

            ctrl = bool(e.modifiers() & Qt.ControlModifier)
            shift = bool(e.modifiers() & Qt.ShiftModifier)

            # Override Save, SavesAs and Run
            if (
                e.matches(QKeySequence.Save)
                or (ctrl and shift and e.key() == Qt.Key_S)
                or (ctrl and e.key() == Qt.Key_R)
            ):
                e.accept()
                return True

        return unpatched().event(e)

    def keyPressEvent(self, e):

        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        shift = bool(e.modifiers() & Qt.ShiftModifier)

        # Ctrl+S: Save
        if e.matches(QKeySequence.Save):
            self.parent.save()
            return

        # Ctrl+Shift+As: Save As
        if ctrl and shift and e.key() == Qt.Key_S:
            self.parent.tw.saveAs()
            return

        # Ctrl+R: Run Script
        if ctrl and e.key() == Qt.Key_R:
            self.runScriptCode()
            return

        # Ctrl+Space: Autocomplete
        if ctrl and e.key() == Qt.Key_Space:
            self.signatures()
            char = self.character_before_cursor()
            if char.isidentifier() or char in (r"\/."):
                self.autocomplete()
            return

        # If press escape and call tips widget is shown, hide it

        if (
            e.key() == Qt.Key_Escape
            and hasattr(self, "hintToolTip")
            and self.hintToolTip.isVisible()
        ):
            self.hintToolTip.hide()

        # If completer popup is visible, discard those events
        if self.completer.popup().isVisible():
            # The following keys are forwarded by the completer to the widget
            if e.key() in (
                Qt.Key_Enter,
                Qt.Key_Return,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Backtab,
            ):
                e.ignore()
                return  # let the completer do default behavior

        # Let QSciScintilla handle the keyboard event
        unpatched().keyPressEvent(e)
        prefix = self.text_under_cursor()

        if e.text() == "(":
            self.signatures()

        if e.text() == ".":
            self.autocomplete()
            return

        # end of word
        eow = "~!@#$%^&*()+{}|:\"<>?,/;'[]\\-= "

        last_char = self.character_before_cursor()

        if last_char in eow:
            self.completer.popup().hide()
            return

        if prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(prefix)

        settings = QSettings()
        settings.beginGroup("plugins/bettereditor")
        threshold = settings.value("autocomplete_threshold", 4, int)
        # Jedi completion model is already accurate
        if self.completer.modelprefix and prefix.lower().startswith(
            self.completer.modelprefix.lower()
        ):

            # No more suggested completion: hide popup
            if self.completer.completionModel().rowCount() == 0:
                self.completer.popup().hide()
                return
            # Else, show popup select the first suggestion
            else:
                self.completer.popup().setCurrentIndex(
                    self.completer.completionModel().index(0, 0)
                )
                self.completer.popup().show()
                return

        # Jedi completion model must be updated
        elif len(prefix) >= threshold and e.text() and e.text().isidentifier():
            self.autocomplete()
        else:
            self.completer.popup().hide()

    def on_position_changed(self):
        if hasattr(self, "hintToolTip") and self.hintToolTip.isVisible():
            self.signatures()

    def insert_completion(self, completion):
        line, column = self.getCursorPosition()
        self.setSelection(
            line, column - len(self.completer.completionPrefix()), line, column
        )
        self.replaceSelectedText(completion)
        if completion.endswith("/"):
            self.autocomplete()

    def character_before_cursor(self):
        pos = self.positionFromLineIndex(*self.getCursorPosition())
        return self.text(pos - 1, pos)

    def text_under_cursor(self):
        line, column = self.getCursorPosition()
        return self.wordAtLineIndex(line, column)

    def set_completer(self, completer):
        if hasattr(self, "completer") and self.completer:
            self.completer.disconnect()

        self.completer = completer
        self.completer.modelprefix = ""
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setModelSorting(QCompleter.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated[str].connect(self.insert_completion)

    def signatures(self):
        if not check_module("jedi", "0.17"):
            return
        import jedi

        line, column = self.getCursorPosition()

        # Simulate QGIS python default imports
        init_lines = [
            "from qgis.core import *",
            "from qgis.gui import *",
            "from qgis.utils import iface",
            "from PyQt5.QtCore import *",
            "from PyQt5.QtWidgets import *",
            "from PyQt5.QtGui import *",
            "iface: QgisInterface = iface",
        ]
        init_text = "\n".join(init_lines) + "\n"
        script = jedi.Interpreter(
            code=init_text + self.text(), namespaces=(globals(), locals())
        )
        try:
            res = script.get_signatures(line + 1 + len(init_lines), column)
        except TypeError:
            res = None
        if not res:
            self.hintToolTip.hide()
            return

        bracket_line, bracket_column = res[0].bracket_start
        pos = self.positionFromLineIndex(
            bracket_line - 1 - len(init_lines), bracket_column
        )
        x = self.SendScintilla(QsciScintilla.SCI_POINTXFROMPOSITION, 0, pos)
        y = self.SendScintilla(QsciScintilla.SCI_POINTYFROMPOSITION, 0, pos)

        self.hintToolTip.show_signatures(res, QPoint(x, y))

    def autocomplete(self):
        if not check_module("jedi", "0.17"):
            return
        import jedi

        line, column = self.getCursorPosition()

        # Simulate QGIS python default imports
        init_lines = [
            "from qgis.core import *",
            "from qgis.gui import *",
            "from qgis.utils import iface",
            "from PyQt5.QtCore import *",
            "from PyQt5.QtWidgets import *",
            "from PyQt5.QtGui import *",
            "iface: QgisInterface = iface",
        ]

        init_text = "\n".join(init_lines) + "\n"
        script = jedi.Script(code=init_text + self.text(), project=self.project)
        completions = script.complete(line + 1 + len(init_lines), column)

        prefix = self.text_under_cursor()
        self.completer.modelprefix = prefix

        if not completions:
            self.completer.popup().hide()
            self.completer.model().setCompletions([])
            return

        self.completer.model().setCompletions(completions)
        self.completer.setCompletionPrefix(prefix)

        pos = self.positionFromLineIndex(line, column - len(prefix))
        x = self.SendScintilla(QsciScintilla.SCI_POINTXFROMPOSITION, 0, pos)
        y = self.SendScintilla(QsciScintilla.SCI_POINTYFROMPOSITION, 0, pos)
        line_height = self.SendScintilla(QsciScintilla.SCI_TEXTHEIGHT, line)

        content_rect = QRect(0, 0, 450, 300)
        content_rect.setWidth(
            self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width()
            + 30
        )
        self.completer.complete(content_rect)
        self.completer.popup().setFont(self.font())
        self.completer.popup().move(self.mapToGlobal(QPoint(x, y + line_height + 2)))

        self.completer.popup().setCurrentIndex(
            self.completer.completionModel().index(0, 0)
        )
        self.completer.popup().setUniformItemSizes(True)
        self.completer.popup().setLayoutMode(QListView.Batched)
        self.completer.popup().setIconSize(QSize(16, 16))

        p = self.completer.popup().palette()
        p.setColor(QPalette.Highlight, QColor("#ccddff"))
        p.setColor(QPalette.HighlightedText, QColor("black"))
        self.completer.popup().setPalette(p)


class CompletionModel(QAbstractListModel):
    def __init__(self, completions=None, parent=None):
        super().__init__(parent)
        if not completions:
            self.completions = []
        else:
            self.completions = completions

    def rowCount(self, index=QModelIndex()):
        return len(self.completions)

    def setCompletions(self, completions):
        self.beginResetModel()
        self.completions = completions
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid():
            return

        completion = self.completions[index.row()]

        if completion.type == "path" and completion.name.endswith("\\"):
            name = f"{completion.name[:-1]}/"
        else:
            name = completion.name

        if role == Qt.DisplayRole:
            return name
        elif role == Qt.EditRole:
            return name
        elif role == Qt.DecorationRole:
            if completion.type == "class":
                return QIcon(":/plugins/bettereditor/icons/symbol-class.svg")
            elif completion.type == "keyword":
                return QIcon(":/plugins/bettereditor/icons/symbol-keyword.svg")
            elif completion.type == "function":
                return QIcon(":/plugins/bettereditor/icons/symbol-namespace.svg")
            elif completion.type == "path":
                if name.endswith("/"):
                    return QIcon(":/plugins/bettereditor/icons/folder.svg")
                else:
                    return QIcon(":/plugins/bettereditor/icons/file-1.svg")
            elif completion.type == "statement":
                return QIcon(":/plugins/bettereditor/icons/symbol-enumerator.svg")
            elif completion.type == "param":
                return QIcon(":/plugins/bettereditor/icons/symbol-variable.svg")
            else:
                return QIcon(":/plugins/bettereditor/icons/symbol-method.svg")


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


class HintToolTip(QFrame):
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
