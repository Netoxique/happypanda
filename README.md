# HappyPanda 1.2

Community-maintained release of HappyPanda with modernized tools and
improvements over the original implementation.

This is a cross-platform manga/doujinshi manager with namespace and tag
support.

## Changes over the original

- Added WebP image support.
- Added Schale Network tag support
- Added a reproducible portable Windows x64 build based on CPython 3.11 and
  cx_Freeze, with bundled UnRAR support.
- Improved startup and gallery loading performance.
- Modernized E-Hentai and ExHentai metadata fetching with batching, source
  fallback, and safer error handling.
- Added compatibility with current Eze JSON metadata.
- Improved gallery scanning and page counts.
- Added gallery color labels.
- Added "Date Modified" sorting and automatic detection for modified gallery sources (This change will open a database update prompt if you're updating).
- Improved duplicate detection system, search reduced from 10 minutes to less than 1 second.
- Improve gallery name detection. 

## Features

- Portable, self-contained in a folder, and cross-platform
- Low memory footprint
- Advanced gallery search with regex support
  ([learn more about it here](https://github.com/Pewpews/happypanda/wiki/Gallery-Searching))
- Gallery tagging: user-defined namespaces and tags
- Gallery metadata fetching from the web (supports various sources)
- Gallery downloading from the web (supports various sources)*
- Date Modified display and sorting based on gallery source files
- Folder monitoring that automatically refreshes chapters, thumbnails,
  hashes, page counts, and modification dates when gallery content changes
- Multiple ways of adding galleries to make it as convenient as possible
- Recursive directory/archive scanning
- Supports ZIP/CBZ, RAR/CBR, and directories with loose files
- Very customizable
- And lots more...

\* Gallery downloading from E-Hentai costs Credits/GP.

## Screenshots

These screenshots show the original interface; some 1.2 visual options may
differ.

![HappyPanda screenshot 1](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot1.png)

![HappyPanda screenshot 2](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot2.png)

![HappyPanda screenshot 3](https://github.com/Pewpews/happypanda/raw/master/misc/screenshot3.png)

## How to install and run

### Windows

The portable release supports 64-bit Windows 10 and Windows 11.

1. Download the latest Windows x64 archive from this fork's
   [releases page](https://github.com/Netoxique/happypanda/releases).
2. Extract the archive to its own folder.
3. Find `Happypanda.exe` and double-click it.

### macOS and Linux

Run this fork from source by following [INSTALL.md](INSTALL.md).

### Legacy PyPI package

The package published as `happypanda` on PyPI is the original release and does
not contain the changes in this fork. To install that legacy version:

```shell
pip install happypanda
```

Thanks to [@Evolution0](https://github.com/Evolution0).

Run the legacy package with:

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

Do not overwrite your existing installation. Extract the new release into a
separate folder, then copy your existing `settings.ini`, `.happypanda`, `db`,
and `downloads` data into the new folder. Keep the old installation until the
new one has been verified. See [INSTALL.md](INSTALL.md) for the complete
migration procedure.

When opening an existing 0.26 library, HappyPanda prompts before upgrading its
database to version 0.27 and creates a backup. Existing galleries initially
have an unknown Date Modified value. After the upgrade, populate those values
from the source files with **Settings → Advanced → Database → Maintenance →
Recalculate Date Modified**. Missing or inaccessible gallery sources are
skipped.

## Miscellaneous

For general documentation, including how to add galleries and use search,
check the [wiki](https://github.com/Pewpews/happypanda/wiki).

To import galleries from the Pururin database torrent, see the
[Convertor project](https://github.com/Exedge/Convertor).

## Dependencies

Source dependencies are maintained in [requirements.txt](requirements.txt):

```shell
python -m pip install -r requirements.txt
```

The portable Windows build uses the fully pinned and hash-locked dependencies
in `requirements-win64.lock`; users of that build do not need to install
Python or the dependencies separately.

## Building Windows x64

The supported Windows release is a portable 64-bit folder for Windows 10 and
Windows 11, built with CPython 3.11.9 and cx_Freeze. It includes a verified
copy of UnRAR for RAR/CBR support. See [INSTALL.md](INSTALL.md) for
prerequisites, the one-command build, and the saved-data migration procedure.

## Contributing

Issues and pull requests for this maintenance fork are welcome. For the
actively developed successor project, see
[HappyPanda X](https://github.com/happypandax/server).
