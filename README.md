# Restic API Server

A REST API server that provides a web interface for the restic backup tool. This server exposes HTTP endpoints to manage restic repositories, create backups, list snapshots, and restore data.

## Features

- Configuration management for restic repositories and backup paths
- Repository initialization with password protection
- Backup creation with real-time progress via Server-Sent Events
- Snapshot listing and browsing
- Data restoration with dry-run support
- Real-time command output streaming

## Installation

1. Clone the repository:
```bash
git clone git@github.com:pocha/restic-api.git
cd restic-api
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Verify installation:
```bash
pip list
```

5. Run the server:
```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Documentation

### Authentication

All API endpoints (except configuration endpoints) require authentication via the `X-Restic-Password` header:

```
X-Restic-Password: your-repository-password
```

### Configuration Management

#### GET /config
Returns the current configuration.

**Response:**
```json
{
  "restic_version": "0.16.0",
  "locations": {
    "backup1": "/path/to/repo"
  },
  "paths": ["/home/user", "/etc"]
}
```

#### POST /config
Updates the configuration.

**Request Body:**
```json
{
  "restic_version": "0.16.0",
  "locations": {
    "backup1": "/path/to/repo"
  },
  "paths": ["/home/user", "/etc"]
}
```

**Response:**
```json
{
  "message": "Configuration updated successfully"
}
```

### Repository Management

#### POST /locations
Initialize a new restic repository.

**Request Body:**
```json
{
  "location": "/path/to/new/repo",
  "password": "your-secure-password"
}
```

**Response:**
```json
{
  "message": "Repository initialized successfully",
  "location_id": "repo",
  "location": "/path/to/new/repo"
}
```

### Backup Management

#### GET /locations/{location_id}/backups
List all snapshots for a repository location.

**Headers:**
```
X-Restic-Password: your-repository-password
```

**Query Parameters:**
- `path` (optional): Filter snapshots by specific path

**Response:**
```json
[
  {
    "snapshot_id": "a1b2c3d4",
    "date": "2024-01-15 10:30:00",
    "size": "1.2GB"
  },
  {
    "snapshot_id": "e5f6g7h8",
    "date": "2024-01-14 10:30:00", 
    "size": "1.1GB"
  }
]
```

#### POST /locations/{location_id}/backups
Create a new backup with real-time streaming output.

**Headers:**
```
X-Restic-Password: your-repository-password
Content-Type: application/json
```

**Request Body:**
```json
{
  "path": "/path/to/backup"
}
```

**Response:** Server-Sent Events stream
```
data: {"message": "Starting backup..."}

data: {"output": "scanning /path/to/backup"}

data: {"output": "processed 1000 files"}

data: {"completed": true, "success": true, "snapshot_id": "a1b2c3d4"}
```

#### GET /locations/{location_id}/backups/{backup_id}
List contents of a specific backup snapshot.

**Headers:**
```
X-Restic-Password: your-repository-password
```

**Query Parameters:**
- `directory_path` (optional): Browse specific directory within backup (default: "/")

**Response:**
```json
[
  {
    "name": "file1.txt",
    "type": "file",
    "path": "/home/user/file1.txt",
    "size": 1024,
    "mode": 644,
    "mtime": "2024-01-15T10:30:00Z"
  },
  {
    "name": "documents",
    "type": "dir", 
    "path": "/home/user/documents",
    "mode": 755,
    "mtime": "2024-01-15T10:25:00Z"
  }
]
```

### Data Restoration

#### POST /locations/{location_id}/backups/{backup_id}/restore
Restore data from a backup snapshot with real-time streaming output.

**Headers:**
```
X-Restic-Password: your-repository-password
Content-Type: application/json
```

**Request Body:**
```json
{
  "target": "/path/to/restore/location",
  "is_dry_run": 0
}
```

**Parameters:**
- `target`: Directory where files should be restored
- `is_dry_run`: Set to 1 for dry-run mode (preview only)

**Response:** Server-Sent Events stream
```
data: {"message": "Starting restore..."}

data: {"output": "restoring file1.txt"}

data: {"output": "restoring documents/"}

data: {"completed": true, "success": true}
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (missing parameters, invalid JSON)
- `404`: Not Found (location or backup not found)
- `500`: Internal Server Error

Error responses follow this format:
```json
{
  "error": "Description of the error"
}
```

## Server-Sent Events

Backup and restore operations use Server-Sent Events (SSE) for real-time progress updates. Connect to these endpoints with an EventSource client:

```javascript
const eventSource = new EventSource('/locations/backup1/backups', {
  method: 'POST',
  headers: {
    'X-Restic-Password': 'your-password',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({path: '/home/user'})
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

## Configuration File

The server stores configuration in `~/config.json`:

```json
{
  "restic_version": "0.16.0",
  "locations": {
    "backup1": "/path/to/repo1",
    "backup2": "/path/to/repo2"
  },
  "paths": [
    "/home/user",
    "/etc",
    "/var/log"
  ]
}
```

## Backup Logs

Successful backup operations are logged to `~/backup_logs/{snapshot_id}.txt` for audit purposes.

## Security Notes

- Repository passwords are passed via HTTP headers and environment variables
- Ensure HTTPS is used in production environments
- Store repository passwords securely
- Consider implementing additional authentication mechanisms for production use

## Development

### Testing

Run the test script to verify basic functionality:

```bash
python test_server.py
```

### Starting the Server

Use the provided script:

```bash
./start_server.sh
```

Or manually:

```bash
source venv/bin/activate
python app.py
```

The server runs on `http://0.0.0.0:5000` by default.
