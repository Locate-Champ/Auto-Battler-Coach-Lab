function ItemSuggestions({ items }) {
  const buildItems = items?.build || []
  const avoidItems = items?.avoid || []

  return (
    <div className="panel-card p-3">
      <h2 className="text-sm font-bold text-[#00d4ff] border-b border-gray-700 pb-2 mb-3">
        Items
      </h2>

      <div className="grid grid-cols-2 gap-4">
        {/* BUILD Column */}
        <div>
          <h3 className="text-xs font-bold text-green-500 mb-2">BUILD:</h3>
          <div className="space-y-1">
            {buildItems.map(item => (
              <div key={item.name} className="flex justify-between text-xs">
                <span className="text-gray-300">{item.name}</span>
                <span className="text-green-500">{item.rate}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* AVOID Column */}
        <div>
          <h3 className="text-xs font-bold text-red-500 mb-2">AVOID:</h3>
          <div className="space-y-1">
            {avoidItems.map(item => (
              <div key={item.name} className="flex justify-between text-xs">
                <span className="text-gray-500 line-through">{item.name}</span>
                <span className="text-red-500">{item.rate}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ItemSuggestions
