import os
import json
import subprocess
import re

from flask import Response, jsonify, request

# Configuration file path
CONFIG_DIR = os.path.expanduser('~/.restic-api')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
PASSWORD_STORE_FILE = os.path.join(CONFIG_DIR, 'password-store')

def ensure_config_dir():
    """Ensure the config directory exists"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

# Helper Functions
def load_config():
    """Load configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config
    return {'restic_version': 'NA', 'locations': {}}

def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_password_store():
    ensure_config_dir()
    if os.path.exists(PASSWORD_STORE_FILE):
        with open(PASSWORD_STORE_FILE, 'r') as f:
            return dict(line.strip().split('=', 1) for line in f if '=' in line)
    return {}

def save_password_to_store(key, password):
    ensure_config_dir()
    password_store = load_password_store()
    password_store[key] = password
    with open(PASSWORD_STORE_FILE, 'w') as f:
        for k, v in password_store.items():
            f.write(f"{k}={v}\n")

def get_password_from_key(key):
    password_store = load_password_store()
    return password_store.get(key)

def get_password_from_header():
    """Extract restic password from request header"""
    password = request.headers.get('X-Restic-Password')
    if not password:
        return None, {'error': 'X-Restic-Password header is required'}, 400
    return password, None, None

def extract_password_and_launch_backup(location_id, data):
    try:
        # Check if key parameter is provided for password lookup
        key = data.get('key')
        
        if key:
            # Get password from password store using key
            password = get_password_from_key(key)
            if not password:
                return jsonify({'error': f'Password key "{key}" not found in password store'}), 400
        else:
            # Use traditional header-based password
            password, error_response, status_code = get_password_from_header()
            if error_response:
                return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        # Support both directory and command-based backups
        backup_type = data.get('type', 'directory')  # default to directory for backward compatibility
        
        if backup_type == 'directory':
            if not data or 'path' not in data:
                return jsonify({'error': 'path parameter is required for directory backup'}), 400
            
            repo_path = config['locations'][location_id]['repo_path']
            backup_path = data['path']
            if not os.path.exists(backup_path):
                return jsonify({'error': 'backup_path provided does not exist'}), 400
            
            # Add backup path to location's paths list if not already present
            if backup_path not in config['locations'][location_id]['paths']:
                config['locations'][location_id]['paths'].append(backup_path)
                save_config(config)
            
            cmd = ['restic', 'backup', backup_path, '--repo', repo_path, '--verbose']
            
        elif backup_type == 'command':
            if not data or 'command' not in data or 'filename' not in data:
                return jsonify({'error': 'command and filename parameters are required for command backup'}), 400
            
            repo_path = config['locations'][location_id]['repo_path']
            backup_command = data['command']
            filename = data['filename']
            

            # Add command backup path to location's paths list for restore functionality
            command_backup_path = backup_command + ":/" + filename
            if command_backup_path not in config['locations'][location_id]['paths']:
                config['locations'][location_id]['paths'].append(command_backup_path)
                save_config(config)
            # Split the command into arguments for proper execution
            command_args = backup_command.split()
            cmd = ['restic', 'backup', '--stdin', '--stdin-from-command'] + command_args + [
                   '--stdin-filename', filename, '--repo', repo_path, '--verbose']
        else:
            return jsonify({'error': 'type must be either "directory" or "command"'}), 400
        
        env_vars = {'RESTIC_PASSWORD': password}
        
        def event_stream():
            yield "data: {\"message\": \"Starting backup...\"}\n\n"
            yield from generate_backup_stream(cmd, env_vars, location_id)
        
        return Response(event_stream(), mimetype='text/event-stream')
        
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
            output_file = os.path.expanduser(f'~/.restic-api/backup_logs/{snapshot_id}.txt')
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w') as f:
                f.writelines(output_lines)
        
        yield f"data: {json.dumps({'completed': True, 'success': process.returncode == 0, 'snapshot_id': snapshot_id})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        if process.poll() is None:
            process.terminate()

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