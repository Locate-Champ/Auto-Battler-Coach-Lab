function ItemSuggestions({ items }) {
  const buildItems = items?.build || []
  const avoidItems = items?.avoid || []

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-[#374151] pb-2 mb-3">
        Items
      </h2>

      <div className="grid grid-cols-2 gap-4">
        {/* BUILD Column */}
        <div>
          <h3 className="text-xs font-bold text-[#22c55e] mb-2">BUILD:</h3>
          <div className="space-y-1">
            {buildItems.map(item => (
              <div key={item.name} className="flex justify-between text-xs h-[18px] items-center">
                <span className="text-[#d1d5db]">{item.name}</span>
                <span className="text-[#22c55e]">{item.rate}%</span>
              </div>
            ))}
            {buildItems.length === 0 && (
              <span className="text-xs text-[#6b7280]">No data</span>
            )}
          </div>
        </div>

        {/* AVOID Column */}
        <div>
          <h3 className="text-xs font-bold text-[#ef4444] mb-2">AVOID:</h3>
          <div className="space-y-1">
            {avoidItems.map(item => (
              <div key={item.name} className="flex justify-between text-xs h-[18px] items-center">
                <span className="text-[#6b7280] line-through">{item.name}</span>
                <span className="text-[#ef4444]">{item.rate}%</span>
              </div>
            ))}
            {avoidItems.length === 0 && (
              <span className="text-xs text-[#6b7280]">No data</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ItemSuggestions
