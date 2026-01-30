// Champion cost mapping for Set 16
const CHAMPION_COSTS = {
  // 1-cost
  TFT16_Anivia: 1, TFT16_Ashe: 1, TFT16_Briar: 1, TFT16_Caitlyn: 1, TFT16_Elise: 1,
  TFT16_Illaoi: 1, TFT16_JarvanIV: 1, TFT16_Lulu: 1, TFT16_Nocturne: 1, TFT16_Poppy: 1,
  TFT16_RekSai: 1, TFT16_Rumble: 1, TFT16_Soraka: 1, TFT16_TwistedFate: 1, TFT16_Viego: 1,
  TFT16_Zoe: 1, TFT16_Blitzcrank: 1, TFT16_KogMaw: 1,
  // 2-cost
  TFT16_Ekko: 2, TFT16_Kennen: 2, TFT16_Leona: 2, TFT16_Neeko: 2, TFT16_Orianna: 2,
  TFT16_Senna: 2, TFT16_Shen: 2, TFT16_Sona: 2, TFT16_Teemo: 2, TFT16_Tristana: 2,
  TFT16_Vi: 2, TFT16_XinZhao: 2, TFT16_Yorick: 2, TFT16_Malzahar: 2,
  // 3-cost
  TFT16_Ahri: 3, TFT16_ChoGath: 3, TFT16_Draven: 3, TFT16_Gangplank: 3, TFT16_Gwen: 3,
  TFT16_Jinx: 3, TFT16_Kobuko: 3, TFT16_Loris: 3, TFT16_Mordekaiser: 3,
  TFT16_Nautilus: 3, TFT16_Sejuani: 3, TFT16_Sion: 3, TFT16_Swain: 3, TFT16_Vayne: 3,
  TFT16_Wukong: 3, TFT16_Fizz: 3, TFT16_Ziggs: 3, TFT16_Renekton: 3, TFT16_Veigar: 3,
  // 4-cost
  TFT16_Ambessa: 4, TFT16_Braum: 4, TFT16_Galio: 4, TFT16_Garen: 4, TFT16_Kalista: 4,
  TFT16_Lissandra: 4, TFT16_Lux: 4, TFT16_MissFortune: 4, TFT16_RiftHerald: 4,
  TFT16_Seraphine: 4, TFT16_Taric: 4, TFT16_Yunara: 4, TFT16_BelVeth: 4,
  // 5-cost
  TFT16_Aatrox: 5, TFT16_Azir: 5, TFT16_Fiddlesticks: 5, TFT16_Kindred: 5, TFT16_Lucian: 5,
  TFT16_Ornn: 5, TFT16_Ryze: 5, TFT16_Sett: 5, TFT16_Shyvana: 5, TFT16_Thresh: 5,
  TFT16_Zilean: 5,
}

// Cost color scheme (border colors)
const COST_COLORS = {
  1: '#5a5a6f',  // Gray
  2: '#2ecc71',  // Green
  3: '#3498db',  // Blue
  4: '#9b59b6',  // Purple
  5: '#f1c40f',  // Gold
}

// Tier badge gradients
const TIER_GRADIENTS = {
  S: 'linear-gradient(135deg, #ff6b6b, #c92a2a)',
  A: 'linear-gradient(135deg, #ffa94d, #e67700)',
  B: 'linear-gradient(135deg, #69db7c, #2f9e44)',
  C: 'linear-gradient(135deg, #868e96, #495057)',
}

// Levelling badge colors
const LEVELLING_COLORS = {
  'Fast 9': '#9b59b6',
  'Fast 8': '#3498db',
  'Standard': '#6b7280',
  'Slow Roll': '#2ecc71',
  '2-Cost Reroll': '#2ecc71',
  '3-Cost Reroll': '#3498db',
}

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

  // Get champion cost
  const getChampionCost = (name) => CHAMPION_COSTS[name] || 3

  // Get cost-based border color
  const getCostBorderColor = (name) => COST_COLORS[getChampionCost(name)] || COST_COLORS[3]

  // Calculate tier from top4 rate (override API tier if needed)
  const calculateTier = (top4Rate, apiTier) => {
    // Use API tier if available, otherwise calculate
    if (apiTier && ['S', 'A', 'B', 'C'].includes(apiTier)) {
      return apiTier
    }
    if (top4Rate >= 65) return 'S'
    if (top4Rate >= 55) return 'A'
    if (top4Rate >= 45) return 'B'
    return 'C'
  }

  // Get tier gradient
  const getTierGradient = (tier) => TIER_GRADIENTS[tier] || TIER_GRADIENTS.C

  // Get levelling color
  const getLevellingColor = (levelling) => {
    if (!levelling) return LEVELLING_COLORS.Standard
    if (levelling.includes('Fast 9')) return LEVELLING_COLORS['Fast 9']
    if (levelling.includes('Fast 8')) return LEVELLING_COLORS['Fast 8']
    if (levelling.includes('Reroll') || levelling.includes('Roll')) return LEVELLING_COLORS['Slow Roll']
    return LEVELLING_COLORS.Standard
  }

  // Get stat color based on value
  const getStatColor = (value, type) => {
    if (type === 'avgPlacement') {
      if (value <= 3.5) return '#69db7c'  // Good
      if (value <= 4.2) return '#ffa94d'  // Mid
      return '#ff6b6b'  // Bad
    }
    if (type === 'winRate') {
      if (value >= 15) return '#69db7c'
      if (value >= 10) return '#ffa94d'
      return '#ff6b6b'
    }
    return '#ffffff'
  }

  // Determine how many units to show based on levelling
  const getUnitLimit = (comp) => {
    // Fast 8 comps typically show 8 units, Fast 9/Standard show 9
    const levelling = comp.levelling || ''
    if (levelling.includes('Fast 8') && !levelling.includes('Fast 9')) {
      return Math.min(8, comp.units.length)
    }
    return Math.min(9, comp.units.length)
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

      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
        {metaComps.comps.slice(0, 15).map((comp, index) => {
          const tier = calculateTier(comp.top4_rate, comp.tier)
          const tierGradient = getTierGradient(tier)
          const levellingColor = getLevellingColor(comp.levelling)
          const unitLimit = getUnitLimit(comp)

          return (
            <div
              key={index}
              className="p-2 rounded bg-[rgba(31,41,55,0.5)] hover:bg-[rgba(31,41,55,0.7)] transition-colors"
              style={{
                border: tier === 'S' ? '1px solid rgba(255,107,107,0.4)' : '1px solid transparent',
              }}
            >
              {/* Row 1: Tier badge, Rank, Levelling, Games */}
              <div className="flex justify-between items-center mb-1.5">
                <div className="flex items-center gap-2">
                  {/* Tier badge */}
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
                    style={{ background: tierGradient }}
                  >
                    {tier}
                  </span>
                  <span className="text-xs font-bold text-[#6b7280]">#{index + 1}</span>
                  {/* Levelling badge */}
                  {comp.levelling && (
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px]"
                      style={{
                        backgroundColor: `${levellingColor}22`,
                        color: levellingColor,
                        border: `1px solid ${levellingColor}`,
                      }}
                    >
                      {comp.levelling}
                    </span>
                  )}
                </div>
                <span className="text-xs text-[#6b7280]">
                  {(comp.games_played / 1000).toFixed(1)}k games
                </span>
              </div>

              {/* Row 2: Units with cost-colored borders */}
              <div className="flex flex-wrap gap-1 mb-1.5">
                {comp.units.slice(0, unitLimit).map((unit, unitIndex) => {
                  const borderColor = getCostBorderColor(unit)
                  return (
                    <span
                      key={unitIndex}
                      className="text-xs px-1.5 py-0.5 rounded text-[#e5e7eb] font-medium"
                      style={{
                        backgroundColor: 'rgba(55,65,81,0.6)',
                        borderLeft: `3px solid ${borderColor}`,
                      }}
                    >
                      {formatChampion(unit)}
                    </span>
                  )
                })}
              </div>

              {/* Row 3: Traits (show those with count >= 2) */}
              {comp.traits && comp.traits.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {comp.traits
                    .filter(t => t.count >= 2)
                    .slice(0, 5)
                    .map((trait, traitIndex) => (
                      <span
                        key={traitIndex}
                        className="px-1 py-0.5 rounded text-[10px]"
                        style={{
                          backgroundColor: 'rgba(201,160,51,0.15)',
                          color: '#c9a033',
                          border: '1px solid rgba(201,160,51,0.4)',
                        }}
                      >
                        {trait.name} {trait.count}
                      </span>
                    ))}
                </div>
              )}

              {/* Row 4: Stats */}
              <div className="flex items-center gap-4 text-xs">
                <span className="text-[#6b7280]">
                  Top 4: <span className="font-bold" style={{ color: getStatColor(comp.avg_placement, 'avgPlacement') }}>
                    {comp.top4_rate}%
                  </span>
                </span>
                <span className="text-[#6b7280]">
                  Win: <span style={{ color: getStatColor(comp.win_rate, 'winRate') }}>
                    {comp.win_rate}%
                  </span>
                </span>
                <span className="text-[#6b7280]">
                  Avg: <span style={{ color: getStatColor(comp.avg_placement, 'avgPlacement') }}>
                    {comp.avg_placement}
                  </span>
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer with total games */}
      <div className="mt-3 pt-2 border-t border-[#374151] text-xs text-[#6b7280] text-center">
        Data from {(metaComps.total_games / 1000000).toFixed(1)}M games
      </div>
    </div>
  )
}

export default MetaComps
