const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test('Complete backup scheduling workflow', async ({ page }) => {
  // Test configuration
  const baseUrl = 'http://localhost:5000';
  const timestamp = Date.now();
  const tmpLocation = `/tmp/restic-test-location-${timestamp}`;
  const backupDir = `/tmp/test-backup-source-${timestamp}`;
  const backupDirRenamed = `/tmp/test-backup-source-${timestamp}-renamed`;
  const restoreDir = `/tmp/test-restore-target-${timestamp}`;
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
    await page.fill('#locationPath', tmpLocation);
    await page.fill('#locationPassword', 'testpassword123');
    await page.click('button[type="submit"]');

    // Wait for location to be added and appear in the list
    await page.waitForTimeout(3000);
    // Wait for loading to complete - loading indicator should disappear
    await page.waitForFunction(() => {
      const locationsList = document.getElementById('locationsList');
      return locationsList && !locationsList.innerHTML.includes('Loading...');
    }, { timeout: 15000 });
    
    // Debug: Check what's actually in the locations list
    const locationsContent = await page.locator('#locationsList').innerHTML();
    console.log('Locations content after loading:', locationsContent);
    
    // Wait for the new location to appear in the list
    await page.waitForFunction((locationPath) => {
      const locationsList = document.getElementById('locationsList');
      return locationsList && locationsList.textContent.includes(locationPath);
    }, tmpLocation, { timeout: 15000 });
    
    await expect(page.locator('#locationsList')).toContainText(tmpLocation);
    console.log('✓ Location added and verified in UI');

    // Step 3: Schedule a backup
    await page.selectOption('#backupLocation', { index: 1 }); // Select first location
    await page.fill('#backupPath', backupDir);
    await page.selectOption('#backupFrequency', 'daily');
    await page.fill('#backupTime', '10:30');
    await page.click('button:has-text("Schedule Backup")');

    // Wait for schedule to be created
    await page.waitForTimeout(3000);

    // Wait for schedule to be created
    await page.waitForTimeout(3000);

    // Step 4: Verify scheduled entry shows in UI
    await page.waitForTimeout(1000);
    await expect(page.locator('#scheduledBackupsList')).toBeVisible();
    await expect(page.locator('#scheduledBackupsContent')).toContainText(backupDir);
    await expect(page.locator('#scheduledBackupsContent')).toContainText('daily');
    await expect(page.locator('#scheduledBackupsContent')).toContainText('10:30');
    console.log('✓ Scheduled backup entry verified in UI');

    // Step 5: Hit the "Backup Now" button
    await page.click('button:has-text("Backup Now")');

    // Wait for backup modal to appear and complete
    await expect(page.locator('#dataModal')).toBeVisible();
    await page.waitForTimeout(1000);

    // Wait for backup to complete (look for success message or modal close)
    await page.waitForFunction(() => {
      const modal = document.querySelector('#backupModal');
      const output = document.querySelector('#backupOutput');
      return !modal || modal.style.display === 'none' || 
             (output && output.textContent.includes('snapshot') && output.textContent.includes('saved'));
    }, { timeout: 30000 });

    console.log('✓ Backup completed successfully');

    // Step 6: List backups to ensure one snapshot is showing
    await page.selectOption('#restoreLocation', { index: 1 });
    await page.selectOption('#restoreDirectory', backupDir);
    await page.fill('#restorePassword', 'testpassword123');
    await page.click('#listBackupsBtn');
    await page.waitForTimeout(2000);

    const snapshotItems = page.locator('[data-backup-index]');
    await expect(snapshotItems).toHaveCount(1);
    console.log('✓ One snapshot verified in backup list');

    // Step 7: Delete the scheduled backup
    await page.click('button:has-text("Delete")');
    await page.waitForTimeout(2000);

    // Verify scheduled backup is removed from UI
    await expect(page.locator('#scheduledBackupsContent div.bg-gray-50')).toHaveCount(0);
    console.log('✓ Scheduled backup deleted and removed from UI');

    // Step 9: List backups again (should still have the snapshot)
    await page.click('#listBackupsBtn');
    await page.waitForTimeout(2000);
    const snapshotItemsAfterDelete = page.locator('.snapshot-item');
    await expect(snapshotItemsAfterDelete).toHaveCount(1);
    console.log('✓ Snapshot still exists after schedule deletion');

    // Step 10: Click on the snapshot and show files
    await page.click('[data-backup-index]');
    await page.waitForTimeout(1000);

    // Click show files button
    await page.click('button:has-text("Show Files")');
    await page.waitForTimeout(2000);

    // Verify files are shown
    await expect(page.locator('#modalContent pre')).toHaveCount(1);
    console.log('✓ Snapshot files displayed');

    // Step 11: Show logs
    await page.click('button:has-text("Show Logs")');
    await page.waitForTimeout(1000);

    // Verify logs are displayed
    await expect(page.locator('#dataModal')).toBeVisible();
    await expect(page.locator('#modalContent')).toContainText('backup');
    
    // Close logs modal
    await page.click('#closeModal');
    await page.waitForTimeout(500);
    // Close logs modal
    await page.click('#closeModalBtn');
    console.log('✓ Backup logs displayed');

    // Step 12: Prepare for restore - rename the original directory
    fs.renameSync(backupDir, backupDirRenamed);
    console.log('✓ Original backup directory renamed');

    // Step 13: Perform restore
    await page.fill('input[placeholder="Enter path to restore to"]', backupDir);
    await page.click('button:has-text("Restore")');

    // Wait for restore modal and completion
    await expect(page.locator('#dataModal')).toBeVisible();
    await page.waitForFunction(() => {
      const output = document.querySelector('#restoreOutput');
      return output && (output.textContent.includes('Restore completed') || 
                       output.textContent.includes('restored') ||
                       output.textContent.includes('success'));
    }, { timeout: 60000 });

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
