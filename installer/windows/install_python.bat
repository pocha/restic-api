@echo off
title Restic API Installer
echo ===============================================
echo  Python for Restic API Server - Windows Installer
echo ===============================================
echo.
echo This installer will:
echo - Check and install Python if needed
pause

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. The installer will download and install Python.
    echo This may require administrator privileges.
    echo.
    
    if not exist python-installer.exe (
      :: Download Python installer
      echo Downloading Python 3.11.9...
      powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python-installer.exe'"
    )
    if not exist python-installer.exe (
        echo Failed to download Python installer.
        echo Please download Python manually from https://www.python.org/downloads/
        echo and run this installer again.
        pause
        exit /b 1
    )
    
    :: Install Python silently with pip and add to PATH
    echo Installing Python...
    powershell -Command "Start-Process -FilePath '.\python-installer.exe' -ArgumentList 'InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0 Include_doc=0' -Wait"
	
  
    echo Python installed successfully! Run run_installer_py.bat file next.
    pause
    exit /b 0
)
echo Python is already installed. Run run_installer_py.bat file next
pause