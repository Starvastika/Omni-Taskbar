# Third-party components

YASB 2.0.7 is MIT licensed by amnweb; its license is in distribution/licenses/YASB-LICENSE.txt.
The reviewed frozen Python code snapshot is built on that version. Snapshot filenames are sanitized;
its SHA-256 and Python ABI are pinned in distribution/runtime-base.json.
Snapshots of custom visibility, Wi-Fi, language and native-window fixes are in shell-updater/runtime-source;
command-provider sources are under helpers. The installer obtains the official versioned YASB native
runtime separately, verifies its checksum, and replaces only its Python library with the reviewed release.

Python, cx_Freeze, PyQt6/Qt, PySide6/shiboken6, comtypes, PyYAML, Astral, tzdata, tzlocal and tzfpy
retain their respective licenses. Vendored comtypes/PyYAML notices remain with their packages.
Qt bindings and Python dependencies are installed into an isolated environment, not copied
from personal virtual environments. The frozen application notice and available runtime notices
are retained under distribution/licenses. YASB's official runtime contains further dependency notices.

Natural Earth land/country datasets are public domain; existing attribution files remain with the
Time Center map and Weather Center assets. Open-Meteo/GeoNames, RainViewer and official alert-provider
attribution remains in Weather Center; those services have their own usage terms.
Windows system fonts/icons and optional Nerd Fonts are not redistributed.

No license for this project's original custom work has been chosen. This notice preserves
third-party licenses and does not grant a new license to that custom work.
