"""Regression tests for gallery drag-and-drop serialization."""

import concurrent.futures
import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

VERSION_DIR = Path(__file__).resolve().parents[1] / "version"
sys.path.insert(0, str(VERSION_DIR))

import gallery
import gallery_mime
import gallerydb
from PyQt5.QtWidgets import QApplication


class GalleryIndex:
    def __init__(self, gallery_object):
        self.gallery_object = gallery_object

    def data(self, role):
        if role == gallery.GalleryModel.GALLERY_ROLE:
            return self.gallery_object
        return None


def test_mime_data_serializes_ids_not_gallery_runtime_state():
    application = QApplication.instance() or QApplication([])
    gallery_object = gallerydb.Gallery()
    gallery_object.id = 42
    gallery_object._profile_qimage["small"] = concurrent.futures.Future()
    model = gallery.SortFilterModel(None)

    mime_data = model.mimeData([GalleryIndex(gallery_object)])

    assert gallery_mime.decode_gallery_ids(
        mime_data.data(gallery_mime.MIME_TYPE)
    ) == [42]
    application.processEvents()


def test_mime_data_deduplicates_rows_with_multiple_selected_cells():
    gallery_object = gallerydb.Gallery()
    gallery_object.id = 42
    model = gallery.SortFilterModel(None)

    mime_data = model.mimeData([
        GalleryIndex(gallery_object),
        GalleryIndex(gallery_object),
    ])

    assert gallery_mime.decode_gallery_ids(
        mime_data.data(gallery_mime.MIME_TYPE)
    ) == [42]


def test_gallery_ids_resolve_to_canonical_objects_and_ignore_stale_ids():
    first = gallerydb.Gallery()
    first.id = 7
    second = gallerydb.Gallery()
    second.id = 11

    resolved = gallery_mime.resolve_galleries([11, 99, 7], [first, second])

    assert resolved == [second, first]


def test_invalid_gallery_drag_payload_is_rejected():
    for payload in (b"not-json", b'{"id":42}', b'[42,"bad"]', b"[true]"):
        try:
            gallery_mime.decode_gallery_ids(payload)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid drag payload was accepted")
