export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach MeetNotes. Start the backend with python run.py, then retry.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = Array.isArray(body.detail) ? body.detail.map(e => e.msg).join(' ') : body.detail
    throw new Error(detail || `Request failed (${response.status}). Please retry.`)
  }
  return response.status === 204 ? null : response.json()
}

export const post = (path, body) => api(path, { method: 'POST', ...(body ? { body: JSON.stringify(body) } : {}) })
export const put = (path, body) => api(path, { method: 'PUT', body: JSON.stringify(body) })

export async function downloadMeeting(id, format) {
  const response = await fetch(`/api/meetings/${id}/export?format=${format}`)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || 'Export failed. Please retry.')
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = `meetnotes-${id}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const time = seconds => {
  const n = Math.max(0, Math.floor(seconds || 0))
  return [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(v => String(v).padStart(2, '0')).join(':')
}
export const date = value => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
export const busyStatuses = ['recording', 'paused', 'transcribing', 'generating']
