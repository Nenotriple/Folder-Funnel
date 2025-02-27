HELP_TEXT = {
    "Welcome to Folder-Funnel":
    "Folder-Funnel watches a folder for new files, then seamlessly moves them to a chosen folder.\n\n"
    "Filenames are automatically renamed to avoid duplicates and checks if they are identical before moving.\n\n",

    "Basic Steps:":
    "**1) Select** a folder to watch from *'File' > 'Select source path...'* or via the *'Browse...'* button.\n"
    "**2) Click 'Start'** to duplicate the folder structure and begin monitoring changes.\n"
    "**3) Click 'Stop'** to remove the duplicate folder and end the process.",

    "Duplicate Handling:":
    "• **Rigorous Check**: Compares file contents using MD5 hashes to ensure files are identical.\n"
    "• **Simple Check**: Compares file sizes before moving.\n"
    "• **Duplicate Matching Mode**: Choose *'Strict'* to match filenames exactly, or *'Flexible'* to match similar filenames.",

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
