"""Regression tests for duplicate-gallery detection and grouping."""

import os
import sys
import time
from pathlib import Path


os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import duplicates
import gallery
import gallerydb
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import (
    QApplication, QListView, QStyleOptionViewItem)


def make_gallery(gallery_id, title='', path=''):
    item = gallerydb.Gallery()
    item.id = gallery_id
    item.title = title
    item.path = path
    return item


def test_duplicate_groups_match_normalized_title_and_path():
    title_first = make_gallery(1, '  Shared Title ')
    title_second = make_gallery(2, 'shared title')
    path_first = make_gallery(3, 'First', r'C:\Gallery\Same')
    path_second = make_gallery(
        4, 'Second', os.path.normcase(r'C:\Gallery\Same'))

    groups = duplicates.find_duplicate_groups(
        [title_first, title_second, path_first, path_second])

    assert [[item.id for item in group.galleries] for group in groups] == [
        [1, 2],
        [3, 4],
    ]
    assert groups[0].matches[1] == {'title': ('shared title',)}
    assert groups[1].matches[3] == {
        'path': (os.path.normcase(r'C:\Gallery\Same'),)}


def test_overlapping_matches_form_one_connected_group():
    first = make_gallery(1, 'Shared title', r'C:\one')
    bridge = make_gallery(2, 'shared title', r'C:\shared-path')
    third = make_gallery(3, 'Another title', r'C:\shared-path')

    groups = duplicates.find_duplicate_groups([first, bridge, third])

    assert len(groups) == 1
    assert [item.id for item in groups[0].galleries] == [1, 2, 3]
    assert set(groups[0].matches[2]) == {'title', 'path'}


def test_blank_values_missing_ids_and_repeated_ids_are_ignored():
    galleries = [
        make_gallery(1),
        make_gallery(2),
        make_gallery(None, 'Same'),
        make_gallery(None, 'same'),
        make_gallery(3, 'Repeated id'),
        make_gallery(3, 'repeated id'),
    ]

    assert duplicates.find_duplicate_groups(galleries) == []


def test_groups_and_members_preserve_library_order():
    galleries = [
        make_gallery(10, 'Later group'),
        make_gallery(20, 'Earlier group'),
        make_gallery(21, 'earlier group'),
        make_gallery(11, 'later group'),
    ]

    groups = duplicates.find_duplicate_groups(galleries)

    assert [group.number for group in groups] == [1, 2]
    assert [[item.id for item in group.galleries] for group in groups] == [
        [10, 11],
        [20, 21],
    ]


def test_seventeen_thousand_galleries_are_indexed_without_quadratic_delay():
    galleries = [
        make_gallery(index, 'Unique {}'.format(index),
                     r'C:\galleries\{}'.format(index))
        for index in range(17000)
    ]
    galleries[-1].title = galleries[0].title.lower()

    started = time.perf_counter()
    groups = duplicates.find_duplicate_groups(galleries)
    elapsed = time.perf_counter() - started

    assert [[item.id for item in group.galleries] for group in groups] == [
        [0, 16999]]
    assert elapsed < 3.0


def test_duplicate_model_exposes_group_annotations_and_stable_order():
    application = QApplication.instance() or QApplication([])
    first = make_gallery(1, 'Shared')
    second = make_gallery(2, 'shared')
    groups = duplicates.find_duplicate_groups([first, second])
    model = gallery.GalleryModel([])
    original_data = model._data

    model.set_duplicate_groups(groups)

    assert model._data is original_data
    first_index = model.index(0, app_constants.TITLE)
    assert first_index.data(gallery.GalleryModel.DUPLICATE_GROUP_ROLE) == 1
    assert first_index.data(gallery.GalleryModel.DUPLICATE_MATCH_ROLE) == (
        'title',)
    assert first_index.data(gallery.GalleryModel.DUPLICATE_ORDER_ROLE) == 0
    assert first_index.data(gallery.GalleryModel.DUPLICATE_VALUES_ROLE) == {
        'title': ('shared',)}
    assert 'Duplicate group:</b> 1' in first_index.data(
        Qt.ToolTipRole)

    delegate = gallery.DuplicateTableDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, first_index)
    assert option.text == 'Group 1 - Same title | Shared'

    duplicate_table = gallery.MangaTableView(
        app_constants.ViewType.Duplicate)
    assert duplicate_table.isSortingEnabled() is False
    assert duplicate_table.horizontalHeader().isSortIndicatorShown() is False
    duplicate_table.deleteLater()

    first.get_profile = lambda *args, **kwargs: None
    duplicate_grid = QListView()
    duplicate_grid.scroll_speed = 0
    duplicate_grid.view_type = app_constants.ViewType.Duplicate
    grid_delegate = gallery.GridDelegate(None, duplicate_grid)
    grid_delegate._paint_level = 1
    image = QImage(
        grid_delegate.W, grid_delegate.H, QImage.Format_ARGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    paint_option = QStyleOptionViewItem()
    paint_option.rect = QRect(
        0, 0, grid_delegate.W, grid_delegate.H)
    grid_delegate.paint(painter, paint_option, first_index)
    painter.end()
    assert image.pixelColor(2, 2) != QColor('white')
    duplicate_grid.close()
    application.processEvents()
