"""Verify App Server agent-message items render as separate paragraphs."""

from PySide6 import QtWidgets

from nuke_codex_panel.ui.panel_widget import CodexPanelWidget


app = QtWidgets.QApplication.instance()
assert app is not None


class RenderHarness:
    _start_assistant_message = CodexPanelWidget._start_assistant_message
    _start_agent_message_item = CodexPanelWidget._start_agent_message_item
    _append_assistant_delta = CodexPanelWidget._append_assistant_delta

    def __init__(self):
        self.chat = QtWidgets.QTextEdit()
        self._assistant_stream_open = False
        self._assistant_item_id = None
        self._assistant_item_seen = False


panel = RenderHarness()
panel._start_assistant_message()
panel._start_agent_message_item("commentary-1", "commentary")
panel._append_assistant_delta("First commentary.")
panel._start_agent_message_item("commentary-2", "commentary")
panel._append_assistant_delta("Second commentary.")
panel._start_agent_message_item("final-1", "final_answer")
panel._append_assistant_delta("Final answer.\n\nConnection: A → B")

expected = (
    "Codex:\n"
    "First commentary.\n\n"
    "Second commentary.\n\n"
    "Final answer.\n\nConnection: A → B"
)
actual = panel.chat.toPlainText()
assert actual == expected, repr(actual)
print("NUKE_CODEX_CHAT_RENDER_OK", repr(actual))
