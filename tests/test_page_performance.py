import threading
from unittest.mock import Mock

from app import SnapSortApp
from ui.gallery import GalleryPage
from ui.history_view import HistoryPage


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_show_page_ignores_repeated_current_navigation():
    app = SnapSortApp.__new__(SnapSortApp)
    page = Mock()
    nav = Mock()
    root = Mock()
    app.page_factories = {"gallery": Mock()}
    app.pages = {"gallery": page}
    app.nav_buttons = {"gallery": nav}
    app.current_page = "gallery"
    app.root = root

    app.show_page("gallery")

    page.pack_forget.assert_not_called()
    page.pack.assert_not_called()
    nav.configure.assert_not_called()
    root.after_idle.assert_not_called()


def test_deferred_refresh_only_runs_for_visible_page():
    app = SnapSortApp.__new__(SnapSortApp)
    visible = Mock(spec=["on_show"])
    hidden = Mock(spec=["on_show"])
    app.pages = {"gallery": visible, "history": hidden}
    app.current_page = "gallery"

    app._refresh_visible_page("history")
    app._refresh_visible_page("gallery")

    hidden.on_show.assert_not_called()
    visible.on_show.assert_called_once_with()


def test_gallery_on_show_reuses_results_until_browse_key_changes(monkeypatch):
    page = GalleryPage.__new__(GalleryPage)
    page.app = Mock(output_var=_Var(" D:/photos "))
    page.category_var = _Var("全部")
    page._loaded_key = ("D:/photos", "全部")
    page._loaded_signature = ("unchanged",)
    monkeypatch.setattr(
        page, "_browse_signature", lambda *_args: ("unchanged",)
    )
    page.refresh = Mock()

    page.on_show()
    page.app.output_var.value = "D:/other"
    page.on_show()

    page.refresh.assert_called_once_with()


def test_gallery_on_show_detects_directory_metadata_change(monkeypatch):
    page = GalleryPage.__new__(GalleryPage)
    page.app = Mock(output_var=_Var("D:/photos"))
    page.category_var = _Var("全部")
    page._loaded_key = ("D:/photos", "全部")
    page._loaded_signature = ("old",)
    monkeypatch.setattr(page, "_browse_signature", lambda *_args: ("new",))
    page.refresh = Mock()

    page.on_show()

    page.refresh.assert_called_once_with()


def test_gallery_stale_render_callback_is_ignored():
    page = GalleryPage.__new__(GalleryPage)
    page._refresh_token = 2
    cancel_flag = threading.Event()
    page.info_label = Mock()
    page.gallery_scroll = Mock()

    page._start_render(["old.jpg"], refresh_token=1, cancel_flag=cancel_flag)

    page.info_label.configure.assert_not_called()


def test_history_on_show_refreshes_first_time_then_reuses_signature():
    page = HistoryPage.__new__(HistoryPage)
    page._has_loaded = False
    page._loaded_signature = None
    page._history_signature = Mock(return_value=(1, 10))
    page.refresh = Mock()

    page.on_show()
    page._has_loaded = True
    page._loaded_signature = (1, 10)
    page.on_show()

    page.refresh.assert_called_once_with()
