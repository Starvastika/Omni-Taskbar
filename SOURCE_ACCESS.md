# Omni Taskbar 1.0.0

Normal download: **Omni-Taskbar-Setup-1.0.0.exe**. Install per user without a separate Python/YASB installation. The updater ZIP and corresponding-source ZIP are advanced/internal assets. See README for usage, update policies and uninstall. This build is unsigned; Windows may show Unknown Publisher / SmartScreen. Verify SHA256SUMS.txt.

# Source access and third-party licenses

Omni Taskbar's original custom code is MIT licensed, Copyright (c) 2026 Starvastika.
The full product includes components under their separate original licenses.
In particular, PyQt6 is GPLv3 licensed; its presence is not converted to MIT.
PySide6/shiboken6 and open-source Qt retain their LGPL/GPL terms and notices.

The public source repository is [Starvastika/Omni-Taskbar](https://github.com/Starvastika/Omni-Taskbar).
The release's corresponding-source archive contains the project source, readable frozen-runtime
patches and build recipes, exact YASB source, and the PyQt6/SIP/PySide6 binding sources.
The patch reproduction gate verifies that every modified frozen module is reproducible from the
readable patch sources on the verified upstream YASB 2.0.7 library. Nothing is offered only as
opaque modified bytecode.

Unmodified Qt framework source is available through the official public source servers:

- [Qt 6.10.2 complete source](https://download.qt.io/official_releases/qt/6.10/6.10.2/single/qt-everywhere-src-6.10.2.tar.xz)
- [Qt 6.10.3 complete source](https://download.qt.io/official_releases/qt/6.10/6.10.3/single/qt-everywhere-src-6.10.3.tar.xz)

Exact source URLs and SHA-256 values are retained in distribution/source-access.json.
These source-access directions must accompany binary release links. Qt libraries are installed as
replaceable shared libraries, rather than hidden permanently inside a one-file application.
Users may replace/relink those libraries and debug such replacements under their original terms.

YASB is credited to amnweb and remains MIT licensed. Python remains under the PSF license;
cx_Freeze, comtypes, PyYAML and other dependencies keep their included copyright/license notices.
The installer builder's license does not relicense installed software.
Natural Earth datasets remain public domain with attribution preserved.
No original ownership of upstream software or affiliation with Microsoft/YASB is asserted.
