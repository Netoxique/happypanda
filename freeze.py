"""cx_Freeze configuration for the portable Windows x64 release."""

from pathlib import Path
import sys

from cx_Freeze import Executable, setup


ROOT = Path(__file__).resolve().parent
UNRAR_ROOT = ROOT / ".build-cache" / "unrar" / "extracted"
UNRAR_EXE = UNRAR_ROOT / "UnRAR.exe"
UNRAR_LICENSE = UNRAR_ROOT / "license.txt"
QTA_DIST_INFO = (
    Path(sys.prefix)
    / "Lib"
    / "site-packages"
    / "qtawesome-1.4.2.dist-info"
)
QTA_LICENSE = QTA_DIST_INFO / "licenses" / "LICENSE.txt"
QTA_METADATA = QTA_DIST_INFO / "METADATA"

for required_file in (UNRAR_EXE, UNRAR_LICENSE, QTA_LICENSE, QTA_METADATA):
    if not required_file.is_file():
        raise FileNotFoundError(
            f"Missing build dependency: {required_file}. "
            "Run scripts/build-win64.ps1 to stage dependencies and build."
        )

build_exe_options = {
    "build_exe": str(ROOT / "dist" / "HappyPanda"),
    "excludes": [
        "PyQt6",
        "PySide2",
        "PySide6",
        "pytest",
        "tkinter",
        "unittest",
    ],
    "include_files": [
        (str(ROOT / "res"), "res"),
        (str(ROOT / "LICENSE"), "LICENSE"),
        (str(ROOT / "LICENSE-3RD-PARTY"), "LICENSE-3RD-PARTY"),
        (str(UNRAR_EXE), "bin/unrar.exe"),
        (str(UNRAR_LICENSE), "licenses/UNRAR-LICENSE.txt"),
        (str(QTA_LICENSE), "licenses/QtAwesome-LICENSE.txt"),
        (str(QTA_METADATA), "licenses/QtAwesome-METADATA.txt"),
    ],
    "include_msvcr_version": "17",
    "includes": [
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtNetwork",
        "PyQt5.QtSql",
        "PyQt5.QtSvg",
        "PyQt5.QtWidgets",
    ],
    "optimize": 1,
    "packages": [
        "bs4",
        "dateutil",
        "PIL",
        "qtawesome",
        "rarfile",
        "requests",
        "robobrowser",
        "send2trash",
        "watchdog",
    ],
    "path": [str(ROOT / "version"), *sys.path],
}

setup(
    name="HappyPanda",
    version="1.2",
    description="A manga/doujinshi manager with namespace and tag support",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            script=str(ROOT / "version" / "main.py"),
            base="gui",
            target_name="Happypanda.exe",
            icon=str(ROOT / "happypanda.ico"),
            copyright="HappyPanda contributors; GPL-2.0-or-later",
        )
    ],
)
