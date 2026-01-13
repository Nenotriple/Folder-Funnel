#region - Imports

# Standard GUI
import tkinter as tk
from tkinter import ttk, scrolledtext

# Third-party
import nenotk as ntk
from nenotk import ToolTip as Tip, PopUpZoom

# Custom
from . import listbox_logic

# Set Tooltip defaults
Tip.SHOW_DELAY = 250
Tip.ORIGIN = "widget"
Tip.ANIMATION = "slide"

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Entry point


def create_interface(app: 'Main'):
    _create_menubar(app)
    _create_control_row(app)
    # Pack message row BEFORE main frame so it reserves bottom space
    # (main_frame uses expand=True which would otherwise push it out of view)
    _create_message_row(app)
    _create_main_frame(app)


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
    file_menu.add_command(label="Open: Funnel", command=lambda: app.open_folder(app.funnel_dir))
    file_menu.add_command(label="Open: Duplicates", command=lambda: app.open_folder(app.duplicate_storage_path))
    file_menu.add_separator()
    file_menu.add_command(label="Reset App Settings", command=app.reset_settings)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=app.exit_application)
    app.file_menu = file_menu


def _create_edit_menu(app: 'Main', menubar: tk.Menu):
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Sync Source-and-Funnel Folders", command=app.sync_funnel_folders)
    edit_menu.add_command(label="Process Move Queue", command=app.process_move_queue)
    edit_menu.add_separator()
    edit_menu.add_command(label="Find Duplicate Files...", command=app.show_duplicate_scanner)
    edit_menu.add_separator()
    edit_menu.add_command(label="Clear: Log", command=app.clear_log)
    edit_menu.add_command(label="Clear: History", command=app.clear_history)


def _create_view_menu(app: 'Main', menubar: tk.Menu):
    view_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="View", menu=view_menu)
    # Layout options
    layout_menu = tk.Menu(view_menu, tearoff=0)
    view_menu.add_cascade(label="Layout", menu=layout_menu)
    layout_menu.add_command(label="Layout Orientation", state="disabled")
    layout_menu.add_radiobutton(
        label="Side-by-side (Log | History)",
        variable=app.main_pane_orient_var,
        value="horizontal",
        command=lambda: app.apply_main_pane_layout(user_action=True),
    )
    layout_menu.add_radiobutton(
        label="Vertical (Top / Bottom)",
        variable=app.main_pane_orient_var,
        value="vertical",
        command=lambda: app.apply_main_pane_layout(user_action=True),
    )
    layout_menu.add_separator()
    layout_menu.add_command(label="Layout Order", state="disabled")
    layout_menu.add_radiobutton(
        label="Log First (Left/Top)",
        variable=app.main_pane_order_var,
        value="log_first",
        command=lambda: app.apply_main_pane_layout(user_action=True),
    )
    layout_menu.add_radiobutton(
        label="History First (Left/Top)",
        variable=app.main_pane_order_var,
        value="history_first",
        command=lambda: app.apply_main_pane_layout(user_action=True),
    )
    view_menu.add_separator()
    # History Options
    view_menu.add_checkbutton(label="History: Image Preview on Hover", variable=app.history_image_preview_var, command=app.toggle_history_preview)
    view_menu.add_separator()
    view_menu.add_radiobutton(label="History View: All", variable=app.history_mode_var, value="All", command=app.toggle_history_mode)
    view_menu.add_radiobutton(label="History View: Moved", variable=app.history_mode_var, value="Moved", command=app.toggle_history_mode)
    view_menu.add_radiobutton(label="History View: Duplicate", variable=app.history_mode_var, value="Duplicate", command=app.toggle_history_mode)
    view_menu.add_separator()
    # Log options
    view_menu.add_checkbutton(label="Show Log Prefix", variable=app.log_prefix_filter_var)
    view_menu.add_checkbutton(label="Wrap Text", variable=app.text_log_wrap_var, command=app.toggle_text_wrap)
    log_verbosity_menu = tk.Menu(view_menu, tearoff=0)
    view_menu.add_cascade(label="Log Verbosity", menu=log_verbosity_menu)
    log_verbosity_menu.add_radiobutton(label="(1) Essential", variable=app.log_verbosity_var, value=1)
    log_verbosity_menu.add_radiobutton(label="(2) Extended", variable=app.log_verbosity_var, value=2)
    log_verbosity_menu.add_radiobutton(label="(3) Detailed", variable=app.log_verbosity_var, value=3)
    log_verbosity_menu.add_radiobutton(label="(4) Debug", variable=app.log_verbosity_var, value=4)


def _create_options_menu(app: 'Main', menubar: tk.Menu):
    options_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Options", menu=options_menu)
    # System tray option
    options_menu.add_checkbutton(label="Minimize to Tray on Close", variable=app.minimize_to_tray_var)
    options_menu.add_checkbutton(label="Desktop Notifications", variable=app.notifications_enabled_var)
    options_menu.add_separator()
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
    queue_menu.add_radiobutton(label="1 second", variable=app.move_queue_length_var, value=1000)
    queue_menu.add_radiobutton(label="3 seconds", variable=app.move_queue_length_var, value=3000)
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
    dupe_menu.add_radiobutton(label="75", variable=app.dupe_max_files_var, value=75)
    dupe_menu.add_radiobutton(label="100", variable=app.dupe_max_files_var, value=100)
    dupe_menu.add_radiobutton(label="250", variable=app.dupe_max_files_var, value=250)
    dupe_menu.add_radiobutton(label="500", variable=app.dupe_max_files_var, value=500)
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


def _create_dir_entry(app: 'Main', control_frame: tk.Frame):
    tip_text = "Select the folder to funnel files into"
    dir_selection_frame = tk.Frame(control_frame)
    dir_selection_frame.pack(side="left", fill="x", expand=True)
    #Label
    dir_label = tk.Label(dir_selection_frame, text="Source Folder:")
    dir_label.pack(side="left")
    Tip(widget=dir_label, text=tip_text, widget_anchor="sw", pady=2)
    # Entry
    app.dir_entry = ttk.Entry(dir_selection_frame, textvariable=app.source_dir_var)
    app.dir_entry.pack(side="left", fill="x", expand=True)
    app.dir_entry_tooltip = Tip(widget=app.dir_entry, text=tip_text, widget_anchor="sw", pady=2)
    ntk.bind_helpers(app.dir_entry)
    # Browse
    app.browse_button = ttk.Button(dir_selection_frame, text="Browse...", command=app.select_working_dir)
    app.browse_button.pack(side="left")
    Tip(widget=app.browse_button, text=tip_text, widget_anchor="sw", pady=2)
    # Open
    open_button = ttk.Button(dir_selection_frame, text="Open", command=lambda: app.open_folder(app.source_dir_var.get()))
    open_button.pack(side="left")
    Tip(widget=open_button, text="Open the selected folder in File Explorer", widget_anchor="sw", pady=2)
    # Start/Stop
    app.start_stop_button = ttk.Button(control_frame, text="Start", command=app.start_folder_watcher)
    app.start_stop_button.pack(side="left")
    Tip(widget=app.start_stop_button, text="Start/Stop the Folder-Funnel process", widget_anchor="sw", pady=2)


#endregion
#region - Main frame


def _create_main_frame(app: 'Main'):
    # Create main frame
    main_frame = tk.Frame(app.root)
    main_frame.pack(fill="both", expand=True)
    # paned window
    main_pane = tk.PanedWindow(main_frame, orient="horizontal", sashwidth=6, bg="#d0d0d0", bd=0)
    main_pane.pack(fill="both", expand=True)
    app.main_pane = main_pane
    # Widgets
    _create_text_log(app, main_pane)
    _create_history_list(app, main_pane)

    # Capture the initial/default sash position once geometry is computed.
    try:
        app.root.after(0, lambda: _capture_main_pane_default_sash(app))
    except Exception:
        pass


def _capture_main_pane_default_sash(app: 'Main') -> None:
    pane = getattr(app, "main_pane", None)
    if not pane:
        return
    # Only capture once per app session
    if getattr(app, "main_pane_default_sash_x", None) is not None:
        return
    try:
        pane.update_idletasks()
        x, _y = pane.sash_coord(0)
        app.main_pane_default_sash_x = int(x)
    except Exception:
        return


def _create_text_log(app: 'Main', main_pane: tk.PanedWindow):
    # Frame
    text_frame = tk.Frame(main_pane)
    app.log_pane_frame = text_frame
    main_pane.add(text_frame, stretch="always")
    main_pane.paneconfigure(text_frame, minsize=200, width=400)
    text_frame.grid_rowconfigure(2, weight=1)
    text_frame.grid_columnconfigure(0, weight=1)
    # Label/Menu
    textlog_menubutton = ttk.Menubutton(text_frame, text="Log")
    textlog_menubutton.grid(row=0, column=0, sticky="ew")
    textlog_menu = tk.Menu(textlog_menubutton, tearoff=0)
    textlog_menubutton.config(menu=textlog_menu)
    textlog_menu.add_command(label="Clear Log", command=app.clear_log)
    textlog_menu.add_separator()
    textlog_menu.add_checkbutton(label="Show Log Prefix", variable=app.log_prefix_filter_var)
    textlog_menu.add_checkbutton(label="Wrap Text", variable=app.text_log_wrap_var, command=app.toggle_text_wrap)
    # Log verbosity submenu mirrors View menu
    log_verbosity_menu = tk.Menu(textlog_menu, tearoff=0)
    textlog_menu.add_cascade(label="Log Verbosity", menu=log_verbosity_menu)
    log_verbosity_menu.add_radiobutton(label="(1) Essential", variable=app.log_verbosity_var, value=1)
    log_verbosity_menu.add_radiobutton(label="(2) Extended", variable=app.log_verbosity_var, value=2)
    log_verbosity_menu.add_radiobutton(label="(3) Detailed", variable=app.log_verbosity_var, value=3)
    log_verbosity_menu.add_radiobutton(label="(4) Debug", variable=app.log_verbosity_var, value=4)
    Tip(widget=textlog_menubutton, text="Log of events and actions", widget_anchor="sw", pady=2)
    # Text log with dynamic horizontal scrollbar
    app.text_log_hscroll = tk.Scrollbar(text_frame, orient="horizontal")
    app.text_log = scrolledtext.ScrolledText(text_frame, wrap="word" if app.text_log_wrap_var.get() else "none", state="disabled", width=1, height=1, padx=4, pady=4, font=("Consolas", 10), xscrollcommand=app.text_log_hscroll.set if not app.text_log_wrap_var.get() else None)
    app.text_log.grid(row=2, column=0, sticky="nsew")
    # Create horizontal scrollbar only if wrap is disabled
    if not app.text_log_wrap_var.get():
        app.text_log_hscroll.config(command=app.text_log.xview)
        app.text_log_hscroll.grid(row=3, column=0, sticky="ew")
    else:
        app.text_log_hscroll.grid_remove()
    app.log("Welcome to Folder-Funnel - Please see the Help menu for more information.", verbose=1)
    # Search
    app.text_search = ntk.FindReplaceEntry(text_frame, app.text_log, show_replace=False)
    app.text_search.grid(row=1, column=0, sticky="ew")
    app.text_search.grid_remove()
    # Bind keyboard shortcuts from the text widget to the find/replace widget
    app.text_log.bind("<Control-f>", app.text_search.show_widget)
    app.text_log.bind("<KeyRelease>", app.text_search.perform_search)
    app.text_log.bind("<Escape>", app.text_search.hide_widget)


def _create_history_list(app: 'Main', main_pane: tk.PanedWindow):
    # Frame
    list_frame = tk.Frame(main_pane)
    app.history_pane_frame = list_frame
    main_pane.add(list_frame, stretch="never")
    main_pane.paneconfigure(list_frame, minsize=200, width=200)
    # Label/Menu
    app.history_menubutton = ttk.Menubutton(list_frame, text="History - " + app.history_mode_var.get())
    app.history_menubutton.pack(fill="x")
    history_menu = tk.Menu(app.history_menubutton, tearoff=0)
    app.history_menubutton.config(menu=history_menu)
    history_menu.add_command(label="Clear History", command=app.clear_history)
    history_menu.add_separator()
    history_menu.add_checkbutton(label="History: Image Preview on Hover", variable=app.history_image_preview_var, command=app.toggle_history_preview)
    history_menu.add_radiobutton(label="History View: All", variable=app.history_mode_var, value="All", command=app.toggle_history_mode)
    history_menu.add_radiobutton(label="History View: Moved", variable=app.history_mode_var, value="Moved", command=app.toggle_history_mode)
    history_menu.add_radiobutton(label="History View: Duplicate", variable=app.history_mode_var, value="Duplicate", command=app.toggle_history_mode)
    Tip(widget=app.history_menubutton, text="List of processed files", widget_anchor="sw", pady=2)
    # Treeview (replaces Listbox for richer history)
    tree_frame = tk.Frame(list_frame)
    tree_frame.pack(fill="both", expand=True)
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    columns = ("time", "type", "name", "rel", "action")
    app.history_listbox = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    app.history_listbox.grid(row=0, column=0, sticky="nsew")

    vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=app.history_listbox.yview)
    vscroll.grid(row=0, column=1, sticky="ns")
    hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=app.history_listbox.xview)
    hscroll.grid(row=1, column=0, sticky="ew")
    app.history_listbox.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

    # Headings: clicking sorts by column (text + arrows updated in listbox_logic)
    app.history_listbox.heading("time", text="Time", command=lambda c="time": app.sort_history_by_column(c))
    app.history_listbox.heading("type", text="Type", command=lambda c="type": app.sort_history_by_column(c))
    app.history_listbox.heading("name", text="Name", command=lambda c="name": app.sort_history_by_column(c))
    app.history_listbox.heading("rel", text="Relative", command=lambda c="rel": app.sort_history_by_column(c))
    app.history_listbox.heading("action", text="Action", command=lambda c="action": app.sort_history_by_column(c))

    app.history_listbox.column("time", width=70, stretch=False, anchor="w")
    app.history_listbox.column("type", width=70, stretch=False, anchor="w")
    app.history_listbox.column("name", width=180, stretch=True, anchor="w")
    app.history_listbox.column("rel", width=220, stretch=True, anchor="w")
    app.history_listbox.column("action", width=120, stretch=False, anchor="w")

    app.history_listbox.bind("<Button-3>", app.show_history_context_menu)
    app.history_listbox.bind("<Motion>", lambda e: listbox_logic.handle_history_hover(app, e))
    app.history_listbox.bind("<Leave>", lambda e: listbox_logic.handle_history_leave(app, e))

    # Context menu
    create_history_context_menu(app)
    create_history_header_context_menu(app)
    # Hover preview
    app.history_zoom = PopUpZoom(app.history_listbox, zoom_enabled=app.history_image_preview_var.get(), full_image_mode=True, popup_size=200)

    # Initialize binds + initial render
    try:
        app.apply_history_column_visibility()
        app.toggle_history_mode()
    except Exception:
        pass


def create_history_header_context_menu(app: 'Main'):
    """Build the history header right-click menu (column visibility toggles)."""
    app.history_header_menu = tk.Menu(app.history_listbox, tearoff=0)
    # Ensure Name stays visible
    try:
        app.history_column_visible_vars["name"].set(True)
    except Exception:
        pass
    for col in getattr(app, "history_columns", ("time", "type", "name", "rel", "action")):
        label = getattr(app, "history_column_labels", {}).get(col, col.title())
        var = getattr(app, "history_column_visible_vars", {}).get(col)
        if col == "name":
            app.history_header_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=col: app.toggle_history_column(c),
                state="disabled",
            )
        else:
            app.history_header_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=col: app.toggle_history_column(c),
            )


def create_history_context_menu(app: 'Main', entry: dict | None = None):
    """Build the history context menu for the currently selected history entry."""
    app.history_menu = tk.Menu(app.history_listbox, tearoff=0)
    kind = (entry or {}).get("kind")

    # Default to smart actions if entry isn't known
    if not kind:
        app.history_menu.add_command(label="Open", command=app.open_selected_file_smart)
        app.history_menu.add_command(label="Show in File Explorer", command=app.show_selected_in_explorer_smart)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Copy Path", command=lambda: listbox_logic.copy_selected_path(app, target="smart"))
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Delete", command=app.delete_selected_file_smart)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Remove From History", command=lambda: listbox_logic.remove_selected_history_entry(app))
        return

    if kind == "duplicate":
        app.history_menu.add_command(label="Open: Duplicate", command=app.open_selected_duplicate_file)
        app.history_menu.add_command(label="Show Duplicate in Explorer", command=app.show_selected_duplicate_in_explorer)
        app.history_menu.add_command(label="Copy Duplicate Path", command=lambda: listbox_logic.copy_selected_path(app, target="duplicate"))
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Open: Source", command=app.open_selected_source_file)
        app.history_menu.add_command(label="Show Source in Explorer", command=app.show_selected_source_in_explorer)
        app.history_menu.add_command(label="Copy Source Path", command=lambda: listbox_logic.copy_selected_path(app, target="source"))
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Delete: Duplicate", command=app.delete_selected_duplicate_file)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Remove From History", command=lambda: listbox_logic.remove_selected_history_entry(app))
    else:
        app.history_menu.add_command(label="Open", command=app.open_selected_file)
        app.history_menu.add_command(label="Show in File Explorer", command=app.show_selected_in_explorer)
        app.history_menu.add_command(label="Copy Path", command=lambda: listbox_logic.copy_selected_path(app, target="default"))
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Delete", command=app.delete_selected_file)
        app.history_menu.add_separator()
        app.history_menu.add_command(label="Remove From History", command=lambda: listbox_logic.remove_selected_history_entry(app))


#endregion
#region - Message row


def _create_message_row(app: 'Main'):
    # Message row
    message_frame = tk.Frame(app.root)
    message_frame.pack(side="bottom", fill="x")
    ttk.Separator(message_frame, orient="horizontal").pack(fill="x")
    # Status label
    status_label = tk.Label(message_frame, textvariable=app.status_label_var, relief="groove", anchor="w")
    status_label.pack(side="left", fill="x", expand=True)
    app.status_label = status_label
    app.status_label_default_fg = status_label.cget("fg")
    app.set_status(getattr(app, "status_state", "idle"), app.status_label_var.get())
    Tip(widget=status_label, text="Current status of the Folder-Funnel process", tooltip_anchor="sw", pady=-2)
    # Foldercount label
    foldercount_label = tk.Label(message_frame, textvariable=app.foldercount_var, relief="groove", anchor="w")
    foldercount_label.pack(side="left", fill="x", expand=True)
    Tip(widget=foldercount_label, text="Number of folders in the source folder", tooltip_anchor="sw", pady=-2)
    # Filecount label
    filecount_label = tk.Label(message_frame, textvariable=app.filecount_var, relief="groove", anchor="w")
    filecount_label.pack(side="left", fill="x", expand=True)
    Tip(widget=filecount_label, text="Number of files in the source folder", tooltip_anchor="sw", pady=-2)
    # Movecount label
    movecount_label = tk.Label(message_frame, textvariable=app.movecount_var, relief="groove", anchor="w")
    movecount_label.pack(side="left", fill="x", expand=True)
    Tip(widget=movecount_label, text="Number of files moved to the source folder", tooltip_anchor="sw", pady=-2)
    # Duplicate count label
    dupecount_label = tk.Label(message_frame, textvariable=app.dupecount_var, relief="groove", anchor="w")
    dupecount_label.pack(side="left", fill="x", expand=True)
    Tip(widget=dupecount_label, text="Number of duplicate files found", tooltip_anchor="sw", pady=-2)
    # Queuecount label
    queuecount_label = tk.Label(message_frame, textvariable=app.queuecount_var, relief="groove", anchor="w")
    queuecount_label.pack(side="left", fill="x", expand=True)
    Tip(widget=queuecount_label, text="Number of files in the move queue", tooltip_anchor="sw", pady=-2)
    # Queue Timer
    app.queue_progressbar = ttk.Progressbar(message_frame, mode="determinate")
    app.queue_progressbar.pack(side="left", fill="x", expand=True)
    Tip(widget=app.queue_progressbar, text="Progress of the move queue timer", tooltip_anchor="sw", pady=-2)
