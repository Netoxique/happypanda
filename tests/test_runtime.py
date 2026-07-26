"""Tests for portable frozen-application path handling."""

from pathlib import Path

from version.runtime import set_frozen_working_directory


def test_frozen_application_uses_executable_directory(tmp_path, monkeypatch):
    application_directory = tmp_path / "portable"
    application_directory.mkdir()
    other_directory = tmp_path / "shortcut-working-directory"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    result = set_frozen_working_directory(
        frozen=True,
        executable=str(application_directory / "Happypanda.exe"),
    )

    assert result == str(application_directory)
    assert Path.cwd() == application_directory


def test_source_run_keeps_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert set_frozen_working_directory(frozen=False) is None
    assert Path.cwd() == tmp_path
