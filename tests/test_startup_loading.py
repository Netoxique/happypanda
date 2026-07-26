"""Regression tests for bulk database startup hydration."""
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import app_constants
import app
import gallery
import gallerydb
import misc_db
from database import db
from database.db import DBBase
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication


def create_library():
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(db.STRUCTURE_SCRIPT)
    conn.execute(
        """INSERT INTO series(
               title, artist, profile, series_path, is_archive,
               path_in_archive, info, fav, type, link, language, rating,
               status, pub_date, date_added, last_read, times_read, exed,
               db_v, view)
           VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ('Gallery', 'Artist', b'thumbnail.png', b'Z:/missing/gallery',
         0, b'', 'Info', 0, 'Manga', b'', 'English', 0, 'Completed',
         None, '2026-01-01 00:00:00', None, 0, 0, 0.26,
         int(app_constants.ViewType.Default)))
    gallery_id = conn.execute(
        'SELECT series_id FROM series').fetchone()['series_id']
    conn.execute(
        """INSERT INTO chapters(
               series_id, chapter_title, chapter_number, chapter_path,
               pages, in_archive)
           VALUES(?, ?, ?, ?, ?, ?)""",
        (gallery_id, 'Chapter', 0, b'Z:/missing/gallery', 10, 0))
    chapter_id = conn.execute(
        'SELECT chapter_id FROM chapters').fetchone()['chapter_id']
    conn.execute(
        'INSERT INTO namespaces(namespace) VALUES(?)', ('artist',))
    namespace_id = conn.execute(
        'SELECT namespace_id FROM namespaces').fetchone()['namespace_id']
    conn.execute('INSERT INTO tags(tag) VALUES(?)', ('sample',))
    tag_id = conn.execute('SELECT tag_id FROM tags').fetchone()['tag_id']
    conn.execute(
        'INSERT INTO tags_mappings(namespace_id, tag_id) VALUES(?, ?)',
        (namespace_id, tag_id))
    mapping_id = conn.execute(
        'SELECT tags_mappings_id FROM tags_mappings').fetchone()[0]
    conn.execute(
        'INSERT INTO series_tags_map(series_id, tags_mappings_id) VALUES(?, ?)',
        (gallery_id, mapping_id))
    conn.execute(
        'INSERT INTO hashes(hash, series_id, chapter_id, page) VALUES(?, ?, ?, ?)',
        (b'hash', gallery_id, chapter_id, 1))
    conn.execute(
        """INSERT INTO list(
               list_name, list_filter, profile, type, enforce, regex,
               l_case, strict)
           VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
        ('Saved', None, b'', gallerydb.GalleryList.REGULAR, 0, 0, 0, 0))
    list_id = conn.execute('SELECT list_id FROM list').fetchone()['list_id']
    conn.execute(
        'INSERT INTO series_list_map(list_id, series_id) VALUES(?, ?)',
        (list_id, gallery_id))
    conn.commit()
    return conn, gallery_id


def test_bulk_hydration_preserves_all_relationships():
    conn, gallery_id = create_library()
    old_connection = DBBase._DB_CONN
    old_lists = app_constants.GALLERY_LISTS
    app_constants.GALLERY_LISTS = set()
    DBBase._DB_CONN = conn
    statements = []
    conn.set_trace_callback(statements.append)

    try:
        gallerydb.ListDB.init_lists()
        galleries, tags, hashes, namespace_tags = (
            gallerydb.DatabaseStartup._hydrate_snapshot())
    finally:
        conn.set_trace_callback(None)
        conn.close()
        DBBase._DB_CONN = old_connection
        app_constants.GALLERY_LISTS = old_lists

    assert len(galleries) == 1
    loaded = galleries[0]
    assert loaded.id == gallery_id
    assert loaded.title == 'Gallery'
    assert len(loaded.chapters) == 1
    assert loaded.chapters[0].pages == 10
    assert loaded.dead_link is False
    assert tags == {gallery_id: {'artist': ['sample']}}
    assert hashes == {gallery_id: [b'hash']}
    assert namespace_tags == {'artist': ['sample']}

    selects = [
        statement for statement in statements
        if statement.lstrip().upper().startswith('SELECT')
    ]
    assert len(selects) <= 6


def test_startup_signal_order(monkeypatch):
    conn, _ = create_library()
    old_connection = DBBase._DB_CONN
    old_lists = app_constants.GALLERY_LISTS
    app_constants.GALLERY_LISTS = set()
    DBBase._DB_CONN = conn
    events = []

    def run_immediately(method, no_return, *args, **kwargs):
        return method(*args, **kwargs)

    monkeypatch.setattr(gallerydb, 'execute', run_immediately)
    startup = gallerydb.DatabaseStartup()
    monkeypatch.setattr(startup, '_validate_paths', lambda galleries: None)
    startup.START.connect(lambda: events.append('start'))
    startup.GALLERY_BATCH.connect(
        lambda view, batch: events.append('galleries'))
    startup.BASE_READY.connect(lambda: events.append('base'))
    startup.METADATA_BATCH.connect(lambda batch: events.append('metadata'))
    startup.DONE.connect(lambda: events.append('done'))

    try:
        startup.startup([])
    finally:
        conn.close()
        DBBase._DB_CONN = old_connection
        app_constants.GALLERY_LISTS = old_lists

    assert events[0] == 'start'
    assert events.index('galleries') < events.index('base')
    assert events.index('base') < events.index('metadata')
    assert events[-1] == 'done'


def test_indexes_do_not_change_database_version(tmp_path):
    database_path = tmp_path / 'library.db'
    conn = db.init_db(str(database_path))
    try:
        version = conn.execute('SELECT version FROM version').fetchone()[0]
        assert version == db.db_constants.CURRENT_DB_VERSION
        assert {
            'idx_chapters_series',
            'idx_hashes_series',
            'idx_series_list_map_series',
        }.issubset({
            row[1]
            for table in ('chapters', 'hashes', 'series_list_map')
            for row in conn.execute('PRAGMA index_list({})'.format(table))
        })
    finally:
        conn.close()


def test_gallery_model_inserts_startup_batch_in_order():
    model = gallery.GalleryModel([])
    galleries = [gallerydb.Gallery() for _ in range(3)]
    for gallery_id, gallery_object in enumerate(galleries, 1):
        gallery_object.id = gallery_id
    model._gallery_to_add.extend(galleries)

    assert model.insertRows(0, len(galleries))
    assert [gallery_object.id for gallery_object in model._data] == [1, 2, 3]


def test_tag_tree_populates_namespace_only_when_expanded():
    application = QApplication.instance() or QApplication([])
    tree = misc_db.TagsTreeView(None)
    tree.setup_tags({'artist': ['beta', 'alpha']})

    namespace = tree.topLevelItem(0)
    assert namespace.text(0) == 'artist'
    assert namespace.childCount() == 1
    assert namespace.data(0, Qt.UserRole + 1) is False

    tree._populate_namespace(namespace)

    assert namespace.data(0, Qt.UserRole + 1) is True
    assert [
        namespace.child(index).text(0)
        for index in range(namespace.childCount())
    ] == ['alpha', 'beta']
    tree.close()
    application.processEvents()


def test_startup_advances_delegate_paint_state_for_thumbnails(monkeypatch):
    delegate = mock.Mock()
    model = mock.Mock()
    model.rowCount.return_value = 0
    sort_model = mock.Mock()
    manga_view = SimpleNamespace(
        list_view=SimpleNamespace(manga_delegate=delegate),
        gallery_model=model,
        sort_model=sort_model)
    monkeypatch.setattr(gallery.MangaViews, 'manga_views', [manga_view])
    window = object()

    app.AppWindow._mark_startup_base_ready(window)
    app.AppWindow._finish_startup_load(window)

    assert delegate._increment_paint_level.call_count == 2
    sort_model.end_startup_load.assert_called_once_with()
