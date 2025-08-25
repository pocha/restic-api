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
