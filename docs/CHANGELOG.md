<!-- markdownlint-disable MD033-->

# Index

- [v1.03](#v103)
- [v1.02](#v102)
- [v1.01](#v101)
- [v1.0](#v10)

<!--###########################################################################-->

## v1.03

- [💾](https://github.com/Nenotriple/folder-funnel/releases/tag/v1.03)

## New

- The app can now be minimized to the system tray if `Options > Minimize to Tray on Close` is enabled.
  - When minimized to tray, the app can be restored by double-clicking the tray icon or via the tray context menu.
- Folder-Funnel now keeps track of the lifetime moves and duplicate actions and can give you an estimate of the time saved. You can adjust the time values in the `settings.cfg` file.
- You will now be asked at startup if you want to reload the last directory and start the funnel process.
- Pre-existing files/folders in the funnel folder are now detected and moved to the source folder on startup *(or optionally ignored)*.
- Added a dedicated and robust duplicate file scanner via `Edit > Find Duplicate Files...`.
  - This tool works independently of the funnel process and can be used to scan a specific folder for duplicate files.
  - The scanning process allows for lightweight or deep scanning.
  - Duplicates can be previewed and selectively dealt with or in bulk.
- Added improved detail reporting during the funnel warm-up phase.

## Changes

- Stop/Start buttons are consolidated into a single button.
- The Browse button and directory input are now disabled while the funnel is active.
- The log now uses the Consolas font for better readability.
- The running indicator animation is removed for simplicity.
- Logs are now prefixed which can help spot specific types of messages more easily.
- Improved shutdown flow.

## Fixed

- Fix state issue with text wrap option.

<!--###########################################################################-->

## v1.02

- [💾](https://github.com/Nenotriple/folder-funnel/releases/tag/v1.02)

## Fixed

- Fixed the `settings.cfg` file not being created or loaded.

<!--###########################################################################-->

## v1.01

- [💾](https://github.com/Nenotriple/folder-funnel/releases/tag/v1.01)

## New

- **File Rules**:
  - `Ignore Temp Files`:
    - Files with the following extensions are ignored: `.tmp, .temp, .part, .crdownload, .partial, .bak`.
  - `Ignore Temp Firefox Files`:
    - Skip placeholder and .part files created by Firefox during its download process, and only move the finished download.
  - `Auto-Extract Zip Files '*\'`:
    - Automatically extract ZIP files to the source folder, creating a new folder with the same name as the ZIP file.
  - `Auto Delete Zip Files After Extraction`:
    - Automatically delete the ZIP file after auto-extraction. This option does nothing if auto-extraction is disabled.
  - `Overwrite on File Conflict`:
    - Overwrite existing files in the source folder with incoming files from the funnel folder.

## Other Changes

- All actions now have an additional 2-second delay to allow files to "settle".
- Updated some labels and tooltips to better reflect their purpose.

<!--###########################################################################-->

## v1.0

- [💾](https://github.com/Nenotriple/folder-funnel/releases/tag/v1.0)

**This is the first release.**
