import os
import json
import subprocess
import platform
import uuid
import requests
from flask import request, jsonify
from app_factory import app
from utils import load_config, save_config, get_password_from_header, save_password_to_store

def get_cron_expression(frequency, time_str):
    """Convert frequency and time to cron expression"""
    try:
        hour, minute = map(int, time_str.split(':'))
    except ValueError:
        raise ValueError("Invalid time format. Use HH:MM")
    
    if frequency == 'daily':
        return f"{minute} {hour} * * *"
    elif frequency == 'weekly':
        return f"{minute} {hour} * * 0"  # Sunday
    elif frequency == 'monthly':
        return f"{minute} {hour} 1 * *"  # First day of month
    else:
        raise ValueError("Invalid frequency. Use daily, weekly, or monthly")

def create_cron_job(schedule_id, location_id, backup_data, cron_expression):
    """Create a cron job for scheduled backup"""
    try:
        # Always use key-based authentication for cron jobs
        password = get_password_from_header()
        if not password:
            raise ValueError("Password is required")
        
        # Save password with schedule_id as key
        save_password_to_store(schedule_id, password)
        
        # Prepare backup data with key instead of password
        backup_data_with_key = backup_data.copy()
        backup_data_with_key['key'] = schedule_id
        
        # Create curl command for the backup API
        curl_cmd = f"curl -X POST -H 'Content-Type: application/json' -d '{json.dumps(backup_data_with_key)}' http://localhost:5000/locations/{location_id}/backups"
        
        # Create cron job with unique comment
        cron_entry = f'{cron_expression} {curl_cmd} # restic-api-{schedule_id}'
        
        # Add to crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_crontab = result.stdout if result.returncode == 0 else ""
        
        # Add new entry
        new_crontab = current_crontab + cron_entry + '\n'
        
        # Write back to crontab
        process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crontab)
        
        if process.returncode == 0:
            return True
        else:
            raise Exception("Failed to add cron job")
            
    except Exception as e:
        print(f"Error creating cron job: {e}")
        raise

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
    """Remove a scheduled job (cron job or Windows task)"""
    try:
        if platform.system() == 'Windows':
            # Remove Windows scheduled task
            task_name = f"restic-api-{schedule_id}"
            cmd = ['schtasks', '/delete', '/tn', task_name, '/f']
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        else:
            # Remove cron job
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            if result.returncode != 0:
                return True  # No crontab exists
            
            current_crontab = result.stdout
            lines = current_crontab.split('\n')
            
            # Filter out the line with our schedule_id
            filtered_lines = [line for line in lines if f'restic-api-{schedule_id}' not in line]
            
            # Write back to crontab
            new_crontab = '\n'.join(filtered_lines)
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_crontab)
            
            return process.returncode == 0
            
    except Exception as e:
        print(f"Error removing scheduled job: {e}")
        return False

@app.route('/locations/<location_id>/schedule', methods=['POST'])
def create_backup_schedule(location_id):
    """Create a scheduled backup for a location"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        data = request.get_json()
        backup_data = data.get('backup_data', {})
        frequency = data.get('frequency')
        time_str = data.get('time')
        
        if not frequency or not time_str:
            return jsonify({'error': 'Frequency and time are required'}), 400
        
        # Generate unique schedule ID
        schedule_id = str(uuid.uuid4())
        
        # Get cron expression
        cron_expression = get_cron_expression(frequency, time_str)
        
        # Create the scheduled job
        if platform.system() == 'Windows':
            path = backup_data.get('path')
            if not path:
                return jsonify({'error': 'Path is required for Windows scheduling'}), 400
            success = create_windows_task(schedule_id, location_id, path, frequency, time_str)
        else:
            success = create_cron_job(schedule_id, location_id, backup_data, cron_expression)
        
        if success:
            # Store schedule info in config
            if 'schedules' not in config:
                config['schedules'] = {}
            
            schedule_info = {
                'schedule_id': schedule_id,
                'location_id': location_id,
                'backup_data': backup_data,
                'frequency': frequency,
                'time': time_str,
                'cron_expression': cron_expression if platform.system() != 'Windows' else None
            }
            
            # Add type and path/command info for display
            if backup_data.get('type') == 'command':
                schedule_info['type'] = 'command'
                schedule_info['command'] = backup_data.get('command')
                schedule_info['filename'] = backup_data.get('filename')
            else:
                schedule_info['type'] = 'directory'
                schedule_info['path'] = backup_data.get('path')
            
            config['schedules'][schedule_id] = schedule_info
            save_config(config)
            
            return jsonify({
                'message': 'Backup scheduled successfully',
                'schedule_id': schedule_id
            })
        else:
            return jsonify({'error': 'Failed to create scheduled backup'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/schedule/<schedule_id>/execute-backup', methods=['POST'])
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

@app.route('/locations/<location_id>/schedule', methods=['GET'])
def list_backup_schedules(location_id):
    """List all scheduled backups for a location"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        schedules = []
        if 'schedules' in config:
            for schedule_id, schedule_info in config['schedules'].items():
                if schedule_info['location_id'] == location_id:
                    schedules.append(schedule_info)
        
        return jsonify({'schedules': schedules})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/locations/<location_id>/schedule/<schedule_id>', methods=['DELETE'])
def delete_backup_schedule(location_id, schedule_id):
    """Delete a scheduled backup"""
    try:
        config = load_config()
        if location_id not in config['locations']:
            return jsonify({'error': 'Location not found'}), 404
        
        if 'schedules' not in config or schedule_id not in config['schedules']:
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Remove the scheduled job
        success = remove_scheduled_job(schedule_id)
        
        if success:
            # Remove from config
            del config['schedules'][schedule_id]
            save_config(config)
            
            return jsonify({'message': 'Scheduled backup deleted successfully'})
        else:
            return jsonify({'error': 'Failed to remove scheduled job'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
