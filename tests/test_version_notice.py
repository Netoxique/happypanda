"""Regression tests for the once-per-version startup notice."""

import os
import sys
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app


def test_version_notice_is_persisted_and_shown_only_once(monkeypatch):
    monkeypatch.setattr(app.app_constants, 'UPDATE_VERSION', '1.1')
    monkeypatch.setattr(app.app_constants, 'vs', '1.2')

    with mock.patch.object(app.settings, 'set') as set_version, \
            mock.patch.object(app.settings, 'save') as save_settings:
        assert app._record_current_version() is True
        set_version.assert_called_once_with(
            '1.2', 'Application', 'version')
        save_settings.assert_called_once_with()

        assert app._record_current_version() is False
        assert set_version.call_count == 1
        assert save_settings.call_count == 1
