"""Verify the chat view pins smoothly while streaming and never yanks a user who scrolled up."""

from PySide6 import QtCore, QtWidgets

from nuke_codex_panel.ui.chat_view import ChatView


app = QtWidgets.QApplication.instance()
assert app is not None

# The scroll area must see a fixed viewport or the window auto-grows to fit
# the content and nothing ever scrolls (vacuous test).
holder = QtWidgets.QWidget()
holder.setFixedSize(420, 260)  # pin the viewport or hint-based resizing defeats the test
holder_layout = QtWidgets.QVBoxLayout(holder)
holder_layout.setContentsMargins(0, 0, 0, 0)
chat = ChatView()
holder_layout.addWidget(chat)
holder.show()
chat.add_user_message("question?", [])
chat.start_assistant("Codex")


def pump(cycles=3):
    for _ in range(cycles):
        app.processEvents()


def send_chunk(n):
    chat.append_delta("chunk %d: " % n + ("lorem ipsum dolor sit amet " * 3) + "\n\n")


# Phase 1: stream 40 chunks pinned at bottom; the scrollbar must follow the
# maximum and never bounce backwards while deltas arrive.
pump()
assert chat.verticalScrollBar().maximum() == 0, "expected no scroll before content"
samples = []


def sample(tag):
    bar = chat.verticalScrollBar()
    samples.append((tag, bar.value(), bar.maximum()))


def step(n):
    send_chunk(n)
    sample("s%d" % n)


for n in range(40):
    send_chunk(n)
    pump()
sample("end")

backward_bounces = sum(
    1
    for (_, prev_v, prev_m), (_, v, m) in zip(samples, samples[1:])
    if v < prev_v and m >= prev_m
)
# After layout settles the value must sit at the maximum; never fall behind.
pump(6)
bar = chat.verticalScrollBar()
assert bar.maximum() > 0, "content never overran the viewport \u2014 test is vacuous"
assert bar.value() == bar.maximum(), "not pinned after stream: %d vs %d" % (
    bar.value(),
    bar.maximum(),
)
assert backward_bounces == 0, "scrollbar ran backwards %d times while streaming" % backward_bounces

# Phase 2: user scrolls up to read; streaming more must not yank them down.
chat.verticalScrollBar().setValue(0)
pump()
start_value = chat.verticalScrollBar().value()
for n in range(10):
    send_chunk(100 + n)
    pump()
yank_test = chat.verticalScrollBar().value()
assert yank_test <= start_value + 60, "stream yanked a user who scrolled up: %d -> %d" % (
    start_value,
    yank_test,
)

print("NUKE_CODEX_CHAT_SCROLL_OK backward_bounces=%d max=%d yank=%d" % (
    backward_bounces, bar.maximum(), yank_test
))
chat.close()