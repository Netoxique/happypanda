"""Serialization helpers for internal gallery drag-and-drop data."""

import json


MIME_TYPE = "list/gallery"


def encode_gallery_ids(gallery_ids):
    """Return a compact JSON payload containing unique gallery IDs."""
    unique_ids = []
    seen = set()

    for gallery_id in gallery_ids:
        if isinstance(gallery_id, bool) or not isinstance(gallery_id, int):
            raise ValueError("Gallery IDs must be integers")
        if gallery_id not in seen:
            seen.add(gallery_id)
            unique_ids.append(gallery_id)

    return json.dumps(unique_ids, separators=(",", ":")).encode("utf-8")


def decode_gallery_ids(payload):
    """Decode and validate gallery IDs from a drag-and-drop payload."""
    try:
        gallery_ids = json.loads(bytes(payload).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid gallery drag data") from exc

    if not isinstance(gallery_ids, list):
        raise ValueError("Gallery drag data must contain a list")

    unique_ids = []
    seen = set()
    for gallery_id in gallery_ids:
        if isinstance(gallery_id, bool) or not isinstance(gallery_id, int):
            raise ValueError("Gallery drag data contains an invalid ID")
        if gallery_id not in seen:
            seen.add(gallery_id)
            unique_ids.append(gallery_id)

    return unique_ids


def resolve_galleries(gallery_ids, galleries):
    """Resolve IDs to the canonical gallery objects, preserving ID order."""
    galleries_by_id = {gallery.id: gallery for gallery in galleries}
    return [
        galleries_by_id[gallery_id]
        for gallery_id in gallery_ids
        if gallery_id in galleries_by_id
    ]
