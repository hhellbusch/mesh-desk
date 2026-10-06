import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw

from mesh_desk.theme import watch_os_color_scheme
from mesh_desk.window import MainWindow


class MeshDeskApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="app.meshdesk.MeshDesk")
        self.connect("activate", self._activate)

    def _activate(self, _app) -> None:
        watch_os_color_scheme()
        win = self.props.active_window
        if win is None:
            win = MainWindow(self)
        win.present()


def main() -> None:
    raise SystemExit(MeshDeskApp().run(None))
