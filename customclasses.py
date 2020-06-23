# pylint: disable=no-member

import os
import subprocess
import tempfile

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QDialog

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
        if not check_module("jedi"):
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

        line_length = self.settings.value("max_line_length", 88, int)

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

