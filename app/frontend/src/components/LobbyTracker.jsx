function LobbyTracker({ comps, counts, onUpdateCount }) {
  const getStatusIcon = (count) => {
    if (count === 0) return { icon: '✓', color: 'text-green-500' }
    if (count === 1) return { icon: '⚠', color: 'text-yellow-500' }
    return { icon: '⛔', color: 'text-red-500' }
  }

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-gray-700 pb-2 mb-3">
        Lobby Tracker
      </h2>

      <div className="space-y-1">
        {comps.map(comp => {
          const count = counts[comp.id] || 0
          const status = getStatusIcon(count)

          return (
            <div key={comp.id} className="flex justify-between items-center h-7">
              {/* Left side - status icon and name */}
              <div className="flex items-center gap-2">
                <span className={`text-sm ${status.color}`}>{status.icon}</span>
                <span
                  className="text-xs"
                  style={{ color: count === 0 ? comp.color : '#9ca3af' }}
                >
                  {comp.name}
                </span>
              </div>

              {/* Right side - counter */}
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => onUpdateCount(comp.id, -1)}
                  className="w-5 h-5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs flex items-center justify-center"
                >
                  -
                </button>
                <span className="w-5 text-center text-sm font-bold text-white">
                  {count}
                </span>
                <button
                  onClick={() => onUpdateCount(comp.id, 1)}
                  className="w-5 h-5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs flex items-center justify-center"
                >
                  +
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default LobbyTracker
