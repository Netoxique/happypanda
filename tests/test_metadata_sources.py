"""Regression tests for E-Hentai metadata source selection."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

VERSION_DIR = Path(__file__).resolve().parents[1] / 'version'
sys.path.insert(0, str(VERSION_DIR))

import fetch
import pewnet
import settingsdialog
from PyQt5.QtWidgets import QApplication


class FakeClock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if seconds > 0:
            self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture(scope='module')
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_rate_limit_clock(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(pewnet.time, 'monotonic', clock.monotonic)
    monkeypatch.setattr(pewnet.time, 'sleep', clock.sleep)
    pewnet.CommenHen._reset_rate_limits()
    yield clock
    pewnet.CommenHen._reset_rate_limits()


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


@pytest.mark.parametrize('source_type', ['ehen', 'exhen'])
@pytest.mark.parametrize('url_type', ['ehen', 'exhen'])
def test_both_eh_sources_accept_both_gallery_url_types(
        source_type, url_type):
    assert fetch.Fetch._source_accepts_url(url_type, source_type)


def test_chaika_only_accepts_chaika_urls():
    accepts = fetch.Fetch._source_accepts_url

    assert accepts('chaikahen', 'chaikahen')
    assert not accepts('ehen', 'chaikahen')
    assert not accepts('exhen', 'chaikahen')


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


def test_zero_delay_keeps_safe_search_interval(
        fake_rate_limit_clock, monkeypatch):
    monkeypatch.setattr(pewnet.app_constants, 'GLOBAL_EHEN_TIME', 0)

    pewnet.CommenHen.wait_for_search()
    pewnet.CommenHen.wait_for_search()

    assert fake_rate_limit_clock.sleeps == [3]


def test_settings_dialog_accepts_and_restores_zero_delay(
        application, monkeypatch):
    monkeypatch.setattr(pewnet.app_constants, 'GLOBAL_EHEN_TIME', 0)
    dialog = settingsdialog.SettingsDialog()
    try:
        assert dialog.web_time_offset.minimum() == 0
        assert dialog.web_time_offset.value() == 0
    finally:
        dialog.close()


def test_configured_search_delay_is_read_dynamically(
        fake_rate_limit_clock, monkeypatch):
    monkeypatch.setattr(pewnet.app_constants, 'GLOBAL_EHEN_TIME', 3)
    pewnet.CommenHen.wait_for_search()

    monkeypatch.setattr(pewnet.app_constants, 'GLOBAL_EHEN_TIME', 7)
    pewnet.CommenHen.wait_for_search()

    assert fake_rate_limit_clock.sleeps == [7]


def test_metadata_api_uses_four_request_bursts(fake_rate_limit_clock):
    for _request in range(4):
        pewnet.CommenHen.wait_for_api()

    assert fake_rate_limit_clock.sleeps == []

    pewnet.CommenHen.wait_for_api()

    assert fake_rate_limit_clock.sleeps == [5]


def test_metadata_api_partial_burst_expires_after_cooldown(
        fake_rate_limit_clock):
    for _request in range(3):
        pewnet.CommenHen.wait_for_api()
    fake_rate_limit_clock.now += 5

    for _request in range(4):
        pewnet.CommenHen.wait_for_api()

    assert fake_rate_limit_clock.sleeps == []


def test_file_search_rate_limit_waits_ten_seconds_and_retries_once(
        fake_rate_limit_clock, monkeypatch, tmp_path):
    image_path = tmp_path / 'cover.jpg'
    image_path.write_bytes(b'image')
    response = SimpleNamespace(
        text='<html><body><div>Please wait a bit longer between each '
             'file search.</div></body></html>')
    requests = []
    source = pewnet.EHen({})
    monkeypatch.setattr(
        source._browser.session,
        'post',
        lambda *args, **kwargs: requests.append((args, kwargs)) or response)

    result = source.search(str(image_path), color=True)

    assert result == {}
    assert len(requests) == 2
    assert fake_rate_limit_clock.sleeps == [10]


@pytest.mark.parametrize(
    'url_count, expected_batches',
    [
        (26, [25, 1]),
        (100, [25, 25, 25, 25]),
        (101, [25, 25, 25, 25, 1]),
    ])
def test_metadata_queue_batches_at_most_25_urls(
        url_count, expected_batches):
    class RecordingSource(pewnet.CommenHen):
        def __init__(self):
            super().__init__()
            self.batch_sizes = []

        def get_metadata(self, urls):
            self.batch_sizes.append(len(urls))
            return {}, {}

    source = RecordingSource()
    for index in range(url_count):
        source.add_to_queue(
            'https://e-hentai.org/g/{}/token'.format(index),
            proc=index == url_count - 1,
            parse=False)

    assert source.batch_sizes == expected_batches


def test_metadata_queues_are_isolated_by_source_instance():
    first = pewnet.EHen({})
    second = pewnet.ExHen({})

    first.add_to_queue('https://e-hentai.org/g/1/token')

    assert len(first.QUEUE) == 1
    assert second.QUEUE == []


def test_existing_eh_url_skips_discovery_for_exhentai(monkeypatch):
    gallery = SimpleNamespace(
        title='Gallery',
        link='https://e-hentai.org/g/123/token')
    fetcher = fetch.Fetch()
    calls = []
    fetcher.fetch_metadata = lambda gallery=None, hen=None, proc=False: \
        calls.append((gallery, proc))
    source = SimpleNamespace(
        search=lambda *_args, **_kwargs: pytest.fail(
            'URL discovery should not run'))
    monkeypatch.setattr(fetch.app_constants, 'USE_GALLERY_LINK', True)

    fetcher._auto_metadata_process([gallery], source, 'exhen')

    assert gallery.temp_url == gallery.link
    assert calls[-1] == (gallery, True)


def test_discovered_url_is_reused_even_when_saved_links_are_disabled(
        monkeypatch):
    gallery = SimpleNamespace(
        title='Gallery',
        link='',
        temp_url='https://exhentai.org/g/123/token')
    fetcher = fetch.Fetch()
    calls = []
    fetcher.fetch_metadata = lambda gallery=None, hen=None, proc=False: \
        calls.append((gallery, proc))
    source = SimpleNamespace(
        search=lambda *_args, **_kwargs: pytest.fail(
            'URL discovery should not repeat'))
    monkeypatch.setattr(fetch.app_constants, 'USE_GALLERY_LINK', False)

    fetcher._auto_metadata_process([gallery], source, 'ehen')

    assert calls[-1] == (gallery, True)


def test_empty_search_result_is_reported_without_crashing():
    gallery = SimpleNamespace(
        title='Drug and Drop 4',
        link='',
        hashes=['gallery-hash'])
    fetcher = fetch.Fetch()
    fetcher.fetch_metadata = lambda gallery=None, hen=None, proc=False: None
    source = SimpleNamespace(
        search=lambda *_args, **_kwargs: {'gallery-hash': []})

    fetcher._auto_metadata_process([gallery], source, 'ehen')

    assert fetcher.error_galleries == [
        (gallery, 'Could not find url for gallery')]
