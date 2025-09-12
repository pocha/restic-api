// API calls
const API_BASE = window.location.protocol + "//" +  window.location.host

export async function fetchConfig() {
  try {
    const response = await fetch(`${API_BASE}/config`)
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch config")
    }
    const config = await response.json()
    return config
  } catch (error) {
    console.error("Error fetching config:", error)
    return null
  }
}


export async function fetchSize(path) {
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

export async function addBackupLocation(path, password) {
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
    return null
  }
}

export async function listBackups(locationId, path, password) {
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
    return null
  }
}

export async function scheduleBackupAPICall(locationId, backupData, password, frequency, time) {
    try {
        const requestBody = {
            type: backupData.type,
            frequency: frequency,
            time: time,
        }

        // Add backup-specific data based on type
        if (backupData.type === "directory") {
            requestBody.path = backupData.path
        } else if (backupData.type === "command") {
            requestBody.command = backupData.command
            requestBody.filename = backupData.filename
        }

        const response = await fetch(`/locations/${locationId}/schedule`, {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-Restic-Password": password,  // Correct header name
            },
            body: JSON.stringify(requestBody),
        })

        if (!response.ok) {
            const error = await response.json()
            throw new Error(error.error || "Failed to schedule backup")
        }

        const result = await response.json()

        return result
    } catch (error) {
        console.log("Error scheduling backup: ", error)
        return null
    }

}

export async function getScheduledBackups(locationId) {
  try {
    const response = await fetch(`/locations/${locationId}/schedule`)
    if (!response.ok) {
      console.error("Failed to load scheduled backups")
      return null
    }

    const data = await response.json()
    return  data.schedules || []
  } catch (error) {
    console.error("Error loading scheduled backups:", error)
    return null
  }
}

export async function getSnapshotData(locationId, backupId, password, isLogs=false) {
    try {
    let url = `${API_BASE}/locations/${locationId}/backups/${backupId}`
    if (isLogs) {
        url += "?is_logs=1"
    }
    const response = await fetch( url, {
      headers: {
        "X-Restic-Password": password,
      },
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to fetch backup files")
    }

    return await response.json()
  } catch (error) {
    alert(`Error loading files: ${error.message}`)
    return null
  }
}