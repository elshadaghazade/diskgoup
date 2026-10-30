import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, percent } from '../lib/format'
import type { MonitorSample } from '../lib/types'

/** Live disk and network readings. */
export default function MonitorTab() {
  const [sample, setSample] = useState<MonitorSample | null>(null)
  const [error, setError] = useState('')
  const [live, setLive] = useState(true)

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    const tick = () => {
      api
        .monitor()
        .then((result) => {
          if (!cancelled) setSample(result)
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message)
        })
    }

    tick()
    if (live) {
      timer = window.setInterval(tick, 2000)
    }
    return () => {
      cancelled = true
      if (timer) window.clearInterval(timer)
    }
  }, [live])

  return (
    <>
      <div className="workspace-heading">
        <h1>Monitor</h1>
        <span className="summary">Simulated sample readings</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        {sample && (
          <>
            <div className="stat-row">
              <div className="stat">
                <div className="label">Network ↓</div>
                <div className="value">{bytes(sample.network.down)}/s</div>
              </div>
              <div className="stat">
                <div className="label">Network ↑</div>
                <div className="value">{bytes(sample.network.up)}/s</div>
              </div>
              <div className="stat">
                <div className="label">Disk read</div>
                <div className="value">{bytes(sample.disk.read)}/s</div>
              </div>
              <div className="stat">
                <div className="label">Disk write</div>
                <div className="value">{bytes(sample.disk.write)}/s</div>
              </div>
              <div className="stat">
                <div className="label">Disk usage</div>
                <div className="value">{bytes(sample.disk.usage)}</div>
                <div className="note">
                  {percent(sample.disk.usage, sample.disk.total, 0)} of{' '}
                  {bytes(sample.disk.total)}
                </div>
              </div>
            </div>

            <div className="panel">
              <h3>Sample processes</h3>
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">PID</th>
                    <th>Name</th>
                    <th className="num">CPU %</th>
                    <th className="num">Memory</th>
                  </tr>
                </thead>
                <tbody>
                  {sample.processes.map((process) => (
                    <tr key={process.pid}>
                      <td className="num">{process.pid}</td>
                      <td>{process.name}</td>
                      <td className="num">{process.cpu.toFixed(1)}</td>
                      <td className="num">{bytes(process.memory)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        <button className="button small" onClick={() => setLive(!live)}>
          {live ? 'Pause live updates' : 'Resume live updates'}
        </button>
      </div>
    </>
  )
}
