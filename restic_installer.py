import os
import subprocess
import requests
import json
import platform
import zipfile
import tarfile
import shutil
from flask import jsonify, request
from app_factory import app
from utils import load_config, save_config

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

@app.route('/size', methods=['GET'])
def get_directory_size():
    """Get directory size information"""
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'Path parameter is required'}), 400
    
    try:
        import shutil
        import os
        
        # Get total and used space for the path
        if os.path.exists(path):
            # Get directory size (used space)
            if os.path.isdir(path):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, IOError):
                            # Skip files that can't be accessed
                            continue
                used_space = total_size
            else:
                # Single file
                used_space = os.path.getsize(path)
            
            # Get total disk space for the filesystem containing this path
            total_space, used_disk, free_space = shutil.disk_usage(path)
            
            return jsonify({
                'path': path,
                'used': used_space,
                'total': total_space,
                'free': free_space,
                'used_disk': used_disk
            })
        else:
            return jsonify({'error': 'Path does not exist'}), 404
            
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


@app.route('/config/update_restic', methods=['POST'])
def update_restic():
    """Update restic binary and version in configuration with cross-platform support"""
    try:
        import platform
        import tempfile
        
        # Get root/admin password if provided
        root_password = request.form.get('root_password', '')
        
        # Check if a file was uploaded
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Detect platform
            current_platform = platform.system().lower()
            
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix='.exe' if current_platform == 'windows' else '') as temp_file:
                file.save(temp_file.name)
                temp_binary_path = temp_file.name
            
            try:
                # Install using platform-specific installer
                if current_platform == 'linux':
                    if not root_password:
                        return jsonify({'error': 'Root password required for Linux installation'}), 400
                    
                    # Import and use Linux installer
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("linux_installer", "restic_installer_scripts/linux.py")
                    linux_installer = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(linux_installer)
                    
                    result = linux_installer.install_restic_linux(temp_binary_path, root_password)
                    
                elif current_platform == 'windows':
                    # Import and use Windows installer
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("windows_installer", "restic_installer_scripts/windows.py")
                    windows_installer = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(windows_installer)
                    
                    result = windows_installer.install_restic_windows(temp_binary_path, root_password if root_password else None)
                    
                else:
                    return jsonify({'error': f'Unsupported platform: {current_platform}'}), 400
                
                # Check installation result
                if not result['success']:
                    return jsonify({'error': result['message']}), 500
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_binary_path)
                except:
                    pass
        
        # Get restic version (works for both platforms)
        try:
            # Try different command variations
            commands = ['restic', 'restic.exe'] if platform.system().lower() == 'windows' else ['restic']
            version_output = 'NA'
            
            for cmd in commands:
                try:
                    result = subprocess.run([cmd, 'version'], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        version_output = result.stdout.strip()
                        break
                except FileNotFoundError:
                    continue
                    
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            version_output = 'NA'
        
        # Update config with version
        config = load_config()
        config['restic_version'] = version_output
        save_config(config)
        
        return jsonify({
            'message': 'Restic version updated successfully',
            'restic_version': version_output,
            'platform': platform.system().lower()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500