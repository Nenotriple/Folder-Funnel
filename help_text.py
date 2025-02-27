HELP_TEXT = {
    "Welcome to Folder-Funnel":
    "Folder-Funnel watches a folder for new files, then seamlessly moves them to a chosen folder.\n\n"
    "Filenames are automatically renamed to avoid duplicates and checks if they are identical before moving.\n\n",

    "Basic Steps:":
    "**1) Select** a folder to watch from *'File' > 'Select source path...'* or via the *'Browse...'* button.\n"
    "**2) Click 'Start'** to copy a folder structure *(the funnel)* and begin monitoring changes there.\n"
    "**3) Click 'Stop'** to remove the funnel folder *(and any detected duplicates)* and end the process.",

    "Duplicate Handling Options:":
    "• **Duplicate Handling Mode**:\n"
    "  - *Move*: Move incoming duplicate files to a '#DUPLICATE#_' storage folder.\n"
    "  - *Delete*: Remove incoming duplicate files.\n"
    "• **Duplicate Matching Mode**:\n"
    "  - *Flexible*: More flexible initial filename matching.\n"
    "  - *Strict*: More strict initial filename matching\n"
    "• **Duplicate Checking Mode**:\n"
    "  - *Similar*: Perform additional MD5 check against files with a similar filename\n"
    "  - *Single*: Perform on MD5 check only on exact filename match.\n"
    "• **Duplicate Checking: Max Files**:\n"
    "  - The maximum number of similar files to check for duplicates.\n",

    "Queue Timer:":
    "• New files and folders in the watch folder are queued for moving after a brief delay. This groups changes together and prevents partial moves.\n"
    "• The queue timer length can be adjusted under *'Options' > 'Queue Timer'*. This delay occurs between moving batches of files.\n"
    "• The timer progress bar shows the remaining time before the next move.\n"
    "• The timer resets each time a new file is added to the queue.",

    "Tips & Tricks:":
    "• Right-click items in *'History'* to open or locate them quickly.\n"
    "• Clear logs or history anytime under the *'Edit'* menu.\n"
    "• Check the status bar at the bottom to see progress and queue details."
}
