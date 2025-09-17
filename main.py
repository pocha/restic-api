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
    """Browse restored directory content with recursive navigation and validation"""
    try:
        # Load config to validate restored paths
        config = load_config()
        restored_paths = config.get('restored_paths', [])
        
        # Normalize the requested path
        restore_path = '/' + restore_path if not restore_path.startswith('/') else restore_path
        restore_path = os.path.normpath(restore_path)
        
        # Validate that the requested path is within one of our restored directories
        is_valid_path = False
        base_restore_path = None
        
        for restored_path in restored_paths:
            restored_path = os.path.normpath(restored_path)
            # Check if the requested path is the restored path itself or a subdirectory
            if restore_path == restored_path or restore_path.startswith(restored_path + os.sep):
                is_valid_path = True
                base_restore_path = restored_path
                break
        
        if not is_valid_path:
            return jsonify({'error': 'Access denied. Path not found in restored directories.'}), 403
        
        # Check if directory exists
        if not os.path.exists(restore_path) or not os.path.isdir(restore_path):
            return jsonify({'error': 'Directory not found or inaccessible.'}), 404
        
        # Generate breadcrumb navigation
        breadcrumbs = []
        current_path = restore_path
        
        # Build breadcrumbs from current path back to base restore path
        while current_path and current_path != base_restore_path:
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:  # Reached root
                break
            breadcrumbs.insert(0, {
                'name': os.path.basename(current_path),
                'path': current_path
            })
            current_path = parent_path
        
        # Add the base restore directory as the root breadcrumb
        breadcrumbs.insert(0, {
            'name': os.path.basename(base_restore_path) or 'Root',
            'path': base_restore_path
        })
        
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
                    'size': size,
                    'path': item_path
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
                                 base_path=base_restore_path,
                                 items=items,
                                 breadcrumbs=breadcrumbs,
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

