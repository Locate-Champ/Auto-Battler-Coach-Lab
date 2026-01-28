function HexUnit({ unit }) {
  const { name, cost, stars, items } = unit

  // Generate portrait URL
  const portraitUrl = getPortraitUrl(name)

  // TFTFlows cost colors (matching the builder exactly)
  const costColors = {
    1: { border: '#344049', glow: 'rgba(52, 64, 73, 0.6)' },
    2: { border: '#1C964D', glow: 'rgba(28, 150, 77, 0.6)' },
    3: { border: '#2D72B3', glow: 'rgba(45, 114, 179, 0.6)' },
    4: { border: '#C40C93', glow: 'rgba(196, 12, 147, 0.6)' },
    5: { border: '#D88810', glow: 'rgba(216, 136, 16, 0.6)' },
  }
  const colors = costColors[Math.min(cost, 5)] || costColors[1]

  // SVG hexagon path (pointed top, matching TFTFlows)
  const hexPath = "M50 0 L93.3 25 L93.3 75 L50 100 L6.7 75 L6.7 25 Z"
  const hexClipPath = "polygon(50% 0%, 93.3% 25%, 93.3% 75%, 50% 100%, 6.7% 75%, 6.7% 25%)"

  return (
    <div className="w-[72px] h-[100px] relative flex flex-col items-center cursor-pointer hover:scale-105 transition-transform">
      {/* Item Slots - positioned above hex */}
      <div className="flex gap-1 mb-1 z-10">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-5 h-5 rounded-sm flex items-center justify-center"
            style={{
              background: items[i] ? '#1a1a2e' : 'transparent',
              border: items[i] ? '1px solid #3a3a4f' : 'none',
            }}
            title={items[i] || 'Empty slot'}
          >
            {items[i] && (
              <img
                src={getItemIconUrl(items[i])}
                alt={items[i]}
                className="w-4 h-4 object-contain"
                onError={(e) => {
                  e.target.style.display = 'none'
                  e.target.parentElement.innerHTML = `<span class="text-[6px] text-gray-300">${getItemAbbr(items[i])}</span>`
                }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Hexagon Container with SVG border */}
      <div className="relative w-[66px] h-[76px]">
        {/* SVG Hexagon Frame */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <defs>
            <clipPath id={`hex-clip-${name}`}>
              <path d={hexPath} />
            </clipPath>
            <filter id={`glow-${name}`}>
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor={colors.border} floodOpacity="0.8"/>
            </filter>
          </defs>
          {/* Hexagon border */}
          <path
            d={hexPath}
            fill="none"
            stroke={colors.border}
            strokeWidth="3"
            filter={`url(#glow-${name})`}
          />
        </svg>

        {/* Portrait inside hexagon */}
        <div
          className="absolute inset-[5px] overflow-hidden"
          style={{
            clipPath: hexClipPath,
            background: '#0a0a14'
          }}
        >
          <img
            src={portraitUrl}
            alt={name}
            className="w-full h-full object-cover scale-125"
            onError={(e) => {
              e.target.style.display = 'none'
              e.target.parentElement.innerHTML = `<span class="text-sm text-gray-400 font-bold">${name.slice(0,2)}</span>`
            }}
          />
        </div>

        {/* Stars - positioned over the hex */}
        {stars > 0 && (
          <div
            className="absolute -top-1 left-1/2 -translate-x-1/2 flex gap-0.5 z-20"
          >
            {Array.from({ length: stars }).map((_, i) => (
              <span
                key={i}
                className="text-[10px]"
                style={{
                  color: stars === 3 ? '#FFD700' : '#eab308',
                  textShadow: '0 0 4px rgba(0,0,0,1), 0 0 8px rgba(234,179,8,0.5), 1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000'
                }}
              >
                ★
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Champion Name - TFTFlow style shadow */}
      <div
        className="text-[10px] whitespace-nowrap mt-1 font-semibold tracking-wide"
        style={{
          color: '#dce2e1',
          textShadow: '0 0 1px transparent, 0 2px 2px rgba(0,0,0,0.8), 1px 1px 0 #000, -1px 1px 0 #000'
        }}
      >
        {name}
      </div>
    </div>
  )
}

function getPortraitUrl(name) {
  // Normalize champion name for CDragon URL
  const normalized = name.toLowerCase().replace(/['\s]/g, '').replace(/\./g, '')
  return `https://raw.communitydragon.org/latest/game/assets/characters/tft16_${normalized}/hud/tft16_${normalized}_square.tft_set16.png`
}

function getItemIconUrl(itemName) {
  // Normalize item name for CDragon URL
  const normalized = itemName.toLowerCase().replace(/['\s]/g, '').replace(/\./g, '')
  return `https://raw.communitydragon.org/latest/game/assets/maps/particles/tft/item_icons/standard/${normalized}.png`
}

function getItemAbbr(item) {
  const abbrs = {
    'Blue Buff': 'BB',
    'Morellonomicon': 'MO',
    'Morello': 'MO',
    'Jeweled Gauntlet': 'JG',
    'JG': 'JG',
    'Warmogs': 'WM',
    "Warmog's Armor": 'WM',
    'Gargoyle': 'GA',
    "Gargoyle Stoneplate": 'GA',
    'Titans': 'TR',
    "Titan's Resolve": 'TR',
    'Rabadons': 'DC',
    "Rabadon's Deathcap": 'DC',
    'Infinity Edge': 'IE',
    'Giant Slayer': 'GS',
    'Bloodthirster': 'BT',
    'Hand of Justice': 'HoJ',
    'Ionic Spark': 'IS',
    'Quicksilver': 'QS',
    'Redemption': 'RD',
    'Sunfire Cape': 'SF',
    'Bramble Vest': 'BV',
    "Dragon's Claw": 'DC',
    'Hextech Gunblade': 'GB',
    'Guinsoos': 'GR',
    "Guinsoo's Rageblade": 'GR',
    'Spear of Shojin': 'SS',
    'Archangels': 'AA',
    "Archangel's Staff": 'AA',
    'Statikk Shiv': 'SH',
    'Last Whisper': 'LW',
    'Runaans': 'RH',
    "Runaan's Hurricane": 'RH',
  }
  return abbrs[item] || item.slice(0, 2).toUpperCase()
}

export default HexUnit
