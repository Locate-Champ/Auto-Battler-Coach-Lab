function HexUnit({ unit }) {
  const { name, cost, stars, items } = unit

  // Generate portrait URL
  const portraitUrl = getPortraitUrl(name)

  // Cost colors
  const costColors = {
    1: { border: '#6b7280', glow: 'rgba(107, 114, 128, 0.5)' },
    2: { border: '#22c55e', glow: 'rgba(34, 197, 94, 0.5)' },
    3: { border: '#3b82f6', glow: 'rgba(59, 130, 246, 0.5)' },
    4: { border: '#a855f7', glow: 'rgba(168, 85, 247, 0.5)' },
    5: { border: '#eab308', glow: 'rgba(234, 179, 8, 0.5)' },
  }
  const colors = costColors[Math.min(cost, 5)] || costColors[1]

  return (
    <div className="w-16 h-[72px] relative flex flex-col items-center cursor-pointer hover:scale-105 transition-transform">
      {/* Item Slots */}
      <div className="flex gap-0.5 mb-0.5">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-4 h-4 rounded-full bg-[#1f2937] border border-[#4b5563] flex items-center justify-center"
            title={items[i] || 'Empty slot'}
          >
            {items[i] && (
              <span className="text-[7px] text-[#e5e7eb] font-medium">
                {getItemAbbr(items[i])}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Stars */}
      <div
        className="text-[10px] text-[#eab308] z-10"
        style={{ textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}
      >
        {'★'.repeat(stars)}
      </div>

      {/* Hexagon Portrait */}
      <div
        className="w-14 h-12 hex-clip overflow-hidden -mt-1 flex items-center justify-center"
        style={{
          border: `2px solid ${colors.border}`,
          boxShadow: `0 0 8px ${colors.glow}`,
          background: '#111827'
        }}
      >
        <img
          src={portraitUrl}
          alt={name}
          className="w-full h-full object-cover scale-110"
          onError={(e) => {
            e.target.style.display = 'none'
            e.target.parentElement.innerHTML = `<span class="text-xs text-gray-400">${name.slice(0,2)}</span>`
          }}
        />
      </div>

      {/* Champion Name */}
      <div
        className="text-[9px] text-white whitespace-nowrap mt-0.5 font-normal"
        style={{ textShadow: '0 1px 2px rgba(0,0,0,0.9)' }}
      >
        {name}
      </div>
    </div>
  )
}

function getPortraitUrl(name) {
  const normalized = name.toLowerCase().replace(/['\s]/g, '')
  return `https://raw.communitydragon.org/latest/game/assets/characters/tft16_${normalized}/hud/tft16_${normalized}_square.tft_set16.png`
}

function getItemAbbr(item) {
  const abbrs = {
    'Blue Buff': 'BB',
    'Morellonomicon': 'MO',
    'Morello': 'MO',
    'Jeweled Gauntlet': 'JG',
    'JG': 'JG',
    'Warmogs': 'WM',
    'Gargoyle': 'GA',
    'Titans': 'TR',
    'Rabadons': 'DC',
    'Infinity Edge': 'IE',
    'Giant Slayer': 'GS',
  }
  return abbrs[item] || item.slice(0, 2).toUpperCase()
}

export default HexUnit
