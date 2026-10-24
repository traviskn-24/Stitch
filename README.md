# Stitch

Stitch is a mobile-first, private daily journal built with Python and Flet. It lets you write one short note for each day, attach a photo, and revisit earlier entries.

## Features

- Create or edit one journal entry for the current local date, with a 140-character limit.
- Browse saved entries in a newest-first history.
- Attach a photo from the gallery or take one with the in-app camera preview.
- Save journal entries and copied photos locally on the device.
- Use a simple Sage & Linen visual theme.

## Setup

Requirements:

- Python 3.10 or later.
- [`uv`](https://docs.astral.sh/uv/) for dependency and project commands.
- For Android builds, the Android build tools required by Flet.
- For iOS builds, macOS with Xcode.

Install dependencies:

```powershell
uv sync
```

Run the app on an Android device:

```powershell
uv run flet run --android src/main.py
```

Run on an iPhone from a Mac on the same network:

```powershell
uv run flet run --ios src/main.py
```

The in-app camera uses Flet's `flet-camera` Flutter extension. For camera testing on Android, build and install the project-specific client rather than using the generic Flet app:

```powershell
uv run flet build apk
```

You can also build an iOS simulator app on macOS:

```bash
uv run flet build ios-simulator
```

## Data and privacy

The app stores journal entries in a local SQLite database and copies attached photos into app-private storage. On device, Flet's `FLET_APP_STORAGE_DATA` directory is used. During local development, the data is stored in `~/.one-line-journal`. This project does not include a cloud sync service.

## Artwork disclaimer

The app icon and splash screen are placeholders and still need final artwork. The current icon asset is included for development; replace it with approved production artwork before release.

## Build artifacts

Generated APK files and other build output are not included in this repository. Build artifacts are ignored by Git.

## Project files

- `src/main.py` — Flet user interface and camera flow.
- `src/journal_store.py` — SQLite journal and local image storage.
- `src/assets/icon.png` — current placeholder icon asset.
- `pyproject.toml` and `uv.lock` — project metadata and locked dependencies.
