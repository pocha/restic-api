// API Base URL
const API_BASE = "http://20.42.15.153:5000"

// Global variables
let config = {}
let locations = []

// Utility functions
function showLoading(elementId) {
  const element = document.getElementById(elementId)
  element.innerHTML = '<div class="loading mx-auto"></div><p class="text-center text-gray-500 mt-2">Loading...</p>'
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function convertResticSizeToBytes(sizeStr) {
  if (!sizeStr || sizeStr === "N/A" || sizeStr === "Unknown") {
    return 0
  }

  // Extract number and unit from strings like "123.45MiB", "1.2GiB", etc.
  const match = sizeStr.match(/^([\d.]+)\s*([KMGT]?i?B)$/)
  if (!match) {
    return 0
  }

  const value = parseFloat(match[1])
  const unit = match[2]

  // Convert to bytes based on unit (using binary prefixes as restic uses)
  const multipliers = {
    B: 1,
    KiB: 1024,
    MiB: 1024 * 1024,
    GiB: 1024 * 1024 * 1024,
    TiB: 1024 * 1024 * 1024 * 1024,
    // Also handle decimal prefixes just in case
    KB: 1000,
    MB: 1000 * 1000,
    GB: 1000 * 1000 * 1000,
    TB: 1000 * 1000 * 1000 * 1000,
  }

  return Math.round(value * (multipliers[unit] || 1))
}
// API calls
async function fetchConfig() {
  try {
    const response = await fetch(`${API_BASE}/config`)
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch config")
    }
    config = await response.json()
    return config
  } catch (error) {
    console.error("Error fetching config:", error)
    return null
  }
}

async function fetchSize(path) {
  try {
    const response = await fetch(`${API_BASE}/size?path=${encodeURIComponent(path)}`)
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch size")
    }
    return await response.json()
  } catch (error) {
    console.error("Error fetching size:", error)
    return null
  }
}

async function addLocation(path, password) {
  try {
    const response = await fetch(`${API_BASE}/locations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        location: path,
        password: password,
      }),
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to add location")
    }
    return await response.json()
  } catch (error) {
    console.error("Error adding location:", error)
    throw error
  }
}

async function startBackup(locationId, path, password) {
  try {
    const response = await fetch(`${API_BASE}/locations/${locationId}/backups`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Restic-Password": password,
      },
      body: JSON.stringify({ path: path }),
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to start backup")
    }

    // Use the modal to show backup progress
    showDataInModal("Backup Progress", response.body, true)
  } catch (error) {
    console.error("Error starting backup:", error)
    showDataInModal("Backup Error", error.message, false)
    throw error
  }
}

async function listBackups(locationId, path, password) {
  try {
    const response = await fetch(`${API_BASE}/locations/${locationId}/backups?path=${encodeURIComponent(path)}`, {
      headers: {
        "X-Restic-Password": password,
      },
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to list backups")
    }
    return await response.json()
  } catch (error) {
    console.error("Error listing backups:", error)
    throw error
  }
}

let locationsArray = []
async function fetchLocationsAndStoreLocally() {
  const configData = await fetchConfig()
  if (!configData || !configData.locations) return
  locationsArray = Object.entries(configData.locations).map(([key, value]) => ({
    id: key,
    path: value.repo_path || value.path,
    paths: value.paths || [],
    password: value.password,
  }))
}

// UI functions
async function loadLocations() {
  showLoading("locationsList")

  if (locationsArray.length == 0) {
    document.getElementById("locationsList").innerHTML = '<p class="text-center text-gray-500">No locations found</p>'
    return
  }

  // Convert locations object to array of location objects

  let html = '<div class="space-y-4">'

  for (const location of locationsArray) {
    const sizeData = await fetchSize(location.path)
    const totalSize = sizeData ? formatBytes(sizeData.total || 0) : "Unknown"
    const usedSize = sizeData ? formatBytes(sizeData.used || 0) : "Unknown"
    const pathsCount = location.paths ? location.paths.length : 0

    html += `
            <div class="border border-gray-200 rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-medium text-gray-800">${location.path}</h4>
                        <p class="text-sm text-gray-600 mt-1">
                            Size: ${usedSize} / ${totalSize} | 
                            Backing up ${pathsCount} path${pathsCount !== 1 ? "s" : ""}
                        </p>
                    </div>
                    <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">ID: ${location.id}</span>
                </div>
            </div>
        `
  }

  html += "</div>"
  document.getElementById("locationsList").innerHTML = html
}

function updateLocationDropdowns() {
  const backupSelect = document.getElementById("backupLocation")
  const restoreSelect = document.getElementById("restoreLocation")

  // Clear existing options except first
  backupSelect.innerHTML = '<option value="">Select a location...</option>'
  restoreSelect.innerHTML = '<option value="">Select a location...</option>'

  locationsArray.forEach((location) => {
    const option = `<option value="${location.id}">${location.path} (ID: ${location.id})</option>`
    backupSelect.innerHTML += option
    restoreSelect.innerHTML += option
  })
}

function updateDirectoryDropdown(locationId) {
  const restoreDirectorySelect = document.getElementById("restoreDirectory")
  restoreDirectorySelect.innerHTML = '<option value="">Select a directory...</option>'

  const location = locationsArray.find((loc) => loc.id === locationId)
  if (location && location.paths) {
    location.paths.forEach((path) => {
      restoreDirectorySelect.innerHTML += `<option value="${path}">${path}</option>`
    })
  }
}

// Event listeners
document.addEventListener("DOMContentLoaded", async function () {
  await fetchLocationsAndStoreLocally()
  // Load initial data
  loadLocations()

  // Update dropdowns
  updateLocationDropdowns()

  // Add Location Form
  document.getElementById("addLocationForm").addEventListener("submit", async function (e) {
    e.preventDefault()

    const formData = new FormData(e.target)
    const path = formData.get("path")
    const password = formData.get("password")

    if (!path || !password) {
      alert("Please fill in all fields including password")
      return
    }

    showLoadingOnButton(e.submitter)
    try {
      await addLocation(path, password)
      alert("Location added successfully!")
      location.reload() // Refresh page as requested
    } catch (error) {
      alert("Error adding location: " + error.message)
    }
    hideLoadingOnButton(e.submitter)
  })

  // Backup Directory Input - fetch size on change
  document.getElementById("backupPath").addEventListener("blur", async function () {
    const path = this.value.trim()
    const sizeSpan = document.getElementById("pathSize")

    if (path) {
      sizeSpan.innerHTML = '<div class="loading"></div>'
      const sizeData = await fetchSize(path)
      if (sizeData) {
        sizeSpan.textContent = formatBytes(sizeData.used || 0)
      } else {
        sizeSpan.textContent = "Error"
      }
    } else {
      sizeSpan.textContent = "-"
    }
  })

  // Backup Form
  document.getElementById("backupForm").addEventListener("submit", async function (e) {
    e.preventDefault()

    const formData = new FormData(e.target)
    const locationId = formData.get("location")
    const directory = formData.get("path")
    const password = formData.get("password")

    if (!locationId || !directory || !password) {
      alert("Please fill in all fields including password")
      hideLoadingOnButton(e.submitter)
      return
    }

    showLoadingOnButton(e.submitter)
    try {
      await startBackup(locationId, directory, password)
    } catch (error) {
      console.error("Backup failed:", error)
      showDataInModal("Backup Error", error.message, false)
    }
    hideLoadingOnButton(e.submitter)
  })

  // Restore Location Change
  document.getElementById("restoreLocation").addEventListener("change", function () {
    const locationId = this.value
    if (locationId) {
      updateDirectoryDropdown(locationId)
    } else {
      document.getElementById("restoreDirectory").innerHTML = '<option value="">Select a directory...</option>'
    }
  })

  // List Backups Button
  document.getElementById("listBackupsBtn").addEventListener("click", async function () {
    const locationId = document.getElementById("restoreLocation").value
    const directory = document.getElementById("restoreDirectory").value

    if (!locationId || !directory) {
      alert("Please select both location and directory")
      return
    }

    const button = document.getElementById("listBackupsBtn")
    try {
      const restorePassword = document.getElementById("restorePassword").value
      if (!restorePassword) {
        alert("Please enter password for restore operations")
        return
      }

      showLoadingOnButton(button)
      const backups = await listBackups(locationId, directory, restorePassword)

      document.getElementById("backupsList").classList.remove("hidden")

      if (!backups || backups.length === 0) {
        document.getElementById("backupsContent").innerHTML =
          '<p class="text-center text-gray-500">No backups found for this directory</p>'
        hideLoadingOnButton(button)
        return
      }

      let html = '<div class="space-y-4">'

      backups.forEach((backup, index) => {
        const backupDate = new Date(backup.date).toLocaleString()
        const backupSize = backup.size

        html += `
                    <div class="border border-gray-200 rounded-lg p-4" data-backup-index="${index}">
                        <div class="flex justify-between items-start mb-3">
                            <div>
                                <h4 class="font-medium text-gray-800">Snapshot: ${backup.snapshot_id}</h4>
                                <p class="text-sm text-gray-600">Date: ${backupDate}</p>
                                <p class="text-sm text-gray-600">Size: ${backupSize}</p>
                            </div>
                            <div class="flex space-x-2">
                                <button onclick="showBackupFiles('${locationId}', '${backup.snapshot_id}', ${index}, this)" 
                                        class="bg-blue-500 text-white px-3 py-1 rounded text-sm hover:bg-blue-600">
                                    Show Files
                                </button>
                                <button onclick="showBackupLogs('${locationId}', '${backup.snapshot_id}', ${index}, this)" 
                                        class="bg-green-500 text-white px-3 py-1 rounded text-sm hover:bg-green-600">
                                    Show Logs
                                </button>
                                <button onclick="restoreBackupAction('${locationId}', '${backup.snapshot_id}', ${index}, this)" 
                                        class="bg-red-500 text-white px-3 py-1 rounded text-sm hover:bg-red-600">
                                    Restore
                                </button>
                            </div>
                        </div>
                        <div id="backup-details-${index}" class="hidden mt-3 p-3 bg-gray-50 rounded border-l-4 border-blue-500">
                            <!-- Details will be loaded here -->
                        </div>
                    </div>
                `
      })

      html += "</div>"
      document.getElementById("backupsContent").innerHTML = html
    } catch (error) {
      document.getElementById("backupsList").classList.remove("hidden")
      document.getElementById(
        "backupsContent"
      ).innerHTML = `<p class="text-center text-red-500">Error loading backups: ${error.message}</p>`
    }
    hideLoadingOnButton(button)
  })
})

// Loading utility functions
function showLoadingOnButton(button) {
  button.disabled = true
  button.dataset.originalText = button.textContent
  button.innerHTML =
    '<span class="inline-flex items-center"><svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Loading...</span>'
}

function hideLoadingOnButton(button) {
  button.disabled = false
  if (button.dataset.originalText) {
    button.innerHTML = button.dataset.originalText
    delete button.dataset.originalText
  }
}

// Modal function to display data (SSE or response)
function showDataInModal(title, dataSource, isSSE = false) {
  const modal = document.getElementById("dataModal")
  const modalTitle = document.getElementById("modalTitle")
  const modalContent = document.getElementById("modalContent")
  const closeModal = document.getElementById("closeModal")
  const closeModalBtn = document.getElementById("closeModalBtn")

  // Set title
  modalTitle.textContent = title

  // Clear previous content
  modalContent.innerHTML = '<div class="text-blue-600">Loading...</div>'

  // Show modal
  modal.classList.remove("hidden")

  // Handle SSE data
  if (isSSE && dataSource && typeof dataSource.getReader === "function") {
    handleSSEInModal(dataSource, modalContent)
  }
  // Handle regular response data
  else if (dataSource) {
    if (typeof dataSource === "string") {
      modalContent.innerHTML = `<pre class="text-xs overflow-x-auto whitespace-pre-wrap">${dataSource}</pre>`
    } else {
      modalContent.innerHTML = `<pre class="text-xs overflow-x-auto">${JSON.stringify(dataSource, null, 2)}</pre>`
    }
  }

  // Close modal handlers
  const closeModalHandler = () => {
    modal.classList.add("hidden")
  }

  closeModal.onclick = closeModalHandler
  closeModalBtn.onclick = closeModalHandler

  // Close modal when clicking outside
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeModalHandler()
    }
  }
}

// Helper function to handle SSE data in modal
async function handleSSEInModal(responseBody, modalContent) {
  modalContent.innerHTML = '<div class="text-blue-600">Starting...</div>'

  try {
    const reader = responseBody.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split("\n")

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6))
            const logEntry = document.createElement("div")

            if (data.output) {
              logEntry.textContent = data.output
              logEntry.className = "text-sm text-gray-700 mb-1"
            } else if (data.message) {
              logEntry.textContent = data.message
              logEntry.className = "text-blue-600 mb-1"
            } else if (data.completed) {
              logEntry.textContent = data.success ? "Operation completed successfully!" : "Operation failed!"
              logEntry.className = data.success ? "text-green-600 font-medium" : "text-red-600 font-medium"
            } else if (data.error) {
              logEntry.textContent = `Error: ${data.error}`
              logEntry.className = "text-red-600 font-medium"
            }

            if (logEntry.textContent) {
              modalContent.appendChild(logEntry)
              modalContent.scrollTop = modalContent.scrollHeight
            }
          } catch (parseError) {
            console.warn("Failed to parse SSE data:", line)
          }
        }
      }
    }
  } catch (error) {
    modalContent.innerHTML = `<div class="text-red-600">Error: ${error.message}</div>`
  }
}

// Button handler functions
async function showBackupFiles(locationId, backupId, index, button) {
  const password = document.getElementById("restorePassword").value
  if (!password) {
    alert("Please enter the restore password")
    return
  }

  showLoadingOnButton(button)
  try {
    const response = await fetch(`${API_BASE}/locations/${locationId}/backups/${backupId}`, {
      headers: {
        "X-Restic-Password": password,
      },
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch backup files")
    }

    const data = await response.json()
    // Format files as "<file path>, size"
    let formattedFiles = data
      .map((file) => `${file.path}, ${typeof file.size === "number" ? formatBytes(file.size) : "-"}`)
      .join("\n")
    showDataInModal("Files in backup:", formattedFiles)
  } catch (error) {
    alert(`Error loading files: ${error.message}`)
  }
  hideLoadingOnButton(button)
}

async function showBackupLogs(locationId, backupId, index, button) {
  const password = document.getElementById("restorePassword").value
  if (!password) {
    alert("Please enter the restore password")
    return
  }

  showLoadingOnButton(button)
  try {
    const response = await fetch(`${API_BASE}/locations/${locationId}/backups/${backupId}?is_logs=1`, {
      headers: {
        "X-Restic-Password": password,
      },
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch backup logs")
    }
    const data = await response.json()
    // Display logs as plain text - backend returns {logs: "content"}
    const logContent = data.logs || "No logs available"
    showDataInModal("Backup Logs", logContent)
  } catch (error) {
    alert(`Error loading logs: ${error.message}`)
  }
  hideLoadingOnButton(button)
}

async function restoreBackupAction(locationId, backupId, index, button) {
  const password = document.getElementById("restorePassword").value
  if (!password) {
    alert("Please enter the restore password")
    return
  }

  // Get target directory from user
  const target = prompt("Enter target directory for restore:", "/tmp/restore_" + backupId)
  if (!target) {
    alert("Target directory is required for restore")
    return
  }

  showLoadingOnButton(button)
  try {
    const response = await fetch(`${API_BASE}/locations/${locationId}/backups/${backupId}/restore`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Restic-Password": password,
      },
      body: JSON.stringify({ target: target }),
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to restore backup")
    }

    // Use the modal to display restore progress
    showDataInModal(`Restore Progress - Backup ${backupId}`, response.body, true)
  } catch (error) {
    console.error("Error starting restore:", error)
    showDataInModal(`Restore Error - Backup ${backupId}`, `Error: ${error.message}`, false)
  }
  hideLoadingOnButton(button)
}
