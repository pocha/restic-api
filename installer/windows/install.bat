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
    pause
)

:: Run the Python installer
echo Starting installation...
python installer.py

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
