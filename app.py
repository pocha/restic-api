import os
import json
import subprocess
import threading
import time
import re
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CONFIG_FILE = os.path.expanduser('~/config.json')

# Helper Functions
def load_config():
    """Load configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'restic_version': '', 'locations': {}, 'paths': []}

def save_config(config):
    """Save configuration to config.json"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_password_from_header():
    """Extract restic password from request header"""
    password = request.headers.get('X-Restic-Password')
    if not password:
        return None, {'error': 'X-Restic-Password header is required'}, 400
    return password, None, None

def execute_restic_command(cmd, env_vars=None, stream_output=False):
    """Execute restic command with optional streaming"""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    
    if stream_output:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env
        )
        return process
    else:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env
        )
        return result

def parse_snapshots_output(output):
    """Parse restic snapshots output to extract snapshot info"""
    snapshots = []
    lines = output.strip().split('\n')
    
    for line in lines[2:]:  # Skip header lines
        if line.strip():
            parts = line.split()
            if len(parts) >= 4:
                snapshot_id = parts[0]
                date_str = ' '.join(parts[1:3])
                # Try to find size info (may not always be present)
                size = 'N/A'
                for part in parts[3:]:
                    if 'B' in part or 'KB' in part or 'MB' in part or 'GB' in part:
                        size = part
                        break
                
                snapshots.append({
                    'snapshot_id': snapshot_id,
                    'date': date_str,
                    'size': size
                })
    
    return snapshots

# API Endpoints

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        config = load_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        config = load_config()
        config.update(data)
        save_config(config)
        
        return jsonify({'message': 'Configuration updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations', methods=['POST'])
def init_location():
    """Initialize a new restic repository location"""
    try:
        data = request.get_json()
        if not data or 'location' not in data or 'password' not in data:
            return jsonify({'error': 'location and password are required'}), 400
        
        location = data['location']
        password = data['password']
        
        # Initialize restic repository
        cmd = ['restic', 'init', '--repo', location]
        env_vars = {'RESTIC_PASSWORD': password}
        
        result = execute_restic_command(cmd, env_vars)
        
        if result.returncode != 0:
            return jsonify({'error': f'Failed to initialize repository: {result.stderr}'}), 500
        
        # Update config with new location
        config = load_config()
        if 'locations' not in config:
            config['locations'] = {}
        
        # Generate a location ID (use the last part of the path)
        location_id = os.path.basename(location.rstrip('/'))
        config['locations'][location_id] = location
        save_config(config)
        
        return jsonify({
            'message': 'Repository initialized successfully',
            'location_id': location_id,
            'location': location
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/backups', methods=['GET'])
def list_backups(location_id):
    """List all backups for a location"""
    try:
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        repo_path = config['locations'][location_id]
        path_filter = request.args.get('path', '')
        
        # Build restic snapshots command
        cmd = ['restic', 'snapshots', '--repo', repo_path, '--compact']
        if path_filter:
            cmd.extend(['--path', path_filter])
        
        env_vars = {'RESTIC_PASSWORD': password}
        result = execute_restic_command(cmd, env_vars)
        
        if result.returncode != 0:
            return jsonify({'error': f'Failed to list snapshots: {result.stderr}'}), 500
        
        snapshots = parse_snapshots_output(result.stdout)
        return jsonify(snapshots)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_backup_stream(cmd, env_vars, location_id):
    """Generator function for streaming backup output"""
    process = execute_restic_command(cmd, env_vars, stream_output=True)
    
    output_lines = []
    snapshot_id = None
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                output_lines.append(line)
                yield f"data: {json.dumps({'output': line.strip()})}\n\n"
                
                # Extract snapshot ID from output
                if 'snapshot' in line.lower() and 'saved' in line.lower():
                    match = re.search(r'snapshot ([a-f0-9]{8})', line)
                    if match:
                        snapshot_id = match.group(1)
        
        process.wait()
        
        # Save output to file if snapshot was created
        if snapshot_id and process.returncode == 0:
            output_file = os.path.expanduser(f'~/backup_logs/{snapshot_id}.txt')
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w') as f:
                f.writelines(output_lines)
        
        yield f"data: {json.dumps({'completed': True, 'success': process.returncode == 0, 'snapshot_id': snapshot_id})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        if process.poll() is None:
            process.terminate()

@app.route('/locations/<location_id>/backups', methods=['POST'])
def create_backup(location_id):
    """Create a new backup with streaming output"""
    try:
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'path parameter is required'}), 400
        
        repo_path = config['locations'][location_id]
        backup_path = data['path']
        
        cmd = ['restic', 'backup', backup_path, '--repo', repo_path, '--verbose']
        env_vars = {'RESTIC_PASSWORD': password}
        
        def event_stream():
            yield "data: {\"message\": \"Starting backup...\"}\n\n"
            yield from generate_backup_stream(cmd, env_vars, location_id)
        
        return Response(event_stream(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/backups/<backup_id>', methods=['GET'])
def list_backup_contents(location_id, backup_id):
    """List contents of a specific backup"""
    try:
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        repo_path = config['locations'][location_id]
        directory_path = request.args.get('directory_path', '/')
        recursive = request.args.get('recursive', 'false').lower() == 'true'
        
        cmd = ['restic', 'ls', backup_id, '--repo', repo_path, '--json']
        if recursive:
            cmd.append('--recursive')
        if directory_path != '/':
            cmd.append(directory_path)
        
        env_vars = {'RESTIC_PASSWORD': password}
        result = execute_restic_command(cmd, env_vars)
        
        if result.returncode != 0:
            return jsonify({'error': f'Failed to list backup contents: {result.stderr}'}), 500
        
        # Parse JSON output
        contents = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    contents.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        return jsonify(contents)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_restore_stream(cmd, env_vars):
    """Generator function for streaming restore output"""
    process = execute_restic_command(cmd, env_vars, stream_output=True)
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                yield f"data: {json.dumps({'output': line.strip()})}\n\n"
        
        process.wait()
        yield f"data: {json.dumps({'completed': True, 'success': process.returncode == 0})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        if process.poll() is None:
            process.terminate()

@app.route('/locations/<location_id>/backups/<backup_id>/restore', methods=['POST'])
def restore_backup(location_id, backup_id):
    """Restore a backup with streaming output"""
    try:
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        data = request.get_json()
        if not data or 'target' not in data:
            return jsonify({'error': 'target parameter is required'}), 400
        
        repo_path = config['locations'][location_id]
        target = data['target']
        is_dry_run = data.get('is_dry_run', 0)
        
        cmd = ['restic', 'restore', backup_id, '--repo', repo_path, '--target', target, '--verbose=2']
        if is_dry_run:
            cmd.append('--dry-run')
        
        env_vars = {'RESTIC_PASSWORD': password}
        
        def event_stream():
            yield "data: {\"message\": \"Starting restore...\"}\n\n"
            yield from generate_restore_stream(cmd, env_vars)
        
        return Response(event_stream(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create backup logs directory
    os.makedirs(os.path.expanduser('~/backup_logs'), exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
