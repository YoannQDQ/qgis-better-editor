# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Better Editor
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
import sys
import configparser


from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QTimer
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import (
    QAction,
    QMessageBox,
    QWidget,
    QToolBar,
    QShortcut,
    QCompleter,
)
from PyQt5.Qsci import QsciScintilla

from qgis.core import QgsApplication

from console.console import PythonConsole
from console.console_editor import Editor, EditorTabWidget, EditorTab
from processing.script.ScriptEdit import ScriptEdit
from processing.script.ScriptEditorDialog import ScriptEditorDialog


from .dependencies import (
    import_or_install,
    check_pip,
    check_minimum_version,
    install,
    check_module,
)
from .customclasses import (
    MonkeyEditorTab,
    MonkeyEditor,
    MonkeyScriptEditor,
    MonkeyScriptEditorDialog,
)
from .settingsdialogimpl import SettingsDialog
from .indicatorsutils import define_indicators, clear_all_indicators, MARKER_NUMBER
from .completionmodel import CompletionModel
from .calltips import CallTips
from .monkeypatch import patch, unpatch
from .resources import *


class BetterEditor:
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
        locale_path = os.path.join(self.plugin_dir, "i18n", "BetterEditor_{}.qm".format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Init settings
        self.settings = QSettings()
        self.settings.beginGroup("plugins/bettereditor")

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
        return QCoreApplication.translate("BetterEditor", message)

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
            QIcon(":/plugins/bettereditor/icons/about.svg"),
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
            QIcon(":/plugins/bettereditor/icons/icon.svg"), "Better Editor"
        )
        self.plugin_menu.addAction(self.about_action)
        self.plugin_menu.addAction(self.settings_action)
        self.toolbar = self.python_console.findChild(QToolBar)
        self.tab_widget = self.python_console.findChild(EditorTabWidget)

        # Connect current
        self.tab_widget.currentChanged.connect(self.customize_current_editor)

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

        # Customize buttons tooltips
        save_button = self.python_console.widget().saveFileButton
        saveas_button = self.python_console.widget().saveAsFileButton
        run_button = self.python_console.widget().runScriptEditorButton

        save_button.setToolTip(f"<b>{save_button.text()}</b> (Ctrl+S)")
        saveas_button.setToolTip(f"<b>{saveas_button.text()}</b> (Ctrl+Shift+S)")
        run_button.setToolTip(f"<b>{run_button.text()}</b> (Ctrl+R)")

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

        # Check that submodules are installed
        self.black = None
        self.jedi = None
        self.check_dependencies()

        # Add format action
        self.format_action = self.toolbar.addAction(
            QIcon(r":/plugins/bettereditor/icons/wizard.svg"), self.tr("Format file")
        )
        self.format_action.setObjectName("format")
        self.format_action.setShortcut("Ctrl+Alt+F")
        self.format_action.triggered.connect(self.format_file)
        self.format_action.setToolTip(
            f"<b>{self.format_action.text()}</b> ({self.format_action.shortcut().toString()})"
        )
        if not self.black:
            self.format_action.setEnabled(False)

        self.project = None
        if self.jedi:
            self.project = self.jedi.Project("", sys_path=sys.path, load_unsafe_extensions=True, smart_sys_path=False)

        patch(Editor, MonkeyEditor)
        patch(EditorTab, MonkeyEditorTab)
        patch(ScriptEdit, MonkeyScriptEditor)
        patch(ScriptEditorDialog, MonkeyScriptEditorDialog)
        ScriptEdit.project = self.project
        ScriptEdit.settings = self.settings

        self.oldAutoCloseBracketEditor = QSettings().value("pythonConsole/autoCloseBracketEditor", False, bool)
        QSettings().setValue("pythonConsole/autoCloseBracketEditor", False)

        # Add insert icon from ressource action
        self.insert_resource_action = self.toolbar.addAction(
            QIcon(":/images/themes/default/propertyicons/diagram.svg"),
            self.tr("Insert resource path"),
        )
        self.insert_resource_action.setObjectName("insertResource")
        self.insert_resource_action.triggered.connect(self.insert_resource)
        self.insert_resource_action.setToolTip(f"<b>{self.insert_resource_action.text()}</b>")

        # Add next / previous tab shortcuts
        self.next_tab_shortcut = QShortcut("Ctrl+PgDown", self.python_console)
        self.next_tab_shortcut.setObjectName("NextTab")
        self.next_tab_shortcut.activated.connect(self.go_to_next_tab)

        self.previous_tab_shortcut = QShortcut("Ctrl+PgUp", self.python_console)
        self.previous_tab_shortcut.setObjectName("PreviousTab")
        self.previous_tab_shortcut.activated.connect(self.go_to_previous_tab)

        self.on_settings_changed()

        if not self.black or not self.jedi:
            if not check_pip():

                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Error"),
                    self.tr(
                        "Pip is not installed. Try to get it, then restart QGIS, or  manually install <b>black</b> and <b>jedi</b>"
                    ),
                )

            else:
                if not self.black:
                    QMessageBox.warning(
                        self.iface.mainWindow(),
                        self.tr("Error"),
                        self.tr(
                            "Unable to load <b>black</b>. Formatting will be disabled. You could try to manually install <b>black</b> with pip"
                        ),
                    )

                if not self.jedi:

                    # If check_module return true, an obsolete version was loaded, ad user was already informed
                    if not check_module("jedi"):
                        QMessageBox.warning(
                            self.iface.mainWindow(),
                            self.tr("Error"),
                            self.tr(
                                "Unable to load <b>jedi</b>. Multi syntax error check will be disabled. You could try to manually install <b>jedi</b> with pip"
                            ),
                        )

    def check_dependencies(self):
        install("packaging")
        self.black, _ = import_or_install("black")
        self.jedi, jedi_version = import_or_install("jedi")

        # JEDI 0.17 is required
        if not check_minimum_version(jedi_version, "0.17"):
            res = QMessageBox.question(
                self.iface.mainWindow(),
                self.tr("Information"),
                self.tr(
                    "<b>jedi</b> version is {0} and BetterEditor needs {1}. Do you want to upgrade <b>jedi</b>?<br><b>Warning:</b> it could cause old code relying on the obsolete <b>jedi</b> to stop working correctly."
                ).format(jedi_version, "0.17"),
                QMessageBox.Yes | QMessageBox.No,
            )

            if res == QMessageBox.Yes:
                install("jedi", True)
                QMessageBox.information(
                    self.iface.mainWindow(),
                    self.tr("Information"),
                    self.tr("Jedi was upgraded. You need to restart QGIS to fully use BetterEditor"),
                )

            self.jedi = None

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

        # Remove buttons tooltips
        save_button = self.python_console.widget().saveFileButton
        saveas_button = self.python_console.widget().saveAsFileButton
        run_button = self.python_console.widget().runScriptEditorButton

        save_button.setToolTip(save_button.text())
        saveas_button.setToolTip(saveas_button.text())
        run_button.setToolTip(run_button.text())

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

        self.iface.mainWindow().findChild(QAction, "mActionZoomIn").setShortcut("Ctrl+Alt++")
        self.iface.mainWindow().findChild(QAction, "mActionZoomOut").setShortcut("Ctrl+Alt+-")

        self.zoom_out_shortcut.activated.disconnect()
        self.zoom_out_shortcut.setEnabled(False)
        self.zoom_out_shortcut.deleteLater()

        self.tab_widget.currentChanged.disconnect(self.customize_current_editor)
        for editor in self.python_console.findChildren(Editor):
            clear_all_indicators(editor)
            self.restore_editor(editor)

        # Revert MonkeyPatch
        unpatch(Editor)
        unpatch(EditorTab)
        unpatch(ScriptEdit)
        unpatch(ScriptEditorDialog)

        del ScriptEdit.project
        del ScriptEdit.settings

        # Remove menu from plugins menu
        self.iface.pluginMenu().removeAction(self.plugin_menu.menuAction())

        # Reactivate old autoCloseBracketEditor
        QSettings().setValue("pythonConsole/autoCloseBracketEditor", self.oldAutoCloseBracketEditor)

    def current_editor(self) -> Editor:
        if not self.tab_widget.currentWidget():
            return None
        return self.tab_widget.currentWidget().findChild(Editor)

    def toggle_comment(self):
        self.current_editor().toggle_comment()

    def format_file(self):
        self.current_editor().format_file()

    def insert_resource(self):
        self.current_editor().insert_resource()

    def go_to_next_tab(self):
        self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() + 1) % self.tab_widget.count())

    def go_to_previous_tab(self):
        self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() - 1) % self.tab_widget.count())

    def show_about(self):

        # Used to display plugin icon in the about message box
        bogus = QWidget(self.iface.mainWindow())
        bogus.setWindowIcon(QIcon(":/plugins/bettereditor/icons/icon.svg"))

        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(os.path.dirname(__file__), "metadata.txt"))
        version = cfg.get("general", "version")

        QMessageBox.about(
            bogus,
            self.tr("About Better Editor"),
            "<b>Version</b> {0}<br><br>"
            "<b>{1}</b> : <a href=https://github.com/YoannQDQ/qgis-better-editor>GitHub</a><br>"
            "<b>{2}</b> : <a href=https://github.com/YoannQDQ/qgis-better-editor/issues>GitHub</a><br>"
            "<b>{3}</b> : <a href=https://github.com/YoannQDQ/qgis-better-editor#better-editor-qgis-plugin>GitHub</a>".format(
                version,
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
        self.set_old_comments_action_visible(not self.settings.value("hide_old_comment_actions", True, bool))

        for editor in self.python_console.findChildren(Editor):
            self.customize_editor(editor)

    def customize_current_editor(self):
        return self.customize_editor()

    def customize_editor(self, editor: Editor = None):
        if editor is None:
            editor = self.current_editor()

        if editor is None:
            return
        editor.project = self.project

        # Disable shortcuts
        for shortcut in editor.findChildren(QShortcut):
            shortcut.setEnabled(False)

        editor.set_completer(QCompleter(editor))
        editor.completer.setModel(CompletionModel([], editor))
        editor.callTips = CallTips(editor)
        editor.callTipsTimer = QTimer(editor)
        editor.callTipsTimer.setSingleShot(True)
        editor.callTipsTimer.setInterval(500)
        editor.callTipsTimer.timeout.connect(editor.update_calltips)

        editor.setCallTipsStyle(QsciScintilla.CallTipsNone)
        editor.setAutoCompletionSource(QsciScintilla.AcsNone)
        editor.setFolding(self.settings.value("folding_style", QsciScintilla.BoxedTreeFoldStyle, int))

        # Add a small margin after the indicator (if folding is not Plain or None)
        if editor.folding() > 1:
            editor.setMarginWidth(3, "0")
        else:
            editor.setMarginWidth(3, "")

        if self.settings.value("ruler_visible", True, bool):
            editor.setEdgeMode(QsciScintilla.EdgeLine)
            editor.setEdgeColumn(self.settings.value("max_line_length", 88, int))
            editor.setEdgeColor(self.settings.value("ruler_color", QColor("#00aaff"), QColor))
        else:
            editor.setEdgeMode(QsciScintilla.EdgeNone)

        # Change syntax error marker
        define_indicators(editor)

        editor.cursorPositionChanged.connect(editor.on_position_changed)

    def restore_editor(self, editor: Editor):
        editor.cursorPositionChanged.disconnect(editor.on_position_changed)
        editor.setFolding(QsciScintilla.PlainFoldStyle)
        editor.setEdgeMode(QsciScintilla.EdgeLine)
        editor.setEdgeColumn(80)
        editor.setMarginWidth(3, "")
        editor.setEdgeColor(QSettings().value("pythonConsole/edgeColorEditor", QColor("#efefef"), QColor))

        # Disable shortcuts
        for shortcut in editor.findChildren(QShortcut):
            shortcut.setEnabled(True)

        editor.markerDefine(
            QgsApplication.getThemePixmap("console/iconSyntaxErrorConsole.svg"),
            MARKER_NUMBER,
        )

        editor.setAnnotationDisplay(QsciScintilla.AnnotationBoxed)
        editor.setCallTipsStyle(QsciScintilla.CallTipsNoContext)
        editor.setAutoCompletionSource(QsciScintilla.AcsAll)

        editor.callTips.deleteLater()
        del editor.callTips
        editor.callTipsTimer.deleteLater()
        del editor.callTipsTimer
        editor.completer.deleteLater()
        del editor.completer
        del editor.project
