@echo off
title Restic API Server
echo ===============================================
echo    Starting Restic API Server
echo ===============================================
echo.
echo Server will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

:: Change to the directory where this script is located
cd /d "%~dp0"

:: Start the Flask application
python app.py

echo.
echo Server stopped.
pause
