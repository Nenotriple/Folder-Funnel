<p align="center"><img src="https://github.com/user-attachments/assets/37631bed-426a-4f9d-9043-a4e125c8016d" alt="cover" width="730"></p>
<p align="center">Copy a folder structure and funnel files from it to a source folder while handling duplicate files.</p>
<p align="center"><img src="https://github.com/user-attachments/assets/95d14545-9084-41f3-952a-dd157acc76db" alt="cover"></p>

## [💾 Download Latest Release](https://github.com/Nenotriple/Folder-Funnel/releases)

## ❓ What's this for?
Folder-Funnel is designed to speed up the process of saving files to a specific directory by automating the creation of unique filenames. It works by creating an empty copy of a folder structure, known as the "funnel" folder. You can save files to the funnel folder, and Folder-Funnel will automatically move them to the destination folder, resolving any filename conflicts and handling potential duplicate files.


## 💡 Usage

### Quick Start
1) Select a folder to watch from `File > Select source path...` or via the `Browse...` button.
2) Click *Start* to copy a folder structure *(the funnel)* and begin monitoring changes there.
3) Move files into the funnel folder to have them automatically moved to the destination folder.
4) Click *Stop* to remove the funnel folder *(and any detected duplicates)* and end the process.

### Basic Tips
- View *Moved* or *Duplicate* history via `View > History View`.
- Double or right-click items in the *'History'* list to open or locate them quickly.
- Clear logs or history anytime under the *'Edit'* menu.
- Check the status bar at the bottom to see progress and queue details.

### File Rules
- **Ignore Temp Files**:
  - Files with the following extensions are ignored: *.tmp*, *.temp*, *.part*, *.crdownload*, *.partial*, *.bak*.
- **Ignore Temp Firefox Files**:
  - Skip placeholder and *.part* files created by Firefox during its download process and only move the finished download.
- **Auto-Extract Zip Files**:
  - Automatically extract zip files to the source folder, creating a new folder with the same name as the zip file.
- **Auto Delete Zip Files After Extraction**:
  - Automatically delete the zip file after auto-extraction. This option does nothing if auto-extraction is disabled.
- **Overwrite on File Conflict**:
  - Overwrite existing files in the source folder with incoming files from the funnel folder.

### Duplicate Handling Options
- **Duplicate Handling Mode**:
  - *Move*: Move incoming duplicate files to a *'#DUPLICATE#_'* storage folder.
  - *Delete*: Remove incoming duplicate files.
- **Duplicate Name Matching Mode**:
  - *Flexible*: More flexible initial filename matching.
  - *Strict*: More strict initial filename matching.
- **Duplicate Checking Mode**:
  - *Similar*: Perform additional MD5 checksum check against files with a similar filename.
  - *Single*: Perform an MD5 checksum check only on exact filename match.
- **Duplicate Checking: Max Files**:
  - The maximum number of similar files to check for duplicates.

### Queue Timer
- The queue timer length can be adjusted under `Options > Queue Timer`.
- New files and folders in the watch folder are queued for moving after a brief delay. This groups changes together and prevents partial moves.
- The timer progress bar shows the remaining time before the next move.
- The timer resets each time a new file is added to the queue.

### Notes and Warnings
- **Warning**: Moving, renaming, or deleting the source or funnel folders while Folder-Funnel is running may cause issues.
- **Warning**: Avoid creating temporary files in the funnel folder.
- **Note**: The app creates two base folders: `#FUNNEL#_` and `#DUPLICATE#_` in the same path as the source folder.
- **Note**: When closing the app, you can choose to keep the duplicate storage folder or delete it.


## 🚀 Installation

Created and tested on: ![Static Badge](https://img.shields.io/badge/Windows-blue)

### From Release
1. Download the [latest release](https://github.com/Nenotriple/Folder-Funnel/releases/latest).
2. Run the portable executable file.

### From Source
1. Ensure [Python](https://www.python.org/downloads/) is installed on your system.
2. Clone the repository:
   ```bash
   git clone https://github.com/Nenotriple/Folder-Funnel.git
   ```
3. Run `Start.bat` to set up the environment and launch the application. This script will:
   - Set up local virtual environment.
   - Install from requirements.txt.
   - Launch the Folder-Funnel application.

### Build from Source
1. Follow the 'From Source' instructions.
2. See the [Build Instructions](docs/Build_Instructions.md) for more information on building the executable.
