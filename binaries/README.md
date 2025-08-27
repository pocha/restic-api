# Restic API Windows Installer

## Package Contents
- `restic-api-windows-installer.zip` - Complete Windows installer package

## Installation Instructions
1. Download `restic-api-windows-installer.zip`
2. Extract the zip file to any directory
3. Check python is installed by running `install_python.bat`. It has to be run in Powershell as Administrator.
4. Run `run_installer_py.bat` to install Restic API server. 

## What the Installer Does
- Checks for Python installation (downloads and installs if needed)
- Creates installation directory at `%USERPROFILE%\ResticAPI`
- Installs all required dependencies
- Creates desktop shortcut for easy access
- Sets up initial configuration

## After Installation
- Use the desktop shortcut "Restic API Server" to start the server
- Or navigate to `%USERPROFILE%\ResticAPI` and run `start_server.bat`
- Server will be available at `http://localhost:5000`

## Testing Note
This installer was created on Linux and has not been tested on Windows systems. 
Users should test the installation process and report any issues.

## Requirements
- Windows 7 or later
- Internet connection (for Python download if needed)
- Administrator privileges may be required for Python installation
