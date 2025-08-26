@echo off
title Restic API Installer
echo ===============================================
echo    Restic API Server - Windows Installer
echo ===============================================
echo.
echo This installer will:
echo - Check and install Python if needed
echo - Install Restic API Server
echo - Install all dependencies
echo - Create desktop shortcut
echo.
echo Installation directory: %USERPROFILE%\ResticAPI
echo.
pause

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. The installer will download and install Python.
    echo This may require administrator privileges.
    echo.
    
    :: Download Python installer
    echo Downloading Python 3.11.9...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python-installer.exe'"
    
    if not exist python-installer.exe (
        echo Failed to download Python installer.
        echo Please download Python manually from https://www.python.org/downloads/
        echo and run this installer again.
        pause
        exit /b 1
    )
    
    :: Install Python silently with pip and add to PATH
    echo Installing Python...
    powershell -Command "Start-Process .\python-installer.exe -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tests=0' -NoNewWindow -Wait
    
    ::if %errorlevel% neq 0 (
    ::    echo Python installation failed.
    ::    echo Please install Python manually from https://www.python.org/downloads/
    ::    pause
    ::    exit /b 1
    ::)
    
    :: Clean up installer
    del python-installer.exe
    
    :: Refresh environment variables
    echo Refreshing environment variables...
    call refreshenv.cmd >nul 2>&1 || (
        echo Please restart your command prompt or computer to refresh PATH
        echo Then run this installer again.
        pause
        exit /b 1
    )
    
    echo Python installed successfully!
    pause
)

:: Run the Python installer
echo Starting installation...
python "%~dp0installer.py"

if %errorlevel% neq 0 (
    echo.
    echo Installation failed. Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo Installation completed successfully!
echo You can now start the Restic API Server from the desktop shortcut
echo or by navigating to %USERPROFILE%\ResticAPI and running start_server.bat
echo.
pause
