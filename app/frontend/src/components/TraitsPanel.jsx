function TraitsPanel({ traits, unitCount, boardCost, stats }) {
  // Get tier for a trait based on personal stats
  const getTier = (traitName) => {
    if (!stats?.traits) return null
    const trait = stats.traits.find(t =>
      t.name.toLowerCase() === traitName.toLowerCase()
    )
    if (!trait) return null
    const rate = trait.top4_rate
    if (rate >= 70) return 'S'
    if (rate >= 60) return 'A'
    if (rate >= 50) return 'B'
    if (rate >= 40) return 'C'
    return 'F'
  }

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
        Traits
      </h2>

      {/* Stats Row */}
      <div className="flex gap-4 mb-3 text-sm">
        <span className="flex items-center">
          <span className="mr-1">👥</span>
          <span className="font-bold text-white">{unitCount}</span>
        </span>
        <span className="flex items-center">
          <span className="mr-1">💰</span>
          <span className="font-bold text-white">{boardCost}g</span>
        </span>
      </div>

      {/* Traits List */}
      <div className="space-y-1">
        {traits.map(trait => {
          const tier = getTier(trait.name)
          return (
            <div key={trait.name} className="flex justify-between items-center h-6">
              <div className="flex items-center gap-1">
                <span className="text-sm text-[#d1d5db]">{trait.name}</span>
                {tier && <TierBadge tier={tier} />}
              </div>
              <span className="text-sm text-[#6b7280]">{trait.count}</span>
            </div>
          )
        })}

        {traits.length === 0 && (
          <div className="text-xs text-[#6b7280] text-center py-2">
            No active traits
          </div>
        )}
      </div>
    </div>
  )
}

function TierBadge({ tier }) {
  const colors = {
    'S': 'bg-[#eab308]',
    'A': 'bg-[#22c55e]',
    'B': 'bg-[#3b82f6]',
    'C': 'bg-[#6b7280]',
    'D': 'bg-[#f97316]',
    'F': 'bg-[#ef4444]',
  }

  return (
    <span className={`text-[10px] font-bold text-white px-1 py-0.5 rounded ${colors[tier] || colors['C']}`}>
      {tier}
    </span>
  )
}

export default TraitsPanel
