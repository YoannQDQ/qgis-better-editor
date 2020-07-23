# pylint: disable=no-member

import os
import subprocess
import tempfile
import tokenize
from io import BytesIO

from PyQt5.QtCore import (
    QSettings,
    Qt,
    QPoint,
    QRect,
    QSize,
    QEvent,
    QTimer,
    QCoreApplication,
)
from PyQt5.QtGui import QPalette, QColor, QKeySequence, QIcon
from PyQt5.QtWidgets import QDialog, QCompleter, QListView, QShortcut
from PyQt5.Qsci import QsciScintilla

from qgis.utils import iface

from .dependencies import check_module
from .monkeypatch import unpatched
from .resourcebrowserimpl import ResourceBrowser
from .indicatorsutils import define_indicators, check_syntax
from .completionmodel import CompletionModel
from .calltips import CallTips


def tr(message):
    return QCoreApplication.translate("BetterEditor", message)


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
            if hasattr(self, "callTips"):
                self.callTips.hide()
        if e.type() == QEvent.ShortcutOverride:

            ctrl = bool(e.modifiers() & Qt.ControlModifier)
            shift = bool(e.modifiers() & Qt.ShiftModifier)
            alt = bool(e.modifiers() & Qt.AltModifier)

            # Override Save, SavesAs and Run
            if (
                e.matches(QKeySequence.Save)
                or (ctrl and shift and e.key() == Qt.Key_S)
                or (ctrl and e.key() == Qt.Key_R)
                or (ctrl and alt and e.key() == Qt.Key_F)
                or (e.key() == Qt.Key_F12)
                or (e.key() == Qt.Key_F2)
            ):
                e.accept()
                return True

        return unpatched().event(e)

    def keyPressEvent(self, e):

        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        alt = bool(e.modifiers() & Qt.AltModifier)

        # Ctrl+S: Save
        if e.matches(QKeySequence.Save):
            self.save()
            return

        # Ctrl+Shift+As: Save As
        if ctrl and shift and e.key() == Qt.Key_S:
            self.saveAs()
            return

        # Ctrl+R: Run Script
        if ctrl and e.key() == Qt.Key_R:
            self.runScriptCode()
            return

        # Ctrl+: Toggle comment
        if ctrl and e.key() == Qt.Key_Colon:
            self.toggle_comment()
            return

        # Ctrl+Alt+F: Format
        if ctrl and alt and e.key() == Qt.Key_F:
            self.format_file()
            return

        # F12 or F2: Go to definition
        if e.key() in (Qt.Key_F12, Qt.Key_F2):
            self.goto()
            return

        # Ctrl+Space: Autocomplete
        if ctrl and e.key() == Qt.Key_Space:
            self.update_calltips()
            char = self.character_before_cursor()
            if char.isidentifier() or char in (r"\/."):
                self.autocomplete()
            return

        # If press escape and call tips widget is shown, hide it

        if (
            e.key() == Qt.Key_Escape
            and hasattr(self, "callTips")
            and self.callTips.isVisible()
        ):
            self.callTips.hide()

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

        # Handle closing and opening
        last_char = self.character_before_cursor()
        next_char = self.character_after_cursor()
        line, column = self.getCursorPosition()

        openings = "([{'\""
        closings = ")]}'\""
        pairs = list(zip(openings, closings))

        if not self.hasSelectedText():
            if e.key() == Qt.Key_Backspace:
                pair = (last_char, next_char)
                if pair in pairs:
                    self.setSelection(line, column - 1, line, column + 1)
                    self.removeSelectedText()
                    return

            if e.text() and e.text() in closings and next_char == e.text():
                self.setSelection(line, column, line, column + 1)
                self.removeSelectedText()

            elif self.code_context() and e.text() and e.text() in openings:
                # Allow to enter """ and '''
                if not (e.text() in "'\"" and last_char == e.text()):
                    i = openings.index(e.text())
                    self.insert("".join(pairs[i]))
                    self.setCursorPosition(line, column + 1)

                    if e.text() == "(":
                        self.callTipsTimer.start()
                    return

        elif e.text() and e.text() in openings:
            i = openings.index(e.text())
            start_line, start_pos, end_line, end_pos = self.getSelection()

            # Multi line quotes
            if start_line != end_line and e.text() in "'\"":
                self.replaceSelectedText(
                    f"{openings[i]*3}{self.selectedText()}{closings[i]*3}"
                )
                self.setSelection(start_line, start_pos + 3, end_line, end_pos + 3)
            else:
                self.replaceSelectedText(
                    f"{openings[i]}{self.selectedText()}{closings[i]}"
                )
                self.setSelection(start_line, start_pos + 1, end_line, end_pos + 1)
            return

        # Let QSciScintilla handle the keyboard event
        unpatched().keyPressEvent(e)
        prefix = self.text_under_cursor()

        if e.text() == "(":
            self.callTipsTimer.start()

        if e.text() == ".":
            self.autocomplete()
            return

        # end of word
        eow = "~!@#$%^&*()+{}|:\"<>?,/;'[]\\-= "

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

    def code_context(self):
        """ Return true if current position is not inside a string or a comment """
        line, column = self.getCursorPosition()
        inside_string = False
        single_quote = False
        double_quote = False
        triple_single_quote = False
        triple_double_quote = False

        pos = self.positionFromLineIndex(line, 0)
        for i in range(column):
            char = self.text(pos + i, pos + i + 1)
            if not inside_string:
                if char == "#":
                    return False
                if char == "'":
                    if self.text(pos + i - 2, pos + i + 1) == "'''":
                        triple_single_quote = True
                        inside_string = True

                    inside_string = True
                    single_quote = True
                if char == '"':
                    if self.text(pos + i - 2, pos + i + 1) == '"""':
                        triple_double_quote = True
                        inside_string = True
                    inside_string = True
                    double_quote = True
            else:
                if char == "'":
                    if single_quote:
                        inside_string = False
                        single_quote = False
                    if triple_single_quote:
                        if self.text(pos + i - 2, pos + i + 1) == "'''":
                            inside_string = False
                            triple_single_quote = False

                if char == '"':
                    if double_quote:
                        inside_string = False
                        double_quote = False
                    if triple_double_quote:
                        if self.text(pos + i - 2, pos + i + 1) == '"""':
                            inside_string = False
                            triple_double_quote = False

        return not inside_string

    def save(self):
        self.parent.save()

    def saveAs(self):
        self.parent.tw.saveAs()

    def on_position_changed(self):
        if hasattr(self, "callTips") and self.callTips.isVisible():
            self.callTipsTimer.start()

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

    def character_after_cursor(self):
        pos = self.positionFromLineIndex(*self.getCursorPosition())
        return self.text(pos, pos + 1)

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

    def update_calltips(self):
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
            self.callTips.hide()
            return

        bracket_line, bracket_column = res[0].bracket_start
        pos = self.positionFromLineIndex(
            bracket_line - 1 - len(init_lines), bracket_column
        )
        x = self.SendScintilla(QsciScintilla.SCI_POINTXFROMPOSITION, 0, pos)
        y = self.SendScintilla(QsciScintilla.SCI_POINTYFROMPOSITION, 0, pos)

        self.callTips.show_signatures(res, QPoint(x, y))

    def goto(self):
        if not check_module("jedi", "0.17"):
            return
        import jedi

        line, column = self.getCursorPosition()
        script = jedi.Script(code=self.text(), project=self.project)
        names = script.goto(line + 1, column)
        if not names:
            return
        definition_pos = names[0].get_definition_start_position()
        if definition_pos:
            line = definition_pos[0] - 1
            column = definition_pos[1]
            self.setCursorPosition(line, column)

    def get_words(self):
        tokens = tokenize.tokenize(BytesIO(self.text().encode("utf-8")).readline)
        names = {token.string for token in tokens if token.type == 1}
        return names

    def word_completions(self):
        return sorted(
            (
                WordCompletion(word)
                for word in self.get_words()
                if word != self.text_under_cursor()
            ),
            key=lambda x: x.name.lower(),
        )

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

        if not completions and prefix:
            completions = self.word_completions()

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


class MonkeyScriptEditor(MonkeyEditor):
    def customize(self):
        # Disable shortcuts
        for shortcut in self.findChildren(QShortcut):
            shortcut.setEnabled(False)
        self.bufferMarkerLine = []
        self.set_completer(QCompleter(self))
        self.completer.setModel(CompletionModel([], self))
        self.callTips = CallTips(self)
        self.callTipsTimer = QTimer(self)
        self.callTipsTimer.setSingleShot(True)
        self.callTipsTimer.setInterval(500)
        self.callTipsTimer.timeout.connect(self.update_calltips)

        self.setCallTipsStyle(QsciScintilla.CallTipsNone)
        self.setAutoCompletionSource(QsciScintilla.AcsNone)
        self.setFolding(
            self.settings.value("folding_style", QsciScintilla.BoxedTreeFoldStyle, int)
        )

        # Add a small margin after the indicator (if folding is not Plain or None)
        if self.folding() > 1:
            self.setMarginWidth(3, "0")
        else:
            self.setMarginWidth(3, "")

        if self.settings.value("ruler_visible", True, bool):
            self.setEdgeMode(QsciScintilla.EdgeLine)
            self.setEdgeColumn(self.settings.value("max_line_length", 88, int))
            self.setEdgeColor(
                self.settings.value("ruler_color", QColor("#00aaff"), QColor)
            )
        else:
            self.setEdgeMode(QsciScintilla.EdgeNone)

        # Change syntax error marker
        define_indicators(self)

        self.cursorPositionChanged.connect(self.on_position_changed)

    def call_parent_method(self, name, *args, **kwargs):
        temp = self.parent()
        while temp:
            if hasattr(temp, name):
                return getattr(temp, name)(*args, **kwargs)
            temp = temp.parent()

    def save(self):
        self.call_parent_method("save")

    def saveAs(self):
        self.call_parent_method("saveAs")

    def runScriptCode(self):
        if self.syntaxCheck():
            self.call_parent_method("runAlgorithm")


class MonkeyScriptEditorDialog:
    def show(self):
        self.customize()
        unpatched().show()

    def customize(self):
        if hasattr(self.editor, "completer"):
            return
        self.editor.customize()

        self.toolBar.addSeparator()
        self.toggle_comment_action = self.toolBar.addAction(
            QIcon(":/images/themes/default/console/iconCommentEditorConsole.svg"),
            tr("Toggle Comment"),
        )
        self.toggle_comment_action.setObjectName("toggleComment")
        self.toggle_comment_action.triggered.connect(self.editor.toggle_comment)
        self.toggle_comment_action.setShortcut("Ctrl+:")
        self.toggle_comment_action.setToolTip(
            f"<b>{self.toggle_comment_action.text()}</b> ({self.toggle_comment_action.shortcut().toString()})"
        )
        self.toolBar.addAction(self.toggle_comment_action)

        if check_module("black"):
            self.format_action = self.toolBar.addAction(
                QIcon(":/plugins/bettereditor/icons/wizard.svg"), tr("Format file")
            )
            self.format_action.setObjectName("format")
            self.format_action.setShortcut("Ctrl+Alt+F")
            self.format_action.triggered.connect(self.editor.format_file)
            self.format_action.setToolTip(
                f"<b>{self.format_action.text()}</b> ({self.format_action.shortcut().toString()})"
            )

    def saveScript(self, saveAs: bool):
        settings = QSettings()
        settings.beginGroup("plugins/bettereditor")
        if settings.value("format_on_save", True, bool):
            self.editor.format_file()
        unpatched().saveScript(saveAs)

    def runAlgorithm(self):
        if self.editor.syntaxCheck():
            unpatched().runAlgorithm()


class WordCompletion:
    def __init__(self, name):
        self.name = name
        self.type = "name"
