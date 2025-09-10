import os
import subprocess
import requests
import json
import platform
import zipfile
import tarfile
import shutil
from flask import jsonify, request
from main import app

def get_latest_restic_version():
    """Get the latest restic version from GitHub API"""
    try:
        response = requests.get('https://api.github.com/repos/restic/restic/releases/latest')
        if response.status_code == 200:
            return response.json()['tag_name'].lstrip('v')
        return None
    except Exception as e:
        print(f"Error getting latest restic version: {e}")
        return None

def get_current_restic_version():
    """Get the currently installed restic version"""
    try:
        result = subprocess.run(['restic', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            # Parse version from output like "restic 0.16.4 compiled with go1.21.8 on linux/amd64"
            version_line = result.stdout.strip().split('\n')[0]
            version = version_line.split()[1]
            return version
        return None
    except Exception as e:
        print(f"Error getting current restic version: {e}")
        return None

def download_and_install_restic(version=None):
    """Download and install restic"""
    try:
        if not version:
            version = get_latest_restic_version()
            if not version:
                raise Exception("Could not determine latest restic version")
        
        # Determine platform and architecture
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Map platform names
        if system == 'darwin':
            system = 'darwin'
        elif system == 'windows':
            system = 'windows'
        else:
            system = 'linux'
        
        # Map architecture names
        if machine in ['x86_64', 'amd64']:
            arch = 'amd64'
        elif machine in ['aarch64', 'arm64']:
            arch = 'arm64'
        elif machine.startswith('arm'):
            arch = 'arm'
        else:
            arch = '386'
        
        # Construct download URL
        if system == 'windows':
            filename = f'restic_{version}_{system}_{arch}.zip'
        else:
            filename = f'restic_{version}_{system}_{arch}.bz2'
        
        url = f'https://github.com/restic/restic/releases/download/v{version}/{filename}'
        
        # Download the file
        print(f"Downloading restic {version} from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Save to temporary file
        temp_file = f'/tmp/{filename}'
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Extract and install
        if system == 'windows':
            # Extract ZIP file
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall('/tmp')
            binary_path = f'/tmp/restic.exe'
            install_path = '/usr/local/bin/restic.exe'
        else:
            # Extract bz2 file
            with tarfile.open(temp_file, 'r:bz2') as tar_ref:
                tar_ref.extractall('/tmp')
            binary_path = f'/tmp/restic_{version}_{system}_{arch}/restic'
            install_path = '/usr/local/bin/restic'
        
        # Make binary executable and move to install location
        os.chmod(binary_path, 0o755)
        shutil.move(binary_path, install_path)
        
        # Clean up
        os.remove(temp_file)
        if system != 'windows':
            shutil.rmtree(f'/tmp/restic_{version}_{system}_{arch}', ignore_errors=True)
        
        print(f"Restic {version} installed successfully")
        return True
        
    except Exception as e:
        print(f"Error installing restic: {e}")
        return False

@app.route('/restic/version', methods=['GET'])
def get_restic_version():
    """Get current and latest restic versions"""
    try:
        current_version = get_current_restic_version()
        latest_version = get_latest_restic_version()
        
        return jsonify({
            'current_version': current_version,
            'latest_version': latest_version,
            'update_available': current_version != latest_version if current_version and latest_version else False
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restic/update', methods=['POST'])
def update_restic():
    """Update restic to the latest version"""
    try:
        current_version = get_current_restic_version()
        latest_version = get_latest_restic_version()
        
        if not latest_version:
            return jsonify({'error': 'Could not determine latest version'}), 500
        
        if current_version == latest_version:
            return jsonify({'message': 'Restic is already up to date', 'version': current_version})
        
        success = download_and_install_restic(latest_version)
        
        if success:
            new_version = get_current_restic_version()
            return jsonify({
                'message': 'Restic updated successfully',
                'old_version': current_version,
                'new_version': new_version
            })
        else:
            return jsonify({'error': 'Failed to update restic'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restic/install', methods=['POST'])
def install_restic():
    """Install restic"""
    try:
        success = download_and_install_restic()
        
        if success:
            version = get_current_restic_version()
            return jsonify({
                'message': 'Restic installed successfully',
                'version': version
            })
        else:
            return jsonify({'error': 'Failed to install restic'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_directory_size(path):
    """Get the size of a directory in bytes"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, IOError):
                    # Skip files that can't be accessed
                    continue
    except Exception as e:
        print(f"Error calculating directory size: {e}")
        return 0
    
    return total_size

@app.route('/directory-size', methods=['POST'])
def get_directory_size_endpoint():
    """Get the size of a directory"""
    try:
        data = request.get_json()
        path = data.get('path')
        
        if not path:
            return jsonify({'error': 'Path is required'}), 400
        
        if not os.path.exists(path):
            return jsonify({'error': 'Path does not exist'}), 404
        
        if not os.path.isdir(path):
            return jsonify({'error': 'Path is not a directory'}), 400
        
        size_bytes = get_directory_size(path)
        
        # Convert to human readable format
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} PB"
        
        return jsonify({
            'path': path,
            'size_bytes': size_bytes,
            'size_formatted': format_bytes(size_bytes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
