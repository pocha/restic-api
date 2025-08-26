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
    

def restic_removal_windows():
    """Remove restic binary on Windows systems"""
    import shutil
    import os
    import subprocess
    
    # Common Windows paths for restic
    possible_paths = [
        'C:\\Program Files\\restic\\restic.exe',
        'C:\\Program Files (x86)\\restic\\restic.exe',
        'C:\\Windows\\System32\\restic.exe',
        'C:\\Windows\\restic.exe'
    ]
    
    restic_backup_path = None
    for path in possible_paths:
        if os.path.exists(path):
            restic_backup_path = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'restic_backup.exe')
            shutil.copy2(path, restic_backup_path)
            print(f"   ✅ Backed up to {restic_backup_path}")
            break
    
    # Remove restic binary from all possible locations
    print("🗑️  Removing restic binary...")
    for path in possible_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                print(f"⚠️  Could not remove {path} - permission denied")
    
    # Also remove from PATH if it exists
    try:
        subprocess.run(['where', 'restic'], check=True, capture_output=True)
        print("⚠️  Restic still found in PATH - manual removal may be required")
    except subprocess.CalledProcessError:
        pass  # Not found in PATH, which is good
    
    return restic_backup_path

def download_restic_windows():
    """Download and prepare restic binary for Windows"""
    import tempfile
    import requests
    import zipfile
    import os
    
    print("⬇️  Downloading latest restic binary from GitHub...")
    releases_url = "https://api.github.com/repos/restic/restic/releases/latest"
    response = requests.get(releases_url)
    if response.status_code != 200:
        print(f"❌ Failed to fetch release info: {response.status_code}")
        return None
    
    release_data = response.json()
    download_url = None
    
    # Find Windows amd64 asset
    for asset in release_data.get('assets', []):
        if 'windows_amd64' in asset['name'] and asset['name'].endswith('.zip'):
            download_url = asset['browser_download_url']
            filename = asset['name']
            break
    
    if not download_url:
        print("❌ Could not find Windows amd64 binary in latest release")
        return None
    
    print(f"   📥 Downloading: {filename}")
    
    # Download and extract the binary
    temp_dir = tempfile.mkdtemp()
    archive_path = os.path.join(temp_dir, filename)
    binary_response = requests.get(download_url)
    if binary_response.status_code != 200:
        print(f"❌ Failed to download binary: {binary_response.status_code}")
        return None
    
    with open(archive_path, 'wb') as f:
        f.write(binary_response.content)
    
    # Extract zip file
    print("📦 Extracting binary...")
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    # Find the extracted restic.exe
    extracted_path = os.path.join(temp_dir, 'restic.exe')
    if not os.path.exists(extracted_path):
        # Look for it in subdirectories
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file == 'restic.exe':
                    extracted_path = os.path.join(root, file)
                    break
    
    if not os.path.exists(extracted_path):
        print("❌ Could not find restic.exe in extracted files")
        return None
    
    return extracted_path

    binary_path = sys.argv[1]
    admin_password = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = install_restic_windows(binary_path, admin_password)
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result['output']:
        print(f"Output: {result['output']}")
