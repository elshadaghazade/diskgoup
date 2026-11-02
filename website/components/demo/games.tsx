'use client'

import { useMemo, useState } from 'react'
import { bytes, count } from './format'
import type { GameLibrary } from './types'

type Props = {
  libraries: GameLibrary[]
  total: number
}

/**
 * The game libraries.
 *
 * Steam and Epic titles, with the space each of them takes and what that
 * space is made of — the game files, the DLC, the saves, the screenshots
 * and the mods.
 */
export default function Games({ libraries, total }: Props) {
  const [platform, setPlatform] = useState('all')

  const platforms = ['all', ...new Set(libraries.map((library) => library.platform))]
  const visible = useMemo(
    () => libraries.filter((library) => platform === 'all' || library.platform === platform),
    [libraries, platform],
  )

  return (
    <>
      <div className="workspace-heading">
        <h1>Games</h1>
        <span className="summary">How much room do your games take?</span>
      </div>

      <div className="workspace-content">
        <div className="view-toolbar" style={{ padding: '0 0 12px', borderBottom: 0 }}>
          <div className="view-switcher" role="group" aria-label="Platform">
            {platforms.map((item) => (
              <button
                key={item}
                aria-pressed={platform === item}
                onClick={() => setPlatform(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="stat-row">
          <div className="stat">
            <div className="label">Total size</div>
            <div className="value">{bytes(total)}</div>
          </div>
          <div className="stat">
            <div className="label">Libraries</div>
            <div className="value">{count(visible.length)}</div>
          </div>
        </div>

        {visible.map((library) => (
          <div className="panel" key={library.platform}>
            <h3>
              {library.platform} · {count(library.games.length)} games · {bytes(library.size)}
            </h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Game</th>
                  <th className="num">Size</th>
                  <th>Categories</th>
                </tr>
              </thead>
              <tbody>
                {library.games.map((game) => (
                  <tr key={game.path}>
                    <td>
                      {game.name}
                      {game.protected && (
                        <span className="badge protected" style={{ marginLeft: 8 }}>
                          protected
                        </span>
                      )}
                    </td>
                    <td className="num">{bytes(game.size)}</td>
                    <td style={{ color: 'var(--dim)', fontSize: 12 }}>
                      {game.categories
                        .filter((entry) => entry.size > 0)
                        .map((entry) => `${entry.category} ${bytes(entry.size)}`)
                        .join(' · ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        {visible.length === 0 && (
          <div className="empty-state">
            <div>No Steam or Epic libraries were found on this machine.</div>
            <div className="hint">
              Unknown libraries and external mod or save folders can be added manually.
            </div>
          </div>
        )}

        <div className="notice">
          Measured game size is not reclaimable space. Saves and game files are protected, and
          removing a game entry only changes the inventory.
        </div>
      </div>
    </>
  )
}
