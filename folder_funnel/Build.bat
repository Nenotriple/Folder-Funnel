@echo off
setlocal enabledelayedexpansion


REM Ensure relative paths resolve from this script's folder
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" || (
    echo [ERROR] Failed to set working directory to "%SCRIPT_DIR%"
    exit /b 1
)


REM ======================================================
REM Folder-Funnel Build Script
REM Created by: github.com/Nenotriple
set "SCRIPT_VERSION=1.02"
REM ======================================================


REM Configuration
set "PYTHON_SCRIPT=app.py"
set "BUILD_NAME=Folder-Funnel"
set "ICON_PATH=main\ui\icon.ico"
set "ADD_DATA=main\ui\icon.png;main\ui"
set "VENV_DIR=.venv"
set "REQUIREMENTS_FILE=requirements.txt"
set "PYINSTALLER_FLAGS=--onefile --windowed --noconfirm --clean"
set "AUTO_CLOSE_CONSOLE=FALSE"
set "ENABLE_COLORS=TRUE"


REM ==============================================
REM Main Execution Flow
REM ==============================================


call :initialize_colors
call :PrintHeader
call :ValidatePython || exit /b 1
call :UpdatePip || exit /b 1
call :InstallRequirements || exit /b 1
call :UpgradePyInstaller || exit /b 1
call :RunPyInstaller || exit /b 1
call :LogOK "Build completed successfully."
call :MaybeKeepConsole
goto :EOF


REM ==============================================
REM Header / Initialization
REM ==============================================


:initialize_colors
    if "%ENABLE_COLORS%"=="TRUE" (
        for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
        set "COLOR_RESET=!ESC![0m"
        set "COLOR_INFO=!ESC![36m"
        set "COLOR_OK=!ESC![32m"
        set "COLOR_WARN=!ESC![33m"
        set "COLOR_ERROR=!ESC![91m"
    ) else (
        set "COLOR_RESET=" & set "COLOR_INFO=" & set "COLOR_OK=" & set "COLOR_WARN=" & set "COLOR_ERROR="
    )
exit /b 0


:PrintHeader
    echo %COLOR_INFO%=====================================================%COLOR_RESET%
    echo %COLOR_INFO%          %SCRIPT_VERSION% Build Script%COLOR_RESET%
    echo %COLOR_INFO%          Created by: github.com/Nenotriple%COLOR_RESET%
    echo %COLOR_INFO%=====================================================%COLOR_RESET%
    echo.
    echo %COLOR_OK%[PROJECT]%COLOR_RESET% %COLOR_WARN%%BUILD_NAME%%COLOR_RESET%
    echo.
exit /b 0


REM ==============================================
REM Validation
REM ==============================================


:ValidatePython
    call :LogInfo "Activating virtual environment..."
    if not exist "%VENV_DIR%\Scripts\activate.bat" (
        call :LogError "Virtual environment not found. Please run Start.bat first."
        exit /b 1
    )
    call "%VENV_DIR%\Scripts\activate.bat"
    where python | findstr /i "%VENV_DIR%" >nul || (
        call :LogError "Virtual environment activation failed"
        exit /b 1
    )
    call :LogInfo "Using Python version:"
    python --version
    call :LogOK "Virtual environment activated."
exit /b 0


:UpdatePip
    call :LogInfo "Upgrading pip..."
    python -m pip install --disable-pip-version-check --upgrade pip
    if !ERRORLEVEL! neq 0 (
        call :LogError "Failed to upgrade pip"
        exit /b 1
    )
    call :LogOK "pip upgraded successfully."
exit /b 0


:InstallRequirements
    if not exist "%REQUIREMENTS_FILE%" (
        call :LogWarn "Requirements file not found: %REQUIREMENTS_FILE%"
        exit /b 0
    )
    call :LogInfo "Installing requirements from %REQUIREMENTS_FILE%..."
    python -m pip install --disable-pip-version-check -r "%REQUIREMENTS_FILE%"
    if !ERRORLEVEL! neq 0 (
        call :LogError "Failed to install requirements"
        exit /b 1
    )
    call :LogOK "Requirements installed successfully."
exit /b 0


REM ==============================================
REM Build Steps
REM ==============================================


:UpgradePyInstaller
    call :LogInfo "Upgrading PyInstaller..."
    python -m pip install --disable-pip-version-check --upgrade pyinstaller
    if !ERRORLEVEL! neq 0 (
        call :LogError "Failed to upgrade PyInstaller"
        exit /b 1
    )
    call :LogOK "PyInstaller upgraded successfully."
exit /b 0


:RunPyInstaller
    call :LogInfo "Running PyInstaller..."
    if exist "%ICON_PATH%" (
        python -m PyInstaller "%PYTHON_SCRIPT%" --name "%BUILD_NAME%" %PYINSTALLER_FLAGS% --icon "%ICON_PATH%" --add-data "%ADD_DATA%"
    ) else (
        call :LogWarn "Icon not found at \"%ICON_PATH%\"; building without a custom icon."
        python -m PyInstaller "%PYTHON_SCRIPT%" --name "%BUILD_NAME%" %PYINSTALLER_FLAGS% --add-data "%ADD_DATA%"
    )
    if !ERRORLEVEL! neq 0 (
        call :LogError "PyInstaller build failed"
        exit /b 1
    )
    call :LogOK "PyInstaller build completed successfully."
exit /b 0


REM ==============================================
REM Logging
REM ==============================================


:LogOK
    echo %COLOR_OK%[OK] %~1%COLOR_RESET%
    goto :EOF


:LogInfo
    echo %COLOR_INFO%[INFO] %~1%COLOR_RESET%
    goto :EOF


:LogWarn
    echo %COLOR_WARN%[WARN] %~1%COLOR_RESET%
    goto :EOF


:LogError
    echo %COLOR_ERROR%[ERROR] %~1%COLOR_RESET%
    call :MaybeKeepConsole
    goto :EOF


:MaybeKeepConsole
    REM Return to the original working directory (if Build.bat was invoked from elsewhere)
    popd 2>nul
    if "%AUTO_CLOSE_CONSOLE%"=="FALSE" goto MenuLoop
    exit /b 0


:MenuLoop
    echo.
    echo %COLOR_INFO%Build script finished.%COLOR_RESET%
    echo %COLOR_INFO%---------------------------------------------%COLOR_RESET%
    echo %COLOR_OK%1%COLOR_RESET% - Rebuild
    echo %COLOR_OK%2%COLOR_RESET% - Drop into venv shell
    echo %COLOR_OK%3%COLOR_RESET% - Exit
    echo %COLOR_INFO%---------------------------------------------%COLOR_RESET%
    set /p MENUCHOICE=%COLOR_INFO%Select option: %COLOR_RESET%
    if "%MENUCHOICE%"=="1" (
        call "%~f0"
        goto :EOF
    )
    if "%MENUCHOICE%"=="2" (
        call "%VENV_DIR%\Scripts\activate.bat"
        cmd /k
        goto :EOF
    )
    if "%MENUCHOICE%"=="3" (
        exit /b 0
    )
    echo Invalid option. Please try again.
    goto MenuLoop
