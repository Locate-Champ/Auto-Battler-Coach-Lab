/**
 * PoolTracker Component
 *
 * Displays the unit pool state showing which champions are contested
 * and their availability across all players.
 */

import { useState } from 'react'
import { usePoolTracker } from '../hooks/usePoolTracker'

// Cost color scheme
const COST_COLORS = {
  1: { bg: '#5a5a6f', border: '#7a7a8f', label: '1-Cost' },
  2: { bg: '#2ecc71', border: '#27ae60', label: '2-Cost' },
  3: { bg: '#3498db', border: '#2980b9', label: '3-Cost' },
  4: { bg: '#9b59b6', border: '#8e44ad', label: '4-Cost' },
  5: { bg: '#f1c40f', border: '#f39c12', label: '5-Cost' },
}

// Availability colors
const AVAILABILITY_COLORS = {
  high: '#69db7c',    // Green - plenty available
  medium: '#ffa94d',  // Orange - some taken
  low: '#ff6b6b',     // Red - heavily contested
  none: '#495057',    // Gray - pool empty
}

function PoolTracker({ gameState }) {
  const poolState = usePoolTracker(gameState)
  const [expandedCost, setExpandedCost] = useState(null)
  const [showContested, setShowContested] = useState(true)

  if (!poolState) {
    return (
      <div className="panel-card p-3">
        <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
          Pool Tracker
        </h2>
        <div className="text-xs text-[#6b7280] text-center py-4">
          Waiting for game data...
        </div>
      </div>
    )
  }

  const poolSummary = poolState.getPoolSummary()
  const totalInPlay = poolState.getTotalInPlay()

  // Get contested units (any with inPlay > 0)
  const getContestedUnits = () => {
    const contested = []
    for (let cost = 1; cost <= 5; cost++) {
      const tier = poolSummary[cost]
      if (!tier) continue
      for (const champ of tier.champions) {
        if (champ.inPlay > 0) {
          contested.push({ ...champ, cost })
        }
      }
    }
    // Sort by most contested (fewest remaining)
    return contested.sort((a, b) => a.remaining - b.remaining)
  }

  const contestedUnits = getContestedUnits()

  return (
    <div className="panel-card p-3">
      <div className="flex justify-between items-center border-b border-[#374151] pb-2 mb-3">
        <h2 className="text-sm font-bold text-[#00d4ff]">
          Pool Tracker
        </h2>
        <span className="text-xs text-[#6b7280]">
          {totalInPlay} units in play
        </span>
      </div>

      {/* Toggle buttons */}
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setShowContested(true)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            showContested
              ? 'bg-[#00d4ff] text-[#0f172a]'
              : 'bg-[rgba(55,65,81,0.5)] text-[#9ca3af] hover:bg-[rgba(55,65,81,0.7)]'
          }`}
        >
          Contested
        </button>
        <button
          onClick={() => setShowContested(false)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            !showContested
              ? 'bg-[#00d4ff] text-[#0f172a]'
              : 'bg-[rgba(55,65,81,0.5)] text-[#9ca3af] hover:bg-[rgba(55,65,81,0.7)]'
          }`}
        >
          By Cost
        </button>
      </div>

      {showContested ? (
        /* Contested view - shows only units that are in play */
        <div className="space-y-1 max-h-[300px] overflow-y-auto pr-1">
          {contestedUnits.length === 0 ? (
            <div className="text-xs text-[#6b7280] text-center py-4">
              No units detected yet
            </div>
          ) : (
            contestedUnits.map((unit) => (
              <div
                key={unit.id}
                className="flex items-center justify-between p-1.5 rounded bg-[rgba(31,41,55,0.5)]"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: COST_COLORS[unit.cost].bg }}
                  />
                  <span className="text-xs text-[#e5e7eb]">
                    {unit.name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs font-mono"
                    style={{ color: AVAILABILITY_COLORS[unit.availability] }}
                  >
                    {unit.remaining}/{poolState.POOL_SIZES[unit.cost]}
                  </span>
                  <div
                    className="w-16 h-1.5 rounded-full bg-[rgba(55,65,81,0.5)] overflow-hidden"
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${(unit.remaining / poolState.POOL_SIZES[unit.cost]) * 100}%`,
                        backgroundColor: AVAILABILITY_COLORS[unit.availability],
                      }}
                    />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* By Cost view - shows all units grouped by cost tier */
        <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
          {[1, 2, 3, 4, 5].map((cost) => {
            const tier = poolSummary[cost]
            if (!tier) return null

            const isExpanded = expandedCost === cost
            const contestedInTier = tier.champions.filter(c => c.inPlay > 0).length

            return (
              <div key={cost} className="rounded bg-[rgba(31,41,55,0.5)]">
                {/* Cost tier header */}
                <button
                  onClick={() => setExpandedCost(isExpanded ? null : cost)}
                  className="w-full flex items-center justify-between p-2 hover:bg-[rgba(55,65,81,0.3)] transition-colors rounded"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
                      style={{ backgroundColor: COST_COLORS[cost].bg }}
                    >
                      {cost}
                    </span>
                    <span className="text-xs text-[#e5e7eb]">
                      {COST_COLORS[cost].label}
                    </span>
                    {contestedInTier > 0 && (
                      <span className="text-[10px] text-[#ffa94d]">
                        {contestedInTier} contested
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-[#6b7280]">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </button>

                {/* Expanded champions list */}
                {isExpanded && (
                  <div className="px-2 pb-2 space-y-1">
                    {tier.champions.map((champ) => (
                      <div
                        key={champ.id}
                        className="flex items-center justify-between py-0.5"
                      >
                        <span
                          className="text-xs"
                          style={{
                            color: champ.inPlay > 0 ? AVAILABILITY_COLORS[champ.availability] : '#6b7280',
                          }}
                        >
                          {champ.name}
                        </span>
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: AVAILABILITY_COLORS[champ.availability] }}
                        >
                          {champ.remaining}/{tier.poolSize}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Shop odds reference */}
      <div className="mt-3 pt-2 border-t border-[#374151]">
        <div className="text-[10px] text-[#6b7280] text-center">
          Pool: 1★ = 30 | 2★ = 25 | 3★ = 18 | 4★ = 10 | 5★ = 9
        </div>
      </div>
    </div>
  )
}

export default PoolTracker
