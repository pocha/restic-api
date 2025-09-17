import os

from flask import jsonify, render_template
from utils import load_config

from app_factory import app


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
        matching_config_path = None
        
        for path_in_config in restored_paths:
            if restore_path.startswith(path_in_config):
                is_valid_path = True
                matching_config_path = path_in_config
                base_restore_path = "/".join(matching_config_path.split("/")[:-1])
                break
        
        if not is_valid_path:
            return jsonify({'error': 'Access denied. Path not found in allowed directories.'}), 403
        
        # Check if directory exists
        if not os.path.exists(restore_path) or not os.path.isdir(restore_path):
            return jsonify({'error': 'Directory not found or inaccessible.'}), 404
        
        # Generate breadcrumb navigation with relative paths for URL generation
        breadcrumbs = []
        current_path = restore_path
        
        # Build breadcrumbs from current path back to allowed browse path
        while current_path and current_path != matching_config_path:
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
        allowed_relative_path = matching_config_path.lstrip('/')
        breadcrumbs.insert(0, {
            'name': os.path.basename(matching_config_path),
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
