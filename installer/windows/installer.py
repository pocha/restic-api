#!/usr/bin/env python3
"""
Restic API Windows Installer
Handles complete installation of Restic API server on Windows
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
import json
from pathlib import Path

class ResticAPIInstaller:
    def __init__(self):
        self.install_dir = Path.home() / "ResticAPI"
        self.python_url = "https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe"
        self.python_installer = "python_installer.exe"
        
    def log(self, message):
        print(f"[INSTALLER] {message}")
        
    def check_python(self):
        """Check if Python is installed and accessible"""
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Python found: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        self.log("Python not found or not accessible")
        return False
        
    def install_python(self):
        """Download and install Python if not present"""
        if self.check_python():
            return True
            
        self.log("Downloading Python installer...")
        try:
            urllib.request.urlretrieve(self.python_url, self.python_installer)
            self.log("Installing Python (this may take a few minutes)...")
            
            # Install Python silently with pip and add to PATH
            subprocess.run([
                self.python_installer,
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
                "Include_pip=1"
            ], check=True)
            
            os.remove(self.python_installer)
            self.log("Python installation completed")
            return True
            
        except Exception as e:
            self.log(f"Failed to install Python: {e}")
            return False
            
    def create_install_directory(self):
        """Create installation directory"""
        try:
            self.install_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"Installation directory created: {self.install_dir}")
            return True
        except Exception as e:
            self.log(f"Failed to create install directory: {e}")
            return False
            
    def copy_application_files(self):
        """Copy application files to installation directory"""
        try:
            # Files to copy from current directory
            files_to_copy = [
                "app.py",
                "requirements.txt",
                "README.md",
                "start_server.bat"
            ]
            
            current_dir = Path(__file__).parent
            
            for file_name in files_to_copy:
                src = current_dir / file_name
                dst = self.install_dir / file_name
                
                if src.exists():
                    shutil.copy2(src, dst)
                    self.log(f"Copied: {file_name}")
                else:
                    self.log(f"Warning: {file_name} not found")
                    
            return True
            
        except Exception as e:
            self.log(f"Failed to copy application files: {e}")
            return False
            
    def install_dependencies(self):
        """Install Python dependencies"""
        try:
            requirements_file = self.install_dir / "requirements.txt"
            if not requirements_file.exists():
                self.log("Creating requirements.txt...")
                with open(requirements_file, 'w') as f:
                    f.write("flask>=2.0.0\n")
                    f.write("flask-cors>=3.0.0\n")
                    f.write("requests>=2.25.0\n")
            
            self.log("Installing Python dependencies...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", 
                str(requirements_file)
            ], check=True, cwd=str(self.install_dir))
            
            self.log("Dependencies installed successfully")
            return True
            
        except Exception as e:
            self.log(f"Failed to install dependencies: {e}")
            return False
            
    def create_config(self):
        """Create initial configuration file"""
        try:
            config_file = self.install_dir / "config.json"
            if not config_file.exists():
                config = {
                    "restic_version": "NA",
                    "locations": {}
                }
                
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                    
                self.log("Initial configuration created")
            else:
                self.log("Configuration file already exists")
                
            return True
            
        except Exception as e:
            self.log(f"Failed to create configuration: {e}")
            return False
            
    def create_desktop_shortcut(self):
        """Create desktop shortcut"""
        try:
            desktop = Path.home() / "Desktop"
            shortcut_path = desktop / "Restic API Server.bat"
            
            shortcut_content = f'''@echo off
cd /d "{self.install_dir}"
start_server.bat
'''
            
            with open(shortcut_path, 'w') as f:
                f.write(shortcut_content)
                
            self.log("Desktop shortcut created")
            return True
            
        except Exception as e:
            self.log(f"Failed to create desktop shortcut: {e}")
            return False
            
    def run_installation(self):
        """Run the complete installation process"""
        self.log("Starting Restic API installation...")
        self.log("=" * 50)
        
        steps = [
            ("Checking/Installing Python", self.install_python),
            ("Creating installation directory", self.create_install_directory),
            ("Copying application files", self.copy_application_files),
            ("Installing dependencies", self.install_dependencies),
            ("Creating configuration", self.create_config),
            ("Creating desktop shortcut", self.create_desktop_shortcut)
        ]
        
        for step_name, step_func in steps:
            self.log(f"Step: {step_name}")
            if not step_func():
                self.log(f"Installation failed at step: {step_name}")
                return False
            self.log(f"Step completed: {step_name}")
            print()
            
        self.log("=" * 50)
        self.log("Installation completed successfully!")
        self.log(f"Application installed at: {self.install_dir}")
        self.log("You can start the server using the desktop shortcut")
        self.log("or by running start_server.bat in the installation directory")
        
        return True

if __name__ == "__main__":
    installer = ResticAPIInstaller()
    
    try:
        success = installer.run_installation()
        if success:
            input("\nPress Enter to exit...")
        else:
            input("\nInstallation failed. Press Enter to exit...")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
