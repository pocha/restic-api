#!/usr/bin/env python3
"""
Linux Restic Installer Script
Handles installation of restic binary on Linux systems with proper permissions
"""

import os
import sys
import subprocess
import stat
import tempfile

def install_restic_linux(binary_path, root_password):
    """
    Install restic binary on Linux system
    
    Args:
        binary_path (str): Path to the restic binary file
        root_password (str): Root password for sudo operations
    
    Returns:
        dict: Installation result with success status and message
    """
    try:
        # Target installation path
        target_path = '/usr/local/bin/restic'
        
        # Create a temporary script for sudo operations
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as temp_script:
            temp_script.write(f"""#!/bin/bash
# Copy restic binary to target location
cp "{binary_path}" "{target_path}"

# Set proper permissions (executable for all, writable by owner)
chmod 755 "{target_path}"

# Set ownership to root
chown root:root "{target_path}"

echo "Restic binary installed successfully at {target_path}"
""")
            temp_script_path = temp_script.name
        
        # Make the temporary script executable
        os.chmod(temp_script_path, stat.S_IRWXU)
        
        # Execute the script with sudo using the provided password
        sudo_cmd = f'echo "{root_password}" | sudo -S bash {temp_script_path}'
        result = subprocess.run(sudo_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        # Clean up temporary script
        try:
            os.unlink(temp_script_path)
        except:
            pass
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': f'Restic binary installed successfully at {target_path}',
                'output': result.stdout
            }
        else:
            return {
                'success': False,
                'message': f'Failed to install restic binary: {result.stderr}',
                'output': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'message': 'Installation timed out',
            'output': ''
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
        result = subprocess.run(['restic', 'version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return 'NA'
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return 'NA'

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 linux_restic_installer.py <binary_path> <root_password>")
        sys.exit(1)
    
    binary_path = sys.argv[1]

def restic_removal_linux():
    """Remove restic binary on Linux systems"""
    import shutil
    import os
    
    restic_backup_path = None
    if os.path.exists('/usr/bin/restic'):
        restic_backup_path = '/tmp/restic_backup'
        shutil.copy2('/usr/bin/restic', restic_backup_path)
        print(f"   ✅ Backed up to {restic_backup_path}")
    
    # Remove restic binary
    print("🗑️  Removing restic binary...")
    if os.path.exists('/usr/bin/restic'):
        os.system('sudo rm -f /usr/bin/restic')
    if os.path.exists('/usr/local/bin/restic'):
        os.system('sudo rm -f /usr/local/bin/restic')
    
    return restic_backup_path

def download_restic_linux():
    """Download and prepare restic binary for Linux"""
    import tempfile
    import requests
    import bz2
    import shutil
    import stat
    import os
    
    print("⬇️  Downloading latest restic binary from GitHub...")
    releases_url = "https://api.github.com/repos/restic/restic/releases/latest"
    response = requests.get(releases_url)
    if response.status_code != 200:
        print(f"❌ Failed to fetch release info: {response.status_code}")
        return None
    
    release_data = response.json()
    download_url = None
    
    # Find Linux amd64 asset
    for asset in release_data.get('assets', []):
        if 'linux_amd64' in asset['name'] and asset['name'].endswith('.bz2'):
            download_url = asset['browser_download_url']
            filename = asset['name']
            break
    
    if not download_url:
        print("❌ Could not find Linux amd64 binary in latest release")
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
    
    # Extract bz2 file
    print("📦 Extracting binary...")
    extracted_path = os.path.join(temp_dir, 'restic')
    with bz2.BZ2File(archive_path, 'rb') as f_in:
        with open(extracted_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    # Make it executable
    os.chmod(extracted_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    
    return extracted_path

    root_password = sys.argv[2]
    
    result = install_restic_linux(binary_path, root_password)
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result['output']:
        print(f"Output: {result['output']}")
