@echo off
setlocal enabledelayedexpansion


REM ======================================================
REM Folder-Funnel Build Script
REM Created by: github.com/Nenotriple
set "SCRIPT_VERSION=1.00"
REM ======================================================


REM Configuration
set "PYTHON_SCRIPT=app.py"
set "BUILD_NAME=Folder-Funnel"
set "ICON_PATH=main\ui\icon.ico"
set "ADD_DATA=main\ui\icon.png;main\ui"
set "VENV_DIR=.venv"
set "REQUIREMENTS_FILE=requirements.txt"
set "PYINSTALLER_FLAGS=--onefile --windowed --icon="%ICON_PATH%" --add-data="%ADD_DATA%""
set "AUTO_CLOSE_CONSOLE=FALSE"


REM ==============================================
REM Main Execution Flow
REM ==============================================


call :PrintHeader
call :ValidatePython || exit /b 1
call :ActivateVenv || exit /b 1
call :UpgradePyInstaller || exit /b 1
call :RunPyInstaller || exit /b 1
call :LogOK "Build completed successfully."
call :MaybeKeepConsole
goto :EOF


REM ==============================================
REM Header
REM ==============================================


:PrintHeader
    echo ============================================================
    echo   %SCRIPT_VERSION% Folder-Funnel Build Script
    echo   Created by: github.com/Nenotriple
    echo ============================================================
    echo.
    echo [PROJECT] %BUILD_NAME%
    echo.
exit /b 0


REM ==============================================
REM Validation
REM ==============================================


:ValidatePython
    where python >nul 2>&1 || (
        call :LogError "Python is not installed or not found in PATH"
        exit /b 1
    )
    python --version
exit /b 0


:ActivateVenv
    if not exist "%VENV_DIR%\Scripts\activate.bat" (
        call :LogError "Virtual environment not found. Please run Start.bat first."
        exit /b 1
    )
    call "%VENV_DIR%\Scripts\activate.bat"
exit /b 0


REM ==============================================
REM Build Steps
REM ==============================================


:UpgradePyInstaller
    echo Upgrading PyInstaller...
    pip install --upgrade pyinstaller
    if !ERRORLEVEL! neq 0 (
        call :LogError "Failed to upgrade PyInstaller"
        exit /b 1
    )
exit /b 0


:RunPyInstaller
    echo Running PyInstaller...
    pyinstaller %PYTHON_SCRIPT% --name %BUILD_NAME% %PYINSTALLER_FLAGS%
    if !ERRORLEVEL! neq 0 (
        call :LogError "PyInstaller build failed"
        exit /b 1
    )
exit /b 0


REM ==============================================
REM Logging
REM ==============================================


:LogOK

    echo [OK] %~1
    goto :EOF


:LogError
    echo [ERROR] %~1
    call :MaybeKeepConsole
    goto :EOF


:MaybeKeepConsole
    if "%AUTO_CLOSE_CONSOLE%"=="FALSE" goto MenuLoop
    exit /b 0


:MenuLoop
    echo.
    echo Build script finished.
    echo ---------------------------------------------
    echo 1 - Rebuild
    echo 2 - Drop into venv shell
    echo 3 - Exit
    echo ---------------------------------------------
    set /p MENUCHOICE="Select option: "
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
