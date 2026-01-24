function ModelSuggestions({ recommendations, counts }) {
  const medals = ['🥇', '🥈', '🥉', '4️⃣']

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-gray-700 pb-2 mb-3">
        Recommended
      </h2>

      <div className="space-y-2">
        {recommendations.slice(0, 4).map((comp, index) => {
          const isTop = index === 0
          const contested = comp.contested > 0

          return (
            <div
              key={comp.id}
              className={`p-2 rounded ${
                isTop
                  ? 'bg-cyan-900/30 border border-cyan-600/30'
                  : 'bg-gray-800/50'
              }`}
            >
              {/* Row 1: Medal, Name, Score */}
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{medals[index]}</span>
                  <span className="text-sm font-bold text-white">{comp.name}</span>
                </div>
                <span className="text-sm font-bold text-[#00d4ff]">
                  {Math.round(comp.finalScore * 100)}%
                </span>
              </div>

              {/* Row 2: Contestation warning */}
              {contested && (
                <div className="text-xs text-yellow-500 mt-1">
                  ⚠ {comp.contested} contesting
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ModelSuggestions
