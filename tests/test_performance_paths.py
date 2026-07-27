"""Regression tests for archive, search, paint, and thumbnail hot paths."""
import datetime
import os
import sys
import threading
import zipfile
from concurrent import futures
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import executors
import gallery
import gallerydb
import utils
from PyQt5.QtGui import QColor, QFont, QImage
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication, QListView


@pytest.fixture(scope='module')
def application():
    return QApplication.instance() or QApplication([])


def test_archive_open_skips_full_validation_and_caches_directory(monkeypatch,
                                                                  tmp_path):
    archive_path = tmp_path / 'gallery.cbz'
    with zipfile.ZipFile(str(archive_path), 'w') as archive:
        archive.writestr('chapter/', b'')
        archive.writestr('chapter/001.jpg', b'image')
        archive.writestr('cover.jpg', b'image')

    monkeypatch.setattr(
        zipfile.ZipFile, 'testzip',
        lambda self: pytest.fail('archive was eagerly validated'))
    archive = utils.ArchiveFile(str(archive_path))
    try:
        monkeypatch.setattr(
            archive.archive, 'namelist',
            lambda: pytest.fail('archive was enumerated more than once'))
        assert archive.namelist() == [
            'chapter/', 'chapter/001.jpg', 'cover.jpg']
        assert archive.dir_list() == ['chapter/']
        assert archive.dir_contents('') == ['chapter/', 'cover.jpg']
        assert archive.dir_contents('chapter/') == ['chapter/001.jpg']
        assert archive.dir_contents('chapter/') == ['chapter/001.jpg']
    finally:
        archive.close()


def test_archive_corruption_is_reported_when_member_is_read(tmp_path):
    archive_path = tmp_path / 'corrupt.cbz'
    payload = b'unique-image-payload'
    with zipfile.ZipFile(str(archive_path), 'w', zipfile.ZIP_STORED) as archive:
        archive.writestr('page.jpg', payload)
    content = bytearray(archive_path.read_bytes())
    payload_offset = content.index(payload)
    content[payload_offset] ^= 0xFF
    archive_path.write_bytes(content)

    archive = utils.ArchiveFile(str(archive_path))
    try:
        with pytest.raises(app_constants.CreateArchiveFail):
            archive.open('page.jpg')
    finally:
        archive.close()


def make_gallery():
    item = gallerydb.Gallery()
    item.id = 7
    item.title = 'Case Sensitive Title'
    item.artist = 'Example Artist'
    item.language = 'English'
    item.type = 'Manga'
    item.status = 'Completed'
    item.info = 'Long description'
    item.tags = {
        'Artist': ['Alice Smith'],
        'default': ['Action'],
    }
    item.rating = 4
    item.times_read = 3
    item.date_added = datetime.datetime(2026, 1, 2, 12, 0, 0)
    return item


@pytest.mark.parametrize(
    'term,args,expected',
    [
        ('sensitive', [], True),
        ('sensitive', [app_constants.Search.Strict], False),
        ('Case Sensitive Title', [app_constants.Search.Strict], True),
        ('case', [app_constants.Search.Case], False),
        ('Case', [app_constants.Search.Case], True),
        ('action', [], True),
        ('Artist:alice', [], True),
        ('Artist:Alice Smith', [app_constants.Search.Strict], True),
        ('Rating:4', [], True),
        ('Rating:>3', [], True),
        ('Date_added:02/01/2026', [], True),
        ('-missing', [], True),
        ('-action', [], False),
        ('Title:^Case', [app_constants.Search.Regex], True),
    ],
)
def test_cached_search_preserves_supported_search_forms(term, args, expected):
    assert make_gallery().contains(term, args) is expected


def test_search_cache_detects_scalar_and_in_place_tag_changes():
    item = make_gallery()
    assert item.contains('originally-missing', []) is False

    item.title = 'Originally-missing'
    assert item.contains('originally-missing', []) is True

    item.tags['default'].append('New Tag')
    assert item.contains('new tag', []) is True


def test_gallery_search_uses_matching_id_set_and_short_circuits():
    first = make_gallery()
    second = make_gallery()
    second.id = 8
    second.title = 'Other'
    search = gallery.GallerySearch([first, second])

    assert search._filter(['Case', 'Artist:alice'], []) == {7}
    assert search._filter([], []) == {7, 8}


def test_proxy_search_worker_applies_only_latest_result(application):
    first = make_gallery()
    second = make_gallery()
    second.id = 8
    second.title = 'Other'
    source = gallery.GalleryModel([first, second])
    proxy = gallery.SortFilterModel(None)
    proxy.setSourceModel(source)
    proxy.setup_search()
    completed = QSignalSpy(proxy.ROWCOUNT_CHANGE)
    try:
        proxy.init_search('Other', [])
        assert completed.wait(2000)
        assert proxy.rowCount() == 1
        assert proxy.index(0, 0).data(
            gallery.GalleryModel.GALLERY_ROLE).id == 8

        current = proxy.gallery_search.result
        proxy._apply_search_result(proxy._search_request_id - 1, {7})
        assert proxy.gallery_search.result is current
    finally:
        proxy._stop_search_thread()


def test_grid_text_layout_is_reused_and_invalidated(application):
    item = make_gallery()
    view = QListView()
    view.scroll_speed = 0
    view.view_type = app_constants.ViewType.Default
    delegate = gallery.GridDelegate(None, view)
    font = QFont('Segoe UI', 10)
    try:
        first = delegate._text_area(
            item, 133, font, 'font-size:10px;', 'font-size:10px;',
            '#ffffff', '#808080')
        second = delegate._text_area(
            item, 133, font, 'font-size:10px;', 'font-size:10px;',
            '#ffffff', '#808080')
        assert first is second

        item.artist = 'Changed Artist'
        changed = delegate._text_area(
            item, 133, font, 'font-size:10px;', 'font-size:10px;',
            '#ffffff', '#808080')
        assert changed is not first
    finally:
        view.close()


def test_thumbnail_image_cache_evicts_to_configured_budget():
    cache = executors._ThumbnailImageCache()
    cache.configure(16)
    first = QImage(4, 4, QImage.Format_ARGB32)
    second = QImage(4, 4, QImage.Format_ARGB32)
    first.fill(QColor('red'))
    second.fill(QColor('blue'))

    for key, image in [
            (('first', 1, (4, 4)), first),
            (('second', 1, (4, 4)), second)]:
        future = futures.Future()
        future.set_result(image)
        cache.track(key, future)
        cache.complete(key, future)

    assert cache._bytes <= cache._limit


def test_thumbnail_loads_for_same_key_share_in_flight_work(monkeypatch,
                                                           tmp_path):
    image_path = tmp_path / 'thumb.png'
    image_path.write_bytes(b'placeholder')
    started = threading.Event()
    release = threading.Event()

    def slow_load(path, size):
        started.set()
        assert release.wait(2)
        image = QImage(size[0], size[1], QImage.Format_ARGB32)
        image.fill(QColor('green'))
        return image

    executors.Executors.invalidate_thumbnail(str(image_path))
    monkeypatch.setattr(executors, '_task_load_thumbnail', slow_load)
    first = executors.Executors.load_thumbnail(
        str(image_path), app_constants.THUMB_SMALL)
    assert started.wait(2)
    second = executors.Executors.load_thumbnail(
        str(image_path), app_constants.THUMB_SMALL)
    assert first is second
    release.set()
    assert first.result(2) is not None
