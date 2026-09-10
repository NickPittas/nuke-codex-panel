"""Verify the bubble chat view streams, orders sections chronologically, and renders Markdown."""

from PySide6 import QtCore, QtGui, QtWidgets

from nuke_codex_panel.ui.chat_view import BubbleText, ChatView, CollapsibleSection


app = QtWidgets.QApplication.instance()
assert app is not None


def bubble_sections(chat):
    """Ordered [kind, text] of the last assistant bubble's sections."""
    for index in range(chat.messages_layout.count() - 1, -1, -1):
        row = chat.messages_layout.itemAt(index).widget()
        if row is None:
            continue
        bubble = row.layout().itemAt(0).widget()
        if bubble is not None and bubble.objectName() == "assistantBubble":
            inner = bubble.layout()
            break
    else:
        raise AssertionError("no assistant bubble found")
    out = []
    for index in range(inner.count()):
        widget = inner.itemAt(index).widget()
        if isinstance(widget, CollapsibleSection):
            body = widget.body
            text = (
                body.toPlainText()
                if isinstance(body, BubbleText)
                else "\n".join(label.text() for label in body.findChildren(QtWidgets.QLabel))
            )
            out.append([widget.title.split()[0], text])
        elif isinstance(widget, BubbleText):
            out.append(["text", widget.toPlainText()])
    return out


chat = ChatView()
chat.resize(400, 300)
chat.add_user_message("hello\n\n```json\n{\"a\": 1}\n```", [])
chat.start_assistant("Codex")
chat.append_thinking("first thought")
chat.append_delta("first reply")
chat.add_tool_event({"phase": "start", "id": "t1", "tool": "bash", "detail": "ls /"})
chat.add_tool_event({"phase": "end", "id": "t1", "tool": "bash", "ok": True, "detail": "afs bin"})
chat.add_tool_event({"phase": "start", "id": "t2", "tool": "read", "detail": "a.py"})
chat.append_thinking("second thought")
chat.append_delta("second reply")
chat.finish_assistant()
chat.add_error("boom")

sections = bubble_sections(chat)
kinds = [kind for kind, _text in sections]
assert kinds == ["Thinking", "text", "Tools", "Thinking", "text"], kinds
assert "first thought" in sections[0][1]
assert "first reply" in sections[1][1]
assert "bash" in sections[2][1] and "read" in sections[2][1]
assert "second thought" in sections[3][1]
assert "second reply" in sections[4][1]
# a tool result must not land in the reply block above it
assert "afs bin" not in sections[1][1] and "afs bin" in sections[2][1]

browsers = chat.container.findChildren(QtWidgets.QTextBrowser)
texts = [widget.document().toMarkdown() for widget in browsers]
assert '"a": 1' in texts[0], texts[0]
assert "boom" in texts[-1], texts[-1]

# Sections collapse and expand.
sections_widgets = chat.container.findChildren(CollapsibleSection)
for section in sections_widgets:
    assert not section.body.isHidden()
    section.header.setChecked(False)
    assert section.body.isHidden(), section.title
    assert section.header.text().startswith("▸")
    section.header.setChecked(True)
    assert not section.body.isHidden()

# Wheel over a bubble must scroll the chat, not die inside the bubble.
tall_text = "\n\n".join("paragraph %d with some padding text" % i for i in range(60))
chat.start_assistant("Tall")
chat.append_delta(tall_text)
chat.finish_assistant()
chat.resize(400, 300)
chat.show()
chat.verticalScrollBar().setValue(0)
first = chat.container.findChildren(QtWidgets.QTextBrowser)[1]
wheel = QtGui.QWheelEvent(
    QtCore.QPointF(5, 5), QtCore.QPointF(5, 5),
    QtCore.QPoint(0, 0), QtCore.QPoint(0, -120),
    QtCore.Qt.MouseButtons(QtCore.Qt.MouseButton.NoButton),
    QtCore.Qt.KeyboardModifiers(QtCore.Qt.KeyboardModifier.NoModifier),
    QtCore.Qt.ScrollPhase.NoScrollPhase, False,
)
for _ in range(4):
    app.processEvents()
QtWidgets.QApplication.sendEvent(first.viewport(), wheel)
assert chat.verticalScrollBar().value() > 0, "wheel did not scroll the chat"

print(
    "NUKE_CODEX_CHAT_RENDER_OK",
    len(sections),
    "ordered sections,",
    len(sections_widgets),
    "collapsible",
)
