"""Regression tests for accurate gallery removal and viewport anchoring."""

import os
import sys
from pathlib import Path


os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import duplicates
import gallery
import gallerydb
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QWidget


def make_gallery(gallery_id):
    item = gallerydb.Gallery()
    item.id = gallery_id
    item.title = 'Gallery {}'.format(gallery_id)
    return item


def test_noncontiguous_gallery_removal_emits_exact_source_ranges():
    items = [make_gallery(index) for index in range(6)]
    model = gallery.GalleryModel(list(items))
    about_to_remove = QSignalSpy(model.rowsAboutToBeRemoved)

    removed = model.remove_galleries([items[1], items[4]])

    assert removed == 2
    assert [item.id for item in model._data] == [0, 2, 3, 5]
    assert [(signal[1], signal[2]) for signal in about_to_remove] == [
        (4, 4),
        (1, 1),
    ]


def test_contiguous_gallery_removal_uses_one_range():
    items = [make_gallery(index) for index in range(6)]
    model = gallery.GalleryModel(list(items))
    about_to_remove = QSignalSpy(model.rowsAboutToBeRemoved)

    model.remove_galleries(items[2:5])

    assert [item.id for item in model._data] == [0, 1, 5]
    assert [(signal[1], signal[2]) for signal in about_to_remove] == [
        (2, 4)]


def test_duplicate_delete_proxy_removes_matching_library_objects():
    items = [make_gallery(index) for index in range(5)]
    library_model = gallery.GalleryModel(list(items))
    duplicate_model = gallery.GalleryModel([items[1], items[3]])
    duplicate_views = gallery.MangaViews.__new__(gallery.MangaViews)
    duplicate_views.gallery_model = duplicate_model
    duplicate_views._delete_proxy_model = library_model
    duplicate_model.rowsAboutToBeRemoved.connect(
        duplicate_views._delegate_delete)

    duplicate_model.remove_galleries([items[1], items[3]])

    assert duplicate_model._data == []
    assert [item.id for item in library_model._data] == [0, 2, 4]


def test_scroll_anchor_keeps_next_gallery_at_same_offset():
    application = QApplication.instance() or QApplication([])
    items = [make_gallery(index) for index in range(80)]
    source_model = gallery.GalleryModel(list(items))
    table = gallery.MangaTableView(app_constants.ViewType.Duplicate)
    proxy = gallery.SortFilterModel(table)
    proxy.change_model(source_model)
    table.gallery_model = source_model
    table.sort_model = proxy
    table.setModel(proxy)
    table.resize(600, 240)
    table.show()
    application.processEvents()

    table.scrollTo(proxy.index(35, 0), table.PositionAtTop)
    application.processEvents()
    first_visible_row = table.rowAt(0)
    first_visible = proxy.index(first_visible_row, 0).data(
        gallery.GalleryModel.GALLERY_ROLE)
    anchor = gallery.CommonView.capture_scroll_anchor(
        table, [first_visible])
    expected_gallery = anchor['gallery']
    expected_offset = anchor['offset']

    source_model.remove_galleries([first_visible])
    gallery.CommonView.restore_scroll_anchor(table, anchor)
    application.processEvents()

    restored_index = next(
        proxy.index(row, 0)
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(
            gallery.GalleryModel.GALLERY_ROLE) is expected_gallery)
    assert abs(table.visualRect(restored_index).top() - expected_offset) <= 1

    table.close()
    proxy.deleteLater()
    application.processEvents()


def test_grid_scroll_anchor_keeps_next_gallery_at_same_offset():
    application = QApplication.instance() or QApplication([])
    items = [make_gallery(index) for index in range(80)]
    source_model = gallery.GalleryModel(list(items))
    grid = gallery.MangaView(
        source_model, app_constants.ViewType.Duplicate)
    grid.resize(620, 320)
    grid.show()
    application.processEvents()

    grid.scrollTo(grid.sort_model.index(40, 0), grid.PositionAtTop)
    application.processEvents()
    visible = grid.get_visible_indexes()
    first_visible = min(
        visible,
        key=lambda index: (
            grid.visualRect(index).top(),
            grid.visualRect(index).left()))
    first_gallery = first_visible.data(
        gallery.GalleryModel.GALLERY_ROLE)
    anchor = gallery.CommonView.capture_scroll_anchor(
        grid, [first_gallery])
    expected_gallery = anchor['gallery']
    expected_offset = anchor['offset']

    source_model.remove_galleries([first_gallery])
    gallery.CommonView.restore_scroll_anchor(grid, anchor)
    application.processEvents()

    restored_index = next(
        grid.sort_model.index(row, 0)
        for row in range(grid.sort_model.rowCount())
        if grid.sort_model.index(row, 0).data(
            gallery.GalleryModel.GALLERY_ROLE) is expected_gallery)
    assert abs(grid.visualRect(restored_index).top() - expected_offset) <= 1

    grid._scroll_speed_timer.stop()
    grid.close()
    grid.sort_model.deleteLater()
    application.processEvents()


def test_full_duplicate_view_preserves_anchor_after_async_proxy_events():
    application = QApplication.instance() or QApplication([])
    items = [make_gallery(index) for index in range(400)]
    for item in items:
        item.title = 'Shared title'
    groups = duplicates.find_duplicate_groups(items)
    parent = QWidget()
    duplicate_views = gallery.MangaViews(
        app_constants.ViewType.Duplicate, parent)
    duplicate_views.set_duplicate_groups(groups)
    grid = duplicate_views.list_view
    grid.setBatchSize(5)
    grid.resize(620, 320)
    parent.resize(620, 320)
    parent.show()
    grid.show()
    for _ in range(100):
        if grid.sort_model.rowCount() == len(items):
            break
        QTest.qWait(10)
    application.processEvents()
    assert grid.sort_model.rowCount() == len(items)
    QTest.qWait(100)
    application.processEvents()

    grid.scrollTo(grid.sort_model.index(300, 0), grid.PositionAtTop)
    QTest.qWait(50)
    application.processEvents()
    visible = grid.get_visible_indexes()
    selected_index = max(
        visible,
        key=lambda index: (
            grid.visualRect(index).top(),
            grid.visualRect(index).left()))
    grid.setCurrentIndex(selected_index)
    selected_gallery = selected_index.data(
        gallery.GalleryModel.GALLERY_ROLE)
    anchor = gallery.CommonView.capture_scroll_anchor(
        grid, [selected_gallery])
    expected_gallery = anchor['gallery']
    expected_offset = anchor['offset']

    grid.gallery_model.remove_galleries([selected_gallery])
    gallery.CommonView.restore_scroll_anchor(grid, anchor)
    QTest.qWait(250)
    application.processEvents()

    restored_index = next(
        grid.sort_model.index(row, 0)
        for row in range(grid.sort_model.rowCount())
        if grid.sort_model.index(row, 0).data(
            gallery.GalleryModel.GALLERY_ROLE) is expected_gallery)
    assert abs(grid.visualRect(restored_index).top() - expected_offset) <= 1

    grid._scroll_speed_timer.stop()
    grid.sort_model._stop_search_thread()
    parent.close()
    application.processEvents()
