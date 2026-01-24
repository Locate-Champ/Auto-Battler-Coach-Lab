function HexUnit({ unit }) {
  const { name, cost, stars, items } = unit

  // Generate portrait URL
  const portraitUrl = getPortraitUrl(name)

  // Cost color classes
  const costClass = `cost-${Math.min(cost, 5)}`

  return (
    <div className="w-16 h-[72px] relative flex flex-col items-center">
      {/* Item Slots */}
      <div className="flex gap-0.5 mb-0.5">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-4 h-4 rounded-full bg-gray-800 border border-gray-600 flex items-center justify-center"
            title={items[i] || 'Empty'}
          >
            {items[i] && (
              <span className="text-[8px] text-gray-300">
                {items[i].slice(0, 2)}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Stars */}
      <div className="text-[10px] text-yellow-500 drop-shadow-lg z-10">
        {'★'.repeat(stars)}
      </div>

      {/* Hexagon Portrait */}
      <div
        className={`w-14 h-12 hex-clip border-2 ${costClass} overflow-hidden -mt-1`}
        style={{ boxShadow: `0 0 8px ${getCostGlow(cost)}` }}
      >
        <img
          src={portraitUrl}
          alt={name}
          className="w-full h-full object-cover scale-110"
          onError={(e) => {
            e.target.style.display = 'none'
          }}
        />
      </div>

      {/* Champion Name */}
      <div
        className="text-[9px] text-white whitespace-nowrap mt-0.5"
        style={{ textShadow: '0 1px 2px rgba(0,0,0,0.9)' }}
      >
        {name}
      </div>
    </div>
  )
}

function getPortraitUrl(name) {
  // Normalize name for URL
  const normalized = name.toLowerCase().replace(/['\s]/g, '')
  return `https://raw.communitydragon.org/latest/game/assets/characters/tft16_${normalized}/hud/tft16_${normalized}_square.tft_set16.png`
}

function getCostGlow(cost) {
  const glows = {
    1: 'rgba(107, 114, 128, 0.5)',
    2: 'rgba(34, 197, 94, 0.5)',
    3: 'rgba(59, 130, 246, 0.5)',
    4: 'rgba(168, 85, 247, 0.5)',
    5: 'rgba(234, 179, 8, 0.5)',
  }
  return glows[Math.min(cost, 5)] || glows[1]
}

export default HexUnit
