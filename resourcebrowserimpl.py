# -*- coding: utf-8 -*-

import os

from PyQt5.QtCore import (
    QAbstractListModel,
    QResource,
    Qt,
    QModelIndex,
    QSortFilterProxyModel,
    QSize,
)
from PyQt5.QtGui import QIcon, QGuiApplication
from PyQt5.QtWidgets import QDialog, QTreeWidgetItem, QMenu

from .resourcebrowser import Ui_ResourceBrowser


class RessourceModel(QAbstractListModel):
    def __init__(self, extensions=None, parent=None):

        super().__init__(parent)
        self.ressource_root = ""
        self.icons = []
        self.extensions = extensions

    def set_source(self, path):
        self.beginResetModel()
        self.ressource_root = path
        self.icons = sorted(
            [
                name
                for name in QResource(self.ressource_root).children()
                if (
                    QResource(self.ressource_root + "/" + name).isFile()
                    and (
                        self.extensions is None
                        or os.path.splitext(name)[1].lower() in self.extensions
                    )
                )
            ]
        )
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return

        name = self.icons[index.row()]
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return name
        if role == Qt.EditRole:
            return f":{self.ressource_root}/{name}"
        if role == Qt.DecorationRole:
            return QIcon(f":{self.ressource_root}/{name}")

        return

    def rowCount(self, index=QModelIndex()):
        return len(self.icons)


class ResourceBrowser(QDialog, Ui_ResourceBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.icon = None

        self.extensions = (".svg", ".png", ".jpg", ".gif", ".jpeg", ".bmp", ".ico")

        self.resource_model = RessourceModel(self.extensions, self)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSourceModel(self.resource_model)
        self.view.setModel(self.proxy_model)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.on_context_menu)
        self.filterLineEdit.textChanged.connect(self.proxy_model.setFilterRegExp)
        self.view.clicked.connect(self.on_click)
        self.view.doubleClicked.connect(self.on_double_click)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.default_item = None
        self.ressourceTree.setColumnCount(2)
        self.build_resource_tree(self.ressourceTree.invisibleRootItem(), "")
        self.ressourceTree.setColumnHidden(1, True)
        self.ressourceTree.currentItemChanged.connect(self.on_ressource_changed)
        self.ressourceTree.expandItem(self.default_item)
        self.ressourceTree.setCurrentItem(self.default_item)

    def build_resource_tree(self, parent_item, parent_key):
        for key in QResource(parent_key).children():
            full_key = f"{parent_key}/{key}"
            if QResource(full_key).isDir():

                item = QTreeWidgetItem([key, full_key])
                self.build_resource_tree(item, full_key)
                parent_item.addChild(item)
                if full_key == "/images/themes/default":
                    self.default_item = item

    def on_ressource_changed(self, current_item, previous_item):
        self.resource_model.set_source(current_item.data(1, Qt.DisplayRole))

    def set_icon(self, url):
        self.previewLabel.setPixmap(QIcon(url).pixmap(QSize(64, 64)))
        self.previewName.setText(url)
        self.icon = url
        self.okButton.setEnabled(True)

    def on_click(self, index):
        url = self.proxy_model.data(index, Qt.EditRole)
        self.set_icon(url)

    def on_double_click(self, index):
        self.on_click(index)
        self.accept()

    def on_context_menu(self, point):
        index = self.view.indexAt(point)
        if index.isValid():
            menu = QMenu()
            menu.addAction(
                QIcon(":/images/themes/default/mActionEditCopy.svg"),
                self.tr("Copy resource path to clipboard"),
            )
            menu.exec(self.view.mapToGlobal(point))
            QGuiApplication.clipboard().setText(
                self.proxy_model.data(index, Qt.EditRole)
            )
