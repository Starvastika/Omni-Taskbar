# YASB integrated Windows shell

A compact grayscale dual-bar shell for Windows 11, built on YASB 2.0.7. It includes protected
top-bar work-area/reveal behavior, a shared application/window command model, Time Center,
Weather Center and a lightweight recovery watchdog.

## Requirements and installation

Windows 11 x64, Python 3.14 x64 and network access for initial dependency installation.
The installer validates Python and uses an isolated environment for pinned Qt/timezone dependencies.
YASB is obtained from its official versioned release with checksum verification. No user token is
needed for public release checks. Optional GPU/LHM monitoring requires suitable drivers and
Libre Hardware Monitor configured independently. Updates do not require elevation.

Download install.cmd and install.ps1 from a tagged project release into the same folder, then open
install.cmd. The release bootstrap already knows its repository/version. The graphical first-run dialog asks
for Automatic updates, Check automatically, or Manual only. The bootstrap uses the release manifest
and SHA-256, installs only into %USERPROFILE%\.config\yasb, creates user-local settings,
registers the existing watchdog architecture, and starts the shell. Existing configuration is preserved.
The same watchdog task uses a console-free Python host, a current-user mutex, the original 15-second
startup grace/eight-second checks/bounded backoff, and process-lifetime validation. The PowerShell
watchdog file remains a compatible launch entry point. It is one watchdog, not a second updater daemon.

This checkout has no configured GitHub repository yet. Set repository in version.json to the chosen
owner/repository before publishing; clients never update from main. Public clients need public releases.

## Weather

weather-center/data/state.json owns the selected location, saved locations and preferences.
Migration prefers a valid Weather Center selection, otherwise imports a valid old YASB weather.json
location, otherwise remains unconfigured. Coordinates and IANA timezone are retained.

Weather Center atomically writes a derived data/compact.json snapshot of the selected identity and
forecast. The compact bar watches atomic replacements; it never edits a second location state or
sends a separate weather request. Changed identity clears old data, and generations reject old provider
results. SI/UTC values are adapted to the existing upward card's local-time/unit contract.
Compact weather refreshes at the configured interval while Weather Center is hidden.

Click Setup location to open Weather Center directly to Locations with the actual search focused.
Later changes update both surfaces without restarting YASB. Offline/error states preserve the
selected location and indicate stale/unavailable data. State, projections and caches are never committed.

## Updates

Open the existing top-right ... account/power menu, then Taskbar Updates below Manage accounts.
It shows the installed version, Check for Updates, What's New, contextual Install Update /
Restart & Update Now, and the update-mode selector.

- Automatic updates: check on startup and at most every six hours; verify and stage, then apply
  at the next natural taskbar restart. Restart & Update Now is optional.
- Check automatically: background checks and persistent indicators; installation requires a click.
- Manual only: no background network checks; Check for Updates runs only when requested.

The initial choice is unset until you choose. There is no implicit automatic-update opt-in.
Available/staged/failed/rolled-back updates leave red dots on ... and the Taskbar Updates row.
Opening/closing the popup never clears them. Successful installation resolves update attention.
Release notes are plain text, never executable HTML. Windows is never automatically rebooted.

The updater uses the stable latest-release endpoint with ETag caching, bounded timeouts and backoff,
as described by [GitHub's release API](https://docs.github.com/en/rest/releases/releases).
It validates configured-repository assets, stable semantic versions, SHA-256, minimum updater version,
shell restart and an explicit prohibition of Windows restart.

Downloads enter user-scoped staging. SHA-256, inventory hashes, version, paths, duplicates, symlinks,
size bounds and program-file ownership are validated before live files are touched.
The existing watchdog honors a bounded process-owned maintenance lease. A durable transaction journal
and one rollback copy protect replaced files and compatible config/migration metadata.
Shell components are stopped through their existing CLI/IPC. Health verifies the two native YASB
bars and expected companion IPC across several samples. Failed health/migration restores previous
files/config, starts the previous shell and leaves failure attention without a restart loop.
The watchdog recovers interrupted transactions with a pre-update engine copy.

## Data, recovery and uninstall

Live config/styles, stable-v1, companion data/caches/logs/exports, local runtime paths, update
settings/staging/backups and authentication are ignored. Sanitized first-install defaults are in
distribution/defaults; upgrades do not replace live config. Migrations are additive/idempotent,
preserve unknown fields and back up configuration first.

For intentional maintenance, helpers/watchdog-maintenance.ps1 -Action Stop disables supervision;
use the private CLI and companion --quit commands. -Action Start resumes it.
shell-updater/data/state.json records the latest result. Failed rollback keeps its journal/backup
for recovery; retain them until the shell works.

distribution/uninstall.ps1 removes only this shell's autostart/watchdog and retains user data,
stable-v1 and Windows taskbar preferences. Restore native taskbar auto-hide through Windows settings
if desired. LHM installations/tasks are not removed.

## Development and release

Use Python 3.14, matching the frozen YASB bytecode ABI. On Windows:

    python -m unittest discover -s shell-updater/tests
    python tools/build_release_runtime.py
    python tools/release_package.py

The frozen base contains code only, has a pinned checksum and is privacy-reviewed. Builds overlay
the readable weather/account integrations and command model. Native dependencies come from the
verified official YASB release. Updating the frozen base is an explicit reviewed maintenance step.

Maintainer sequence:

1. Choose repository name/visibility; set repository in version.json.
2. Update the single version.json version and CHANGELOG.md.
3. Run tests, privacy scan and package dry-run; review staged changes.
4. Commit/push normally. Never force-push.
5. Push vMAJOR.MINOR.PATCH, matching version.json.
6. Windows GitHub Actions tests/checks privacy and builds the exact tag.
7. Upload the ZIP, SHA256SUMS, manifest and bootstrap to a draft GitHub Release.
8. Inspect the artifacts, then publish the tested release.
9. Clients detect the published stable release according to their policy.

The workflow has not run on GitHub until a repository/tag is actually pushed.
Run local mock-release success/rollback tests before relying on public releases.
Measured local/live results and coverage limits are in the completion report.

## Compatibility and licensing

Pinned to YASB 2.0.7 / Python 3.14 / Windows 11 x64. Fullscreen apps never reveal the top bar;
ordinary maximized/Snap reveal reserves space before showing. Native/UIA commands depend on
what each app exposes; fallback Window/Actions/search remains useful.
Hardware sensors and keyboard layouts are machine settings, not installed by this package.

No license has been chosen for original custom work; see [third-party notices](THIRD_PARTY_NOTICES.md).
