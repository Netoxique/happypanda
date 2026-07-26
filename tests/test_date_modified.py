import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import gallery
import gallerydb
import io_misc
import utils
from database import db
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication


def set_mtime(path, timestamp):
    os.utime(str(path), (timestamp, timestamp))


def test_directory_modified_uses_newest_relevant_content(tmp_path):
    old_image = tmp_path / 'old.jpg'
    ignored = tmp_path / 'notes.txt'
    chapter = tmp_path / 'chapter'
    chapter.mkdir()
    new_image = chapter / 'new.png'
    old_image.write_bytes(b'old')
    ignored.write_text('ignored', encoding='utf-8')
    new_image.write_bytes(b'new')
    set_mtime(old_image, 100)
    set_mtime(new_image, 200)
    set_mtime(ignored, 300)

    assert utils.gallery_source_modified(str(tmp_path)) == 200


def test_archive_modified_uses_outer_archive_timestamp(tmp_path):
    archive = tmp_path / 'gallery.cbz'
    archive.write_bytes(b'archive')
    set_mtime(archive, 456)

    assert utils.gallery_source_modified(str(archive)) == 456


def test_missing_or_irrelevant_source_has_unknown_date(tmp_path):
    (tmp_path / 'notes.txt').write_text('ignored', encoding='utf-8')

    assert utils.gallery_source_modified(str(tmp_path)) is None
    assert utils.gallery_source_modified(str(tmp_path / 'missing')) is None


def test_database_revision_adds_nullable_date_modified(tmp_path):
    database_path = tmp_path / 'old.db'
    conn = sqlite3.connect(str(database_path))
    conn.executescript(
        'CREATE TABLE version(version REAL);'
        'INSERT INTO version VALUES(0.26);'
        'CREATE TABLE series(series_id INTEGER PRIMARY KEY, title TEXT);'
        "INSERT INTO series(title) VALUES('Legacy');")
    conn.commit()
    conn.close()

    db.add_db_revisions(str(database_path))

    conn = sqlite3.connect(str(database_path))
    try:
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(series)')
        }
        row = conn.execute(
            'SELECT date_modified FROM series WHERE title=?',
            ('Legacy',)).fetchone()
        version = conn.execute('SELECT version FROM version').fetchone()[0]
    finally:
        conn.close()

    assert 'date_modified' in columns
    assert row[0] is None
    assert version == db.db_constants.CURRENT_DB_VERSION


def test_gallery_database_round_trip_preserves_date_modified():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(db.STRUCTURE_SCRIPT)
    source = gallerydb.Gallery()
    source.profile = 'thumb.png'
    source.path = 'gallery'
    source.date_modified = 123456

    cursor = conn.execute(*gallerydb.default_exec(source))
    row = conn.execute(
        'SELECT * FROM series WHERE series_id=?',
        (cursor.lastrowid,)).fetchone()
    loaded = gallerydb.Gallery()
    gallerydb.gallery_map(row, loaded, False, False, False)

    assert loaded.date_modified == 123456


def test_date_modified_sort_keeps_unknown_values_last():
    application = QApplication.instance() or QApplication([])
    unknown = gallerydb.Gallery()
    unknown.id = 1
    unknown.title = 'Unknown'
    older = gallerydb.Gallery()
    older.id = 2
    older.title = 'Older'
    older.date_modified = 100
    newer = gallerydb.Gallery()
    newer.id = 3
    newer.title = 'Newer'
    newer.date_modified = 200
    model = gallery.GalleryModel([unknown, older, newer])
    proxy = gallery.SortFilterModel(None)
    proxy.setSourceModel(model)
    proxy.setSortRole(gallery.GalleryModel.DATE_MODIFIED_ROLE)

    proxy.sort(0, Qt.DescendingOrder)
    application.processEvents()
    assert [
        proxy.index(row, 0).data(gallery.GalleryModel.GALLERY_ROLE).title
        for row in range(proxy.rowCount())
    ] == ['Newer', 'Older', 'Unknown']

    proxy.sort(0, Qt.AscendingOrder)
    application.processEvents()
    assert [
        proxy.index(row, 0).data(gallery.GalleryModel.GALLERY_ROLE).title
        for row in range(proxy.rowCount())
    ] == ['Older', 'Newer', 'Unknown']


def test_monitor_child_event_resolves_to_owning_gallery(tmp_path):
    gallery_path = tmp_path / 'gallery'
    gallery_path.mkdir()
    image_path = gallery_path / 'page.jpg'
    image_path.write_bytes(b'image')
    gallery_object = gallerydb.Gallery()
    gallery_object.id = 1
    gallery_object.path = str(gallery_path)
    old_data = app_constants.GALLERY_DATA
    app_constants.GALLERY_DATA = [gallery_object]
    handler = io_misc.GalleryHandler()
    events = []
    handler.MODIFIED_SIGNAL.connect(
        lambda path, item: events.append((path, item)))

    try:
        handler.on_modified(SimpleNamespace(
            src_path=str(image_path), is_directory=False))
    finally:
        app_constants.GALLERY_DATA = old_data

    assert events == [(str(image_path), gallery_object)]


def test_atomic_archive_replace_resolves_destination_gallery(tmp_path):
    archive_path = tmp_path / 'gallery.cbz'
    archive_path.write_bytes(b'old')
    temporary_path = tmp_path / 'download.tmp'
    gallery_object = gallerydb.Gallery()
    gallery_object.id = 1
    gallery_object.path = str(archive_path)
    gallery_object.is_archive = 1
    old_data = app_constants.GALLERY_DATA
    app_constants.GALLERY_DATA = [gallery_object]
    handler = io_misc.GalleryHandler()
    events = []
    handler.MODIFIED_SIGNAL.connect(
        lambda path, item: events.append((path, item)))

    try:
        handler.on_moved(SimpleNamespace(
            src_path=str(temporary_path),
            dest_path=str(archive_path),
            is_directory=False))
    finally:
        app_constants.GALLERY_DATA = old_data

    assert events == [(str(archive_path), gallery_object)]
