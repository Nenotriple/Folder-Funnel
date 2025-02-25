#region - Imports


# Standard
import tkinter as tk
from tkinter import ttk, scrolledtext

# Third-party
from TkToolTip.TkToolTip import TkToolTip as Tip


#endregion
#region - Entry point


def create_interface(self):
    create_menubar(self)
    create_control_row(self)
    create_main_frame(self)
    create_message_row(self)


#endregion
#region - Menubar


def create_menubar(self):
    # Create menubar
    menubar = tk.Menu(self.root)
    self.root.config(menu=menubar)
    # Menus
    _create_file_menu(self, menubar)
    _create_edit_menu(self, menubar)
    _create_options_menu(self, menubar)
    menubar.add_command(label="Help", command=self.open_help_window)


def _create_file_menu(self, menubar):
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Select source path...", command=self.select_working_dir)
    file_menu.add_command(label="Open selected path", command=self.open_folder)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=self.on_closing)


def _create_edit_menu(self, menubar):
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Sync Folders", command=self.sync_watch_folders)
    edit_menu.add_separator()
    edit_menu.add_command(label="Clear log", command=self.clear_log)
    edit_menu.add_command(label="Clear history", command=self.clear_history)


def _create_options_menu(self, menubar):
    options_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Options", menu=options_menu)
    # Queue Timer submenu
    queue_timer_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Queue Timer", menu=queue_timer_menu)
    queue_timer_menu.add_command(label="Queue Timer Length", state="disabled")
    queue_timer_menu.add_radiobutton(label="5 seconds", variable=self.move_queue_timer_length_var, value=5000)
    queue_timer_menu.add_radiobutton(label="15 seconds", variable=self.move_queue_timer_length_var, value=15000)
    queue_timer_menu.add_radiobutton(label="30 seconds", variable=self.move_queue_timer_length_var, value=30000)
    queue_timer_menu.add_radiobutton(label="1 minute", variable=self.move_queue_timer_length_var, value=60000)
    queue_timer_menu.add_radiobutton(label="5 minutes", variable=self.move_queue_timer_length_var, value=300000)
    # Duplicate handling submenu
    duplicate_handling_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Duplicate Handling", menu=duplicate_handling_menu)
    duplicate_handling_menu.add_command(label="Duplicate Checking Mode", state="disabled")
    duplicate_handling_menu.add_radiobutton(label="Rigorous", variable=self.rigorous_duplicate_check_var, value=True)
    duplicate_handling_menu.add_radiobutton(label="Simple", variable=self.rigorous_duplicate_check_var, value=False)
    duplicate_handling_menu.add_separator()
    # Rigorous Check
    duplicate_handling_menu.add_command(label="Rigorous Check: Max Files", state="disabled")
    duplicate_handling_menu.add_radiobutton(label="10", variable=self.rigorous_dupe_max_files_var, value=10)
    duplicate_handling_menu.add_radiobutton(label="25", variable=self.rigorous_dupe_max_files_var, value=25)
    duplicate_handling_menu.add_radiobutton(label="50", variable=self.rigorous_dupe_max_files_var, value=50)
    duplicate_handling_menu.add_radiobutton(label="100", variable=self.rigorous_dupe_max_files_var, value=100)
    duplicate_handling_menu.add_radiobutton(label="1000", variable=self.rigorous_dupe_max_files_var, value=1000)
    duplicate_handling_menu.add_separator()
    # Dupe Filter Mode
    duplicate_handling_menu.add_command(label="Duplicate Matching Mode", state="disabled")
    duplicate_handling_menu.add_radiobutton(label="Strict", variable=self.dupe_filter_mode_var, value="Strict")
    duplicate_handling_menu.add_radiobutton(label="Flexible", variable=self.dupe_filter_mode_var, value="Flexible")
    # Text Log submenu
    text_log_menu = tk.Menu(options_menu, tearoff=0)
    options_menu.add_cascade(label="Text Log", menu=text_log_menu)
    text_log_menu.add_checkbutton(label="Wrap Text", variable=self.text_log_wrap_var, command=self.toggle_text_wrap)


#endregion
#region - Control row


def create_control_row(self):
    # Create control row
    control_frame = tk.Frame(self.root)
    control_frame.pack(side="top", fill="x")
    # Separator
    ttk.Separator(control_frame, orient="horizontal").pack(side="bottom", fill="x")
    # Widgets
    _create_dir_entry(self, control_frame)
    _create_buttons(self, control_frame)


def _create_dir_entry(self, control_frame):
    dir_selection_frame = tk.Frame(control_frame)
    dir_selection_frame.pack(side="left", fill="x", expand=True)
    #Label
    dir_label = tk.Label(dir_selection_frame, text="Watch Folder:")
    dir_label.pack(side="left")
    Tip(dir_label, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Entry
    self.dir_entry = ttk.Entry(dir_selection_frame, textvariable=self.working_dir_var)
    self.dir_entry.pack(side="left", fill="x", expand=True)
    self.dir_entry_tooltip = Tip(self.dir_entry, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Browse
    browse_button = ttk.Button(dir_selection_frame, text="Browse...", command=self.select_working_dir)
    browse_button.pack(side="left")
    Tip(browse_button, "Select the folder to watch for new files", delay=250, pady=25, origin="widget")
    # Open
    open_button = ttk.Button(dir_selection_frame, text="Open", command=self.open_folder)
    open_button.pack(side="left")
    Tip(open_button, "Open the selected folder in File Explorer", delay=250, pady=25, origin="widget")


def _create_buttons(self, control_frame):
    self.start_button = ttk.Button(control_frame, text="Start", command=self.start_folder_watcher)
    self.start_button.pack(side="left")
    Tip(self.start_button, "Begin watching the selected folder", delay=250, pady=25, origin="widget")
    # Stop
    self.stop_button = ttk.Button(control_frame, text="Stop", state="disabled", command=self.stop_folder_watcher)
    self.stop_button.pack(side="left")
    Tip(self.stop_button, "Stop watching the folder and remove the duplicate", delay=250, pady=25, origin="widget")


#endregion
#region - Main frame


def create_main_frame(self):
    # Create main frame
    main_frame = tk.Frame(self.root)
    main_frame.pack(fill="both", expand=True)
    # paned window
    main_pane = tk.PanedWindow(main_frame, orient="horizontal", sashwidth=6, bg="#d0d0d0", bd=0)
    main_pane.pack(fill="both", expand=True)
    # Widgets
    _create_text_log(self, main_pane)
    _create_history_list(self, main_pane)


def _create_text_log(self, main_pane):
    # Frame
    text_frame = tk.Frame(main_pane)
    main_pane.add(text_frame, stretch="always")
    main_pane.paneconfigure(text_frame, minsize=200, width=400)
    # Label
    log_label = tk.Label(text_frame, text="Log")
    log_label.pack(fill="x")
    Tip(log_label, "Log of events and actions", delay=250, pady=25, origin="widget")
    # Text
    self.text_log = scrolledtext.ScrolledText(text_frame, wrap="word", state="disable", width=1, height=1)
    self.text_log.pack(fill="both", expand=True)


def _create_history_list(self, main_pane):
    # Frame
    list_frame = tk.Frame(main_pane)
    main_pane.add(list_frame, stretch="never")
    main_pane.paneconfigure(list_frame, minsize=200, width=200)
    # Label
    history_label = tk.Label(list_frame, text="History")
    history_label.pack(fill="x")
    Tip(history_label, "List of files moved to the source folder", delay=250, pady=25, origin="widget")
    # Listbox
    self.history_listbox = tk.Listbox(list_frame, width=1, height=1)
    self.history_listbox.pack(fill="both", expand=True)
    self.history_listbox.bind("<Button-3>", self.show_context_menu)
    # Context menu
    self.list_context_menu = tk.Menu(self.history_listbox, tearoff=0)
    self.list_context_menu.add_command(label="Open", command=self.open_selected_file)
    self.list_context_menu.add_command(label="Show in File Explorer", command=self.show_selected_in_explorer)
    self.list_context_menu.add_separator()
    self.list_context_menu.add_command(label="Delete", command=self.delete_selected_file)


#endregion
#region - Message row


def create_message_row(self):
    # Message row
    message_frame = tk.Frame(self.root)
    message_frame.pack(side="bottom", fill="x")
    ttk.Separator(message_frame, orient="horizontal").pack(fill="x")
    # Status label
    status_label = tk.Label(message_frame, textvariable=self.status_label_var, relief="groove", width=15, anchor="w")
    status_label.pack(side="left")
    Tip(status_label, "Current status of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Foldercount label
    Foldercount_label = tk.Label(message_frame, textvariable=self.foldercount_var, relief="groove", width=15, anchor="w")
    Foldercount_label.pack(side="left")
    Tip(Foldercount_label, "Number of folders in the source folder", delay=250, pady=-25, origin="widget")
    # Filecount label
    filecount_label = tk.Label(message_frame, textvariable=self.filecount_var, relief="groove", width=15, anchor="w")
    filecount_label.pack(side="left")
    Tip(filecount_label, "Number of files in the source folder", delay=250, pady=-25, origin="widget")
    # Movecount label
    movecount_label = tk.Label(message_frame, textvariable=self.movecount_var, relief="groove", width=15, anchor="w")
    movecount_label.pack(side="left")
    Tip(movecount_label, "Number of files moved to the source folder", delay=250, pady=-25, origin="widget")
    # Progress bar
    self.progressbar = ttk.Progressbar(message_frame, maximum=20, mode="determinate")
    self.progressbar.pack(side="left", fill="x", expand=True)
    Tip(self.progressbar, "Running indicator of the Folder-Funnel process", delay=250, pady=-25, origin="widget")
    # Queue Timer
    self.queue_progressbar = ttk.Progressbar(message_frame, mode="determinate")
    self.queue_progressbar.pack(side="left", fill="x", expand=True)
    Tip(self.queue_progressbar, "Progress of the move queue timer", delay=250, pady=-25, origin="widget")
