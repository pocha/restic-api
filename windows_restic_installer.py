#!/usr/bin/env python3
"""
Windows Restic Installer Script
Handles installation of restic binary on Windows systems
"""

import os
import sys
import subprocess
import shutil
import tempfile
import platform

def install_restic_windows(binary_path, admin_password=None):
    """
    Install restic binary on Windows system
    
    Args:
        binary_path (str): Path to the restic.exe binary file
        admin_password (str): Admin password (optional, for future use)
    
    Returns:
        dict: Installation result with success status and message
    """
    try:
        # Target installation paths (try multiple common locations)
        possible_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'restic'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'restic'),
            os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'restic')
        ]
        
        target_dir = None
        target_path = None
        
        # Try to find a writable location
        for path in possible_paths:
            try:
                os.makedirs(path, exist_ok=True)
                test_file = os.path.join(path, 'test_write.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                target_dir = path
                target_path = os.path.join(path, 'restic.exe')
                break
            except (PermissionError, OSError):
                continue
        
        if not target_dir:
            return {
                'success': False,
                'message': 'Could not find a writable directory for installation',
                'output': ''
            }
        
        # Copy the binary to target location
        shutil.copy2(binary_path, target_path)
        
        # Add to PATH if not already there
        path_env = os.environ.get('PATH', '')
        if target_dir not in path_env:
            # Note: This only affects the current process
            # For persistent PATH changes, we'd need registry modifications
            os.environ['PATH'] = f"{target_dir};{path_env}"
        
        return {
            'success': True,
            'message': f'Restic binary installed successfully at {target_path}',
            'output': f'Installation directory: {target_dir}'
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Installation failed: {str(e)}',
            'output': ''
        }

def get_restic_version():
    """
    Get the version of installed restic binary
    
    Returns:
        str: Version string or 'NA' if not available
    """
    try:
        # Try different possible restic command names
        commands = ['restic.exe', 'restic']
        
        for cmd in commands:
            try:
                result = subprocess.run([cmd, 'version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return result.stdout.strip()
            except FileNotFoundError:
                continue
        
        return 'NA'
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return 'NA'

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python windows_restic_installer.py <binary_path> [admin_password]")
        sys.exit(1)
    
    binary_path = sys.argv[1]
    admin_password = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = install_restic_windows(binary_path, admin_password)
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result['output']:
        print(f"Output: {result['output']}")
