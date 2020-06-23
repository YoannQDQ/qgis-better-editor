# -*- coding: utf-8 -*-

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QDialog
from PyQt5.Qsci import QsciScintilla

from .settingsdialog import Ui_SettingsDialog


class SettingsDialog(QDialog, Ui_SettingsDialog):

    settingsChanged = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.resetting = False
        self.settings = settings
        self.setWindowIcon(QIcon(":/plugins/bettereditor/icon.svg"))

        # Populate folding style combobox
        self.foldingStyleComboBox.addItem(self.tr("None"), QsciScintilla.NoFoldStyle)
        self.foldingStyleComboBox.addItem(
            self.tr("Plain"), QsciScintilla.PlainFoldStyle
        )
        self.foldingStyleComboBox.addItem(
            self.tr("Circled"), QsciScintilla.CircledTreeFoldStyle
        )
        self.foldingStyleComboBox.addItem(
            self.tr("Boxed"), QsciScintilla.BoxedTreeFoldStyle
        )

        # Init dialog from settings
        self.hideCommentCheckBox.setChecked(
            self.settings.value("hide_old_comment_actions", True, bool)
        )
        self.maxLineLengthSpinBox.setValue(
            self.settings.value("max_line_length", 88, int)
        )
        self.formatOnSaveCheckBox.setChecked(
            self.settings.value("format_on_save", True, bool)
        )

        self.rulerCheckBox.setChecked(self.settings.value("ruler_visible", True, bool))
        self.rulerColorButton.setColor(
            self.settings.value("ruler_color", QColor("#00aaff"), QColor)
        )

        self.foldingStyleComboBox.setCurrentIndex(
            self.foldingStyleComboBox.findData(
                self.settings.value(
                    "folding_style", QsciScintilla.BoxedTreeFoldStyle, int
                )
            )
        )

        # Connect signals
        self.hideCommentCheckBox.toggled.connect(self.on_hide_comment_actions_changed)
        self.maxLineLengthSpinBox.valueChanged.connect(self.on_max_length_changed)
        self.formatOnSaveCheckBox.toggled.connect(self.on_format_on_save_changed)
        self.foldingStyleComboBox.currentIndexChanged.connect(
            self.on_folding_style_changed
        )
        self.rulerCheckBox.toggled.connect(self.on_ruler_visible_changed)
        self.rulerColorButton.colorChanged.connect(self.on_ruler_color_changed)
        self.foldingStyleComboBox.currentIndexChanged.connect(
            self.on_folding_style_changed
        )

        self.restoreButton.clicked.connect(self.restore_default_values)

    def on_max_length_changed(self, value):
        """ Called whenever the max line length changes """
        self.settings.setValue("max_line_length", value)
        if not self.resetting:
            self.settingsChanged.emit()

    def on_hide_comment_actions_changed(self, checked):
        """ Called whenever the hide comment actions state changes """
        self.settings.setValue("hide_old_comment_actions", checked)
        if not self.resetting:
            self.settingsChanged.emit()

    def on_format_on_save_changed(self, checked):
        """ Called whenever the hide comment actions state changes """
        self.settings.setValue("format_on_save", checked)
        if not self.resetting:
            self.settingsChanged.emit()

    def on_folding_style_changed(self):
        """ Called whenever the folding style changes """
        self.settings.setValue("folding_style", self.foldingStyleComboBox.currentData())
        if not self.resetting:
            self.settingsChanged.emit()

    def on_ruler_color_changed(self):
        """ Called whenever the ruler color changes """
        self.settings.setValue("ruler_color", self.rulerColorButton.color())
        if not self.resetting:
            self.settingsChanged.emit()

    def on_ruler_visible_changed(self, checked):
        """ Called whenever the ruler visible state changes """
        self.settings.setValue("ruler_visible", checked)
        if not self.resetting:
            self.settingsChanged.emit()

    def restore_default_values(self):
        """ Restore the default value: BoxedTree folding indicator
        88 character-long lines and hide comment/uncomment actions """
        self.resetting = True
        self.hideCommentCheckBox.setChecked(True)
        self.maxLineLengthSpinBox.setValue(88)
        self.formatOnSaveCheckBox.setChecked(True)
        self.foldingStyleComboBox.setCurrentIndex(3)
        self.rulerCheckBox.setChecked(True)
        self.rulerColorButton.setColor(QColor("#00aaff"))
        self.resetting = False
        self.settingsChanged.emit()
