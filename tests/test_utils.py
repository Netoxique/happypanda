"""test utils module."""
import datetime
import json
import zipfile
from types import SimpleNamespace
from unittest import mock
from itertools import product

import pytest

from version.utils import (
    GMetafile,
    _normalize_delete_path,
    backup_database,
    check_archive,
    delete_path,
    make_chapters,
    normalize_gallery_category,
    recursive_gallery_check,
    title_parser,
)


class Chapters:
    """Minimal chapter container used to exercise gallery discovery."""

    def __init__(self):
        self.items = []

    def create_chapter(self):
        chapter = SimpleNamespace(path='', title='', pages=0, in_archive=0)
        self.items.append(chapter)
        return chapter


SAMPLE_INFO = {
    'gallery_info': {
        'title': (
            '[Gyuunyuuya-san (Gyuunyuu Nomio)] Koisuru Randoseru | '
            'Randoseru in Love [English]'),
        'title_original': 'Original title',
        'category': 'non-h',
        'tags': {
            'language': ['english', 'translated'],
            'group': ['gyuunyuuya-san'],
            'artist': ['osanai nii | gyuunyuu nomio'],
            'female': ['lolicon'],
            'other': ['rough translation'],
        },
        'language': 'English',
        'translated': True,
        'favorite_category': None,
        'upload_date': [2024, 8, 14, 19, 33, 0],
        'source': {
            'site': 'exhentai',
            'gid': 3022948,
            'token': '20bc2c7068',
            'parent_gallery': None,
            'newer_versions': [],
        },
    },
}


@pytest.mark.parametrize(
    ('raw_title', 'expected'),
    [
        (
            '[OrangeMaru (YD)] XX ROM (Fate/Grand Order) [English]',
            'XX ROM (Fate/Grand Order)',
        ),
        (
            '[Hikiwari Nattou] Boku no Inmon Illya-chan 5DL '
            '(Fate／kaleid liner Prisma Illya) [Digital].zip',
            'Boku no Inmon Illya-chan 5DL '
            '(Fate／kaleid liner Prisma Illya)',
        ),
    ],
)
def test_title_parser_preserves_slashes_in_titles(raw_title, expected):
    assert title_parser(raw_title)['title'] == expected


def test_eze_metadata_title_preserves_ascii_slash(tmp_path):
    gallery_path = tmp_path / 'gallery'
    gallery_path.mkdir()
    metadata = {
        'gallery_info': {
            'title': '[Circle] Story (Fate/Grand Order) [English]',
        },
    }
    (gallery_path / 'info.json').write_text(
        json.dumps(metadata), encoding='utf-8')
    gallery = SimpleNamespace(
        title='', artist='', type='', tags={}, language='',
        pub_date=None, link='', info='')

    GMetafile(str(gallery_path)).apply_gallery(gallery)

    assert gallery.title == 'Story (Fate/Grand Order)'


def test_windows_delete_path_normalization_uses_native_separators():
    mixed_path = (
        'D:/H\\(C86) [Example] Starting Today.zip')

    assert _normalize_delete_path(mixed_path, 'nt') == (
        'D:\\H\\(C86) [Example] Starting Today.zip')


def test_delete_path_sends_normalized_path_to_trash(monkeypatch):
    mixed_path = 'D:/H\\Example.zip'
    normalized_path = _normalize_delete_path(mixed_path)
    sent_paths = []

    monkeypatch.setattr(
        'version.utils.os.path.exists',
        lambda path: path == normalized_path)
    monkeypatch.setattr(
        'version.utils.app_constants.SEND_FILES_TO_TRASH', True)
    monkeypatch.setattr(
        'version.utils.send2trash.send2trash',
        sent_paths.append)

    assert delete_path(mixed_path) is True
    assert sent_paths == [normalized_path]


def assert_sample_metadata(metadata):
    assert metadata.title == 'Koisuru Randoseru | Randoseru in Love'
    assert metadata.artist == 'Osanai nii | gyuunyuu nomio'
    assert metadata.type == 'Non-H'
    assert metadata.language == 'English'
    assert metadata.pub_date == datetime.datetime(2024, 8, 14, 19, 33)
    assert metadata.link == (
        'https://exhentai.org/g/3022948/20bc2c7068')
    assert metadata.tags['Language'] == ['english', 'translated']
    assert metadata.tags['Group'] == ['gyuunyuuya-san']


def test_minimal_eze_info_json_is_applied(tmp_path):
    gallery_path = tmp_path / 'gallery'
    gallery_path.mkdir()
    (gallery_path / 'info.json').write_text(
        json.dumps(SAMPLE_INFO), encoding='utf-8')
    gallery = SimpleNamespace(
        title='', artist='', type='', tags={}, language='',
        pub_date=None, link='', info='')

    GMetafile(str(gallery_path)).apply_gallery(gallery)

    assert_sample_metadata(gallery)


def test_minimal_eze_info_json_is_applied_from_archive(
        tmp_path, monkeypatch):
    archive_path = tmp_path / 'gallery.zip'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('info.json', json.dumps(SAMPLE_INFO))
        archive.writestr('001.jpg', b'image')
    extraction_path = tmp_path / 'extract'
    extraction_path.mkdir()
    monkeypatch.setattr(
        'version.utils.app_constants.temp_dir', str(extraction_path))
    gallery = SimpleNamespace(
        title='', artist='', type='', tags={}, language='',
        pub_date=None, link='', info='')

    GMetafile('', str(archive_path)).apply_gallery(gallery)

    assert_sample_metadata(gallery)


def test_schale_network_yaml_redirect_is_applied_from_archive(
        tmp_path, monkeypatch):
    archive_path = tmp_path / 'gallery.cbz'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr(
            'info.yaml',
            'source: SchaleNetwork:/g/2290/21283cfa38ac\n')
        archive.writestr('001.jpg', b'image')
    extraction_path = tmp_path / 'extract'
    extraction_path.mkdir()
    monkeypatch.setattr(
        'version.utils.app_constants.temp_dir', str(extraction_path))
    gallery = SimpleNamespace(
        title='', artist='', type='', tags={}, language='',
        pub_date=None, link='', info='')

    GMetafile('', str(archive_path)).apply_gallery(gallery)

    assert gallery.link == (
        'https://niyaniya.moe/g/2290/21283cfa38ac')


@pytest.mark.parametrize(
    ('source_category', 'expected'),
    [('image set', 'Image Set'), ('artist cg', 'Artist CG'),
     ('non-h', 'Non-H'), ('misc', 'Miscellaneous')])
def test_gallery_category_is_normalized(source_category, expected):
    assert normalize_gallery_category(source_category) == expected


def test_webp_gallery_directory_is_detected(tmpdir):
    """A folder containing WebP pages is a valid gallery source."""
    gallery_path = tmpdir.mkdir('webp-gallery')
    gallery_path.join('001.webp').write_binary(b'webp')

    gallery_dirs, gallery_archives = recursive_gallery_check(str(gallery_path))

    assert gallery_dirs == [str(gallery_path)]
    assert gallery_archives == []


def test_webp_gallery_archive_is_detected(tmpdir):
    """An archive containing WebP pages is a valid gallery source."""
    archive_path = str(tmpdir.join('webp-gallery.cbz'))
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('001.webp', b'webp')

    assert check_archive(archive_path) == ['']


def test_make_chapters_handles_webp_zip_on_windows(tmpdir):
    """Archive chapter creation must not pass a ZIP path to scandir."""
    archive_path = str(tmpdir.join('OH!みそしる.zip'))
    with zipfile.ZipFile(archive_path, 'w') as archive:
        for page in range(4):
            archive.writestr('{:03}.webp'.format(page), b'webp')
        archive.writestr('notes.txt', b'metadata')

    gallery = SimpleNamespace(
        path=archive_path,
        chapters=Chapters(),
        is_archive=0,
        title='',
        artist='',
        type='',
        tags={},
        language='',
        pub_date=None,
        link='',
        info='',
    )

    make_chapters(gallery)

    assert gallery.is_archive == 1
    assert len(gallery.chapters.items) == 1
    assert gallery.chapters.items[0].path == ''
    assert gallery.chapters.items[0].in_archive == 1
    assert gallery.chapters.items[0].pages == 4


@pytest.mark.parametrize(
    'mock_exists_retval, mock_isdir_retval',
    product([True, False], repeat=2)
)
def test_run_backup_database(mock_exists_retval, mock_isdir_retval):
    """test run with mock obj as input."""
    mock_db_path = mock.Mock()
    mock_base_path = mock.Mock()
    mock_name = mock.Mock()
    with mock.patch('version.utils.os') as mock_os, \
            mock.patch('version.utils.shutil') as mock_shutil, \
            mock.patch('version.utils.datetime') as mock_datetime:
        mock_datetime.datetime.today.return_value = '2016-10-25 15:42:47.649416'
        mock_os.path.split.return_value = (mock_base_path, mock_name)
        mock_os.path.exists.return_value = mock_exists_retval
        mock_os.path.isdir.return_value = mock_isdir_retval
        res = backup_database(mock_db_path)
        assert res
        mock_datetime.datetime.today.assert_called_once_with()
        os_calls = [
            mock.call.path.split(mock_db_path),
            mock.call.path.join(mock_base_path, 'backup'),
            mock.call.path.isdir(mock_os.path.join.return_value),
            mock.call.path.join(
                mock_os.path.join.return_value,
                "2016-10-25-{}".format(mock_name)),
            mock.call.path.exists(mock_os.path.join.return_value),
        ]
        if mock_exists_retval:
            if mock_isdir_retval:
                assert len(mock_os.mock_calls) == 103
            else:
                assert len(mock_os.mock_calls) == 104
            os_calls.extend([
                mock.call.path.join(
                    mock_os.path.join.return_value,
                    "2016-10-25(1)-2016-10-25-{}".format(mock_name)),
                mock.call.path.join(
                    mock_os.path.join.return_value,
                    "2016-10-25(2)-2016-10-25-{}".format(mock_name)),
            ])
            assert not mock_shutil.mock_calls
        else:
            if mock_isdir_retval:
                assert len(mock_os.mock_calls) == 5
            else:
                assert len(mock_os.mock_calls) == 6
            mock_shutil.copyfile.assert_called_once_with(
                mock_db_path, mock_os.path.join.return_value)

        if mock_isdir_retval:
            assert not mock_os.mkdir.called
        else:
            mock_os.mkdir.assert_called_once_with(mock_os.path.join.return_value)
        mock_os.assert_has_calls(os_calls, any_order=True)
