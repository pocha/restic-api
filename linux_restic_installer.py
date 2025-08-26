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
    root_password = sys.argv[2]
    
    result = install_restic_linux(binary_path, root_password)
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result['output']:
        print(f"Output: {result['output']}")
