from datetime import datetime
import json
import os
import subprocess
import platform
import uuid
from flask import request, jsonify, Response
from app_factory import app
from utils import load_config, save_config, get_password_from_header, save_password_to_store, extract_password_and_launch_backup

def get_cron_expression(frequency, time_str):
    """Convert frequency and time to cron expression"""
    output = []
    try:
        hour, minute = map(int, time_str.split(':'))
        output.extend([hour, minute])
    except ValueError:
        raise ValueError("Invalid time format. Use HH:MM")
    
    if frequency == 'daily':
        output.extend(["*","*","*"])
        #return f"{minute} {hour} * * *"
    elif frequency == 'weekly':
        output.extend(["*","*","0"])
        #return f"{minute} {hour} * * 0"  # Sunday
    elif frequency == 'monthly':
        output.extend(["1","*","*"])
        #return f"{minute} {hour} 1 * *"  # First day of month
    else:
        raise ValueError("Invalid frequency. Use daily, weekly, or monthly")
    
    return output

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
            backup_cmd = f"curl -X POST -H 'Content-Type: application/json' -d '{{\"path\": \"{backup_data['path']}\", \"key\": \"{schedule_id}\"}}' http://localhost:5000/locations/{location_id}/backups"
        
        job = cron.new(command=backup_cmd, comment=f"restic_schedule_{schedule_id}")
        job.setall(cron_expression)
        cron.write()
        return True
    except Exception as e:
        print(f"Error creating cron job: {e}")
        return False

def create_windows_task(schedule_id, location_id, path, frequency, time_str):
    """Create a Windows scheduled task for backup"""
    try:
        # Convert frequency to Windows task scheduler format
        if frequency == 'daily':
            schedule_type = 'DAILY'
        elif frequency == 'weekly':
            schedule_type = 'WEEKLY'
        elif frequency == 'monthly':
            schedule_type = 'MONTHLY'
        else:
            raise ValueError("Invalid frequency")
        
        # Create the task
        task_name = f"restic-api-{schedule_id}"
        
        # Prepare the command
        curl_cmd = f'curl -X POST -H "Content-Type: application/json" -d "{{\\"path\\": \\"{path}\\"}}" http://localhost:5000/locations/{location_id}/backups'
        
        # Create scheduled task
        cmd = [
            'schtasks', '/create',
            '/tn', task_name,
            '/tr', curl_cmd,
            '/sc', schedule_type,
            '/st', time_str,
            '/f'  # Force create/overwrite
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            raise Exception(f"Failed to create Windows task: {result.stderr}")
            
    except Exception as e:
        print(f"Error creating Windows task: {e}")
        raise

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

@app.route('/locations/<location_id>/schedule', methods=['POST'])
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
       
        cron_expression = get_cron_expression(frequency, time_str)
        
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
            'platform': current_platform,
            **backup_data
        }
        
        # # Add path to location's paths if not already there (for directory backups)
        # if backup_type == 'directory' and backup_data['path'] not in config['locations'][location_id]['paths']:
        #     config['locations'][location_id]['paths'].append(backup_data['path'])
        # elif backup_type == 'command':
        #     # For command backups, add the snapshot path
        #     snapshot_path = "/" + backup_data['filename']
        #     if snapshot_path not in config['locations'][location_id]['paths']:
        #         config['locations'][location_id]['paths'].append(snapshot_path)
        
        # Save schedule info with cron_id
        config['schedules'][schedule_id] = schedule_data
        
        save_config(config)
        
        return jsonify({
            'message': 'Backup scheduled successfully',
            'schedule_id': schedule_id,
            'schedule': config['schedules'][schedule_id]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/schedule/<schedule_id>/execute-backup', methods=['POST'])
def execute_cron_job(location_id, schedule_id):
    """Execute a scheduled cron job by its ID"""
    try:
        from crontab import CronTab
        cron = CronTab(user=True)
         
        target_command = None
        jobs = cron.find_comment(f"restic_schedule_{schedule_id}")
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
        
        # Extract location_id from the URL
        # url = data_match.group(2)
        # location_match = re.search(r'/locations/([^/]+)/backups', url)
        # if not location_match:
        #     return jsonify({'error': 'Could not extract location_id from URL'}), 400
        
        # location_id = location_match.group(1)

        return extract_password_and_launch_backup(location_id, backup_data)
        
    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/schedule', methods=['GET'])
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

@app.route('/locations/<location_id>/schedule/<schedule_id>', methods=['DELETE'])
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
