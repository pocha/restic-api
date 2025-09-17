import os
import json
import subprocess
from flask import Flask, request, jsonify, send_from_directory, Response
from app_factory import app
from utils import extract_password_and_launch_backup, get_password_from_header, load_config, save_config, execute_restic_command



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
        print(result.stderr, flush=True)
        
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



@app.route('/locations/<location_id>/backups', methods=['POST'])
def create_backup(location_id):
    """Create a new backup"""
    data = request.get_json()
    return extract_password_and_launch_backup(location_id, data)


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
    
def count_files_in_snapshot(snapshot_id, repo_path, password):
    """Count total files in a snapshot for progress calculation"""
    try:
        cmd = ['restic', 'ls', snapshot_id, '--repo', repo_path]
        env_vars = {'RESTIC_PASSWORD': password}
        process = execute_restic_command(cmd, env_vars)
        
        if process.returncode == 0:
            # Count lines in output (each line is a file/directory)
            file_count = len([line for line in process.stdout.strip().split('\n') if line.strip()])
            return file_count
        return 0
    except Exception:
        return 0

def generate_restore_stream(cmd, env_vars, target_path, total_files=0):
    """Generator function for streaming restore output with progress"""
    process = execute_restic_command(cmd, env_vars, stream_output=True)
    
    processed_files = 0
    last_progress = -1
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                processed_files += 1
                
                # Calculate progress percentage
                if total_files > 0:
                    progress = min(int((processed_files / total_files) * 100), 100)
                    
                    # Only send progress updates every 5% to reduce frontend load
                    if progress != last_progress and progress % 5 == 0:
                        yield f"data: {json.dumps({'progress': progress, 'processed': processed_files, 'total': total_files})}\n\n"
                        last_progress = progress
                else:
                    # Fallback: send periodic updates without percentage
                    if processed_files % 100 == 0:  # Every 100 files
                        yield f"data: {json.dumps({'processed': processed_files, 'message': f'Processed {processed_files} files...'})}\n\n"
        
        process.wait()
        
        # If restore was successful, add target path to config
        if process.returncode == 0:
            from utils import load_config, save_config
            config = load_config()
            if 'restored_paths' not in config:
                config['restored_paths'] = []
            
            # Add target path if not already present
            if target_path not in config['restored_paths']:
                config['restored_paths'].append(target_path)
                save_config(config)
            
            # Include browse link in the response
            browse_link = f"/browse{target_path}"
            yield f"data: {json.dumps({'completed': True, 'success': True, 'browse_link': browse_link, 'total_processed': processed_files})}\n\n"
        else:
            yield f"data: {json.dumps({'completed': True, 'success': False})}\n\n"
        
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
            
            # Count files in snapshot for progress tracking
            yield "data: {\"message\": \"Counting files in snapshot...\"}\n\n"
            total_files = count_files_in_snapshot(backup_id, repo_path, password)
            
            if total_files > 0:
                yield f"data: {{\"message\": \"Found {total_files} files to restore. Starting restore...\"}}\n\n"
            else:
                yield "data: {\"message\": \"Starting restore (file count unavailable)...\"}\n\n"
            
            yield from generate_restore_stream(cmd, env_vars, target, total_files)
        
        return Response(event_stream(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
