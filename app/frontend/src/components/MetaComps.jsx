function MetaComps({ metaComps, loading }) {
  if (loading) {
    return (
      <div className="panel-card p-3">
        <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
          Meta Comps
        </h2>
        <div className="text-xs text-[#6b7280] text-center py-4">
          Loading meta data...
        </div>
      </div>
    )
  }

  if (!metaComps || !metaComps.comps || metaComps.comps.length === 0) {
    return (
      <div className="panel-card p-3">
        <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
          Meta Comps
        </h2>
        <div className="text-xs text-[#6b7280] text-center py-4">
          No meta data available
        </div>
      </div>
    )
  }

  // Format champion name (remove TFT16_ prefix)
  const formatChampion = (name) => name.replace('TFT16_', '')

  // Get tier color based on top4 rate
  const getTierColor = (top4Rate) => {
    if (top4Rate >= 65) return 'text-[#22c55e]' // S tier - green
    if (top4Rate >= 55) return 'text-[#3b82f6]' // A tier - blue
    if (top4Rate >= 45) return 'text-[#eab308]' // B tier - yellow
    return 'text-[#6b7280]' // C tier - gray
  }

  return (
    <div className="panel-card p-3">
      <div className="flex justify-between items-center border-b border-[#374151] pb-2 mb-3">
        <h2 className="text-sm font-bold text-[#00d4ff]">
          Meta Comps
        </h2>
        <span className="text-xs text-[#6b7280]">
          Patch {metaComps.patch}
        </span>
      </div>

      <div className="space-y-2">
        {metaComps.comps.slice(0, 5).map((comp, index) => (
          <div
            key={index}
            className={`p-2 rounded ${
              index === 0
                ? 'bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.3)]'
                : 'bg-[rgba(31,41,55,0.5)]'
            }`}
          >
            {/* Row 1: Rank and Stats */}
            <div className="flex justify-between items-center mb-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-[#6b7280]">#{index + 1}</span>
                <span className={`text-sm font-bold ${getTierColor(comp.top4_rate)}`}>
                  {comp.top4_rate}% Top 4
                </span>
              </div>
              <span className="text-xs text-[#6b7280]">
                {(comp.games_played / 1000).toFixed(1)}k games
              </span>
            </div>

            {/* Row 2: Units */}
            <div className="flex flex-wrap gap-1">
              {comp.units.slice(0, 8).map((unit, unitIndex) => (
                <span
                  key={unitIndex}
                  className="text-xs px-1.5 py-0.5 bg-[rgba(55,65,81,0.5)] rounded text-[#d1d5db]"
                >
                  {formatChampion(unit)}
                </span>
              ))}
            </div>

            {/* Row 3: Win rate */}
            <div className="flex justify-between items-center mt-1 text-xs">
              <span className="text-[#6b7280]">
                Win: <span className="text-[#a855f7]">{comp.win_rate}%</span>
              </span>
              <span className="text-[#6b7280]">
                Avg: {comp.avg_placement}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer with total games */}
      <div className="mt-3 pt-2 border-t border-[#374151] text-xs text-[#6b7280] text-center">
        Data from {(metaComps.total_games / 1000000).toFixed(1)}M games
      </div>
    </div>
  )
}

export default MetaComps
