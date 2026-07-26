"""Regression tests for E-Hentai metadata source selection."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import fetch
import pewnet


def test_failed_metadata_request_clears_queue_for_next_source():
    gallery = SimpleNamespace(title='Gallery')
    fetcher = SimpleNamespace(
        galleries_in_queue=[],
        error_galleries=[])
    source = SimpleNamespace(add_to_queue=lambda url, proc: None)
    gallery.temp_url = 'https://e-hentai.org/g/123/token'

    fetch.Fetch.fetch_metadata(fetcher, gallery, source, proc=True)

    assert fetcher.galleries_in_queue == []
    assert fetcher.error_galleries == [
        (gallery, 'No metadata found for gallery')]


def test_both_sites_use_the_official_metadata_api():
    assert pewnet.EHen().e_url == 'https://api.e-hentai.org/api.php'
    assert pewnet.ExHen({}).e_url == 'https://api.e-hentai.org/api.php'


def test_website_checker_accepts_current_ehentai_gallery_urls():
    checker = fetch.Fetch._website_checker

    assert checker(None, 'https://e-hentai.org/g/123/token') == 'ehen'
    assert checker(None, 'https://g.e-hentai.org/g/123/token') == 'ehen'
    assert checker(None, 'https://exhentai.org/g/123/token') == 'exhen'


def test_ehentai_default_also_enables_exhentai_with_access():
    cookies = {'ipb_member_id': 'member', 'ipb_pass_hash': 'hash'}

    sources = fetch.Fetch._ehen_sources(
        'https://e-hentai.org/', cookies)

    assert [source_type for source, source_type in sources] == [
        'ehen', 'exhen']
    assert sources[1][0].cookies is cookies


def test_exhentai_default_falls_back_to_ehentai():
    cookies = {'ipb_member_id': 'member', 'ipb_pass_hash': 'hash'}

    sources = fetch.Fetch._ehen_sources(
        'https://exhentai.org/', cookies)

    assert [source_type for source, source_type in sources] == [
        'exhen', 'ehen']


def test_exhentai_requires_complete_stored_credentials():
    sources = fetch.Fetch._ehen_sources(
        'https://exhentai.org/',
        {'ipb_member_id': 'member'})

    assert [source_type for source, source_type in sources] == ['ehen']
