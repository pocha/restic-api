// Directory Browser Functionality

import { getDirectoryContent } from "./api_calls.js";

let dirBrowserCallback = null;

window.loadDirectory = async function (path) {
  const content = document.getElementById('dirBrowserContent');
  const pathInput = document.getElementById('currentDirPath');
  
  content.innerHTML = '<div class="text-center text-gray-500"><div class="loading mx-auto"></div>Loading...</div>';
  
  try {
    const data = await getDirectoryContent(path);
    pathInput.value = data.current_path;
    
    let html = '<div class="space-y-2">';
    
    // Add parent directory option if not at root
    if (data.parent) {
      html += `
        <div class="flex items-center p-2 hover:bg-gray-200 cursor-pointer rounded" onclick="loadDirectory('${data.parent}')">
          <span class="text-blue-600 mr-2">📁</span>
          <span class="text-blue-600 font-medium">..</span>
        </div>
      `;
    }
    
    // Add directories
    if (data.directories.length === 0) {
      html += '<div class="text-gray-500 text-sm italic">No subdirectories</div>';
    } else {
      data.directories.forEach(dir => {
        html += `
          <div class="flex items-center p-2 hover:bg-gray-200 cursor-pointer rounded" onclick="loadDirectory('${dir.path.replace(/'/g, "\\'")}')">
            <span class="text-yellow-600 mr-2">📁</span>
            <span>${dir.name}</span>
          </div>
        `;
      });
    }
    
    html += '</div>';
    content.innerHTML = html;
    
  } catch (error) {
    content.innerHTML = `<div class="text-red-600">Error: ${error.message}</div>`;
  }
}

function openDirectoryBrowser(callback, startPath = '/') {
  dirBrowserCallback = callback;
  const modal = document.getElementById('dirBrowserModal');
  modal.classList.remove('hidden');
  loadDirectory(startPath);
}

function closeDirectoryBrowser() {
  document.getElementById('dirBrowserModal').classList.add('hidden');
  dirBrowserCallback = null;
}

// Event listeners for directory browser
document.getElementById('closeDirBrowser').onclick = closeDirectoryBrowser;
document.getElementById('closeDirBrowserBtn').onclick = closeDirectoryBrowser;

document.getElementById('selectCurrentDir').onclick = function() {
  const selectedPath = document.getElementById('currentDirPath').value;
  if (dirBrowserCallback) {
    dirBrowserCallback(selectedPath);
  }
  closeDirectoryBrowser();
};

// Close when clicking outside
document.getElementById('dirBrowserModal').onclick = function(e) {
  if (e.target === this) {
    closeDirectoryBrowser();
  }
};

// Add browse buttons functionality
function addBrowseButton(inputId, buttonId) {
  const button = document.getElementById(buttonId);
  const input = document.getElementById(inputId);
  
  if (button && input) {
    button.onclick = function() {
      const currentPath = input.value || '/';
      openDirectoryBrowser((selectedPath) => {
        input.value = selectedPath;
        // Trigger blur event for size calculation if it's backupPath
        if (inputId === 'backupPath') {
          input.dispatchEvent(new Event('blur'));
        }
      }, currentPath);
    };
  }
}

// Initialize browse buttons when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  addBrowseButton('locationPath', 'browseLocationBtn');
  addBrowseButton('backupPath', 'browseBackupBtn');
});