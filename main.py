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
        # and restrict access to only the first directory inside restore_path
        is_valid_path = False
        base_restore_path = None
        allowed_browse_path = None
        
        for restored_path in restored_paths:
            restored_path = os.path.normpath(restored_path)
            
            # Find the first directory inside the restored path
            if os.path.exists(restored_path) and os.path.isdir(restored_path):
                try:
                    items_in_restore = [item for item in os.listdir(restored_path) 
                                      if os.path.isdir(os.path.join(restored_path, item))]
                    if items_in_restore:
                        # Use the first directory as the allowed browse path
                        first_dir = sorted(items_in_restore)[0]
                        allowed_browse_path = os.path.join(restored_path, first_dir)
                        
                        # Check if the requested path is within this allowed directory
                        if (restore_path == allowed_browse_path or 
                            restore_path.startswith(allowed_browse_path + os.sep)):
                            is_valid_path = True
                            base_restore_path = restored_path
                            break
                except (PermissionError, OSError):
                    continue
        
        if not is_valid_path:
            return jsonify({'error': 'Access denied. Path not found in allowed directories.'}), 403
        
        # Check if directory exists
        if not os.path.exists(restore_path) or not os.path.isdir(restore_path):
            return jsonify({'error': 'Directory not found or inaccessible.'}), 404
        
        # Generate breadcrumb navigation with relative paths for URL generation
        breadcrumbs = []
        current_path = restore_path
        
        # Build breadcrumbs from current path back to allowed browse path
        while current_path and current_path != allowed_browse_path:
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:  # Reached root
                break
            # Use relative path by removing leading slash for URL generation
            relative_path = current_path.lstrip('/')
            breadcrumbs.insert(0, {
                'name': os.path.basename(current_path),
                'path': relative_path
            })
            current_path = parent_path
        
        # Add the allowed browse directory as the root breadcrumb
        allowed_relative_path = allowed_browse_path.lstrip('/')
        breadcrumbs.insert(0, {
            'name': os.path.basename(allowed_browse_path),
            'path': allowed_relative_path
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
                
                # Create clickable path for directories (relative path without leading slash)
                clickable_path = None
                if is_dir:
                    clickable_path = item_path.lstrip('/')
                
                items.append({
                    'name': item,
                    'is_directory': is_dir,
                    'size': size,
                    'path': item_path,
                    'clickable_path': clickable_path  # For directory navigation
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
            
        

@app.route('/view/<path:file_path>')
def view_file_content(file_path):
    """View file content with path validation"""
    try:
        # Load config to validate restored paths
        config = load_config()
        restored_paths = config.get('restored_paths', [])
        
        # Normalize the requested file path
        file_path = '/' + file_path.strip('/')
        
        # Validate that the file path is within a restored directory
        is_valid = False
        for restored_path in restored_paths:
            if file_path.startswith(restored_path):
                is_valid = True
                break
        
        if not is_valid:
            return "Access denied: File not in restored directory", 403
            
        # Check if file exists and is actually a file
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return "File not found", 404
            
        # Try to read and display file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Return as plain text with proper content type
            from flask import Response
            return Response(content, mimetype='text/plain')
            
        except UnicodeDecodeError:
            # If file is binary, show info instead of content
            file_size = os.path.getsize(file_path)
            return f"Binary file: {os.path.basename(file_path)}\nSize: {format_size(file_size)}\nCannot display binary content."
            
    except Exception as e:
        return f"Error reading file: {str(e)}", 500

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

