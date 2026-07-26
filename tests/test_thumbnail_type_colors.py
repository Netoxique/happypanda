"""Tests for gallery-type colors in the thumbnail grid."""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import gallery
import gallerydb
import settings
import settingsdialog
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QListView,
    QStyleOptionViewItem,
)


@pytest.fixture(scope='module')
def application():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    'value, legacy_ribbon, expected',
    [
        ('off', True, 'off'),
        ('RIBBON', False, 'ribbon'),
        ('label', True, 'label'),
        (None, True, 'ribbon'),
        (None, False, 'off'),
        (None, None, 'label'),
        ('invalid', True, 'ribbon'),
        ('invalid', None, 'label'),
    ],
)
def test_gallery_type_color_mode_normalizes_legacy_settings(
        value, legacy_ribbon, expected):
    assert app_constants.normalize_gallery_type_color_mode(
        value, legacy_ribbon) == expected


@pytest.mark.parametrize(
    'gallery_type, color_constant',
    [
        ('Manga', 'GRID_VIEW_T_MANGA_COLOR'),
        ('Doujinshi', 'GRID_VIEW_T_DOUJIN_COLOR'),
        ('Artist CG Sets', 'GRID_VIEW_T_ARTIST_CG_COLOR'),
        ('Game CG Sets', 'GRID_VIEW_T_GAME_CG_COLOR'),
        ('Western', 'GRID_VIEW_T_WESTERN_COLOR'),
        ('Image Sets', 'GRID_VIEW_T_IMAGE_COLOR'),
        ('Non-H', 'GRID_VIEW_T_NON_H_COLOR'),
        ('Cosplay', 'GRID_VIEW_T_COSPLAY_COLOR'),
        ('Other', 'GRID_VIEW_T_OTHER_COLOR'),
        ('Unknown type', 'GRID_VIEW_T_OTHER_COLOR'),
        (None, 'GRID_VIEW_T_OTHER_COLOR'),
    ],
)
def test_gallery_type_color_resolver_uses_configured_palette(
        gallery_type, color_constant):
    assert gallery.GridDelegate._ribbon_color(
        None, gallery_type) == getattr(app_constants, color_constant)


@pytest.mark.parametrize('mode', app_constants.GALLERY_TYPE_COLOR_MODES)
def test_settings_restore_gallery_type_color_mode(
        application, monkeypatch, mode):
    monkeypatch.setattr(app_constants, 'GALLERY_TYPE_COLOR_MODE', mode)
    dialog = settingsdialog.SettingsDialog()
    try:
        assert dialog.gallery_type_color_off.isChecked() == (mode == 'off')
        assert dialog.gallery_type_color_ribbon.isChecked() == (
            mode == 'ribbon')
        assert dialog.gallery_type_color_label.isChecked() == (mode == 'label')
    finally:
        dialog.close()


def test_settings_save_label_mode_and_legacy_ribbon_value(
        application, monkeypatch):
    saved = {}
    monkeypatch.setattr(settings, 'set', lambda value, section, key: saved.__setitem__(
        (section, key), value))
    monkeypatch.setattr(settings, 'save', lambda: None)
    monkeypatch.setattr(app_constants, 'GALLERY_TYPE_COLOR_MODE', 'ribbon')
    monkeypatch.setattr(app_constants, 'DISPLAY_GALLERY_RIBBON', True)

    dialog = settingsdialog.SettingsDialog()
    dialog.gallery_type_color_label.setChecked(True)
    dialog.accept()

    assert saved[('Visual', 'gallery type color mode')] == 'label'
    assert saved[('Visual', 'display gallery ribbon')] is False
    assert app_constants.GALLERY_TYPE_COLOR_MODE == 'label'
    assert app_constants.DISPLAY_GALLERY_RIBBON is False


def _paint_thumbnail(application, monkeypatch, mode):
    monkeypatch.setattr(app_constants, 'GALLERY_TYPE_COLOR_MODE', mode)
    gallery_object = gallerydb.Gallery()
    gallery_object.id = 1
    gallery_object.title = 'Title'
    gallery_object.artist = 'Artist'
    gallery_object.type = 'Manga'
    gallery_object.get_profile = lambda *args, **kwargs: None

    model = gallery.GalleryModel([gallery_object])
    view = QListView()
    view.scroll_speed = 0
    view.view_type = app_constants.ViewType.Default
    delegate = gallery.GridDelegate(None, view)
    delegate._paint_level = 1

    image = QImage(delegate.W, delegate.H, QImage.Format_ARGB32)
    image.fill(QColor('#ffffff'))
    painter = QPainter(image)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, delegate.W, delegate.H)
    delegate.paint(painter, option, model.index(0, 0))
    painter.end()
    view.close()
    return image, delegate


@pytest.mark.parametrize(
    'mode, expected_label, expected_ribbon',
    [
        ('off', 'GRID_VIEW_LABEL_COLOR', '#ffffff'),
        ('ribbon', 'GRID_VIEW_LABEL_COLOR', 'GRID_VIEW_T_MANGA_COLOR'),
        ('label', 'GRID_VIEW_T_MANGA_COLOR', '#ffffff'),
    ],
)
def test_thumbnail_paints_selected_type_color_mode(
        application, monkeypatch, mode, expected_label, expected_ribbon):
    image, delegate = _paint_thumbnail(application, monkeypatch, mode)
    label_color = (
        getattr(app_constants, expected_label)
        if expected_label.startswith('GRID_') else expected_label)
    ribbon_color = (
        getattr(app_constants, expected_ribbon)
        if expected_ribbon.startswith('GRID_') else expected_ribbon)

    assert image.pixelColor(
        5, app_constants.THUMB_H_SIZE + 5) == QColor(label_color)
    assert image.pixelColor(delegate.W - 5, 15) == QColor(ribbon_color)
