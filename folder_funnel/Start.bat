@echo off
setlocal enabledelayedexpansion


REM ======================================================
REM Python Virtual Environment Setup and Script Launcher
REM Created by: github.com/Nenotriple
set "SCRIPT_VERSION=1.06"
REM ======================================================


REM Configuration (see https://github.com/Nenotriple/pyvenv-launcher/blob/main/README.md for details)
set "VENV_DIR=.venv"
set "PYTHON_PATH="
set "PYTHON_SCRIPT=app.py"
set "REQUIREMENTS_FILE=requirements.txt"

set "FAST_START=FALSE"
set "AUTO_FAST_START=TRUE"
set "AUTO_CLOSE_CONSOLE=TRUE"
set "UPDATE_REQUIREMENTS_ON_LAUNCH=FALSE"

set "ENABLE_COLORS=TRUE"
set "QUIET_MODE=FALSE"
set "LAUNCH_SCRIPT=TRUE"
set "SET_VENV_HIDDEN=TRUE"

REM Runtime Variables
set "SCRIPT_DIR=%~dp0"
set "PIP_TIMEOUT=30"
set "PYCOUNT=0"


REM ==============================================
REM Main Execution Flow
REM ==============================================


call :Main


goto :EOF


:Main
    call :initialize_colors
    call :DetermineProjectName
    title %PROJECT_NAME%
    call :PrintHeader
    call :HandleExistingVenv
    if !ERRORLEVEL! neq 0 exit /b !ERRORLEVEL!
    call :SetupAndLaunch
    if !ERRORLEVEL! neq 0 exit /b !ERRORLEVEL!
exit /b 0


:HandleExistingVenv
    if not exist "%VENV_DIR%\Scripts\python.exe" exit /b 0
    call :ActivateVenv || exit /b 1
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do call :LogOK "Using Python %%i"
    call :LaunchPythonScript || exit /b 1
    call :HandlePostRun
    exit /b 1


:SetupAndLaunch
    call :ValidatePython || exit /b 1
    pushd "%SCRIPT_DIR%" || (call :LogError "Failed to set working directory" & exit /b 1)
    call :SetupVirtualEnvironment || exit /b 1
    call :HandleLaunchOrShell || exit /b 1
    call :LaunchPythonScript || exit /b 1
    call :HandlePostRun
exit /b 0


:HandleLaunchOrShell
    REM Launch or drop to shell
    if "%LAUNCH_SCRIPT%"=="FALSE" (
        call :LogInfo "LAUNCH_SCRIPT is FALSE. Skipping app launch."
        call :LogInfo "Dropping into interactive shell inside the virtual environment."
        call "%VENV_DIR%\Scripts\activate.bat"
        cmd /k
        exit /b 1
    )
exit /b 0


:HandlePostRun
    if "%AUTO_CLOSE_CONSOLE%"=="FALSE" (
        echo.
        call :LogInfo "Script completed."
        echo.
        cmd /k
    )
exit /b 0


REM ==============================================
REM Initialization (colors, project name, header)
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


:DetermineProjectName
    set "DIR=%SCRIPT_DIR%"
    if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
    for %%A in ("%DIR%") do set "PROJECT_NAME=%%~nxA"
    if not defined PROJECT_NAME set "PROJECT_NAME=Unknown"
exit /b 0


:PrintHeader
    echo %COLOR_INFO%============================================================%COLOR_RESET%
    echo %COLOR_INFO%  %SCRIPT_VERSION% Python Virtual Environment Setup and Script Launcher%COLOR_RESET%
    echo %COLOR_INFO%  Created by: github.com/Nenotriple%COLOR_RESET%
    echo %COLOR_INFO%============================================================%COLOR_RESET%
    echo.
    echo %COLOR_OK%[PROJECT]%COLOR_RESET% %COLOR_WARN%%PROJECT_NAME%%COLOR_RESET%
    echo.
exit /b 0


REM ==============================================
REM Validation
REM ==============================================


:ValidatePython
    if defined PYTHON_PATH (
        if exist "%PYTHON_PATH%" (
            set "PYTHON_PATH=%PYTHON_PATH%"
            call :LogOK "Using direct Python path"
            exit /b 0
        ) else (
            call :LogWarn "Direct Python path not found: %PYTHON_PATH%"
        )
    )
    call :LogInfo "Checking Python installations..."
    call :CollectPyVersionTags
    if %PYCOUNT%==0 (
        call :LogError "No Python installations found"
        call :LogError "Please install Python from https://python.org"
        exit /b 1
    )
    call :ResolvePyVersions
    call :DisplayPySelectMenu
    call :PromptPySelection
    if not defined TAG[%CHOICE%] (
        call :LogError "Invalid selection"
        exit /b 1
    )
    call :ResolvePythonPath
    call :LogOK "Using Python !VER[%CHOICE%]!"
exit /b 0


:CollectPyVersionTags
    for /f "tokens=1 delims= " %%A in ('py list 2^>nul ^| findstr /R "^[0-9]"') do (
        set RAW=%%A
        set CLEAN=!RAW:[=!
        for /f "delims=]" %%B in ("!CLEAN!") do set TAG=%%B
        set /a PYCOUNT+=1
        set TAG[!PYCOUNT!]=!TAG!
    )
exit /b 0


:ResolvePyVersions
    for /L %%I in (1,1,%PYCOUNT%) do (
        for /f "delims=" %%V in ('
            py -!TAG[%%I]! -c "import platform; print(platform.python_version())"
        ') do set VER[%%I]=%%V
    )
exit /b 0


:DisplayPySelectMenu
    echo.
    echo Python versions found:
    echo.
    for /L %%I in (1,1,%PYCOUNT%) do (
        echo %%I^) Python !VER[%%I]!
    )
    echo.
exit /b 0


:PromptPySelection
    set /p CHOICE=Make your selection (1-%PYCOUNT%):
exit /b 0


:ResolvePythonPath
    for /f "delims=" %%P in ('
        py -!TAG[%CHOICE%]! -c "import sys; print(sys.executable)"
    ') do set PYTHON_PATH=%%P
exit /b 0


REM ==============================================
REM Virtual Environment lifecycle
REM ==============================================


:CreateVirtualEnvironment
    if exist "%VENV_DIR%\Scripts\python.exe" (
        call :LogInfo "Using existing virtual environment"
        exit /b 0
    )
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    call :LogInfo "Creating virtual environment: %SCRIPT_DIR%%VENV_DIR%"
    "!PYTHON_PATH!" -m venv "%VENV_DIR%" || (call :LogError "Failed to create virtual environment" & exit /b 1)
    if "%SET_VENV_HIDDEN%"=="TRUE" call :SetVenvHidden
    call :LogOK "Virtual environment created"
exit /b 0


:ActivateVenv
    call :LogInfo "Activating virtual environment..."
    call "%VENV_DIR%\Scripts\activate.bat" || (call :LogError "Failed to activate virtual environment" & exit /b 1)
    where python | findstr "%VENV_DIR%" >nul || (call :LogError "Virtual environment activation failed" & exit /b 1)
    call :LogOK "Virtual environment activated"
exit /b 0


:SetVenvHidden
    attrib +h "%VENV_DIR%" 2>nul && call :LogInfo "Virtual environment directory set as hidden" || call :LogWarn "Failed to set directory as hidden"
exit /b 0


:SetupVirtualEnvironment
    REM Check for fast start conditions
    if "%AUTO_FAST_START%"=="TRUE" if exist "%VENV_DIR%\Scripts\python.exe" (
        "%VENV_DIR%\Scripts\python.exe" --version >nul 2>&1 && (
            set "FAST_START=TRUE"
            call :LogInfo "Virtual environment verified. Using fast start mode."
        )
    )
    REM Fast start path
    if "%FAST_START%"=="TRUE" (
        call :ActivateVenv && (
            if "%UPDATE_REQUIREMENTS_ON_LAUNCH%"=="TRUE" call :InstallRequirements
            exit /b 0
        )
        REM If activation fails, fall through to full setup
        set "FAST_START=FALSE"
    )
    REM Full setup path
    call :CreateVirtualEnvironment
    call :ActivateVenv || exit /b 1
    call :InstallOrUpdatePackages
exit /b 0


REM ==============================================
REM Package management (pip / requirements)
REM ==============================================


:InstallOrUpdatePackages
    call :LogInfo "Upgrading pip..."
    set "PIP_FLAGS=--timeout %PIP_TIMEOUT%"
    if "%QUIET_MODE%"=="TRUE" set "PIP_FLAGS=!PIP_FLAGS! --quiet"
    "!PYTHON_PATH!" -m pip install --upgrade pip !PIP_FLAGS! 2>nul
    call :LogInfo "Upgrading setuptools..."
    "!PYTHON_PATH!" -m pip install --upgrade setuptools !PIP_FLAGS! 2>nul
    call :InstallRequirements
exit /b 0


:InstallRequirements
    if not exist "%REQUIREMENTS_FILE%" (
        call :LogWarn "No requirements file found: %REQUIREMENTS_FILE%"
        exit /b 0
    )
    call :LogInfo "Installing requirements from %REQUIREMENTS_FILE%..."
    set "INSTALL_FLAGS=-r "%REQUIREMENTS_FILE%" --timeout %PIP_TIMEOUT%"
    if "%QUIET_MODE%"=="TRUE" set "INSTALL_FLAGS=!INSTALL_FLAGS! --quiet"
    pip install !INSTALL_FLAGS!
    if !ERRORLEVEL! neq 0 (call :LogError "Failed to install requirements" & exit /b 1)
    call :LogOK "Requirements installed successfully"
exit /b 0


REM ==============================================
REM Execution / Launch
REM ==============================================


:LaunchPythonScript
    if "%PYTHON_SCRIPT%"=="" (call :LogInfo "No Python script specified" & exit /b 0)
    if not exist "%PYTHON_SCRIPT%" (call :LogError "Python script not found: %PYTHON_SCRIPT%" & exit /b 1)
    call :LogInfo "Launching: %PYTHON_SCRIPT%"
    echo.
    python "%PYTHON_SCRIPT%"
    if !ERRORLEVEL! neq 0 (
        call :LogError "Script execution failed with exit code !ERRORLEVEL!"
        exit /b !ERRORLEVEL!
    )
exit /b 0


REM ==============================================
REM Utilities / Logging
REM ==============================================


:LogInfo
    echo %COLOR_INFO%[INFO] %~1%COLOR_RESET%
exit /b 0


:LogOK
    echo %COLOR_OK%[OK] %~1%COLOR_RESET%
exit /b 0


:LogWarn
    echo %COLOR_WARN%[WARN] %~1%COLOR_RESET%
exit /b 0


:LogError
    echo %COLOR_ERROR%[ERROR] %~1%COLOR_RESET%
    if "%AUTO_CLOSE_CONSOLE%"=="TRUE" (
        echo Press any key to exit...
        pause >nul
    )
exit /b 0
