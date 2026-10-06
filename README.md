# Omni Taskbar

A compact grayscale Windows 11 shell powered by YASB 2.0.7, with Time Center, Weather Center, Application Command Bar, system tray, virtual desktops, and safe integrated updates.

## Install

Download **Omni-Taskbar-Setup-1.0.0.exe** from [GitHub Releases](https://github.com/Starvastika/Omni-Taskbar/releases). Run that one file. No separate Python, YASB, Git, terminal commands, or dependency downloads are needed. Setup works offline and installs per user without administrator rights.

Requires Windows 11 x64. The installer includes private Python 3.14.7, YASB 2.0.7, Qt bindings, timezone packages, maps, QML, and private Nerd Font glyphs. Windows supplies Segoe UI. Hardware sensors depend on compatible drivers and optional Libre Hardware Monitor; keyboard layouts are your Windows settings.

Default program folder: %LOCALAPPDATA%\Programs\Omni-Taskbar. Settings and personal data: %APPDATA%\Omni-Taskbar. These are separate from a developer checkout at %USERPROFILE%\.config\yasb.

Setup asks how to update and whether to start the shell. Run the same EXE to repair or manually upgrade. Uninstall through Windows Installed Apps; settings and personal data are retained unless you explicitly select their removal. On first launch, Omni enables native Windows taskbar auto-hide once. Uninstall restores the prior preference when it still matches Omni’s setting; later user changes are preserved. Windows is never rebooted automatically. This initial build is unsigned: Windows may show Unknown Publisher or SmartScreen. Verify the release SHA-256; do not disable Windows security.

## Updates

Open the existing top-right **... â†’ Taskbar Updates**, directly below Manage accounts. It shows the installed version, Check for Updates, What's New, an applicable Install Update / Restart & Update Now button, and the update-mode selector.

- **Automatic updates:** verify and stage stable releases; apply at the next safe taskbar restart.
- **Check automatically** (setup default): notify; install only when requested.
- **Manual only:** no background checks; check when requested.

A tiny red dot on ... and Taskbar Updates remains while an update is available, staged, failed, or rolled back. Opening the popup does not clear it. There is no additional updater icon. The internal omni-taskbar-x.y.z-update.zip is for the updater; normal users do not need it.

Updates come only from [Starvastika/Omni-Taskbar releases](https://github.com/Starvastika/Omni-Taskbar/releases), never raw main. Repository-bound manifests, SHA-256 and per-file inventories protect staging. Maintenance leases suspend the existing watchdog during transactions. Compatible configuration migrations preserve unknown fields; component health failure restores the previous files/config and retains an attention indicator.

## Your data

Weather Center owns the selected/saved locations. Its compact projection drives bottom-bar weather. Setup location opens Locations and focuses real search. Changing location updates both surfaces immediately. Offline/provider errors preserve a configured location.

Time Center clocks, timers, alarms and planner, Weather Center locations/preferences, caches, logs and updater state stay in the user-data folder. Fresh installs have empty personal state. Releases contain sanitized defaults, never the developer's configuration or saved locations. Upgrades preserve configuration and data.

The top bar reserves work area while visible. Maximized/Snap hover reveal reserves space before showing; fullscreen-like windows never reveal. Application commands depend on what Windows/applications expose; Window/Actions/search fallback remains available.

## Licensing and source

Original custom work: [MIT](LICENSE), copyright 2026 Starvastika. Upstream components retain their own licenses, including PyQt GPLv3 and Qt/PySide LGPL/GPL conditions. The combined distribution is subject to those conditions; it is not wholly MIT. See [third-party notices](THIRD_PARTY_NOTICES.md) and [corresponding source access](SOURCE_ACCESS.md). Every binary release provides an advanced corresponding-source archive and exact public Qt source links. Required notices are installed. Qt DLLs remain separate and replaceable.

## Build and release

Maintainers need Windows x64, Python 3.14, Visual Studio C++ build tools and Inno Setup 6.7.3. These are build tools, not consumer requirements.

    python tools/prepare_installer_deps.py
    powershell -File tools/build_omni_launcher.ps1
    powershell -File weather-center/build-launcher.ps1
    python -m unittest discover -s shell-updater/tests
    python tools/release_build.py

Verified official dependency archives are downloaded only at build time. The readable patch recipe reproduces the frozen YASB base and is checked against its pinned snapshot. Explicit inventories exclude personal/runtime files. dist contains the full EXE, compact update ZIP, manifest, checksums, and corresponding source.

Use a separate installation fixture; never test over a live developer shell. The Windows release workflow tests a fresh EXE-installed layout, repair, upgrades, updater success/rollback, uninstall and state preservation before creating a draft release. Interactive shell coverage must also be recorded before publication. A prepared workflow is not evidence of an actual successful GitHub run.

Push main normally after privacy review; never force-push. Tag v1.0.0 only at the reviewed version commit. Inspect the actual Actions logs and draft assets, verify checksums and the targeted shell matrix, then publish the stable release. Optional trusted Authenticode signing hooks are in tools/sign_artifacts.ps1. No self-signed certificate is used.
