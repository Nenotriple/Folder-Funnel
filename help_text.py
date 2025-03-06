HELP_TEXT = {
    "Folder-Funnel":
    "Folder-Funnel was created to help speed up the process of saving files to a directory by removing the need to "
    "manually create a unique filename. It does this by creating a copy of a folder with no other files. This allows "
    "you to save the file to the funnel folder and have it automatically moved to the destination folder while handling "
    "filename conflicts and potential duplicate files.\n\n",

    "Quick Start:":
    "**1)** Select a folder to watch from *'File' > 'Select source path...'* or via the *'Browse...'* button.\n"
    "**2)** Click *'Start'* to copy a folder structure *(the funnel)* and begin monitoring changes there.\n"
    "**3)** Move files into the funnel folder to have them automatically moved to the destination folder.\n"
    "**4)** Click *'Stop'* to remove the funnel folder *(and any detected duplicates)* and end the process.",

    "Basic Tips:":
    "• View *'Moved'* or *'Duplicate'* history via *'View' > 'History View'*.\n"
    "• Double or right-click items in the *'History'* list to open or locate them quickly.\n"
    "• Clear logs or history anytime under the *'Edit'* menu.\n"
    "• Check the status bar at the bottom to see progress and queue details.",

    "File Rules:":
    "• **Ignore Temp Files**:\n"
    "   - Files with the following extensions are ignored: *.tmp*, *.temp*, *.part*, *.crdownload*, *.partial*, *.bak*.\n"
    "• **Ignore Temp Firefox Files**:\n"
    "   - Skip placeholder and *.part* files created by Firefox during its download process and only move the finished download.\n"
    "• **Auto-Extract Zip Files '*\\'**:\n"
    "   - Automatically extract zip files to the source folder, creating a new folder with the same name as the zip file.\n"
    "• **Auto Delete Zip Files After Extraction**:\n"
    "   - Automatically delete the zip file after auto-extraction. This option does nothing if auto-extraction is disabled.\n"
    "• **Overwrite on File Conflict**:\n"
    "   - Overwrite existing files in the source folder with incoming files from the funnel folder.",

    "Duplicate Handling Options:":
    "• **Duplicate Handling Mode**:\n"
    "   - *Move*: Move incoming duplicate files to a *'#DUPLICATE#_'* storage folder.\n"
    "   - *Delete*: Remove incoming duplicate files.\n"
    "• **Duplicate Name Matching Mode**:\n"
    "   - *Flexible*: More flexible initial filename matching.\n"
    "   - *Strict*: More strict initial filename matching.\n"
    "• **Duplicate Checking Mode**:\n"
    "   - *Similar*: Perform additional MD5 checksum check against files with a similar filename.\n"
    "   - *Single*: Perform an MD5 checksum check only on exact filename match.\n"
    "• **Duplicate Checking: Max Files**:\n"
    "   - The maximum number of similar files to check for duplicates.",

    "Queue Timer:":
    "• The queue timer length can be adjusted under *'Options' > 'Queue Timer'*.\n"
    "• New files and folders in the watch folder are queued for moving after a brief delay. This groups changes together and prevents partial moves.\n"
    "• The timer progress bar shows the remaining time before the next move.\n"
    "• The timer resets each time a new file is added to the queue.",

    "Notes and Warnings:":
    "• **Warning**: *Moving/renaming/deleting* the source or funnel folders while Folder-Funnel is running may cause issues.\n"
    "• **Warning**: Avoid creating temporary files in the funnel folder.\n"
    "• **Note**: The app creates two base folders: *'#FUNNEL#_'*, and *'#DUPLICATE#_'* in the same path as the source folder.\n"
    "• **Note**: When closing the app you can choose to keep the duplicate storage folder or delete it.",
}
