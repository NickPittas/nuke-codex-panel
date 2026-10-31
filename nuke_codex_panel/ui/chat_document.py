"""Thin adapter from Qt's own Markdown import to the chat look.

The parsing is Qt's (``QTextDocument.setMarkdown``, GitHub dialect: tables, task lists,
strikethrough, autolinks; raw HTML disabled so it is shown as text). Qt hardcodes neither a dark
theme nor wrapping of code, so after the import one pass over the document restyles what the
importer produced: code blocks and inline code (colors, mono font, wrapping), links, table
borders/header, paragraph spacing. Nothing is parsed here.
"""

from __future__ import annotations

from PySide6 import QtGui

from .chat_markdown import MarkdownStyle, user_breaks

_FEATURES = (
    QtGui.QTextDocument.MarkdownFeature.MarkdownDialectGitHub
    | QtGui.QTextDocument.MarkdownFeature.MarkdownNoHTML
)
_PARAGRAPH_GAP = 6
_HEADING_GAP = 8


def _is_code_block(fmt: QtGui.QTextBlockFormat) -> bool:
    return fmt.hasProperty(QtGui.QTextFormat.Property.BlockCodeFence) or fmt.nonBreakableLines()


def load_markdown(document: QtGui.QTextDocument, source: str, style: MarkdownStyle, breaks: bool = False):
    """Replace ``document``'s content by ``source`` rendered with Qt's Markdown importer + chat look."""
    document.setMarkdown(user_breaks(source) if breaks else source, _FEATURES)
    _restyle(document, style)
    document.markContentsDirty(0, document.characterCount())


def _restyle(document: QtGui.QTextDocument, style: MarkdownStyle):
    code_bg = QtGui.QBrush(QtGui.QColor(style.code_bg))
    code_char = QtGui.QTextCharFormat()
    code_char.setForeground(QtGui.QBrush(QtGui.QColor(style.code_fg)))
    code_char.setFontFamilies([style.mono_family])
    code_char.setFontPointSize(style.mono_pt)
    code_char.setFontFixedPitch(True)
    link_char = QtGui.QTextCharFormat()
    link_char.setForeground(QtGui.QBrush(QtGui.QColor(style.accent)))
    inline_code = QtGui.QTextCharFormat(code_char)
    inline_code.setBackground(code_bg)

    block_ops = []  # (block position, new QTextBlockFormat)
    char_ops = []  # (position, length, QTextCharFormat)
    block = document.begin()
    while block.isValid():
        fmt = block.blockFormat()
        in_table = isinstance(document.frameAt(block.position()), QtGui.QTextTable)
        if _is_code_block(fmt):
            previous, following = block.previous(), block.next()
            new = QtGui.QTextBlockFormat(fmt)
            new.setBackground(code_bg)
            new.setNonBreakableLines(False)
            new.setTopMargin(_PARAGRAPH_GAP if not (previous.isValid() and _is_code_block(previous.blockFormat())) else 0)
            new.setBottomMargin(_PARAGRAPH_GAP if not (following.isValid() and _is_code_block(following.blockFormat())) else 0)
            block_ops.append((block.position(), new))
            if block.length() > 1:
                char_ops.append((block.position(), block.length() - 1, code_char))
        else:
            if block.textList() is None and fmt.headingLevel() == 0 and not in_table:
                if fmt.bottomMargin() != _PARAGRAPH_GAP:
                    new = QtGui.QTextBlockFormat(fmt)
                    new.setBottomMargin(_PARAGRAPH_GAP)
                    block_ops.append((block.position(), new))
            elif fmt.headingLevel() > 0 and fmt.topMargin() != _HEADING_GAP:
                new = QtGui.QTextBlockFormat(fmt)
                new.setTopMargin(_HEADING_GAP)
                new.setBottomMargin(_PARAGRAPH_GAP)
                block_ops.append((block.position(), new))
            fragments = block.begin()
            while not fragments.atEnd():
                fragment = fragments.fragment()
                char_format = fragment.charFormat()
                if char_format.isAnchor():
                    char_ops.append((fragment.position(), fragment.length(), link_char))
                elif char_format.fontFixedPitch():
                    char_ops.append((fragment.position(), fragment.length(), inline_code))
                fragments += 1
        block = block.next()

    tables = _tables(document.rootFrame())
    if not (block_ops or char_ops or tables):
        return
    cursor = QtGui.QTextCursor(document)
    cursor.beginEditBlock()
    for position, new in block_ops:
        cursor.setPosition(position)
        cursor.setBlockFormat(new)
    for position, length, char_format in char_ops:
        cursor.setPosition(position)
        cursor.setPosition(position + length, QtGui.QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(char_format)
    for table in tables:
        _style_table(table, style)
    cursor.endEditBlock()


def _tables(frame) -> list:
    found = []
    for child in frame.childFrames():
        if isinstance(child, QtGui.QTextTable):
            found.append(child)
        found.extend(_tables(child))
    return found


def _style_table(table: QtGui.QTextTable, style: MarkdownStyle):
    fmt = table.format()
    fmt.setBorder(1)
    fmt.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle.BorderStyle_Solid)
    fmt.setBorderBrush(QtGui.QBrush(QtGui.QColor(style.border)))
    fmt.setCellPadding(5)
    fmt.setCellSpacing(0)
    table.setFormat(fmt)
    header = QtGui.QBrush(QtGui.QColor(style.table_header_bg))
    for column in range(table.columns()):
        cell = table.cellAt(0, column)
        cell_format = cell.format()
        cell_format.setBackground(header)
        cell.setFormat(cell_format)
