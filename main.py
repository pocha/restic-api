import os
import json
import subprocess
import threading
import time
import re
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from schedule import *
from restic_installer import *
from utils import *

from app_factory import app

def execute_restic_command(command, location_config, password=None):
    """Execute a restic command with proper environment setup"""
    env = os.environ.copy()
    env['RESTIC_REPOSITORY'] = location_config['repository']
    
    if password:
        env['RESTIC_PASSWORD'] = password
    
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return result
    except subprocess.TimeoutExpired:
        raise Exception("Command timed out after 5 minutes")
    except Exception as e:
        raise Exception(f"Failed to execute command: {str(e)}")

def parse_snapshots_output(output):
    """Parse restic snapshots output into structured data"""
    snapshots = []
    lines = output.strip().split('\n')
    
    for line in lines:
        if line.strip() and not line.startswith('repository'):
            # Parse JSON format if available
            try:
                snapshot = json.loads(line)
                snapshots.append({
                    'id': snapshot.get('short_id', snapshot.get('id', '')),
                    'time': snapshot.get('time', ''),
                    'hostname': snapshot.get('hostname', ''),
                    'paths': snapshot.get('paths', []),
                    'tags': snapshot.get('tags', [])
                })
            except json.JSONDecodeError:
                # Fallback to text parsing
                parts = line.split()
                if len(parts) >= 4:
                    snapshots.append({
                        'id': parts[0],
                        'time': ' '.join(parts[1:3]),
                        'hostname': parts[3] if len(parts) > 3 else '',
                        'paths': parts[4:] if len(parts) > 4 else [],
                        'tags': []
                    })
    
    return snapshots

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('basic-web-ui', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('basic-web-ui', filename)

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = load_config()
    return jsonify(config)

@app.route('/locations/<location_id>/init', methods=['POST'])
def init_location(location_id):
    """Initialize a new restic repository"""
    try:
        data = request.get_json()
        repository = data.get('repository')
        password = get_password_from_header()
        
        if not repository or not password:
            return jsonify({'error': 'Repository and password are required'}), 400
        
        # Create location config
        location_config = {
            'repository': repository,
            'name': data.get('name', location_id)
        }
        
        # Initialize repository
        result = execute_restic_command(['restic', 'init'], location_config, password)
        
        if result.returncode == 0:
            # Save location to config
            config = load_config()
            config['locations'][location_id] = location_config
            save_config(config)
            
            return jsonify({'message': 'Repository initialized successfully'})
        else:
            return jsonify({'error': result.stderr or 'Failed to initialize repository'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/backups', methods=['GET'])
def list_backups(location_id):
    """List all backups for a location"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        location_config = config['locations'][location_id]
        password = get_password_from_header()
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        # List snapshots
        result = execute_restic_command(['restic', 'snapshots', '--json'], location_config, password)
        
        if result.returncode == 0:
            try:
                snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                return jsonify({'snapshots': snapshots})
            except json.JSONDecodeError:
                # Fallback to text parsing
                snapshots = parse_snapshots_output(result.stdout)
                return jsonify({'snapshots': snapshots})
        else:
            return jsonify({'error': result.stderr or 'Failed to list backups'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_backup_stream(location_id, backup_data, password):
    """Generate streaming backup output"""
    try:
        config = load_config()
        location_config = config['locations'][location_id]
        
        # Prepare restic command based on backup type
        if backup_data.get('type') == 'command':
            command = backup_data.get('command', '')
            filename = backup_data.get('filename', 'command-output')
            
            # Split command into arguments
            command_args = command.split()
            
            restic_cmd = [
                'restic', 'backup',
                '--stdin-from-command', *command_args,
                '--stdin-filename', filename,
                '--json'
            ]
        else:
            path = backup_data.get('path', '')
            if not os.path.exists(path):
                yield f'data: {{"error": "Path {path} does not exist"}}\n\n'
                return
            
            restic_cmd = ['restic', 'backup', path, '--json']
        
        # Add tags if provided
        tags = backup_data.get('tags', [])
        if tags:
            for tag in tags:
                restic_cmd.extend(['--tag', tag])
        
        # Set up environment
        env = os.environ.copy()
        env['RESTIC_REPOSITORY'] = location_config['repository']
        env['RESTIC_PASSWORD'] = password
        
        # Start the backup process
        process = subprocess.Popen(
            restic_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        snapshot_id = None
        success = False
        
        # Stream output
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                if line:
                    try:
                        # Try to parse as JSON
                        data = json.loads(line)
                        if data.get('message_type') == 'summary':
                            snapshot_id = data.get('snapshot_id')
                            success = True
                        yield f'data: {json.dumps(data)}\n\n'
                    except json.JSONDecodeError:
                        # Send as plain text
                        yield f'data: {{"message": "{line}"}}\n\n'
        
        # Wait for process to complete
        process.wait()
        
        # Send completion status
        yield f'data: {{"completed": true, "success": {str(success).lower()}, "snapshot_id": "{snapshot_id}"}}\n\n'
        
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'

@app.route('/locations/<location_id>/backups', methods=['POST'])
def create_backup(location_id):
    """Create a new backup"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        data = request.get_json()
        
        # Get password from key or header
        password = None
        if 'key' in data:
            password = get_password_from_key(data['key'])
            if not password:
                return jsonify({'error': 'Invalid key or password not found'}), 400
        else:
            password = get_password_from_header()
            if not password:
                return jsonify({'error': 'Password is required'}), 400
        
        # Return streaming response
        return Response(
            generate_backup_stream(location_id, data, password),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/backups/<snapshot_id>/contents', methods=['GET'])
def list_backup_contents(location_id, snapshot_id):
    """List contents of a backup"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        location_config = config['locations'][location_id]
        password = get_password_from_header()
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        # List backup contents
        result = execute_restic_command(['restic', 'ls', snapshot_id, '--json'], location_config, password)
        
        if result.returncode == 0:
            contents = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        item = json.loads(line)
                        contents.append(item)
                    except json.JSONDecodeError:
                        contents.append({'path': line, 'type': 'unknown'})
            
            return jsonify({'contents': contents})
        else:
            return jsonify({'error': result.stderr or 'Failed to list backup contents'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_restore_stream(location_id, snapshot_id, restore_data, password):
    """Generate streaming restore output"""
    try:
        config = load_config()
        location_config = config['locations'][location_id]
        
        target_path = restore_data.get('target_path', '/tmp/restore')
        include_patterns = restore_data.get('include', [])
        exclude_patterns = restore_data.get('exclude', [])
        
        # Prepare restic restore command
        restic_cmd = ['restic', 'restore', snapshot_id, '--target', target_path]
        
        # Add include patterns
        for pattern in include_patterns:
            restic_cmd.extend(['--include', pattern])
        
        # Add exclude patterns
        for pattern in exclude_patterns:
            restic_cmd.extend(['--exclude', pattern])
        
        # Set up environment
        env = os.environ.copy()
        env['RESTIC_REPOSITORY'] = location_config['repository']
        env['RESTIC_PASSWORD'] = password
        
        # Start the restore process
        process = subprocess.Popen(
            restic_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Stream output
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                if line:
                    yield f'data: {{"message": "{line}"}}\n\n'
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Send completion status
        success = return_code == 0
        yield f'data: {{"completed": true, "success": {str(success).lower()}}}\n\n'
        
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'

@app.route('/locations/<location_id>/backups/<snapshot_id>/restore', methods=['POST'])
def restore_backup(location_id, snapshot_id):
    """Restore a backup"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        data = request.get_json()
        password = get_password_from_header()
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        # Return streaming response
        return Response(
            generate_restore_stream(location_id, snapshot_id, data, password),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
