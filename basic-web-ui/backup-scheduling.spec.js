const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test('Complete backup scheduling workflow', async ({ page }) => {
  // Test configuration
  const baseUrl = 'http://localhost:5000';
  const tmpLocation = '/tmp/restic-test-location';
  const backupDir = '/tmp/test-backup-source';
  const backupDirRenamed = '/tmp/test-backup-source-renamed';
  const restoreDir = '/tmp/test-restore-target';
  const testFiles = [
    { name: 'file1.txt', content: 'This is test file 1' },
    { name: 'file2.txt', content: 'This is test file 2' },
    { name: 'subdir/file3.txt', content: 'This is test file 3 in subdirectory' }
  ];

  // Helper function to create directory and files
  const createTestFiles = (dir, files) => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    files.forEach(file => {
      const filePath = path.join(dir, file.name);
      const fileDir = path.dirname(filePath);
      if (!fs.existsSync(fileDir)) {
        fs.mkdirSync(fileDir, { recursive: true });
      }
      fs.writeFileSync(filePath, file.content);
    });
  };

  // Helper function to compare directories
  const compareDirectories = (dir1, dir2, files) => {
    for (const file of files) {
      const file1Path = path.join(dir1, file.name);
      const file2Path = path.join(dir2, file.name);
      
      if (!fs.existsSync(file1Path) || !fs.existsSync(file2Path)) {
        return false;
      }
      
      const content1 = fs.readFileSync(file1Path, 'utf8');
      const content2 = fs.readFileSync(file2Path, 'utf8');
      
      if (content1 !== content2) {
        return false;
      }
    }
    return true;
  };

  // Cleanup function
  const cleanup = () => {
    [tmpLocation, backupDir, backupDirRenamed, restoreDir].forEach(dir => {
      if (fs.existsSync(dir)) {
        fs.rmSync(dir, { recursive: true, force: true });
      }
    });
  };

  try {
    // Initial cleanup
    cleanup();

    // Create tmp location directory
    fs.mkdirSync(tmpLocation, { recursive: true });

    // Create backup source directory with test files
    createTestFiles(backupDir, testFiles);

    console.log('Test setup completed');

    // Step 1: Load the UI
    await page.goto(baseUrl);
    await expect(page).toHaveTitle(/Restic API/);
    console.log('✓ UI loaded successfully');

    // Step 2: Add the location
    await page.fill('#locationName', 'Test Location');
    await page.fill('#locationPath', tmpLocation);
    await page.fill('#locationPassword', 'testpassword123');
    await page.click('#addLocationBtn');

    // Wait for location to be added and appear in the list
    await page.waitForTimeout(2000);
    await expect(page.locator('.location-item')).toContainText('Test Location');
    console.log('✓ Location added and verified in UI');

    // Step 3: Select the location to load backup interface
    await page.click('.location-item:has-text("Test Location")');
    await page.waitForTimeout(1000);

    // Verify backup interface is loaded
    await expect(page.locator('#backupSection')).toBeVisible();
    console.log('✓ Backup interface loaded');

    // Step 4: Schedule a backup
    await page.fill('#backupPath', backupDir);
    await page.selectOption('#frequency', 'daily');
    await page.fill('#backupTime', '10:30');
    await page.click('#scheduleBackupBtn');

    // Wait for schedule to be created
    await page.waitForTimeout(3000);

    // Step 5: Verify scheduled entry shows in UI
    await expect(page.locator('.scheduled-backup-item')).toBeVisible();
    await expect(page.locator('.scheduled-backup-item')).toContainText(backupDir);
    await expect(page.locator('.scheduled-backup-item')).toContainText('daily');
    await expect(page.locator('.scheduled-backup-item')).toContainText('10:30');
    console.log('✓ Scheduled backup entry verified in UI');

    // Step 6: Hit the "Backup Now" button
    await page.click('.backup-now-btn');

    // Wait for backup modal to appear and complete
    await expect(page.locator('#backupModal')).toBeVisible();
    await page.waitForTimeout(1000);

    // Wait for backup to complete (look for success message or modal close)
    await page.waitForFunction(() => {
      const modal = document.querySelector('#backupModal');
      const output = document.querySelector('#backupOutput');
      return !modal || modal.style.display === 'none' || 
             (output && output.textContent.includes('snapshot') && output.textContent.includes('saved'));
    }, { timeout: 30000 });

    console.log('✓ Backup completed successfully');

    // Step 7: List backups to ensure one snapshot is showing
    await page.click('#listBackupsBtn');
    await page.waitForTimeout(2000);

    const snapshotItems = page.locator('.snapshot-item');
    await expect(snapshotItems).toHaveCount(1);
    console.log('✓ One snapshot verified in backup list');

    // Step 8: Delete the scheduled backup
    await page.click('.delete-schedule-btn');
    await page.waitForTimeout(2000);

    // Verify scheduled backup is removed from UI
    await expect(page.locator('.scheduled-backup-item')).toHaveCount(0);
    console.log('✓ Scheduled backup deleted and removed from UI');

    // Step 9: List backups again (should still have the snapshot)
    await page.click('#listBackupsBtn');
    await page.waitForTimeout(2000);
    await expect(snapshotItems).toHaveCount(1);
    console.log('✓ Snapshot still exists after schedule deletion');

    // Step 10: Click on the snapshot and show files
    await page.click('.snapshot-item');
    await page.waitForTimeout(1000);

    await page.click('.show-files-btn');
    await page.waitForTimeout(2000);

    // Verify files are shown
    await expect(page.locator('.file-item')).toHaveCountGreaterThan(0);
    console.log('✓ Snapshot files displayed');

    // Step 11: Show logs
    await page.click('.show-logs-btn');
    await page.waitForTimeout(1000);

    // Verify logs are displayed
    await expect(page.locator('#logsModal')).toBeVisible();
    await expect(page.locator('#logsOutput')).toContainText('backup');
    
    // Close logs modal
    await page.click('.close-logs-btn');
    console.log('✓ Backup logs displayed');

    // Step 12: Prepare for restore - rename the original directory
    fs.renameSync(backupDir, backupDirRenamed);
    console.log('✓ Original backup directory renamed');

    // Step 13: Perform restore
    await page.fill('#restorePath', backupDir);
    await page.click('.restore-btn');

    // Wait for restore modal and completion
    await expect(page.locator('#restoreModal')).toBeVisible();
    await page.waitForFunction(() => {
      const modal = document.querySelector('#restoreModal');
      const output = document.querySelector('#restoreOutput');
      return !modal || modal.style.display === 'none' || 
             (output && (output.textContent.includes('restoring') || output.textContent.includes('restored')));
    }, { timeout: 30000 });

    console.log('✓ Restore completed');

    // Step 14: Compare restored content with original
    await page.waitForTimeout(2000);

    // Verify restored directory exists
    if (!fs.existsSync(backupDir)) {
      throw new Error('Restored directory does not exist');
    }

    // Compare content
    const contentMatches = compareDirectories(backupDir, backupDirRenamed, testFiles);
    if (!contentMatches) {
      throw new Error('Restored content does not match original content');
    }

    console.log('✓ Restored content matches original content');
    console.log('🎉 All test steps completed successfully!');

  } catch (error) {
    console.error('Test failed:', error);
    throw error;
  } finally {
    // Cleanup
    cleanup();
    console.log('✓ Test cleanup completed');
  }
});
