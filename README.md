<p align="center"><img src="https://github.com/user-attachments/assets/34974daf-9315-48eb-90d6-3316a46f417b" alt="cover" width="730"></p>
<p align="center">Copy a folder structure and funnel files from it to a source folder while handling duplicate files.</p>
<p align="center"><img src="https://github.com/user-attachments/assets/95d14545-9084-41f3-952a-dd157acc76db" alt="cover"></p>


## ❓ What's this for?
Folder-Funnel was created to help speed up the process of saving files to a directory by removing the need to manually create a unique filename. It does this by creating a copy of a folder with no other files. This allows you to save the file to the funnel folder and have it automatically moved to the destination folder while handling filename conflicts and potential duplicate files.

## 📋 Index
- [Usage](#usage)
- [Installation](#installation)


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

### Duplicate Handling Options
- **Duplicate Handling Mode**:
  - *Move*: Move incoming duplicate files to a *'#DUPLICATE#_'* storage folder.
  - *Delete*: Remove incoming duplicate files.
- **Duplicate Matching Mode**:
  - *Flexible*: More flexible initial filename matching.
  - *Strict*: More strict initial filename matching
- **Duplicate Checking Mode**:
  - *Similar*: Perform additional MD5 checksum check against files with a similar filename
  - *Single*: Perform an MD5 checksum check only on exact filename match.
- **Duplicate Checking: Max Files**:
  - The maximum number of similar files to check for duplicates.

### Queue Timer
- The queue timer length can be adjusted under `Options > Queue Timer`.
- New files and folders in the watch folder are queued for moving after a brief delay. This groups changes together and prevents partial moves.
- The timer progress bar shows the remaining time before the next move.
- The timer resets each time a new file is added to the queue.

### Notes and Warnings:
- **Warning**: *Moving/renaming/deleting* the source or funnel folders while Folder-Funnel is running may cause issues.
- **Warning**: Avoid creating temporary files in the funnel folder.
- **Note**: The app creates two base folders: `#FUNNEL#_`, and `#DUPLICATE#_` in the same path as the source folder.
- **Note**: When closing the app you can choose to keep the duplicate storage folder or delete it.


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
