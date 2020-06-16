# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Python tools
 A QGIS plugin which improves the embedded python editor

                              -------------------
        begin                : 2020-06-15
        git sha              : $Format:%H$
        copyright            : (C) 2020 Yoann Quenach de Quivillic
        email                : yoann.quenach@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import subprocess
import tempfile
from functools import partial

from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import (
    QAction,
    QDialog,
    QMessageBox,
    QWidget,
    QToolBar,
    QShortcut,
)
from PyQt5.Qsci import QsciScintilla


from console.console import PythonConsole
from console.console_editor import Editor, EditorTabWidget


from .dependencies import import_or_install
from .resourcebrowserimpl import ResourceBrowser
from .settingsdialogimpl import SettingsDialog
from .resources import *


class PythonTools:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", "PythonTools_{}.qm".format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Init settings
        self.settings = QSettings()
        self.settings.beginGroup("plugins/pythontools")

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("PythonTools", message)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        # Create settings dialog
        self.settings_dialog = SettingsDialog(self.settings, self.iface.mainWindow())
        self.settings_dialog.settingsChanged.connect(self.on_settings_changed)

        # Show Python console to trigger its creation
        self.python_console = self.iface.mainWindow().findChild(PythonConsole)
        if not self.python_console:
            self.iface.actionShowPythonDialog().trigger()
            self.python_console = self.iface.mainWindow().findChild(PythonConsole)
            self.python_console.hide()
            self.iface.actionShowPythonDialog().setChecked(False)

        self.about_action = QAction(
            QIcon(":/plugins/pythontools/about.svg"),
            self.tr("About"),
            parent=self.iface.mainWindow(),
        )
        self.about_action.triggered.connect(self.show_about)

        self.settings_action = QAction(
            QIcon(":/images/themes/default/console/iconSettingsConsole.svg"),
            self.tr("Settings"),
            parent=self.iface.mainWindow(),
        )
        self.settings_action.triggered.connect(self.show_settings)

        self.plugin_menu = self.iface.pluginMenu().addMenu(
            QIcon(":/plugins/pythontools/icon.svg"), "Python Tools"
        )
        self.plugin_menu.addAction(self.about_action)
        self.plugin_menu.addAction(self.settings_action)
        self.toolbar = self.python_console.findChild(QToolBar)
        self.tab_widget = self.python_console.findChild(EditorTabWidget)

        # Connect current
        self.tab_widget.currentChanged.connect(partial(self.customize_editor, None))

        # Tweak zoom shortcuts to prevent them from interfering
        # when typing '|' and '}' with an AZERTY (French) keyboard layout
        action_zoom_in = self.iface.mainWindow().findChild(QAction, "mActionZoomIn")
        action_zoom_out = self.iface.mainWindow().findChild(QAction, "mActionZoomOut")
        action_zoom_in.setShortcut("")
        action_zoom_out.setShortcut("")

        self.iface.initializationCompleted.connect(self.on_initialization_completed)
        for shortcut_name in (
            "ZoomInToCanvas",
            "ZoomInToCanvas2",
            "ZoomIn2",
            "ZoomOutOfCanvas",
        ):
            shortcut = self.iface.mainWindow().findChild(QShortcut, shortcut_name)
            if shortcut:
                shortcut.setParent(self.iface.mapCanvas())
                shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.zoom_out_shortcut = QShortcut("Ctrl+Alt+-", self.iface.mapCanvas())
        self.zoom_out_shortcut.setObjectName("MyZoomOut")
        self.zoom_out_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.zoom_out_shortcut.activated.connect(action_zoom_out.trigger)

        # Create our own toggle comment action
        separator = self.toolbar.addSeparator()
        separator = separator.setObjectName("separator")
        self.toggle_comment_action = self.toolbar.addAction(
            QIcon(":/images/themes/default/console/iconCommentEditorConsole.svg"),
            self.tr("Toggle Comment"),
        )
        self.toggle_comment_action.setObjectName("toggleComment")
        self.toggle_comment_action.triggered.connect(self.toggle_comment)
        self.toggle_comment_action.setShortcut("Ctrl+:")
        self.toggle_comment_action.setToolTip(
            f"<b>{self.toggle_comment_action.text()}</b> ({self.toggle_comment_action.shortcut().toString()})"
        )

        # Add format action
        self.format_action = self.toolbar.addAction(
            QIcon(r":/plugins/pythontools/wizard.svg"), self.tr("Format file")
        )

        self.format_action.setObjectName("format")
        self.format_action.setShortcut("Ctrl+Alt+F")
        self.format_action.triggered.connect(self.format_file)
        self.format_action.setToolTip(
            f"<b>{self.format_action.text()}</b> ({self.format_action.shortcut().toString()})"
        )

        # Add insert icon from ressource action
        self.insert_resource_action = self.toolbar.addAction(
            QIcon(":/images/themes/default/propertyicons/diagram.svg"),
            self.tr("Insert resource path"),
        )
        self.insert_resource_action.setObjectName("insertResource")
        self.insert_resource_action.triggered.connect(self.insert_resource)
        self.insert_resource_action.setToolTip(
            f"<b>{self.insert_resource_action.text()}</b>"
        )

        # Add next / previous tab shortcuts
        self.next_tab_shortcut = QShortcut("Ctrl+PgDown", self.python_console)
        self.next_tab_shortcut.setObjectName("NextTab")
        self.next_tab_shortcut.activated.connect(self.go_to_next_tab)

        self.previous_tab_shortcut = QShortcut("Ctrl+PgUp", self.python_console)
        self.previous_tab_shortcut.setObjectName("PreviousTab")
        self.previous_tab_shortcut.activated.connect(self.go_to_previous_tab)

        self.on_settings_changed()

    def on_initialization_completed(self):
        """ Called after QGIS has completed its initialization """

        # Shortcuts are created after plugins
        for shortcut_name in (
            "ZoomInToCanvas",
            "ZoomInToCanvas2",
            "ZoomIn2",
            "ZoomOutOfCanvas",
        ):
            shortcut = self.iface.mainWindow().findChild(QShortcut, shortcut_name)
            if shortcut:
                shortcut.setParent(self.iface.mapCanvas())
                shortcut.setContext(Qt.WidgetWithChildrenShortcut)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        # Delete Settings dialog
        self.settings_dialog.deleteLater()

        # Show comment actions
        self.set_old_comments_action_visible(True)

        # Remove custom actions
        for action_name in ("separator", "toggleComment", "format", "insertResource"):
            action = self.toolbar.findChild(QAction, action_name)
            if action:
                action.deleteLater()

        # Remove Next tab / previous tab shortcuts
        for shortcut in (self.next_tab_shortcut, self.previous_tab_shortcut):
            shortcut.activated.disconnect()
            shortcut.setEnabled(False)
            shortcut.deleteLater()

        # Reenable zoom shortcuts & actions
        for shortcut_name in (
            "ZoomInToCanvas",
            "ZoomInToCanvas2",
            "ZoomIn2",
            "ZoomOutOfCanvas",
        ):
            shortcut = self.iface.mainWindow().findChild(QShortcut, shortcut_name)
            if shortcut:
                shortcut.setParent(self.iface.mainWindow())
                shortcut.setContext(Qt.ApplicationShortcut)

        self.iface.mainWindow().findChild(QAction, "mActionZoomIn").setShortcut(
            "Ctrl+Alt++"
        )
        self.iface.mainWindow().findChild(QAction, "mActionZoomOut").setShortcut(
            "Ctrl+Alt+-"
        )

        self.zoom_out_shortcut.activated.disconnect()
        self.zoom_out_shortcut.setEnabled(False)
        self.zoom_out_shortcut.deleteLater()

        for editor in self.python_console.findChildren(Editor):
            self.restore_editor(editor)

        # Remove menu from plugins menu
        self.iface.pluginMenu().removeAction(self.plugin_menu.menuAction())

    def current_editor(self):
        return self.tab_widget.currentWidget().findChild(Editor)

    def toggle_comment(self):

        editor = self.current_editor()
        editor.beginUndoAction()
        if editor.hasSelectedText():
            start_line, start_pos, end_line, end_pos = editor.getSelection()
        else:
            start_line, start_pos = editor.getCursorPosition()
            end_line, end_pos = start_line, start_pos

        # Special case, only empty lines
        if not any(
            editor.text(line).strip() for line in range(start_line, end_line + 1)
        ):
            return

        all_commented = all(
            editor.text(line).strip().startswith("#")
            for line in range(start_line, end_line + 1)
            if editor.text(line).strip()
        )
        min_indentation = min(
            editor.indentation(line)
            for line in range(start_line, end_line + 1)
            if editor.text(line).strip()
        )

        for line in range(start_line, end_line + 1):
            # Empty line
            if not editor.text(line).strip():
                continue

            delta = 0

            if not all_commented:
                editor.insertAt("# ", line, min_indentation)
                delta = -2
            else:
                if not editor.text(line).strip().startswith("#"):
                    continue
                if editor.text(line).strip().startswith("# "):
                    delta = 2
                else:
                    delta = 1

                editor.setSelection(
                    line,
                    editor.indentation(line),
                    line,
                    editor.indentation(line) + delta,
                )
                editor.removeSelectedText()

        editor.endUndoAction()

        editor.setSelection(start_line, start_pos - delta, end_line, end_pos - delta)

    def format_file(self):
        editor = self.current_editor()

        # Check there's no syntax errors before calling black
        if not editor.syntaxCheck():
            return

        import_or_install("black")

        old_pos = editor.getCursorPosition()
        old_scroll_value = editor.verticalScrollBar().value()

        myfile = tempfile.mkstemp(".py")
        filepath = myfile[1]
        os.close(myfile[0])
        with open(filepath, "w") as out:
            out.write(editor.text().replace("\r\n", "\n"))

        line_length = self.settings.value("max_line_length", 88, int)

        completed_process = subprocess.run(
            f"python3 -m black {filepath} -l {line_length}",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if completed_process.returncode == 0:
            with open(filepath) as out:
                content = out.read()
            editor.beginUndoAction()
            editor.selectAll()
            editor.removeSelectedText()
            editor.insert(content)
            editor.setCursorPosition(*old_pos)
            editor.verticalScrollBar().setValue(old_scroll_value)
            editor.endUndoAction()

        os.remove(filepath)

    def insert_resource(self):
        dialog = ResourceBrowser()
        res = dialog.exec()
        if res == QDialog.Accepted:

            editor = self.current_editor()
            line, offset = editor.getCursorPosition()
            old_selection = editor.getSelection()
            if old_selection == (-1, -1, -1, -1):
                selection = (line, offset - 1, line, offset + 1)
            else:
                selection = (
                    old_selection[0],
                    old_selection[1] - 1,
                    old_selection[2],
                    old_selection[3] + 1,
                )

            editor.setSelection(*selection)
            selected_text = editor.selectedText()

            if selected_text and not (
                selected_text[-1] == selected_text[0]
                and selected_text[-1] in ("'", '"')
            ):
                editor.setSelection(*old_selection)
                if old_selection == (-1, -1, -1, -1):
                    editor.setCursorPosition(line, offset)
            editor.removeSelectedText()
            ressource_path = f'"{dialog.icon}"'
            editor.insert(ressource_path)

            line, offset = editor.getCursorPosition()
            editor.setCursorPosition(line, offset + len(ressource_path))

    def go_to_next_tab(self):
        self.tab_widget.setCurrentIndex(
            (self.tab_widget.currentIndex() + 1) % self.tab_widget.count()
        )

    def go_to_previous_tab(self):
        self.tab_widget.setCurrentIndex(
            (self.tab_widget.currentIndex() - 1) % self.tab_widget.count()
        )

    def show_about(self):

        # Used to display plugin icon in the about message box
        bogus = QWidget(self.iface.mainWindow())
        bogus.setWindowIcon(QIcon(":/plugins/pythontools/icon.svg"))
        QMessageBox.about(
            bogus,
            self.tr("About Python Tools"),
            "<b>{0}</b> : <a href=https://github.com/YoannQDQ/qgis-python-tools>GitHub</a><br>"
            "<b>{1}</b> : <a href=https://github.com/YoannQDQ/qgis-python-tools/issues>GitHub</a><br>"
            "<b>{2}</b> : <a href=https://github.com/YoannQDQ/qgis-python-tools#python-tools-qgis-plugin>GitHub</a>".format(
                self.tr("Source code"),
                self.tr("Report issues"),
                self.tr("Documentation"),
            ),
        )

        bogus.deleteLater()

    def set_old_comments_action_visible(self, value):
        self.toolbar.actions()[13].setVisible(value)
        self.toolbar.actions()[14].setVisible(value)
        self.toolbar.actions()[15].setVisible(value)

    def show_settings(self):

        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def on_settings_changed(self):

        # Hide / Show old comment actions
        self.set_old_comments_action_visible(
            not self.settings.value("hide_old_comment_actions", True, bool)
        )

        for editor in self.python_console.findChildren(Editor):
            self.customize_editor(editor)

    def customize_editor(self, editor=None):
        if editor is None:
            editor = self.current_editor()

        if editor is None:
            return

        editor.setFolding(
            self.settings.value("folding_style", QsciScintilla.BoxedTreeFoldStyle, int)
        )

        # Add a small margin after the indicator (if folding is not Plain or None)
        if editor.folding() > 1:
            editor.setMarginWidth(3, "0")
        else:
            editor.setMarginWidth(3, "")

        if self.settings.value("ruler_visible", True, bool):
            editor.setEdgeMode(QsciScintilla.EdgeLine)
            editor.setEdgeColumn(self.settings.value("max_line_length", 88, int))
            editor.setEdgeColor(
                self.settings.value("ruler_color", QColor("#00aaff"), QColor)
            )
        else:
            editor.setEdgeMode(QsciScintilla.EdgeNone)

    def restore_editor(self, editor):
        editor.setFolding(QsciScintilla.PlainFoldStyle)
        editor.setEdgeMode(QsciScintilla.EdgeLine)
        editor.setEdgeColumn(80)
        editor.setMarginWidth(3, "")
        editor.setEdgeColor(
            QSettings().value(
                "pythonConsole/edgeColorEditor", QColor("#efefef"), QColor
            )
        )
