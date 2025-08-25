# Restic API Server

A REST API server that provides a web interface for the restic backup tool.

## Quick Start

```bash
git clone git@github.com:pocha/restic-api.git
cd restic-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Server runs on `http://localhost:5000`

## Authentication

All endpoints (except config) require `X-Restic-Password` header with repository password.

## API Reference

| Method | Endpoint | Description | (optional) Params | Response |
|--------|----------|-------------|-------------------|----------|
| **Configuration** |
| GET | `/config` | Get current configuration | - | `{"restic_version": "0.16.0", "locations": {...}, "paths": [...]}` |
| POST | `/config` | Update configuration | `{"restic_version": "0.16.0", "locations": {...}, "paths": [...]}` | `{"message": "Configuration updated successfully"}` |
| **Repository** |
| POST | `/locations` | Initialize new repository | `{"location": "/path/to/repo", "password": "pass"}` | `{"message": "Repository initialized successfully", "location_id": "repo"}` |
| **Backups** |
| GET | `/locations/{id}/backups` | List snapshots | Query: `?path=/specific/path` | `[{"snapshot_id": "a1b2c3d4", "date": "2024-01-15", "size": "1.2GB"}]` |
| POST | `/locations/{id}/backups` | Create backup (SSE stream) | `{"path": "/path/to/backup"}` | SSE: `data: {"output": "progress..."}, {"completed": true, "snapshot_id": "..."}` |
| GET | `/locations/{id}/backups/{backup_id}` | Browse backup contents | Query: `?directory_path=/subdir` | `[{"name": "file.txt", "type": "file", "size": 1024, "path": "/file.txt"}]` |
| **Restore** |
| POST | `/locations/{id}/backups/{backup_id}/restore` | Restore data (SSE stream) | `{"target": "/restore/path", "include": [...], "exclude": [...]}` | SSE: `data: {"output": "restoring..."}, {"completed": true, "success": true}` |

## Features

- Real-time backup/restore progress via Server-Sent Events
- Repository initialization with password protection
- Snapshot browsing and file listing
- Selective restore with include/exclude patterns
- Dry-run restore support

## Testing

Run the end-to-end test:
```bash
python e2e_test.py
```
