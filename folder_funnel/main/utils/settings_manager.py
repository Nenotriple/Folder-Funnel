#region - Imports


# Standard
import os
import sys
import configparser

# Third-party
import nenotk as ntk

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Save


def save_settings(app: 'Main'):
    """Save application settings to a config file."""
    cfg = configparser.ConfigParser()
    # General settings
    working_directory = (app.source_dir_var.get() or getattr(app, 'last_working_directory', '') or '').strip()
    try:
        minimize_to_tray_show_close_tip = bool(getattr(app, 'minimize_to_tray_show_close_tip_var', None).get())
    except Exception:
        minimize_to_tray_show_close_tip = True
    cfg['General'] = {
        'working_directory': working_directory,
        'text_log_wrap': str(app.text_log_wrap_var.get()),
        'log_verbosity': str(app.log_verbosity_var.get()),
        'history_mode': app.history_mode_var.get(),
        'minimize_to_tray': str(app.minimize_to_tray_var.get()),
        'minimize_to_tray_show_close_tip': str(minimize_to_tray_show_close_tip),
        'notifications_enabled': str(bool(getattr(app, 'notifications_enabled_var', None).get()) if hasattr(app, 'notifications_enabled_var') else True),
        'fast_discovery_enabled': str(bool(getattr(app, 'fast_discovery_enabled_var', None).get()) if hasattr(app, 'fast_discovery_enabled_var') else (sys.platform == 'win32')),
        'log_prefix_filter': str(app.log_prefix_filter_var.get()),
        'history_image_preview': str(app.history_image_preview_var.get()),
    }
    # Layout
    cfg['Layout'] = {}
    try:
        pane = getattr(app, 'main_pane', None)
        if pane:
            pane.update_idletasks()
            x, y = pane.sash_coord(0)
            orient = str(pane.cget('orient')).lower()
            is_vertical = 'vertical' in orient
            app.main_pane_sash_pos = int(y) if is_vertical else int(x)
        # Store layout options (default/reset are current layout)
        try:
            cfg['Layout']['main_pane_orient'] = str(app.main_pane_orient_var.get())
        except Exception:
            cfg['Layout']['main_pane_orient'] = 'horizontal'
        try:
            cfg['Layout']['main_pane_order'] = str(app.main_pane_order_var.get())
        except Exception:
            cfg['Layout']['main_pane_order'] = 'log_first'

        if getattr(app, 'main_pane_sash_pos', None) is not None:
            cfg['Layout']['main_pane_sash_pos'] = str(int(app.main_pane_sash_pos))
    except Exception:
        pass
    # History (Treeview UI state)
    cfg['History'] = {
        'sort_column': str(getattr(app, 'history_sort_column', '') or ''),
        'sort_desc': str(bool(getattr(app, 'history_sort_desc', False))),
    }
    # Per-column visibility (future-proof for column additions)
    for col in getattr(app, 'history_columns', ("time", "type", "name", "rel", "action")):
        try:
            var = app.history_column_visible_vars.get(col)
            cfg['History'][f'col_visible_{col}'] = str(bool(var.get()) if var is not None else True)
        except Exception:
            cfg['History'][f'col_visible_{col}'] = 'True'
    # Name column cannot be disabled
    cfg['History']['col_visible_name'] = 'True'
    # Duplicate handling settings
    cfg['Duplicates'] = {
        'handle_mode': app.dupe_handle_mode_var.get(),
        'filter_mode': app.dupe_filter_mode_var.get(),
        'check_mode': app.dupe_check_mode_var.get(),
        'max_files': str(app.dupe_max_files_var.get()),
        'use_partial_hash': str(app.dupe_use_partial_hash_var.get()),
        'partial_hash_size': str(app.dupe_partial_hash_size_var.get()),
    }
    # Queue settings
    cfg['Queue'] = {
        'queue_length': str(app.move_queue_length_var.get())
    }
    # File handling options
    cfg['FileRules'] = {
        'ignore_firefox_temp_files': str(app.ignore_firefox_temp_files_var.get()),
        'ignore_temp_files': str(app.ignore_temp_files_var.get()),
        'auto_extract_zip': str(app.auto_extract_zip_var.get()),
        'auto_delete_zip': str(app.auto_delete_zip_var.get()),
        'overwrite_on_conflict': str(app.overwrite_on_conflict_var.get()),
    }
    # Stats settings
    cfg['Stats'] = {
        'grand_move_count': str(app.grand_move_count),
        'grand_duplicate_count': str(app.grand_duplicate_count),
        'move_action_time': str(app.move_action_time),
        'dupe_action_time': str(app.dupe_action_time),
    }
    # Window geometry (position + size)
    try:
        app.root.update_idletasks()
        geom = str(app.root.winfo_geometry() or '').strip()
        if geom:
            cfg['Window'] = {'geometry': geom}
    except Exception:
        pass
    # Create the settings file
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    try:
        with open(settings_path, 'w') as configfile:
            cfg.write(configfile)
        app.log("Settings saved", mode="system", verbose=3)
        return True
    except Exception as e:
        app.log(f"Error saving settings: {str(e)}", mode="error", verbose=1)
        return False


#endregion
#region - Load


def load_settings(app: 'Main'):
    """Load application settings from config file."""
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    if not os.path.exists(settings_path) and getattr(sys, 'frozen', False):
        legacy_path = os.path.join(os.path.dirname(sys.executable), 'settings.cfg')
        if os.path.exists(legacy_path):
            settings_path = legacy_path
    if not os.path.exists(settings_path):
        return False
    cfg = configparser.ConfigParser()
    try:
        cfg.read(settings_path)
        # Load log_verbosity ASAP to prevent missed log messages
        if 'General' in cfg and 'log_verbosity' in cfg['General']:
            app.log_verbosity_var.set(int(cfg['General']['log_verbosity']))
        # General
        if 'General' in cfg:
            # Record last-used working directory (prompted later, after UI/settings apply)
            try:
                wd = (cfg['General'].get('working_directory') or '').strip()
                if wd and os.path.exists(wd):
                    app.last_working_directory = wd
            except Exception:
                app.last_working_directory = ""
            if 'text_log_wrap' in cfg['General']:
                app.text_log_wrap_var.set(cfg.getboolean('General', 'text_log_wrap'))
            if 'history_mode' in cfg['General']:
                app.history_mode_var.set(cfg['General']['history_mode'])
            if 'minimize_to_tray' in cfg['General']:
                app.minimize_to_tray_var.set(cfg.getboolean('General', 'minimize_to_tray'))
            if 'minimize_to_tray_show_close_tip' in cfg['General']:
                try:
                    app.minimize_to_tray_show_close_tip_var.set(cfg.getboolean('General', 'minimize_to_tray_show_close_tip'))
                except Exception:
                    pass
            if 'notifications_enabled' in cfg['General']:
                try:
                    app.notifications_enabled_var.set(cfg.getboolean('General', 'notifications_enabled'))
                except Exception:
                    pass
            if 'log_prefix_filter' in cfg['General']:
                app.log_prefix_filter_var.set(cfg.getboolean('General', 'log_prefix_filter'))
            if 'history_image_preview' in cfg['General']:
                app.history_image_preview_var.set(cfg.getboolean('General', 'history_image_preview'))
            if 'fast_discovery_enabled' in cfg['General']:
                try:
                    app.fast_discovery_enabled_var.set(cfg.getboolean('General', 'fast_discovery_enabled'))
                except Exception:
                    pass
        # Layout
        if 'Layout' in cfg:
            try:
                if 'main_pane_orient' in cfg['Layout']:
                    app.main_pane_orient_var.set(cfg['Layout']['main_pane_orient'])
                if 'main_pane_order' in cfg['Layout']:
                    app.main_pane_order_var.set(cfg['Layout']['main_pane_order'])

                if 'main_pane_sash_pos' in cfg['Layout']:
                    app.main_pane_sash_pos = int(cfg['Layout']['main_pane_sash_pos'])
                # Back-compat: older settings used main_pane_sash_x (horizontal only)
                elif 'main_pane_sash_x' in cfg['Layout']:
                    app.main_pane_sash_pos = int(cfg['Layout']['main_pane_sash_x'])
            except Exception:
                app.main_pane_sash_pos = None
        # History (Treeview UI state)
        if 'History' in cfg:
            # Column visibility
            try:
                for col in getattr(app, 'history_columns', ("time", "type", "name", "rel", "action")):
                    key = f'col_visible_{col}'
                    if key in cfg['History']:
                        app.history_column_visible_vars[col].set(cfg.getboolean('History', key))
            except Exception:
                pass
            # Name column cannot be disabled
            try:
                app.history_column_visible_vars['name'].set(True)
            except Exception:
                pass
            # Sort state
            try:
                col = (cfg['History'].get('sort_column') or '').strip()
                app.history_sort_column = col if col else None
                if 'sort_desc' in cfg['History']:
                    app.history_sort_desc = cfg.getboolean('History', 'sort_desc')
            except Exception:
                app.history_sort_column = None
                app.history_sort_desc = False
        # Duplicates
        if 'Duplicates' in cfg:
            if 'handle_mode' in cfg['Duplicates']:
                app.dupe_handle_mode_var.set(cfg['Duplicates']['handle_mode'])
            if 'filter_mode' in cfg['Duplicates']:
                app.dupe_filter_mode_var.set(cfg['Duplicates']['filter_mode'])
            if 'check_mode' in cfg['Duplicates']:
                app.dupe_check_mode_var.set(cfg['Duplicates']['check_mode'])
            if 'max_files' in cfg['Duplicates']:
                app.dupe_max_files_var.set(int(cfg['Duplicates']['max_files']))
            if 'use_partial_hash' in cfg['Duplicates']:
                app.dupe_use_partial_hash_var.set(cfg.getboolean('Duplicates', 'use_partial_hash'))
            if 'partial_hash_size' in cfg['Duplicates']:
                app.dupe_partial_hash_size_var.set(int(cfg['Duplicates']['partial_hash_size']))
        # Queue
        if 'Queue' in cfg and 'queue_length' in cfg['Queue']:
            app.move_queue_length_var.set(int(cfg['Queue']['queue_length']))
        # FileRules
        if 'FileRules' in cfg:
            if 'ignore_firefox_temp_files' in cfg['FileRules']:
                app.ignore_firefox_temp_files_var.set(cfg.getboolean('FileRules', 'ignore_firefox_temp_files'))
            if 'ignore_temp_files' in cfg['FileRules']:
                app.ignore_temp_files_var.set(cfg.getboolean('FileRules', 'ignore_temp_files'))
            if 'auto_extract_zip' in cfg['FileRules']:
                app.auto_extract_zip_var.set(cfg.getboolean('FileRules', 'auto_extract_zip'))
            if 'auto_delete_zip' in cfg['FileRules']:
                app.auto_delete_zip_var.set(cfg.getboolean('FileRules', 'auto_delete_zip'))
            if 'overwrite_on_conflict' in cfg['FileRules']:
                app.overwrite_on_conflict_var.set(cfg.getboolean('FileRules', 'overwrite_on_conflict'))
        # Stats
        if 'Stats' in cfg:
            if 'grand_move_count' in cfg['Stats']:
                app.grand_move_count = int(cfg['Stats']['grand_move_count'])
            if 'grand_duplicate_count' in cfg['Stats']:
                app.grand_duplicate_count = int(cfg['Stats']['grand_duplicate_count'])
            if 'move_action_time' in cfg['Stats']:
                app.move_action_time = float(cfg['Stats']['move_action_time'])
            if 'dupe_action_time' in cfg['Stats']:
                app.dupe_action_time = float(cfg['Stats']['dupe_action_time'])
        # Window geometry
        try:
            if 'Window' in cfg and 'geometry' in cfg['Window']:
                geom = (cfg['Window'].get('geometry') or '').strip()
                app.window_geometry = geom if geom else None
        except Exception:
            app.window_geometry = None
        app.log("Settings loaded successfully", mode="system", verbose=2)
        return True
    except Exception as e:
        app.log(f"Error loading settings: {str(e)}", mode="error", verbose=1)
        return False


def apply_settings_to_ui(app: 'Main'):
    """Apply loaded settings to UI components."""
    # Apply window geometry early (position + size)
    try:
        geom = getattr(app, 'window_geometry', None)
        if geom:
            app.root.geometry(geom)
    except Exception:
        pass
    # Apply text wrap setting
    if app.text_log:
        wrap_mode = 'word' if app.text_log_wrap_var.get() else 'none'
        app.text_log.configure(wrap=wrap_mode)
    # Sync hover preview toggle
    if hasattr(app, "toggle_history_preview"):
        app.toggle_history_preview()
    # Apply history column visibility + header arrows (requires Treeview to exist)
    if hasattr(app, "apply_history_column_visibility"):
        try:
            app.apply_history_column_visibility()
        except Exception:
            pass
    # If a source dir is already set (non-startup scenarios), sync UI to it.
    # Startup reload is prompted later.
    try:
        current = (app.source_dir_var.get() or '').strip()
        if current and os.path.exists(current):
            app.select_working_dir(current)
    except Exception:
        pass


    def _apply_main_pane_sash():
        """Apply paned window sash position (after geometry settles)"""
        pane = getattr(app, 'main_pane', None)
        if not pane:
            return
        try:
            pane.update_idletasks()
            cx, cy = pane.sash_coord(0)
            desired = getattr(app, 'main_pane_sash_pos', None)
            if desired is None:
                desired = getattr(app, 'main_pane_default_sash_x', None)
            if desired is None:
                return
            orient = str(pane.cget('orient')).lower()
            is_vertical = 'vertical' in orient
            if is_vertical:
                pane.sash_place(0, int(cx), int(desired))
            else:
                pane.sash_place(0, int(desired), int(cy))
        except Exception:
            pass
    try:
        # Apply layout (orientation + order) before sash placement
        if hasattr(app, 'apply_main_pane_layout'):
            try:
                app.apply_main_pane_layout(user_action=False)
            except Exception:
                pass
        app.root.after(50, _apply_main_pane_sash)
    except Exception:
        pass
    # Update history display based on mode
    app.refresh_history_listbox()
    app.toggle_history_mode()
    # Last startup step: ask whether to reload the last working directory.
    try:
        app.root.after(250, lambda: prompt_reload_last_directory(app))
    except Exception:
        pass


def prompt_reload_last_directory(app: 'Main') -> None:
    """Prompt the user (once per session) to reload the last working directory."""
    try:
        if bool(getattr(app, '_startup_reload_prompt_shown', False)):
            return
        app._startup_reload_prompt_shown = True
    except Exception:
        return
    path = (getattr(app, 'last_working_directory', '') or '').strip()
    if not path or not os.path.exists(path):
        return
    if ntk.askyesno("Confirmation", prompt="Reload the last directory and start the funnel?", detail=path):
        # Update UI field/tooltip/log
        try:
            app.select_working_dir(path)
        except Exception:
            try:
                app.source_dir_var.set(path)
            except Exception:
                pass
        # Start after UI is fully settled
        try:
            app.root.after(250, lambda: app.start_folder_watcher(auto_start=True))
        except Exception:
            pass


#endregion
#region - Reset


def reset_settings(app: 'Main'):
    """Reset all settings to default values."""
    try:
        # General
        app.text_log_wrap_var.set(True)
        app.log_verbosity_var.set(1)
        app.history_mode_var.set("All")
        app.minimize_to_tray_var.set(True)
        app.log_prefix_filter_var.set(True)
        app.history_image_preview_var.set(True)
        try:
            app.notifications_enabled_var.set(True)
        except Exception:
            pass
        # Fast discovery
        try:
            app.fast_discovery_enabled_var.set(sys.platform == 'win32')
        except Exception:
            pass
        # Layout
        try:
            app.main_pane_orient_var.set('vertical')
            app.main_pane_order_var.set('history_first')
            app.main_pane_sash_pos = 475
        except Exception:
            app.main_pane_sash_pos = None
        # History Treeview UI state
        try:
            for col in getattr(app, 'history_columns', ("time", "type", "name", "rel", "action")):
                app.history_column_visible_vars[col].set(True)
            app.history_column_visible_vars['name'].set(True)
            # Match shipped defaults: hide Action column
            try:
                app.history_column_visible_vars['action'].set(False)
            except Exception:
                pass
        except Exception:
            pass
        app.history_sort_column = "name"
        app.history_sort_desc = False
        # Duplicate handling
        app.dupe_handle_mode_var.set("Move")
        app.dupe_filter_mode_var.set("Flexible")
        app.dupe_check_mode_var.set("Similar")
        app.dupe_max_files_var.set(75)
        app.dupe_use_partial_hash_var.set(True)
        app.dupe_partial_hash_size_var.set(4096)
        # Queue
        app.move_queue_length_var.set(1000)
        # File handling
        app.ignore_firefox_temp_files_var.set(True)
        app.ignore_temp_files_var.set(True)
        app.auto_extract_zip_var.set(False)
        app.auto_delete_zip_var.set(False)
        app.overwrite_on_conflict_var.set(False)
        # Window geometry (size only; do not force a saved position)
        try:
            app.window_geometry = "960x720"
            app.root.geometry(app.window_geometry)
        except Exception:
            app.window_geometry = None
        # Apply settings to UI
        apply_settings_to_ui(app)
        # Save the new settings
        save_settings(app)
        app.log("Settings reset to default values.", mode="info", verbose=1)
        return True
    except Exception as e:
        app.log(f"Error resetting settings: {str(e)}", mode="error", verbose=1)
        return False
