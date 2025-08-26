#!/usr/bin/env python3
import requests
import json
import os
import tempfile
import shutil
import time
import subprocess
import signal
import sys
from pathlib import Path

# Test configuration
BASE_URL = 'http://localhost:5000'
SERVER_PROCESS = None

def start_server():
    """Start the Flask server in background"""
    global SERVER_PROCESS
    print("🚀 Starting Restic API server...")
    
    # Start server in background
    SERVER_PROCESS = subprocess.Popen(
        ['python3', 'app.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    
    # Wait for server to start
    for i in range(10):
        try:
            response = requests.get(f'{BASE_URL}/config', timeout=2)
            print("✅ Server started successfully!")
            return True
        except:
            time.sleep(1)
    
    print("❌ Failed to start server")
    return False

def stop_server():
    """Stop the Flask server"""
    global SERVER_PROCESS
    if SERVER_PROCESS:
        print("🛑 Stopping server...")
        os.killpg(os.getpgid(SERVER_PROCESS.pid), signal.SIGTERM)
        SERVER_PROCESS = None

def cleanup_handler(signum, frame):
    """Handle cleanup on exit"""
    stop_server()
    sys.exit(0)

def api_call(method, endpoint, data=None, stream=False):
    """Make API call with error handling"""
    url = f'{BASE_URL}{endpoint}'
    try:
        if method == 'GET':
            response = requests.get(url, stream=stream)
        elif method == 'POST':
            response = requests.post(url, json=data, stream=stream)
        elif method == 'PUT':
            response = requests.put(url, json=data, stream=stream)
        
        if stream:
            return response
        
        print(f"📡 {method} {endpoint}: {response.status_code}")
        if response.headers.get('content-type', '').startswith('application/json'):
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"   Response: {response.text}")
            return response.text
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API call failed: {e}")
        return None

def stream_output(response):
    """Stream and display real-time output"""
    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line.decode('utf-8'))
                if data.get('type') == 'output':
                    print(f"   📊 {data.get('data', '').strip()}")
                elif data.get('type') == 'error':
                    print(f"   ❌ {data.get('data', '').strip()}")
                elif data.get('type') == 'complete':
                    print(f"   ✅ Command completed with exit code: {data.get('exit_code', 'unknown')}")
                    return data.get('exit_code', 0)
            except json.JSONDecodeError:
                print(f"   📝 {line.decode('utf-8').strip()}")
    return 0

def create_test_files(directory):
    """Create test files in the given directory"""
    files_created = []
    
    # Create some test files with different content
    test_files = [
        ('document.txt', 'This is a test document with important data.'),
        ('config.json', '{"setting1": "value1", "setting2": "value2"}'),
        ('data.csv', 'name,age,city\nJohn,30,NYC\nJane,25,LA'),
        ('script.py', 'print("Hello, World!")\nprint("This is a backup test")'),
    ]
    
    # Create a subdirectory with files
    subdir = os.path.join(directory, 'subdir')
    os.makedirs(subdir, exist_ok=True)
    
    for filename, content in test_files:
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        files_created.append(filepath)
        
        # Also create a file in subdirectory
        sub_filepath = os.path.join(subdir, f'sub_{filename}')
        with open(sub_filepath, 'w') as f:
            f.write(f'Subdirectory version of {filename}\n{content}')
        files_created.append(sub_filepath)
    
    return files_created

def compare_directories(dir1, dir2):
    """Compare two directories recursively"""
    print(f"🔍 Comparing directories:")
    print(f"   Original: {dir1}")
    print(f"   Restored: {dir2}")
    
    def get_dir_structure(directory):
        structure = {}
        for root, dirs, files in os.walk(directory):
            rel_root = os.path.relpath(root, directory)
            if rel_root == '.':
                rel_root = ''
            
            for file in files:
                rel_path = os.path.join(rel_root, file) if rel_root else file
                full_path = os.path.join(root, file)
                with open(full_path, 'r') as f:
                    structure[rel_path] = f.read()
        return structure
    
    struct1 = get_dir_structure(dir1)
    struct2 = get_dir_structure(dir2)
    
    # Compare structures
    if set(struct1.keys()) != set(struct2.keys()):
        print("❌ Directory structures don't match!")
        print(f"   Original files: {sorted(struct1.keys())}")
        print(f"   Restored files: {sorted(struct2.keys())}")
        return False
    
    # Compare file contents
    for file_path in struct1:
        if struct1[file_path] != struct2[file_path]:
            print(f"❌ File content mismatch: {file_path}")
            return False
    
    print("✅ Directories match perfectly!")
    return True


def restic_removal_linux():
    """Remove restic binary on Linux systems"""
    import shutil
    
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

def restic_removal_windows():
    """Remove restic binary on Windows systems"""
    import shutil
    
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
    import subprocess
    try:
        subprocess.run(['where', 'restic'], check=True, capture_output=True)
        print("⚠️  Restic still found in PATH - manual removal may be required")
    except subprocess.CalledProcessError:
        pass  # Not found in PATH, which is good
    
    return restic_backup_path

def download_restic_linux():
    """Download and prepare restic binary for Linux"""
    import tempfile
    import requests
    import bz2
    import shutil
    import stat
    
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

def download_restic_windows():
    """Download and prepare restic binary for Windows"""
    import tempfile
    import requests
    import zipfile
    
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

def test_restic_installation():
    """Test restic binary installation functionality"""
    print("\n🔧 Testing Restic Installation...")
    print("=" * 40)
    
    try:
        import platform
        import tempfile
        import requests
        import shutil
        
        # Detect the operating system
        current_os = platform.system().lower()
        print(f"🖥️  Detected OS: {current_os}")
        
        restic_backup_path = None
        extracted_path = None
        
        # Step 1: Remove existing restic binary (platform-specific)
        print("📦 Backing up and removing existing restic binary...")
        if current_os == 'linux':
            restic_backup_path = restic_removal_linux()
        elif current_os == 'windows':
            restic_backup_path = restic_removal_windows()
        else:
            print(f"⚠️  Unsupported OS: {current_os}")
            return False
        
        # Step 2: Test that API returns 'NA' for restic version
        print("🔍 Testing API returns 'NA' when restic is not installed...")
        result = api_call('POST', '/config/update_restic', {})
        if not result or result.get('restic_version') != 'NA':
            print(f"❌ Expected 'NA' but got: {result.get('restic_version') if result else 'No result'}")
            return False
        print("✅ API correctly returns 'NA' when restic is not installed")
        
        # Step 3: Download latest binary from GitHub releases (platform-specific)
        if current_os == 'linux':
            extracted_path = download_restic_linux()
        elif current_os == 'windows':
            extracted_path = download_restic_windows()
        
        if not extracted_path:
            print("❌ Failed to download and extract restic binary")
            return False
        
        # Step 4: Test installation via API
        print("🚀 Testing installation via /config/update_restic API...")
        
        with open(extracted_path, 'rb') as binary_file:
            files = {'file': ('restic', binary_file, 'application/octet-stream')}
            data = {'root_password': 'nonbios'}  # Using the user's password
            
            response = requests.post(f'{BASE_URL}/config/update_restic', files=files, data=data)
            
            if response.status_code != 200:
                print(f"❌ Installation API call failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
            result = response.json()
            print(f"✅ Installation successful: {result.get('message', 'Unknown')}")
        
        # Step 5: Verify the version is correctly updated
        print("✅ Verifying installation...")
        result = api_call('POST', '/config/update_restic', {})
        if not result or result.get('restic_version') == 'NA':
            print(f"❌ Installation verification failed. Version: {result.get('restic_version') if result else 'No result'}")
            return False
        
        print(f"✅ Restic successfully installed! Version: {result.get('restic_version')}")
        return True
        
    except Exception as e:
        print(f"❌ Restic installation test failed: {str(e)}")
        return False
    
    finally:
        # Clean up temporary files
        if extracted_path and os.path.exists(extracted_path):
            try:
                temp_dir = os.path.dirname(extracted_path)
                shutil.rmtree(temp_dir)
                print("🧹 Cleaned up temporary files")
            except Exception as e:
                print(f"⚠️  Warning: Could not clean up temporary files: {e}")
        
        # Restore original binary if we backed it up (platform-specific)
        if restic_backup_path and os.path.exists(restic_backup_path):
            print("🔄 Restoring original restic binary...")
            try:
                current_os = platform.system().lower()
                if current_os == 'linux':
                    os.system(f'sudo cp {restic_backup_path} /usr/bin/restic')
                    os.system('sudo chmod 755 /usr/bin/restic')
                    os.remove(restic_backup_path)
                elif current_os == 'windows':
                    # Try to restore to the most common location
                    target_path = 'C:\\Program Files\\restic\\restic.exe'
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(restic_backup_path, target_path)
                    os.remove(restic_backup_path)
                print("✅ Original binary restored")
            except Exception as e:
                print(f"⚠️  Warning: Could not restore original binary: {e}")

def main():
    """Main end-to-end test function"""
    print("🧪 Starting End-to-End Restic API Test")
    print("=" * 50)
    
    # Set up signal handler for cleanup
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    try:
        # Step 1: Start server
        if not start_server():
            return False
        
        # Step 1.5: Test restic installation
        print("\n🔧 Testing restic installation...")
        if not test_restic_installation():
            return False
        
        # Step 2: Create temporary directories in /tmp
        print("\n📁 Creating temporary directories in /tmp...")
        import tempfile
        
        # Create temporary directories in /tmp
        repo_dir = tempfile.mkdtemp(prefix='restic_repo_', dir='/tmp')
        backup_dir = tempfile.mkdtemp(prefix='backup_source_', dir='/tmp')
        restore_dir = tempfile.mkdtemp(prefix='restore_target_', dir='/tmp')
        
        # Set proper permissions
        os.chmod(repo_dir, 0o755)
        os.chmod(backup_dir, 0o755)
        os.chmod(restore_dir, 0o755)
        
        
        print(f"   Repository: {repo_dir}")
        print(f"   Backup source: {backup_dir}")
        print(f"   Restore target: {restore_dir}")
        
        # Step 3: Update restic version in configuration
        print("\n⚙️  Setting up configuration...")
        
        # Use the new /config/update_restic API to set restic version
        result = api_call('POST', '/config/update_restic', {})
        if not result or 'restic_version' not in str(result):
            print("❌ Failed to update restic configuration")
            return False
        print(f"✅ Restic version updated: {result.get('restic_version', 'Unknown')}")
        
        # Step 4: Initialize repository
        print("\n🏗️  Initializing repository...")
        init_data = {
            'location': repo_dir,
            'password': 'test_password_123'
        }
        response = requests.post(f'{BASE_URL}/locations', json=init_data)
        if response.status_code != 200:
            print(f"❌ Failed to initialize repository: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        location_id = result.get('location_id')
        if not location_id:
            print("❌ No location_id returned from initialization")
            return False
        
        print(f"✅ Repository initialized with location_id: {location_id}")
        
        # Step 5: Create test files
        print("\n📝 Creating test files...")
        test_files = create_test_files(backup_dir)
        print(f"   Created {len(test_files)} test files")
        
        # List created files
        for file_path in test_files:
            rel_path = os.path.relpath(file_path, backup_dir)
            size = os.path.getsize(file_path)
            print(f"   📄 {rel_path} ({size} bytes)")
        
        # Step 6: Create backup
        backup_data = {
            'path': backup_dir
        }
        
        headers = {'X-Restic-Password': 'test_password_123'}
        response = requests.post(f'{BASE_URL}/locations/{location_id}/backups', json=backup_data, headers=headers, stream=True)
        if response.status_code != 200:
            print(f"❌ Failed to start backup: {response.status_code}")
            return False
        
        exit_code = stream_output(response)
        if exit_code != 0:
            print("❌ Backup failed")
            return False
        
        
        # Step 6.1: Verify config was updated with backup path
        print("\n🔍 Verifying config was updated with backup path...")
        response = requests.get(f'{BASE_URL}/config')
        if response.status_code != 200:
            print(f"❌ Failed to get config: {response.status_code}")
            return False
        
        config = response.json()
        if location_id not in config.get('locations', {}):
            print(f"❌ Location {location_id} not found in config")
            return False
        
        location_config = config['locations'][location_id]
        if 'paths' not in location_config:
            print(f"❌ Paths field not found in location config")
            return False
        
        if backup_dir not in location_config['paths']:
            print(f"❌ Backup path {backup_dir} not found in config paths: {location_config['paths']}")
            return False
        
        print(f"✅ Config updated successfully - backup path {backup_dir} found in paths")
        
        # Step 7: List snapshots to verify backup
        print("\n📋 Listing snapshots...")
        headers = {'X-Restic-Password': 'test_password_123'}
        response = requests.get(f'{BASE_URL}/locations/{location_id}/backups', headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to list snapshots: {response.status_code}")
            return False
        
        snapshots = response.json()
        if not snapshots or not isinstance(snapshots, list):
            print("❌ Failed to list snapshots")
            return False
        
        snapshot_list = snapshots
        if not snapshot_list:
            print("❌ No snapshots found")
            return False
        
        latest_snapshot = snapshot_list[0]  # Most recent snapshot
        snapshot_id = latest_snapshot['snapshot_id']
        print(f"   📸 Found snapshot: {snapshot_id}")
        print(f"   📅 Created: {latest_snapshot['date']}")
        print(f"   🏷️  Tags: {latest_snapshot.get('tags', [])}")
        
        # Step 8: Rename (simulate deletion) of original directory
        print("\n🔄 Simulating data loss (renaming original directory)...")
        backup_dir_renamed = f"{backup_dir}_original"
        os.rename(backup_dir, backup_dir_renamed)
        print(f"   Renamed {backup_dir} to {backup_dir_renamed}")
        
        # Step 9: List backup contents with recursive option
        print("\n📂 Listing backup contents (recursive)...")
        headers = {'X-Restic-Password': 'test_password_123'}
        response = requests.get(f'{BASE_URL}/locations/{location_id}/backups/{snapshot_id}?recursive=true', headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to list backup contents: {response.status_code}")
            return False
        
        backup_contents = response.json()
        print(f"   📁 Found {len(backup_contents)} items in backup:")
        for item in backup_contents[:10]:  # Show first 10 items
            item_type = "📁" if item.get('type') == 'dir' else "📄"
            size_info = f" ({item.get('size', 0)} bytes)" if item.get('type') == 'file' else ""
            print(f"   {item_type} {item.get('path', item.get('name', 'unknown'))}{size_info}")
        if len(backup_contents) > 10:
            print(f"   ... and {len(backup_contents) - 10} more items")
        
        # Step 10: Restore backup
        print("\n🔄 Restoring backup...")
        restore_data = {
            'target': restore_dir
        }
        
        headers = {'X-Restic-Password': 'test_password_123'}
        response = requests.post(f'{BASE_URL}/locations/{location_id}/backups/{snapshot_id}/restore', json=restore_data, headers=headers, stream=True)
        if response.status_code != 200:
            print(f"❌ Failed to start restore: {response.status_code}")
            return False
        
        exit_code = stream_output(response)
        if exit_code != 0:
            print("❌ Restore failed")
            return False
        
        # Step 11: Compare original and restored directories
        print("\n🔍 Comparing original and restored data...")
        
        # The restored directory will have the full path structure
        # Find the actual restored content
        restored_content_dir = None
        for root, dirs, files in os.walk(restore_dir):
            if os.path.basename(root) == os.path.basename(backup_dir):
                restored_content_dir = root
                break
        
        if not restored_content_dir:
            # If not found, the content might be directly in restore_dir
            restored_content_dir = restore_dir
        
        success = compare_directories(backup_dir_renamed, restored_content_dir)
        
        # Step 12: Cleanup
        print("\n🧹 Cleaning up...")
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(backup_dir_renamed, ignore_errors=True)
        shutil.rmtree(restore_dir, ignore_errors=True)
        print("   Temporary directories cleaned up")
        
        # Final result
        print("\n" + "=" * 50)
        if success:
            print("🎉 END-TO-END TEST PASSED! 🎉")
            print("✅ All operations completed successfully")
            print("✅ Data integrity verified")
            return True
        else:
            print("❌ END-TO-END TEST FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False
    
    finally:
        stop_server()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
