"""Fast, deterministic duplicate-gallery detection."""

import os
from collections import defaultdict


class DuplicateGroup:
    """A connected set of galleries that share a title or path."""

    def __init__(self, number, galleries, matches):
        self.number = number
        self.galleries = tuple(galleries)
        self.matches = matches


def normalize_title(title):
    """Preserve the duplicate check's historical title normalization."""
    return (title or '').strip().lower()


def normalize_path(path):
    """Preserve the duplicate check's historical path normalization."""
    return os.path.normcase(path or '')


def find_duplicate_groups(galleries):
    """Return connected duplicate groups in stable library order.

    Blank keys and records without a unique database id are ignored. A gallery
    can connect otherwise separate title and path matches into one group.
    """
    records = []
    seen_ids = set()
    title_buckets = defaultdict(list)
    path_buckets = defaultdict(list)

    for library_position, gallery in enumerate(galleries):
        gallery_id = getattr(gallery, 'id', None)
        if gallery_id is None or gallery_id in seen_ids:
            continue
        seen_ids.add(gallery_id)

        record_index = len(records)
        records.append((library_position, gallery))

        title_key = normalize_title(getattr(gallery, 'title', ''))
        if title_key:
            title_buckets[title_key].append(record_index)

        path_key = normalize_path(getattr(gallery, 'path', ''))
        if path_key:
            path_buckets[path_key].append(record_index)

    parents = list(range(len(records)))
    ranks = [0] * len(records)
    matches = [defaultdict(set) for _ in records]

    def find(item):
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if ranks[left_root] < ranks[right_root]:
            left_root, right_root = right_root, left_root
        parents[right_root] = left_root
        if ranks[left_root] == ranks[right_root]:
            ranks[left_root] += 1

    def connect_buckets(buckets, match_type):
        for key, members in buckets.items():
            if len(members) < 2:
                continue
            first = members[0]
            for member in members:
                matches[member][match_type].add(key)
            for member in members[1:]:
                union(first, member)

    connect_buckets(title_buckets, 'title')
    connect_buckets(path_buckets, 'path')

    components = defaultdict(list)
    for record_index, member_matches in enumerate(matches):
        if member_matches:
            components[find(record_index)].append(record_index)

    ordered_components = sorted(
        (members for members in components.values() if len(members) > 1),
        key=lambda members: records[members[0]][0])

    groups = []
    for group_number, members in enumerate(ordered_components, 1):
        member_galleries = [records[index][1] for index in members]
        group_matches = {}
        for index in members:
            gallery_id = records[index][1].id
            group_matches[gallery_id] = {
                match_type: tuple(sorted(values))
                for match_type, values in matches[index].items()
            }
        groups.append(DuplicateGroup(
            group_number,
            member_galleries,
            group_matches))
    return groups
