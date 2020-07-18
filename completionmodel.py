from PyQt5.QtCore import QModelIndex, Qt, QAbstractListModel
from PyQt5.QtGui import QIcon


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
