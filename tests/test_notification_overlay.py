"""Tests for the notification overlay shown below the main toolbar."""

import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

from misc import NotificationOverlay


def test_notification_text_has_the_full_bar_height():
    application = QApplication.instance() or QApplication([])
    overlay = NotificationOverlay()
    overlay.resize(640)
    overlay.show()
    overlay.slide_animation.setCurrentTime(overlay.slide_animation.duration())
    application.processEvents()

    margins = overlay._main_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        0, 0, 0, 0
    )
    assert overlay._lbl.geometry().height() == overlay.height()

    overlay.close()
