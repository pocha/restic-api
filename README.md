# Restic API Server with a basic web UI 

An alternative to [Backrest](https://github.com/garethgeorge/backrest), popular Web UI tool for Restic, which I found tad too complicated to operate. This is a simpler version. 

![restic-api-screenshot](/img/restic-screenshot.png)

It comes bundled with a API server so if you want to do your own client (like a mobile app or something), it should be doable. Things are kept fairly basic & will be developed depending on my own need going ahead (or based on what issues/requests people are raising). 

![Nonbios](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQRqlsOSv4d0NPxb9v8942a_7BdWRcYWKpwMw&s)

The project is built using [nonbios.ai](https://nonbios.ai) . I wrote very minimal code & it was nonbios which did most of the heavy lifting. 

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

All endpoints (except config and POST /locations) require `X-Restic-Password` header with repository password.

## API Reference

| Method | Endpoint | Description | (optional) Params | Response |
|--------|----------|-------------|-------------------|----------|
| **Configuration** |
| GET | `/config` | Get current configuration | - | `{"restic_version": "0.16.0", "locations": {...}, "paths": [...]}` |
| POST | `/config/update_restic` | Update restic binary/version | `file` (optional): restic binary file | `{"message": "Restic updated successfully", "version": "0.16.0"}` |
| **Repository** |
| POST | `/locations` | Initialize new repository | `{"location": "/path/to/repo", "password": "pass"}` | `{"message": "Repository initialized successfully", "location_id": "repo"}` |
| **Backups** |
| GET | `/locations/{id}/backups` | List snapshots | Query: `?path=/specific/path` | `[{"snapshot_id": "a1b2c3d4", "date": "2024-01-15", "size": "1.2GB"}]` |
| POST | `/locations/{id}/backups` | Create backup (SSE stream) | `{"path": "/path/to/backup"}` | SSE: `data: {"output": "progress..."}, {"completed": true, "snapshot_id": "..."}` |
| GET | `/locations/{id}/backups/{backup_id}` | Browse backup contents | Query: `?directory_path=/subdir&recursive=true` | `[{"name": "file.txt", "type": "file", "size": 1024, "path": "/file.txt"}]` |
| **Restore** |
| POST | `/locations/{id}/backups/{backup_id}/restore` | Restore data (SSE stream) | `{"target": "/restore/path", "include": [...], "exclude": [...], "dry_run": false}` | SSE: `data: {"output": "restoring..."}, {"completed": true, "success": true}` |

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
