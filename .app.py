import os
import json
import subprocess
import threading
import time
import re
from datetime import datetime
import platform
import uuid
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Serve the web UI
@app.route('/')
def index():
    return send_from_directory('basic-web-ui', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename.startswith('basic-web-ui/'):
        # Remove the basic-web-ui/ prefix and serve from the directory
        actual_filename = filename[len('basic-web-ui/'):]
        return send_from_directory('basic-web-ui', actual_filename)
    return "File not found", 404
    return "File not found", 404

CONFIG_FILE = os.path.expanduser('~/.restic-api/config.json')
PASSWORD_STORE_FILE = os.path.expanduser('~/.restic-api/password-store')

# Helper Functions
def load_config():
    """Load configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        # Migrate old config format to new format if needed
        if 'locations' in config:
            for location_id, location_data in config['locations'].items():
                # If location_data is a string (old format), convert to new format
                if isinstance(location_data, str):
                    config['locations'][location_id] = {
                        'repo_path': location_data,
                        'paths': []
                    }
        return config
    return {'restic_version': 'NA', 'locations': {}}

def save_config(config):
    """Save configuration to config.json"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_password_store():
    """Load password store from file"""
    if os.path.exists(PASSWORD_STORE_FILE):
        passwords = {}
        with open(PASSWORD_STORE_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, password = line.split('=', 1)
                    passwords[key.strip()] = password.strip()
        return passwords
    return {}

def save_password_to_store(key, password):
    """Save password to password store"""
    passwords = load_password_store()
    passwords[key] = password
    
    with open(PASSWORD_STORE_FILE, 'w') as f:
        for k, p in passwords.items():
            f.write(f"{k}={p}\n")

def get_password_from_key(key):
    """Get password from password store using key"""
    passwords = load_password_store()
    return passwords.get(key)

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
                size = ' '.join(parts[4:6])
                
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

@app.route('/locations', methods=['POST'])
def init_location():
    """Initialize a new restic repository location"""
    try:
        data = request.get_json()
        if not data or 'location' not in data or 'password' not in data:
            return jsonify({'error': 'location and password are required'}), 400
        
        location = data['location']
        if not os.path.exists(location):
            return jsonify({'error': 'location provided does not exist'}), 400

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
        config['locations'][location_id] = {
            'repo_path': location,
            'paths': []
        }
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
        
        repo_path = config['locations'][location_id]['repo_path']
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

@app.route('/locations/<location_id>/backups', methods=['POST'])
def create_backup(location_id):
    """Create a new backup with streaming output"""
    try:
        # Check if key parameter is provided for password lookup
        data = request.get_json() or {}
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

@app.route('/locations/<location_id>/backups/<backup_id>', methods=['GET'])
def list_backup_contents(location_id, backup_id):
    """List contents of a specific backup or retrieve backup logs"""
    try:
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        # Check if logs are requested
        is_logs = request.args.get('is_logs', '0') == '1'
        
        if is_logs:
            # Return backup logs
            log_file = os.path.expanduser(f'~/.restic-api/backup_logs/{backup_id}.txt')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = f.read()
                return jsonify({'logs': logs})
            else:
                return jsonify({'logs': 'No logs found for this backup'})
        
        # Original file listing logic
        repo_path = config['locations'][location_id]['repo_path']
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
        
        repo_path = config['locations'][location_id]['repo_path']
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


# Scheduling functionality
def get_cron_expression(frequency, time_str):
    """Convert frequency and time to cron expression"""
    try:
        hour, minute = map(int, time_str.split(':'))
        if frequency == 'daily':
            return f"{minute} {hour} * * *"
        elif frequency == 'weekly':
            return f"{minute} {hour} * * 0"  # Sunday
        elif frequency == 'monthly':
            return f"{minute} {hour} 1 * *"  # 1st of month
        else:
            raise ValueError("Invalid frequency")
    except:
        raise ValueError("Invalid time format")

def create_cron_job(schedule_id, location_id, backup_data, cron_expression):
    """Create cron job for Linux"""
    import uuid
    try:
        from crontab import CronTab
        cron = CronTab(user=True)
        
        
        # Create command to run backup
        if backup_data.get('type') == 'command':
            # For command-based backups
            backup_cmd = f"curl -X POST -H 'Content-Type: application/json' -d '{{\"type\": \"command\", \"command\": \"{backup_data['command']}\", \"filename\": \"{backup_data['filename']}\", \"key\": \"{schedule_id}\"}}' http://localhost:5000/locations/{location_id}/backups"
        else:
            # For directory-based backups
            backup_cmd = f"curl -X POST -H 'Content-Type: application/json' -d '{{\"path\": \"{backup_data['path']}\", \"key\": \"{key}\"}}' http://localhost:5000/locations/{location_id}/backups"
        
        job = cron.new(command=backup_cmd, comment=f"restic_schedule_{schedule_id}")
        job.setall(cron_expression)
        cron.write()
        return True
    except Exception as e:
        print(f"Error creating cron job: {e}")
        return False

def create_windows_task(schedule_id, location_id, path, frequency, time_str):
    """Create Windows scheduled task"""
    try:
        import subprocess
        
        # Create PowerShell script for the backup
        script_content = f'''
$headers = @{{"X-Restic-Password" = "PLACEHOLDER"; "Content-Type" = "application/json"}}
$body = @{{"path" = "{path}"}} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/locations/{location_id}/backups" -Method POST -Headers $headers -Body $body
'''
        
        script_path = f"backup_schedule_{schedule_id}.ps1"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Create scheduled task
        task_name = f"ResticBackup_{schedule_id}"
        
        if frequency == 'daily':
            schedule_arg = "DAILY"
        elif frequency == 'weekly':
            schedule_arg = "WEEKLY"
        elif frequency == 'monthly':
            schedule_arg = "MONTHLY"
        
        cmd = [
            'schtasks', '/create', '/tn', task_name, '/tr', f'powershell.exe -File {script_path}',
            '/sc', schedule_arg, '/st', time_str, '/f'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error creating Windows task: {e}")
        return False

def remove_scheduled_job(schedule_id):
    """Remove scheduled job (cross-platform)"""
    try:
        current_platform = platform.system().lower()
        
        if current_platform == 'linux':
            from crontab import CronTab
            cron = CronTab(user=True)
            jobs = cron.find_comment(f"restic_schedule_{schedule_id}")
            for job in jobs:
                cron.remove(job)
            cron.write()
        elif current_platform == 'windows':
            task_name = f"ResticBackup_{schedule_id}"
            subprocess.run(['schtasks', '/delete', '/tn', task_name, '/f'], capture_output=True)
            
            # Also remove the PowerShell script
            script_path = f"backup_schedule_{schedule_id}.ps1"
            if os.path.exists(script_path):
                os.remove(script_path)
        
        return True
    except Exception as e:
        print(f"Error removing scheduled job: {e}")
        return False

@app.route('/locations/<location_id>/backups/schedule', methods=['POST'])
def create_backup_schedule(location_id):
    """Create a scheduled backup"""
    try:
        data = request.get_json()
        # Support both directory and command-based scheduled backups
        backup_type = data.get('type', 'directory')  # default to directory for backward compatibility
        
        if backup_type == 'directory':
            if not data or 'path' not in data or 'frequency' not in data or 'time' not in data:
                return jsonify({'error': 'path, frequency, time are required for directory backup.'}), 400
            
            path = data['path']
            if not os.path.exists(path):
                return jsonify({'error': 'Path does not exist'}), 400
                
        elif backup_type == 'command':
            if not data or 'command' not in data or 'filename' not in data or 'frequency' not in data or 'time' not in data:
                return jsonify({'error': 'command, filename, frequency, time are required for command backup. key is optional for password store lookup'}), 400
            
            path = f"command:{data['command']}:{data['filename']}"  # Store command info as path for scheduling
            
        else:
            return jsonify({'error': 'type must be either "directory" or "command"'}), 400
        
        frequency = data['frequency']
        time_str = data['time']
        
        # Validate inputs
        if frequency not in ['daily', 'weekly', 'monthly']:
            return jsonify({'error': 'frequency must be daily, weekly, or monthly'}), 400
        
        # Get password from header and store it with the key
        password, error_response, status_code = get_password_from_header()
        if error_response:
            return jsonify(error_response), status_code
        
        # Generate unique schedule ID
        schedule_id = str(uuid.uuid4())

        # Store password in password store
        save_password_to_store(schedule_id, password)
        
        # Load config and validate location
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        # Initialize schedules in config if not exists
        if 'schedules' not in config:
            config['schedules'] = {}
        
        
        # Get cron expression
        try:
            cron_expression = get_cron_expression(frequency, time_str)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        # Create platform-specific scheduled job
        current_platform = platform.system().lower()
        success = False
        
        # Prepare backup data object for cron job
        if backup_type == 'directory':
            backup_data = {'type': 'directory', 'path': data['path']}
        else:  # command type
            backup_data = {'type': 'command', 'command': data['command'], 'filename': data['filename']}
        
        if current_platform == 'linux':
            success = create_cron_job(schedule_id, location_id, backup_data, cron_expression)
            if not success:
                return jsonify({'error': 'Failed to create scheduled job'}), 500
            
            # Store the cron_id in the schedule data
            schedule_data = {
                'id': schedule_id,
                'location_id': location_id,
                'frequency': frequency,
                'time': time_str,
                'created_at': datetime.now().isoformat(),
                **backup_data
            }
        
        # Add path to location's paths if not already there (for directory backups)
        if backup_type == 'directory' and backup_data['path'] not in config['locations'][location_id]['paths']:
            config['locations'][location_id]['paths'].append(backup_data['path'])
        elif backup_type == 'command':
            # For command backups, add the snapshot path
            snapshot_path = "/" + backup_data['filename']
            if snapshot_path not in config['locations'][location_id]['paths']:
                config['locations'][location_id]['paths'].append(snapshot_path)
        
        # Save schedule info with cron_id
        schedule_data['platform'] = current_platform
        config['schedules'][schedule_id] = schedule_data
        
        save_config(config)
        
        return jsonify({
            'message': 'Backup scheduled successfully',
            'schedule_id': schedule_id,
            'schedule': config['schedules'][schedule_id]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/locations/<location_id>/execute-cron/<cron_id>', methods=['POST'])
def execute_cron_job(cron_id):
    """Execute a scheduled cron job by its ID"""
    try:
        from crontab import CronTab
        cron = CronTab(user=True)
         
        target_command = None
        jobs = cron.find_comment(f"restic_schedule_{cron_id}")
        for job in jobs:
            target_command = job.command
            break
        
        if not target_command:
            return jsonify({'error': 'No backup job scheduled for the cron_id'}), 400

        # Parse the curl command to extract parameters
        import re
        import json
        # Extract JSON data from curl command
        data_match = re.search(r"-d\s+'([^']+)' ([^']+)", target_command)
        if not data_match:
            return jsonify({'error': 'Could not extract backup data from cron command'}), 400
        
        
        backup_data = json.loads(data_match.group(1))
        if not backup_data:
            return jsonify({'error': 'Invalid JSON in cron command'}), 400
        
        url = data_match.group(2)
        if not url:
            return jsonify({'error': 'Could not extract url from cron'})
        
        import requests 
        response = requests.post(url, backup_data)

        return response.json()
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/locations/<location_id>/backups/schedule', methods=['GET'])
def list_backup_schedules(location_id):
    """List all scheduled backups for a location"""
    try:
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        # Filter schedules for this location
        schedules = []
        for schedule_id, schedule_data in config.get('schedules', {}).items():
            if schedule_data['location_id'] == location_id:
                schedules.append({
                    'schedule_id': schedule_id,
                    **schedule_data
                })
        
        return jsonify({'schedules': schedules})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/backups/schedule/<schedule_id>', methods=['DELETE'])
def delete_backup_schedule(location_id, schedule_id):
    """Delete a scheduled backup"""
    try:
        config = load_config()
        if location_id not in config.get('locations', {}):
            return jsonify({'error': 'Location not found'}), 404
        
        if schedule_id not in config.get('schedules', {}):
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Remove the scheduled job
        if not remove_scheduled_job(schedule_id):
            return jsonify({'error': 'Failed to remove scheduled job'}), 500
        
        # Remove from config
        del config['schedules'][schedule_id]
        save_config(config)
        
        return jsonify({'message': 'Schedule deleted successfully'})
        
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

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create .restic-api directory structure
    os.makedirs(os.path.expanduser('~/.restic-api'), exist_ok=True)
    os.makedirs(os.path.expanduser('~/.restic-api/backup_logs'), exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
