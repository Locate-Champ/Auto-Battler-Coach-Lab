function ModelSuggestions({ recommendations, counts }) {
  const medals = ['🥇', '🥈', '🥉', '4️⃣']

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
        Recommended
      </h2>

      <div className="space-y-1.5">
        {recommendations.slice(0, 4).map((comp, index) => {
          const isTop = index === 0
          const contested = comp.contested > 0

          return (
            <div
              key={comp.id}
              className={`p-2 rounded ${
                isTop
                  ? 'bg-[rgba(8,145,178,0.15)] border border-[rgba(6,182,212,0.3)]'
                  : 'bg-[rgba(31,41,55,0.5)]'
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
                <div className="text-xs text-[#eab308] mt-1">
                  ⚠ {comp.contested} contesting
                </div>
              )}
            </div>
          )
        })}

        {recommendations.length === 0 && (
          <div className="text-xs text-[#6b7280] text-center py-2">
            Loading recommendations...
          </div>
        )}
      </div>
    </div>
  )
}

export default ModelSuggestions
