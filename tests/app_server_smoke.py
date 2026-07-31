"""Live smoke test for the Codex App Server using Nuke's PySide6 runtime."""

from pathlib import Path
import tempfile

from PySide6 import QtCore, QtGui

from nuke_codex_panel.app_server import CodexAppServerClient


loop = QtCore.QEventLoop()
project_root = Path(__file__).resolve().parents[1]
client = CodexAppServerClient(str(project_root))
deltas = []
failure = []
image_path = Path(tempfile.gettempdir()) / "nuke-codex-panel-app-server-smoke.png"
image = QtGui.QImage(32, 32, QtGui.QImage.Format.Format_RGB32)
image.fill(QtGui.QColor("red"))
assert image.save(str(image_path), "PNG")


def on_ready(ready):
    if ready:
        client.send_turn(
            "Reply with exactly NUKE_PANEL_CODEX_OK and nothing else.",
            [str(image_path)],
        )


def on_error(message):
    failure.append(message)
    loop.quit()


def on_complete(_status):
    loop.quit()


client.ready_changed.connect(on_ready)
client.status_changed.connect(lambda message: print("CODEX_STATUS", message))
client.message_delta.connect(deltas.append)
client.error.connect(on_error)
client.turn_completed.connect(on_complete)
QtCore.QTimer.singleShot(90_000, lambda: (failure.append("timeout"), loop.quit()))
client.start()
loop.exec()
client.stop()
image_path.unlink(missing_ok=True)

if failure:
    raise RuntimeError("; ".join(failure))
response = "".join(deltas)
assert "NUKE_PANEL_CODEX_OK" in response, response
print("NUKE_CODEX_APP_SERVER_OK", response.strip())
