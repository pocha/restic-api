# Restic API Web UI - Testing Guide

This directory contains the web UI for the Restic API and its automated tests.
Web-ui is accessible on / once you start the server with `start_server.sh` script in the main directory. Eg. `http://localhost:5000`

Follow steps below to run the playwright UI tests: 

## Prerequisites

- Node.js (version 14 or higher)
- npm or yarn package manager

We recommend installing nodejs with npm from official Nodejs website using nvm. Link [here](https://nodejs.org/en/download/)

## Installation

1. Navigate to the basic-web-ui directory:
```bash
cd basic-web-ui
```

2. Install dependencies:
```bash
npm install
```

3. Install Playwright browsers:
```bash
npx playwright install
```

## Running Tests

> Running tests will overwrite your config.json file in your home directory. Back it up before you run the test & revert it after running the test

Normally, you would only need to run the test at the start to check if the UI works as expected. The tests are tested to be run on Linux machine only as of now. 

### Run all tests in headless mode:
```bash
cp test-data/config.json ~/config.json & npx playwright test
```

### Run a specific test file:
```bash
cp test-data/config.json ~/config.json & npx playwright test backup-scheduling.spec.js
```

### Run tests with UI (headed mode):
```bash
cp test-data/config.json ~/config.json & npx playwright test --headed
```

### Run tests with debug mode:
```bash
npx playwright test --debug
```

## Test Structure

- `backup-scheduling.spec.js` - Comprehensive test for backup scheduling functionality including:
  - Creating backup locations
  - Scheduling backups with different frequencies
  - Triggering immediate backups
  - Viewing backup snapshots and files
  - Restoring backups
  - Deleting scheduled backups

## Test Requirements

Before running tests, ensure:

1. The Restic API server is running on `http://localhost:5000`
2. The web UI is accessible at `http://localhost:5000`
3. You have sufficient disk space for test backup operations
4. `/tmp` directory is writable for creating test directories

## Troubleshooting

### Common Issues:

1. **"Looks like you launched a headed browser without having a XServer running"**
   - Run tests in headless mode: `npx playwright test`
   - Or install a display server if running on a headless system

2. **Timeout errors**
   - Increase timeout in playwright.config.js
   - Ensure the API server is running and responsive

3. **Permission errors**
   - Ensure `/tmp` directory has write permissions
   - Check that the test user can create and delete files

## Configuration

Test configuration can be modified in `playwright.config.js` (if present) or by using command-line options.

For more information on Playwright testing, visit: https://playwright.dev/docs/intro
