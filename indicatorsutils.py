from PyQt5.QtCore import Qt, QSettings, QSize
from PyQt5.Qsci import QsciScintilla, QsciStyle
from PyQt5.QtGui import QColor, QPixmap, QFont

from .dependencies import check_module


SYNTAX_ERROR_STYLE = 100


def check_syntax(editor, *args, **kwargs):

    if not check_module("jedi", "0.17"):
        return

    import jedi

    s = jedi.Script(code=editor.text())
    errors = s.get_syntax_errors()

    editor.markerDeleteAll()
    editor.clearAnnotations()
    clear_all_indicators(editor)

    if not errors:
        return True

    for error in errors:
        eline = error.line - 1
        ecolumn = error.column
        edescr = error._parso_error.message
        if eline not in editor.bufferMarkerLine:
            editor.bufferMarkerLine.append(eline)
        syntax_error(editor, eline, ecolumn, error.until_line - 1, error.until_column)

        editor.markerAdd(eline, editor.MARKER_NUM)
        editor.annotate(eline, edescr, editor.style_annotation)
        editor.setCursorPosition(eline, ecolumn - 1)
        editor.ensureLineVisible(eline)
    return False


def define_indicators(editor):

    # Create annotation style
    load_font = QSettings().value("pythonConsole/fontfamilytextEditor", "Monospace")
    editor.style_annotation = QsciStyle(
        SYNTAX_ERROR_STYLE,
        "Annotation",
        QColor("#ff0000"),
        QColor("#ffdddd"),
        QFont(load_font, 8, -1, False),
        True,
    )

    editor.markerDefine(
        QPixmap(":/plugins/bettereditor/clear.svg").scaled(
            QSize(16, 16), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ),
        editor.MARKER_NUM,
    )
    editor.setAnnotationDisplay(QsciScintilla.AnnotationStandard)

    editor.indicatorDefine(QsciScintilla.TriangleCharacterIndicator, 20)
    editor.setIndicatorForegroundColor(QColor("red"), 20)
    editor.indicatorDefine(QsciScintilla.SquiggleLowIndicator, 21)
    editor.setIndicatorForegroundColor(QColor("red"), 21)


def indicator(editor, line, col, nb_chars, style=0, value=99):
    editor.SendScintilla(QsciScintilla.SCI_SETINDICATORCURRENT, style)
    editor.SendScintilla(QsciScintilla.SCI_SETINDICATORVALUE, value)
    start_pos = editor.positionFromLineIndex(line, col)
    editor.SendScintilla(QsciScintilla.SCI_INDICATORFILLRANGE, start_pos, nb_chars)


def clear_indicator(editor, line, col, nb_chars, style=0):
    editor.SendScintilla(QsciScintilla.SCI_SETINDICATORCURRENT, style)
    start_pos = editor.positionFromLineIndex(line, col)
    editor.SendScintilla(QsciScintilla.SCI_INDICATORCLEARRANGE, start_pos, nb_chars)


def clear_indicator_from_file(editor, style=2):
    editor.SendScintilla(QsciScintilla.SCI_SETINDICATORCURRENT, style)
    editor.SendScintilla(QsciScintilla.SCI_INDICATORCLEARRANGE, 0, len(editor.text()))


def clear_all_indicators(editor):
    for i in range(32):
        clear_indicator_from_file(editor, i)


def syntax_error(editor, start_line, start_column, end_line, end_column):
    start_pos = editor.positionFromLineIndex(start_line, start_column)
    end_pos = editor.positionFromLineIndex(end_line, end_column)
    indicator(editor, start_line, start_column, end_pos - start_pos, 20)
    indicator(editor, start_line, start_column + 1, end_pos - start_pos - 1, 21)
