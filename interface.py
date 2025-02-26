#region - Imports


# Standard
import tkinter as tk
from tkinter import ttk, scrolledtext

# Third-party
from TkToolTip.TkToolTip import TkToolTip as Tip

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import FolderFunnelApp


#endregion
#region - Entry point


def create_interface(app: 'FolderFunnelApp'):
    create_menubar(app)
    create_control_row(app)
    create_main_frame(app)
    create_message_row(app)


#endregion
#region - Menubar


def create_menubar(app: 'FolderFunnelApp'):
    # Create menubar
    menubar = tk.Menu(app.root)
    app.root.config(menu=menubar)
    # Menus
    _create_file_menu(app, menubar)
    _create_edit_menu(app, menubar)
    _create_options_menu(app, menubar)
    menubar.add_command(label="Help", command=app.open_help_window)


def _create_file_menu(app: 'FolderFunnelApp', menubar: tk.Menu):
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Select source path...", command=app.select_working_dir)
    file_menu.add_command(label="Open selected path", command=app.open_folder)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=app.on_closing)


def _create_edit_menu(app: 'FolderFunnelApp', menubar: tk.Menu):
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Sync Folders", command=app.sync_watch_folders)
    edit_menu.add_separator()
    edit_menu.add_command(label="Clear log", command=app.clear_log)
    edit_menu.add_command(label="Clear history", command=app.clear_history)


def _create_options_menu(app: 'FolderFunnelApp', menubar: tk.Menu):
    options_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Options", menu=options_menu)
    # Queue submenu
    queue_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Queue Timer", menu=queue_menu)
    queue_menu.add_command(label="Queue Timer Length", state="disabled")
    queue_menu.add_radiobutton(label="5 seconds", variable=app.move_queue_length_var, value=5000)
    queue_menu.add_radiobutton(label="15 seconds", variable=app.move_queue_length_var, value=15000)
    queue_menu.add_radiobutton(label="30 seconds", variable=app.move_queue_length_var, value=30000)
    queue_menu.add_radiobutton(label="1 minute", variable=app.move_queue_length_var, value=60000)
    queue_menu.add_radiobutton(label="5 minutes", variable=app.move_queue_length_var, value=300000)
    queue_menu.add_radiobutton(label="10 minutes", variable=app.move_queue_length_var, value=600000)
    queue_menu.add_radiobutton(label="1 hour", variable=app.move_queue_length_var, value=3600000)
    # Duplicate handling submenu
    dupe_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Duplicate Handling", menu=dupe_menu)
    dupe_menu.add_command(label="Duplicate Checking Mode", state="disabled")
    dupe_menu.add_radiobutton(label="Rigorous", variable=app.rigorous_duplicate_check_var, value=True)
    dupe_menu.add_radiobutton(label="Simple", variable=app.rigorous_duplicate_check_var, value=False)
    dupe_menu.add_separator()
    # Rigorous Check
    dupe_menu.add_command(label="Rigorous Check: Max Files", state="disabled")
    dupe_menu.add_radiobutton(label="10", variable=app.rigorous_max_file_var, value=10)
    dupe_menu.add_radiobutton(label="25", variable=app.rigorous_max_file_var, value=25)
    dupe_menu.add_radiobutton(label="50", variable=app.rigorous_max_file_var, value=50)
    dupe_menu.add_radiobutton(label="100", variable=app.rigorous_max_file_var, value=100)
    dupe_menu.add_radiobutton(label="1000", variable=app.rigorous_max_file_var, value=1000)
    dupe_menu.add_radiobutton(label="10000", variable=app.rigorous_max_file_var, value=10000)
    dupe_menu.add_separator()
    # Dupe Filter Mode
    dupe_menu.add_command(label="Duplicate Matching Mode", state="disabled")
    dupe_menu.add_radiobutton(label="Strict", variable=app.dupe_filter_mode_var, value="Strict")
    dupe_menu.add_radiobutton(label="Flexible", variable=app.dupe_filter_mode_var, value="Flexible")
    # Text Log submenu
    text_log_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Text Log", menu=text_log_menu)
    text_log_menu.add_checkbutton(label="Wrap Text", variable=app.text_log_wrap_var, command=app.toggle_text_wrap)


#endregion
#region - Control row


def create_control_row(app: 'FolderFunnelApp'):
    # Create control row
    control_frame = tk.Frame(app.root)
    control_frame.pack(side="top", fill="x")
    # Separator
    ttk.Separator(control_frame, orient="horizontal").pack(side="bottom", fill="x")
    # Widgets
    _create_dir_entry(app, control_frame)
    _create_buttons(app, control_frame)


def _create_dir_entry(app: 'FolderFunnelApp', control_frame: tk.Frame):
    dir_selection_frame = tk.Frame(control_frame)
    dir_selection_frame.pack(side="left", fill="x", expand=True)
    #Label
    dir_label = tk.Label(dir_selection_frame, text="Watch Folder:")
    dir_label.pack(side="left")
    Tip(dir_label, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Entry
    app.dir_entry = ttk.Entry(dir_selection_frame, textvariable=app.working_dir_var)
    app.dir_entry.pack(side="left", fill="x", expand=True)
    app.dir_entry_tooltip = Tip(app.dir_entry, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Browse
    browse_button = ttk.Button(dir_selection_frame, text="Browse...", command=app.select_working_dir)
    browse_button.pack(side="left")
    Tip(browse_button, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Open
    open_button = ttk.Button(dir_selection_frame, text="Open", command=app.open_folder)
    open_button.pack(side="left")
    Tip(open_button, "Open the selected folder in File Explorer", delay=250, pady=25, origin="widget")


def _create_buttons(app: 'FolderFunnelApp', control_frame: tk.Frame):
    app.start_button = ttk.Button(control_frame, text="Start", command=app.start_folder_watcher)
    app.start_button.pack(side="left")
    Tip(app.start_button, "Begin watching the selected folder", delay=250, pady=25, origin="widget")
    # Stop
    app.stop_button = ttk.Button(control_frame, text="Stop", state="disabled", command=app.stop_folder_watcher)
    app.stop_button.pack(side="left")
    Tip(app.stop_button, "Stop watching the folder and remove the duplicate", delay=250, pady=25, origin="widget")


#endregion
#region - Main frame


def create_main_frame(app: 'FolderFunnelApp'):
    # Create main frame
    main_frame = tk.Frame(app.root)
    main_frame.pack(fill="both", expand=True)
    # paned window
    main_pane = tk.PanedWindow(main_frame, orient="horizontal", sashwidth=6, bg="#d0d0d0", bd=0)
    main_pane.pack(fill="both", expand=True)
    # Widgets
    _create_text_log(app, main_pane)
    _create_history_list(app, main_pane)


def _create_text_log(app: 'FolderFunnelApp', main_pane: tk.PanedWindow):
    # Frame
    text_frame = tk.Frame(main_pane)
    main_pane.add(text_frame, stretch="always")
    main_pane.paneconfigure(text_frame, minsize=200, width=400)
    # Label/Menu
    textlog_options_menu = ttk.Menubutton(text_frame, text="Log")
    textlog_options_menu.pack(fill="x")
    textlog_options_menu.menu = tk.Menu(textlog_options_menu, tearoff=0)
    textlog_options_menu["menu"] = textlog_options_menu.menu
    textlog_options_menu.menu.add_command(label="Clear Log", command=app.clear_log)
    textlog_options_menu.menu.add_separator()
    textlog_options_menu.menu.add_checkbutton(label="Wrap Text", variable=app.text_log_wrap_var, command=app.toggle_text_wrap)
    Tip(textlog_options_menu, "Log of events and actions", delay=250, pady=25, origin="widget")
    # Text
    app.text_log = scrolledtext.ScrolledText(text_frame, wrap="word", state="disable", width=1, height=1)
    app.text_log.pack(fill="both", expand=True)



def _create_history_list(app: 'FolderFunnelApp', main_pane: tk.PanedWindow):
    # Frame
    list_frame = tk.Frame(main_pane)
    main_pane.add(list_frame, stretch="never")
    main_pane.paneconfigure(list_frame, minsize=200, width=200)
    # Label/Menu
    history_options_menu = ttk.Menubutton(list_frame, text="History")
    history_options_menu.pack(fill="x")
    history_options_menu.menu = tk.Menu(history_options_menu, tearoff=0)
    history_options_menu["menu"] = history_options_menu.menu
    history_options_menu.menu.add_command(label="Clear History", command=app.clear_history)
    history_options_menu.menu.add_separator()
    history_options_menu.menu.add_radiobutton(label="Show: Moved files", variable=app.history_mode_var, value="Moved")
    history_options_menu.menu.add_radiobutton(label="Show: Duplicate files", variable=app.history_mode_var, value="Duplicate")
    Tip(history_options_menu, "List of files moved to the source folder", delay=250, pady=25, origin="widget")
    # Listbox
    app.history_listbox = tk.Listbox(list_frame, width=1, height=1)
    app.history_listbox.pack(fill="both", expand=True)
    app.history_listbox.bind("<Button-3>", app.show_history_context_menu)
    # Context menu
    app.history_menu = tk.Menu(app.history_listbox, tearoff=0)
    app.history_menu.add_command(label="Open", command=app.open_selected_file)
    app.history_menu.add_command(label="Show in File Explorer", command=app.show_selected_in_explorer)
    app.history_menu.add_separator()
    app.history_menu.add_command(label="Delete", command=app.delete_selected_file)


#endregion
#region - Message row


def create_message_row(app: 'FolderFunnelApp'):
    # Message row
    message_frame = tk.Frame(app.root)
    message_frame.pack(side="bottom", fill="x")
    ttk.Separator(message_frame, orient="horizontal").pack(fill="x")
    # Status label
    status_label = tk.Label(message_frame, textvariable=app.status_label_var, relief="groove", width=15, anchor="w")
    status_label.pack(side="left")
    Tip(status_label, "Current status of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Foldercount label
    Foldercount_label = tk.Label(message_frame, textvariable=app.foldercount_var, relief="groove", width=15, anchor="w")
    Foldercount_label.pack(side="left")
    Tip(Foldercount_label, "Number of folders in the source folder", delay=250, pady=-25, origin="widget")
    # Filecount label
    filecount_label = tk.Label(message_frame, textvariable=app.filecount_var, relief="groove", width=15, anchor="w")
    filecount_label.pack(side="left")
    Tip(filecount_label, "Number of files in the source folder", delay=250, pady=-25, origin="widget")
    # Movecount label
    movecount_label = tk.Label(message_frame, textvariable=app.movecount_var, relief="groove", width=15, anchor="w")
    movecount_label.pack(side="left")
    Tip(movecount_label, "Number of files moved to the source folder", delay=250, pady=-25, origin="widget")
    # Duplicate count label
    dupecount_label = tk.Label(message_frame, textvariable=app.duplicate_count_var, relief="groove", width=15, anchor="w")
    dupecount_label.pack(side="left")
    Tip(dupecount_label, "Number of duplicate files found", delay=250, pady=-25, origin="widget")
    # Running indicator
    app.running_indicator = ttk.Progressbar(message_frame, maximum=20, mode="determinate")
    app.running_indicator.pack(side="left", fill="x", expand=True)
    Tip(app.running_indicator, "Running indicator of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Queue Timer
    app.queue_progressbar = ttk.Progressbar(message_frame, mode="determinate")
    app.queue_progressbar.pack(side="left", fill="x", expand=True)
    Tip(app.queue_progressbar, "Progress of the move queue timer", delay=250, pady=-25, origin="widget")
