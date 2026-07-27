"""Tests for position-aware gallery metadata popup placement."""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

from PyQt5.QtCore import QRect, QSize

from misc import GalleryMetaWindow


WINDOW_BOUNDS = QRect(100, 200, 1200, 800)
POPUP_SIZE = QSize(500, 300)
SAFE_BOUNDS = WINDOW_BOUNDS.adjusted(20, 20, -20, -20)


@pytest.mark.parametrize(
    'thumbnail, expected_direction',
    [
        (QRect(1120, 500, 120, 180), GalleryMetaWindow.RIGHT),
        (QRect(600, 760, 120, 180), GalleryMetaWindow.BOTTOM),
        (QRect(160, 500, 120, 180), GalleryMetaWindow.LEFT),
        (QRect(600, 240, 120, 180), GalleryMetaWindow.TOP),
    ],
)
def test_popup_faces_inward_and_stays_inside_window(
        thumbnail, expected_direction):
    direction, position = GalleryMetaWindow._popup_placement(
        WINDOW_BOUNDS, thumbnail, POPUP_SIZE)
    popup_rect = QRect(position, POPUP_SIZE)

    assert direction == expected_direction
    assert SAFE_BOUNDS.contains(popup_rect)


def test_bottom_right_popup_uses_an_inward_facing_fallback():
    thumbnail = QRect(1120, 760, 120, 180)

    direction, position = GalleryMetaWindow._popup_placement(
        WINDOW_BOUNDS, thumbnail, POPUP_SIZE)

    assert direction in (GalleryMetaWindow.BOTTOM, GalleryMetaWindow.RIGHT)
    assert SAFE_BOUNDS.contains(QRect(position, POPUP_SIZE))


def test_popup_placement_supports_negative_global_coordinates():
    bounds = QRect(-1400, 100, 1200, 800)
    thumbnail = QRect(-400, 400, 120, 180)

    direction, position = GalleryMetaWindow._popup_placement(
        bounds, thumbnail, POPUP_SIZE)

    assert direction == GalleryMetaWindow.RIGHT
    assert bounds.adjusted(20, 20, -20, -20).contains(
        QRect(position, POPUP_SIZE))


def test_popup_clamps_when_no_anchored_candidate_fits():
    bounds = QRect(50, 75, 600, 400)
    thumbnail = QRect(290, 220, 120, 180)
    popup_size = QSize(500, 300)

    _direction, position = GalleryMetaWindow._popup_placement(
        bounds, thumbnail, popup_size)

    assert bounds.adjusted(20, 20, -20, -20).contains(
        QRect(position, popup_size))


def test_oversized_popup_uses_best_effort_safe_origin():
    bounds = QRect(100, 200, 600, 400)
    thumbnail = QRect(340, 300, 120, 180)

    _direction, position = GalleryMetaWindow._popup_placement(
        bounds, thumbnail, QSize(800, 600))

    assert position == bounds.adjusted(20, 20, -20, -20).topLeft()
