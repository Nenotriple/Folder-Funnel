# Build Instructions for img-txt Viewer

## Steps

**1.** Activate the Project Virtual Environment

**2.** Upgrade PyInstaller

```sh
pip install --upgrade pyinstaller
```

**3.** Run PyInstaller

```sh
pyinstaller app.py --name Folder-Funnel --onefile --windowed --icon="main\ui\icon.ico" --add-data="main\ui\icon.png;main\ui"
```

## Breakdown of the PyInstaller Command

1. `pyinstaller`
   - Main command to run PyInstaller.
2. `app.py`
   - The Python script to convert into an executable. This is the main entry point of the application.
3. `--name Folder-Funnel`
   - Filename of the generated executable. This is the name that will be used for the output file.
4. `--onefile`
   - Bundle everything into a single executable file.
5. `--windowed`
   - Run the executable without opening a console window.
6. `--icon=main\ui\icon.ico`
   - Path to the icon file for the executable. This is used to set the icon of the executable file itself.
7. `--add-data="main\ui\icon.png;main\ui"`
   - Include the raw icon.png file from the `main\ui` directory in the `main\ui` folder of the bundled application. This ensures the app can access the icon at runtime.
