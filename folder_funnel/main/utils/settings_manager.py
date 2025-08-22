#region - Imports


# Standard
import os
import configparser

# Standard GUI
from tkinter import messagebox

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
    cfg['General'] = {
        'working_directory': app.working_dir_var.get(),
        'text_log_wrap': str(app.text_log_wrap_var.get()),
        'history_mode': app.history_mode_var.get(),
    }
    # Duplicate handling settings
    cfg['Duplicates'] = {
        'handle_mode': app.dupe_handle_mode_var.get(),
        'filter_mode': app.dupe_filter_mode_var.get(),
        'check_mode': app.dupe_check_mode_var.get(),
        'max_files': str(app.dupe_max_files_var.get()),
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
    # Create the settings file
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    try:
        with open(settings_path, 'w') as configfile:
            cfg.write(configfile)
        return True
    except Exception as e:
        app.log(f"Error saving settings: {str(e)}", mode="error")
        return False


#endregion
#region - Load


def load_settings(app: 'Main'):
    """Load application settings from config file."""
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    if not os.path.exists(settings_path):
        return False
    cfg = configparser.ConfigParser()
    try:
        cfg.read(settings_path)
        # General
        if 'General' in cfg:
            if 'working_directory' in cfg['General'] and os.path.exists(cfg['General']['working_directory']):
                if messagebox.askyesno("Confirmation", "Reload last directory and start funnel process?"):
                    app.working_dir_var.set(cfg['General']['working_directory'])
                    # Schedule the funnel process to start after UI is ready
                    app.root.after(500, lambda: app.start_folder_watcher(auto_start=True))
            if 'text_log_wrap' in cfg['General']:
                app.text_log_wrap_var.set(cfg.getboolean('General', 'text_log_wrap'))
            if 'history_mode' in cfg['General']:
                app.history_mode_var.set(cfg['General']['history_mode'])
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
        return True
    except Exception as e:
        app.log(f"Error loading settings: {str(e)}", mode="error")
        return False


def apply_settings_to_ui(app: 'Main'):
    """Apply loaded settings to UI components."""
    # Apply text wrap setting
    if app.text_log:
        wrap_mode = 'word' if app.text_log_wrap_var.get() else 'none'
        app.text_log.configure(wrap=wrap_mode)
    # Apply working directory if it exists
    if app.working_dir_var.get() and os.path.exists(app.working_dir_var.get()):
        app.select_working_dir(app.working_dir_var.get())
        app.count_folders_and_files()
    # Update history display based on mode
    app.refresh_history_listbox()
    app.toggle_history_mode()


#endregion
#region - Reset

def reset_settings(app: 'Main'):
    """Reset all settings to default values."""
    try:
        # General
        app.text_log_wrap_var.set(True)
        app.history_mode_var.set("Moved")
        # Duplicate handling
        app.dupe_handle_mode_var.set("Move")
        app.dupe_filter_mode_var.set("Flexible")
        app.dupe_check_mode_var.set("Similar")
        app.dupe_max_files_var.set(50)
        # Queue
        app.move_queue_length_var.set(15000)
        # File handling
        app.ignore_firefox_temp_files_var.set(True)
        app.ignore_temp_files_var.set(True)
        app.auto_extract_zip_var.set(False)
        app.auto_delete_zip_var.set(False)
        app.overwrite_on_conflict_var.set(False)
        # Apply settings to UI
        apply_settings_to_ui(app)
        # Save the new settings
        save_settings(app)
        app.log("Settings reset to default values.", mode="info")
        return True
    except Exception as e:
        app.log(f"Error resetting settings: {str(e)}", mode="error")
        return False
