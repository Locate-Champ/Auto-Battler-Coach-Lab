function PriorityUnits({ units, boardUnits }) {
  // Filter out units already on the board
  const boardUnitNames = new Set(boardUnits.map(u => u.name))
  const filteredUnits = units.filter(u => !boardUnitNames.has(u.name))

  // Cost tier colors
  const getCostColor = (cost) => {
    const colors = {
      1: '#6b7280',
      2: '#22c55e',
      3: '#3b82f6',
      4: '#a855f7',
      5: '#eab308',
    }
    return colors[Math.min(cost, 5)] || colors[1]
  }

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-gray-700 pb-2 mb-3">
        Find These
      </h2>

      <div className="space-y-1">
        {filteredUnits.slice(0, 5).map(unit => (
          <div key={unit.name} className="flex justify-between items-center h-6">
            {/* Left side: Name with cost */}
            <div className="flex items-center gap-1">
              <span
                className="text-sm"
                style={{ color: getCostColor(unit.cost) }}
              >
                {unit.name}
              </span>
              <span className="text-xs text-gray-500">
                ({unit.cost}💰)
              </span>
            </div>

            {/* Right side: Win rate */}
            <span className="text-sm text-gray-400">
              {unit.top4_rate}%
            </span>
          </div>
        ))}

        {filteredUnits.length === 0 && (
          <div className="text-xs text-gray-500 text-center py-2">
            All priority units on board!
          </div>
        )}
      </div>
    </div>
  )
}

export default PriorityUnits
