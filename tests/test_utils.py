"""test utils module."""
import zipfile
from types import SimpleNamespace
from unittest import mock
from itertools import product

import pytest

from version.utils import (
    backup_database,
    check_archive,
    make_chapters,
    recursive_gallery_check,
)


class Chapters:
    """Minimal chapter container used to exercise gallery discovery."""

    def __init__(self):
        self.items = []

    def create_chapter(self):
        chapter = SimpleNamespace(path='', title='', pages=0, in_archive=0)
        self.items.append(chapter)
        return chapter


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
