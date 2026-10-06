import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'

export function useResource(path, interval = 0) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const refresh = useCallback(() => setVersion(v => v + 1), [])
  useEffect(() => {
    if (!path) { setLoading(false); return }
    let stopped = false, timer
    const controller = new AbortController()
    setLoading(true)
    async function load() {
      try {
        const result = await api(path, { signal: controller.signal })
        if (!stopped) { setData(result); setError('') }
      } catch (err) {
        if (!stopped && err.name !== 'AbortError') setError(err.message)
      } finally {
        if (!stopped) {
          setLoading(false)
          if (interval) timer = setTimeout(load, interval)
        }
      }
    }
    load()
    return () => { stopped = true; controller.abort(); clearTimeout(timer) }
  }, [path, interval, version])
  return { data, error, loading, refresh, setData }
}
