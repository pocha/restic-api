from flask import jsonify, send_from_directory
from flask import render_template

import os
from schedule import *
from restic_installer import *
from backup import *

from app_factory import app
from utils import load_config

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



@app.route('/browse/<path:restore_path>')
def browse_restored_content(restore_path):
    """Browse restored directory content with validation"""
    try:
        # Load config to validate restored paths
        config = load_config()
        restored_paths = config.get('restored_paths', [])
        
        # Validate that the requested path is in our restored paths
        restore_path = '/' + restore_path if not restore_path.startswith('/') else restore_path
        
        if restore_path not in restored_paths:
            return jsonify({'error': 'Access denied. Path not found in restored directories.'}), 403
        
        # Check if directory exists
        if not os.path.exists(restore_path) or not os.path.isdir(restore_path):
            return jsonify({'error': 'Directory not found or inaccessible.'}), 404
        
        # Get directory contents
        try:
            items = []
            for item in sorted(os.listdir(restore_path)):
                item_path = os.path.join(restore_path, item)
                is_dir = os.path.isdir(item_path)
                
                # Get file size for files
                size = None
                if not is_dir:
                    try:
                        size = os.path.getsize(item_path)
                    except:
                        size = 0
                
                items.append({
                    'name': item,
                    'is_directory': is_dir,
                    'size': size
                })
            
            # Helper function for formatting file sizes
            def format_size(size_bytes):
                if size_bytes == 0:
                    return "0 B"
                size_names = ["B", "KB", "MB", "GB", "TB"]
                import math
                i = int(math.floor(math.log(size_bytes, 1024)))
                p = math.pow(1024, i)
                s = round(size_bytes / p, 2)
                return f"{s} {size_names[i]}"
            
            return render_template('browse.html', 
                                 path=restore_path, 
                                 items=items,
                                 format_size=format_size)
            
        except PermissionError:
            return jsonify({'error': 'Permission denied accessing directory.'}), 403
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
            
        
@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        config = load_config()
        return jsonify(config)
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

