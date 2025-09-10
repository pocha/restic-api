import os
import json

# Configuration file path
CONFIG_DIR = os.path.expanduser('~/.restic-api')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
PASSWORD_STORE_FILE = os.path.join(CONFIG_DIR, 'password-store')

def ensure_config_dir():
    """Ensure the config directory exists"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

def load_config():
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'locations': {}}

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
    from flask import request
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    return None
