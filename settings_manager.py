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
    config = configparser.ConfigParser()
    # General settings
    config['General'] = {
        'working_directory': app.working_dir_var.get(),
        'text_log_wrap': str(app.text_log_wrap_var.get()),
        'history_mode': app.history_mode_var.get(),
    }
    # Duplicate handling settings
    config['Duplicates'] = {
        'handle_mode': app.dupe_handle_mode_var.get(),
        'filter_mode': app.dupe_filter_mode_var.get(),
        'check_mode': app.dupe_check_mode_var.get(),
        'max_files': str(app.dupe_max_files_var.get()),
    }
    # Queue settings
    config['Queue'] = {
        'queue_length': str(app.move_queue_length_var.get())
    }
    # File handling options
    config['FileHandling'] = {
        'ignore_firefox_temp_files': str(app.ignore_firefox_temp_files_var.get()),
        'ignore_temp_files': str(app.ignore_temp_files_var.get()),
        'auto_extract_zip': str(app.auto_extract_zip_var.get()),
        'auto_delete_zip': str(app.auto_delete_zip_var.get()),
        'overwrite_on_conflict': str(app.overwrite_on_conflict_var.get()),
    }
    # Create the settings file
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    try:
        with open(settings_path, 'w') as configfile:
            config.write(configfile)
        return True
    except Exception as e:
        app.log(f"Error saving settings: {str(e)}")
        return False


#endregion
#region - Load


def load_settings(app: 'Main'):
    """Load application settings from config file."""
    settings_path = os.path.join(app.get_data_path(), 'settings.cfg')
    if not os.path.exists(settings_path):
        return False
    config = configparser.ConfigParser()
    try:
        config.read(settings_path)
        # Load General settings
        if 'General' in config:
            if 'working_directory' in config['General'] and os.path.exists(config['General']['working_directory']):
                if messagebox.askyesno("Confirmation", "Reload last directory?"):
                    app.working_dir_var.set(config['General']['working_directory'])
            if 'text_log_wrap' in config['General']:
                app.text_log_wrap_var.set(config.getboolean('General', 'text_log_wrap'))
            if 'history_mode' in config['General']:
                app.history_mode_var.set(config['General']['history_mode'])
        # Load Duplicates settings
        if 'Duplicates' in config:
            if 'handle_mode' in config['Duplicates']:
                app.dupe_handle_mode_var.set(config['Duplicates']['handle_mode'])
            if 'filter_mode' in config['Duplicates']:
                app.dupe_filter_mode_var.set(config['Duplicates']['filter_mode'])
            if 'check_mode' in config['Duplicates']:
                app.dupe_check_mode_var.set(config['Duplicates']['check_mode'])
            if 'max_files' in config['Duplicates']:
                app.dupe_max_files_var.set(int(config['Duplicates']['max_files']))
        # Load Queue settings
        if 'Queue' in config and 'queue_length' in config['Queue']:
            app.move_queue_length_var.set(int(config['Queue']['queue_length']))
        # Load FileHandling settings
        if 'FileHandling' in config:
            if 'ignore_firefox_temp_files' in config['FileHandling']:
                app.ignore_firefox_temp_files_var.set(config.getboolean('FileHandling', 'ignore_firefox_temp_files'))
            if 'ignore_temp_files' in config['FileHandling']:
                app.ignore_temp_files_var.set(config.getboolean('FileHandling', 'ignore_temp_files'))
            if 'auto_extract_zip' in config['FileHandling']:
                app.auto_extract_zip_var.set(config.getboolean('FileHandling', 'auto_extract_zip'))
            if 'auto_delete_zip' in config['FileHandling']:
                app.auto_delete_zip_var.set(config.getboolean('FileHandling', 'auto_delete_zip'))
            if 'overwrite_on_conflict' in config['FileHandling']:
                app.overwrite_on_conflict_var.set(config.getboolean('FileHandling', 'overwrite_on_conflict'))
        return True
    except Exception as e:
        app.log(f"Error loading settings: {str(e)}")
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
        return True
    except Exception as e:
        app.log(f"Error resetting settings: {str(e)}")
        return False
