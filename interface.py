#region - Imports


# Standard GUI
import tkinter as tk
from tkinter import ttk, scrolledtext

# Third-party
from TkToolTip.TkToolTip import TkToolTip as Tip

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Entry point


def create_interface(app: 'Main'):
    _create_menubar(app)
    _create_control_row(app)
    _create_main_frame(app)
    _create_message_row(app)


#endregion
#region - Menubar


def _create_menubar(app: 'Main'):
    # Create menubar
    menubar = tk.Menu(app.root)
    app.root.config(menu=menubar)
    # Menus
    _create_file_menu(app, menubar)
    _create_edit_menu(app, menubar)
    _create_view_menu(app, menubar)
    _create_options_menu(app, menubar)
    _create_help_menu(app, menubar)


def _create_file_menu(app: 'Main', menubar: tk.Menu):
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Select Source Path...", command=app.select_working_dir)
    file_menu.add_separator()
    file_menu.add_command(label="Open: Source", command=app.open_folder)
    file_menu.add_command(label="Open: Funnel", command=lambda: app.open_folder(app.watch_path))
    file_menu.add_command(label="Open: Duplicates", command=lambda: app.open_folder(app.duplicate_storage_path))
    file_menu.add_separator()
    file_menu.add_command(label="Reset App Settings", command=app.reset_settings)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=app.on_closing)


def _create_edit_menu(app: 'Main', menubar: tk.Menu):
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Sync Source-and-Funnel Folders", command=app.sync_watch_folders)
    edit_menu.add_command(label="Process Move Queue", command=app.process_move_queue)
    edit_menu.add_separator()
    edit_menu.add_command(label="Find Duplicate Files...", command=app.show_duplicate_scanner)
    edit_menu.add_separator()
    edit_menu.add_command(label="Clear: Log", command=app.clear_log)
    edit_menu.add_command(label="Clear: History", command=app.clear_history)


def _create_view_menu(app: 'Main', menubar: tk.Menu):
    view_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="View", menu=view_menu)
    view_menu.add_radiobutton(label="History View: Moved", variable=app.history_mode_var, value="Moved", command=app.toggle_history_mode)
    view_menu.add_radiobutton(label="History View: Duplicate", variable=app.history_mode_var, value="Duplicate", command=app.toggle_history_mode)
    view_menu.add_separator()
    view_menu.add_command(label="Toggle: Text Wrap", command=app.toggle_text_wrap)


def _create_options_menu(app: 'Main', menubar: tk.Menu):
    options_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Options", menu=options_menu)
    # File rules submenu
    file_rules_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="File Rules", menu=file_rules_menu)
    file_rules_menu.add_checkbutton(label="Ignore Temp Files", variable=app.ignore_temp_files_var)
    file_rules_menu.add_checkbutton(label="Ignore Temp Firefox Files", variable=app.ignore_firefox_temp_files_var)
    file_rules_menu.add_separator()
    file_rules_menu.add_checkbutton(label='Auto Extract Zip Files "*\\"', variable=app.auto_extract_zip_var)  # Extract to new folder ("*\")
    file_rules_menu.add_checkbutton(label="Auto Delete Zip Files After Extraction", variable=app.auto_delete_zip_var)
    file_rules_menu.add_separator()
    file_rules_menu.add_checkbutton(label="Overwrite on File Conflict", variable=app.overwrite_on_conflict_var)
    options_menu.add_separator()
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
    # Dupe Handle Mode
    dupe_menu.add_command(label="Duplicate Handling Mode", state="disabled")
    dupe_menu.add_radiobutton(label="Move", variable=app.dupe_handle_mode_var, value="Move")
    dupe_menu.add_radiobutton(label="Delete", variable=app.dupe_handle_mode_var, value="Delete")
    dupe_menu.add_separator()
    # Dupe Filter Mode
    dupe_menu.add_command(label="Duplicate Name Matching Mode", state="disabled")
    dupe_menu.add_radiobutton(label="Flexible", variable=app.dupe_filter_mode_var, value="Flexible")
    dupe_menu.add_radiobutton(label="Strict", variable=app.dupe_filter_mode_var, value="Strict")
    dupe_menu.add_separator()
    # Dupe Check Mode
    dupe_menu.add_command(label="Duplicate Checking Mode", state="disabled")
    dupe_menu.add_radiobutton(label="Similar", variable=app.dupe_check_mode_var, value="Similar")
    dupe_menu.add_radiobutton(label="Single", variable=app.dupe_check_mode_var, value="Single")
    dupe_menu.add_separator()
    # Max Files
    dupe_menu.add_command(label="Duplicate Check: Max Files", state="disabled")
    dupe_menu.add_radiobutton(label="10", variable=app.dupe_max_files_var, value=10)
    dupe_menu.add_radiobutton(label="25", variable=app.dupe_max_files_var, value=25)
    dupe_menu.add_radiobutton(label="50", variable=app.dupe_max_files_var, value=50)
    dupe_menu.add_radiobutton(label="100", variable=app.dupe_max_files_var, value=100)
    dupe_menu.add_radiobutton(label="1000", variable=app.dupe_max_files_var, value=1000)
    dupe_menu.add_radiobutton(label="10000", variable=app.dupe_max_files_var, value=10000)


def _create_help_menu(app: 'Main', menubar: tk.Menu):
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Show Help", command=app.open_help_window)
    help_menu.add_command(label="Show Stats", command=app.open_stats_popup)


#endregion
#region - Control row


def _create_control_row(app: 'Main'):
    # Create control row
    control_frame = tk.Frame(app.root)
    control_frame.pack(side="top", fill="x")
    # Separator
    ttk.Separator(control_frame, orient="horizontal").pack(side="bottom", fill="x")
    # Widgets
    _create_dir_entry(app, control_frame)
    _create_buttons(app, control_frame)


def _create_dir_entry(app: 'Main', control_frame: tk.Frame):
    tip_text = "Select the folder to funnel files into"
    dir_selection_frame = tk.Frame(control_frame)
    dir_selection_frame.pack(side="left", fill="x", expand=True)
    #Label
    dir_label = tk.Label(dir_selection_frame, text="Source Folder:")
    dir_label.pack(side="left")
    Tip(dir_label, tip_text, delay=250, pady=25, origin="widget")
    # Entry
    app.dir_entry = ttk.Entry(dir_selection_frame, textvariable=app.working_dir_var)
    app.dir_entry.pack(side="left", fill="x", expand=True)
    app.dir_entry_tooltip = Tip(app.dir_entry, tip_text, delay=250, pady=25, origin="widget")
    # Browse
    app.browse_button = ttk.Button(dir_selection_frame, text="Browse...", command=app.select_working_dir)
    app.browse_button.pack(side="left")
    Tip(app.browse_button, tip_text, delay=250, pady=25, origin="widget")
    # Open
    open_button = ttk.Button(dir_selection_frame, text="Open", command=app.open_folder)
    open_button.pack(side="left")
    Tip(open_button, "Open the selected folder in File Explorer", delay=250, pady=25, origin="widget")


def _create_buttons(app: 'Main', control_frame: tk.Frame):
    app.start_button = ttk.Button(control_frame, text="Start", command=app.start_folder_watcher)
    app.start_button.pack(side="left")
    Tip(app.start_button, "Start the Folder-Funnel process", delay=250, pady=25, origin="widget")
    # Stop
    app.stop_button = ttk.Button(control_frame, text="Stop", state="disabled", command=app.stop_folder_watcher)
    app.stop_button.pack(side="left")
    Tip(app.stop_button, "Stop the Folder-Funnel process and remove temp folders", delay=250, pady=25, origin="widget")


#endregion
#region - Main frame


def _create_main_frame(app: 'Main'):
    # Create main frame
    main_frame = tk.Frame(app.root)
    main_frame.pack(fill="both", expand=True)
    # paned window
    main_pane = tk.PanedWindow(main_frame, orient="horizontal", sashwidth=6, bg="#d0d0d0", bd=0)
    main_pane.pack(fill="both", expand=True)
    # Widgets
    _create_text_log(app, main_pane)
    _create_history_list(app, main_pane)


def _create_text_log(app: 'Main', main_pane: tk.PanedWindow):
    # Frame
    text_frame = tk.Frame(main_pane)
    main_pane.add(text_frame, stretch="always")
    main_pane.paneconfigure(text_frame, minsize=200, width=400)
    # Label/Menu
    textlog_menubutton = ttk.Menubutton(text_frame, text="Log")
    textlog_menubutton.pack(fill="x")
    textlog_menu = tk.Menu(textlog_menubutton, tearoff=0)
    textlog_menubutton.config(menu=textlog_menu)
    textlog_menu.add_command(label="Clear Log", command=app.clear_log)
    textlog_menu.add_separator()
    textlog_menu.add_checkbutton(label="Wrap Text", variable=app.text_log_wrap_var, command=app.toggle_text_wrap)
    Tip(textlog_menubutton, "Log of events and actions", delay=250, pady=25, origin="widget")
    # Text
    app.text_log = scrolledtext.ScrolledText(text_frame, wrap="word", state="disable", width=1, height=1)
    app.text_log.pack(fill="both", expand=True)
    app.log("Welcome to Folder-Funnel - Please see the help menu for more information.")


def _create_history_list(app: 'Main', main_pane: tk.PanedWindow):
    # Frame
    list_frame = tk.Frame(main_pane)
    main_pane.add(list_frame, stretch="never")
    main_pane.paneconfigure(list_frame, minsize=200, width=200)
    # Label/Menu
    app.history_menubutton = ttk.Menubutton(list_frame, text="History - " + app.history_mode_var.get())
    app.history_menubutton.pack(fill="x")
    history_menu = tk.Menu(app.history_menubutton, tearoff=0)
    app.history_menubutton.config(menu=history_menu)
    history_menu.add_command(label="Clear History", command=app.clear_history)
    history_menu.add_separator()
    history_menu.add_radiobutton(label="History View: Moved", variable=app.history_mode_var, value="Moved", command=app.toggle_history_mode)
    history_menu.add_radiobutton(label="History View: Duplicate", variable=app.history_mode_var, value="Duplicate", command=app.toggle_history_mode)
    Tip(app.history_menubutton, "List of files moved to the source folder", delay=250, pady=25, origin="widget")
    # Listbox
    app.history_listbox = tk.Listbox(list_frame, width=1, height=1)
    app.history_listbox.pack(fill="both", expand=True)
    app.history_listbox.bind("<Button-3>", app.show_history_context_menu)
    # Context menu
    create_history_context_menu(app)


def create_history_context_menu(app: 'Main'):
    app.history_menu = tk.Menu(app.history_listbox, tearoff=0)
    if app.history_mode_var.get() == "Moved":
        app.history_menu.add_command(label="Open", command=app.open_selected_file)
        app.history_menu.add_command(label="Show in File Explorer", command=app.show_selected_in_explorer)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Delete", command=app.delete_selected_file)
    elif app.history_mode_var.get() == "Duplicate":
        app.history_menu.add_command(label="Open: Duplicate", command=app.open_selected_duplicate_file)
        app.history_menu.add_command(label="Show Duplicate in Explorer", command=app.show_selected_duplicate_in_explorer)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Open: Source", command=app.open_selected_source_file)
        app.history_menu.add_command(label="Show Source in Explorer", command=app.show_selected_source_in_explorer)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Delete: Duplicate", command=app.delete_selected_duplicate_file)


#endregion
#region - Message row


def _create_message_row(app: 'Main'):
    # Message row
    message_frame = tk.Frame(app.root)
    message_frame.pack(side="bottom", fill="x")
    ttk.Separator(message_frame, orient="horizontal").pack(fill="x")
    # Status label
    status_label = tk.Label(message_frame, textvariable=app.status_label_var, relief="groove", width=15, anchor="w")
    status_label.pack(side="left")
    Tip(status_label, "Current status of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Foldercount label
    foldercount_label = tk.Label(message_frame, textvariable=app.foldercount_var, relief="groove", width=15, anchor="w")
    foldercount_label.pack(side="left")
    Tip(foldercount_label, "Number of folders in the source folder", delay=250, pady=-25, origin="widget")
    # Filecount label
    filecount_label = tk.Label(message_frame, textvariable=app.filecount_var, relief="groove", width=15, anchor="w")
    filecount_label.pack(side="left")
    Tip(filecount_label, "Number of files in the source folder", delay=250, pady=-25, origin="widget")
    # Movecount label
    movecount_label = tk.Label(message_frame, textvariable=app.movecount_var, relief="groove", width=15, anchor="w")
    movecount_label.pack(side="left")
    Tip(movecount_label, "Number of files moved to the source folder", delay=250, pady=-25, origin="widget")
    # Duplicate count label
    dupecount_label = tk.Label(message_frame, textvariable=app.dupecount_var, relief="groove", width=15, anchor="w")
    dupecount_label.pack(side="left")
    Tip(dupecount_label, "Number of duplicate files found", delay=250, pady=-25, origin="widget")
    # Queuecount label
    queuecount_label = tk.Label(message_frame, textvariable=app.queuecount_var, relief="groove", width=15, anchor="w")
    queuecount_label.pack(side="left")
    Tip(queuecount_label, "Number of files in the move queue", delay=250, pady=-25, origin="widget")
    # Running indicator
    app.running_indicator = ttk.Progressbar(message_frame, maximum=20, mode="determinate")
    app.running_indicator.pack(side="left", fill="x", expand=True)
    Tip(app.running_indicator, "Running indicator of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Queue Timer
    app.queue_progressbar = ttk.Progressbar(message_frame, mode="determinate")
    app.queue_progressbar.pack(side="left", fill="x", expand=True)
    Tip(app.queue_progressbar, "Progress of the move queue timer", delay=250, pady=-25, origin="widget")
