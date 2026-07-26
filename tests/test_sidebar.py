"""Regression tests for sidebar visibility behavior."""

import os
import sys
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QFrame

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
from misc_db import SideBarWidget


class MinimalSideBarWidget(SideBarWidget):
    """SideBarWidget shell for testing show events without database setup."""

    def __init__(self):
        QFrame.__init__(self)
        self._startup_visibility_applied = False
        self.arrow_handle = mock.Mock()

    def resizeEvent(self, event):
        QFrame.resizeEvent(self, event)


def test_hidden_startup_preference_is_only_applied_once(monkeypatch):
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(app_constants, 'SHOW_SIDEBAR_WIDGET', False)
    sidebar = MinimalSideBarWidget()

    sidebar.show()
    application.processEvents()
    sidebar.hide()
    application.processEvents()
    sidebar.show()
    application.processEvents()

    sidebar.arrow_handle.click.assert_called_once_with()
    sidebar.close()


def test_visible_startup_preference_does_not_toggle_sidebar(monkeypatch):
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(app_constants, 'SHOW_SIDEBAR_WIDGET', True)
    sidebar = MinimalSideBarWidget()

    sidebar.show()
    application.processEvents()
    sidebar.hide()
    application.processEvents()
    sidebar.show()
    application.processEvents()

    sidebar.arrow_handle.click.assert_not_called()
    sidebar.close()
