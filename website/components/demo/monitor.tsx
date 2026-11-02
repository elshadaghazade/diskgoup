'use client'

import { useEffect, useState } from 'react'
import { bytes, percent } from './format'
import type { MonitorSample } from './types'

type Props = {
  sample: MonitorSample
}

/**
 * Live disk and network readings.
 *
 * The desktop app samples the machine it runs on. Here the readings come
 * from the sample machine, and they move — the numbers are the ones the
 * CLI produces, not the ones of the reader's own computer.
 */
export default function Monitor({ sample }: Props) {
  const [live, setLive] = useState(true)
  const [current, setCurrent] = useState(sample)

  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(() => {
      setCurrent((previous) => {
        // The readings wander around the sampled values — a rate is a rate,
        // not a constant.
        const drift = (value: number, spread: number) =>
          Math.max(0, value * (1 + (Math.random() - 0.5) * spread))
        return {
          ...previous,
          timestamp: Date.now() / 1000,
          network: {
            down: drift(previous.network.down, 0.6),
            up: drift(previous.network.up, 0.8),
          },
          disk: {
            ...previous.disk,
            read: drift(previous.disk.read, 0.5),
            write: drift(previous.disk.write, 0.9),
          },
          processes: previous.processes.map((process) => ({
            ...process,
            cpu: Math.max(0, process.cpu + (Math.random() - 0.5) * 3),
          })),
        }
      })
    }, 2000)
    return () => window.clearInterval(timer)
  }, [live])

  return (
    <>
      <div className="workspace-heading">
        <h1>Monitor</h1>
        <span className="summary">Sample readings of the sample machine</span>
      </div>

      <div className="workspace-content">
        <div className="stat-row">
          <div className="stat">
            <div className="label">Network ↓</div>
            <div className="value">{bytes(current.network.down)}/s</div>
          </div>
          <div className="stat">
            <div className="label">Network ↑</div>
            <div className="value">{bytes(current.network.up)}/s</div>
          </div>
          <div className="stat">
            <div className="label">Disk read</div>
            <div className="value">{bytes(current.disk.read)}/s</div>
          </div>
          <div className="stat">
            <div className="label">Disk write</div>
            <div className="value">{bytes(current.disk.write)}/s</div>
          </div>
          <div className="stat">
            <div className="label">Disk usage</div>
            <div className="value">{bytes(current.disk.usage)}</div>
            <div className="note">
              {percent(current.disk.usage, current.disk.total, 0)} of {bytes(current.disk.total)}
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
              {current.processes.map((process) => (
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

        <button className="button small" onClick={() => setLive(!live)}>
          {live ? 'Pause live updates' : 'Resume live updates'}
        </button>
      </div>
    </>
  )
}
