from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication

from magicgui.protocols import BaseApplicationBackend


# qt implementation
class ApplicationBackend(BaseApplicationBackend):
    def _mg_get_backend_name(self):
        return "qt"

    def _mg_process_events(self):
        app = self._mg_get_native_app()
        app.flush()
        app.processEvents()

    def _mg_run(self):
        app = self._mg_get_native_app()
        if not getattr(app, "_in_event_loop", False):
            return app.exec_()

    def _mg_quit(self):
        return self._mg_get_native_app().quit()

    def _mg_get_native_app(self):
        # Get native app
        return QApplication.instance() or QApplication([])

    def _mg_start_timer(self, interval=0, on_timeout=None, single=False):
        self._timer = QTimer()
        if on_timeout:
            self._timer.timeout.connect(on_timeout)
        self._timer.setSingleShot(single)
        self._timer.setInterval(interval)
        self._timer.start()

    def _mg_stop_timer(self):
        if getattr(self, "_timer", None):
            self._timer.stop()
