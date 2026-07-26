# HappyPanda 1.2

Updated repository of HappyPanda with modernized tools and improvements over the original implementation.

This is a cross-platform manga/doujinshi manager with namespace and tag
support.


Follow twiddly on Twitter to keep up to date with HPX:

[![Follow on Twitter](https://img.shields.io/twitter/follow/pewspew.svg?style=social&label=Follow)](https://twitter.com/twiddly_)

## Changes over the original

- Added WebP image support.
- Added a portable Windows x64 build based on CPython 3.11 and cx_Freeze.
- Improved startup and gallery loading performance.
- Modernized E-Hentai and ExHentai metadata fetching with batching and safer error handling.
- Added configurable thumbnail ribbons, type colors, and labels.
- Fixed sidebar, notification, and fractional-label display issues.

## Features

- Portable, self-contained in a folder, and cross-platform
- Low memory footprint
- Advanced gallery search with regex support
  ([learn more about it here](https://github.com/Pewpews/happypanda/wiki/Gallery-Searching))
- Gallery tagging: user-defined namespaces and tags
- Gallery metadata fetching from the web (supports various sources)
- Gallery downloading from the web (supports various sources)*
- Folder monitoring that notifies you of filesystem changes
- Multiple ways of adding galleries to make it as convenient as possible
- Recursive directory/archive scanning
- Supports ZIP/CBZ, RAR/CBR, and directories with loose files
- Very customizable
- And lots more...

\* Gallery downloading from E-Hentai costs Credits/GP.

## Screenshots

![HappyPanda screenshot 1](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot1.png)

![HappyPanda screenshot 2](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot2.png)

![HappyPanda screenshot 3](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot3.png)

## How to install and run

### Windows

1. Download the archive from the
   [releases page](https://github.com/Pewpews/happypanda/releases).
2. Extract the archive to its own folder.
3. Find `Happypanda.exe` and double-click it.

### macOS and Linux

Install from PyPI or see [INSTALL.md](INSTALL.md).

### PyPI

```shell
pip install happypanda
```

Thanks to [@Evolution0](https://github.com/Evolution0).

Then run:

```shell
happypanda --home
```

The `--home` flag makes HappyPanda create the required files and directories
at the following location:

**Windows**

```text
C:\Users\YourName\AppData\Local\Pewpew\Happypanda
```

**macOS**

```text
/Users/YourName/Library/Application Support/Happypanda
```

**Linux**

```text
/home/YourName/.local/share/Happypanda
```

## Updating

Overwrite your previous installation. More information is available in the
[wiki](https://github.com/Pewpews/happypanda/wiki).

### PyPI

```shell
pip install --upgrade happypanda
```

## Miscellaneous

For general documentation, including how to add galleries and use search,
check the [wiki](https://github.com/Pewpews/happypanda/wiki).

To import galleries from the Pururin database torrent, see the
[Convertor project](https://github.com/Exedge/Convertor).

## Dependencies

- Qt5 >= 5.4 (install this first)
- PyQt5 (pip)
- requests (pip)
- beautifulsoup4 (pip)
- watchdog (pip)
- scandir (pip)
- rarfile (pip)
- robobrowser (pip)
- Send2Trash (pip)
- Pillow (pip) or PIL
- python-dateutil (pip)
- QtAwesome (pip)
- appdirs (pip)

## Building Windows x64

The supported Windows release is a portable 64-bit folder built with CPython
3.11.9 and cx_Freeze. See [INSTALL.md](INSTALL.md) for prerequisites, the
one-command build, and the saved-data migration procedure.

## Contributing

Please refer to [HappyPanda X](https://github.com/happypandax/server) instead.
