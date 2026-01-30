import { useState, useEffect } from 'react'
import Header from './components/Header'
import TraitsPanel from './components/TraitsPanel'
import LobbyTracker from './components/LobbyTracker'
import HexBoard from './components/HexBoard'
import ItemSuggestions from './components/ItemSuggestions'
import ModelSuggestions from './components/ModelSuggestions'
import PriorityUnits from './components/PriorityUnits'
import MetaComps from './components/MetaComps'
import { fetchStats, fetchItems, fetchPriorityUnits, fetchMetaComps } from './api'
import './index.css'

// Demo board state
const DEMO_UNITS = [
  { row: 0, col: 1, name: 'Ornn', cost: 5, stars: 2, items: ['Warmogs', 'Gargoyle'] },
  { row: 0, col: 3, name: 'Sett', cost: 5, stars: 1, items: [] },
  { row: 1, col: 2, name: 'Shen', cost: 2, stars: 2, items: ['Titans'] },
  { row: 2, col: 1, name: 'Fiddlesticks', cost: 5, stars: 2, items: ['Blue Buff', 'Morello', 'JG'] },
  { row: 2, col: 4, name: 'Ryze', cost: 3, stars: 2, items: [] },
  { row: 3, col: 3, name: 'Zilean', cost: 2, stars: 1, items: [] },
]

// Comp archetypes for lobby tracking
const COMP_ARCHETYPES = [
  { id: 'harvester', name: 'Harvester/Fiddle', color: '#22c55e' },
  { id: 'soulbound', name: 'Soulbound', color: '#a855f7' },
  { id: 'blacksmith', name: 'Blacksmith', color: '#3b82f6' },
  { id: 'bruiser', name: 'Bruiser/Sett', color: '#f97316' },
  { id: 'void', name: 'Void', color: '#8b5cf6' },
  { id: 'honeymancy', name: 'Honeymancy', color: '#eab308' },
]

function App() {
  const [units] = useState(DEMO_UNITS)
  const [compCounts, setCompCounts] = useState({})
  const [stats, setStats] = useState(null)
  const [items, setItems] = useState({ build: [], avoid: [] })
  const [priorityUnits, setPriorityUnits] = useState([])
  const [metaComps, setMetaComps] = useState(null)
  const [isLive] = useState(true)
  const [loading, setLoading] = useState(true)
  const [metaLoading, setMetaLoading] = useState(true)

  // Initialize comp counts
  useEffect(() => {
    const initial = {}
    COMP_ARCHETYPES.forEach(comp => {
      initial[comp.id] = 0
    })
    setCompCounts(initial)
  }, [])

  // Fetch data from API
  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, itemsData, priorityData] = await Promise.all([
          fetchStats(),
          fetchItems(),
          fetchPriorityUnits()
        ])
        setStats(statsData)
        setItems(itemsData)
        setPriorityUnits(priorityData.units || [])
      } catch (err) {
        console.error('Failed to load data:', err)
        // Use fallback demo data
        setItems({
          build: [
            { name: 'Blue Buff', rate: 72 },
            { name: 'Morellonomicon', rate: 68 },
            { name: 'Jeweled Gauntlet', rate: 65 },
          ],
          avoid: [
            { name: 'Infinity Edge', rate: 35 },
            { name: 'Giant Slayer', rate: 38 },
          ]
        })
        setPriorityUnits([
          { name: 'Fiddlesticks', cost: 5, top4_rate: 100 },
          { name: 'Ornn', cost: 5, top4_rate: 100 },
          { name: 'Sett', cost: 5, top4_rate: 85 },
        ])
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  // Fetch meta comps separately (can fail without breaking the app)
  useEffect(() => {
    const loadMetaComps = async () => {
      try {
        const metaData = await fetchMetaComps(5)
        setMetaComps(metaData)
      } catch (err) {
        console.error('Failed to load meta comps:', err)
        // Meta comps are optional, app works without them
      } finally {
        setMetaLoading(false)
      }
    }
    loadMetaComps()
  }, [])

  // Calculate traits from units
  const traits = calculateTraits(units)
  const boardCost = units.reduce((sum, u) => sum + u.cost * u.stars, 0)

  // Handle comp count changes
  const updateCompCount = (compId, delta) => {
    setCompCounts(prev => ({
      ...prev,
      [compId]: Math.max(0, (prev[compId] || 0) + delta)
    }))
  }

  // Calculate recommendations based on comp counts
  const recommendations = calculateRecommendations(COMP_ARCHETYPES, compCounts, stats)

  return (
    <div className="min-h-screen bg-[#030712] text-gray-200">
      <Header isLive={isLive} />

      <main className="p-4">
        <div className="grid grid-cols-12 gap-4 max-w-7xl mx-auto">
          {/* Left Column */}
          <div className="col-span-3 space-y-4">
            <TraitsPanel
              traits={traits}
              unitCount={units.length}
              boardCost={boardCost}
              stats={stats}
            />
            <LobbyTracker
              comps={COMP_ARCHETYPES}
              counts={compCounts}
              onUpdateCount={updateCompCount}
            />
            <MetaComps metaComps={metaComps} loading={metaLoading} />
          </div>

          {/* Center Column */}
          <div className="col-span-6 space-y-4">
            <div className="panel-card p-4">
              <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">
                Board State (Live from Riot API)
              </div>
              <HexBoard units={units} />
            </div>
            <ItemSuggestions items={items} />
          </div>

          {/* Right Column */}
          <div className="col-span-3 space-y-4">
            <ModelSuggestions
              recommendations={recommendations}
              counts={compCounts}
            />
            <PriorityUnits units={priorityUnits} boardUnits={units} />
          </div>
        </div>
      </main>
    </div>
  )
}

// Calculate active traits from board
function calculateTraits(units) {
  // Trait data (simplified - would come from API in production)
  const UNIT_TRAITS = {
    'Ornn': ['Blacksmith', 'Behemoth'],
    'Sett': ['Fated', 'Umbral', 'Warden'],
    'Shen': ['Ghostly', 'Behemoth'],
    'Fiddlesticks': ['Harvester', 'Honeymancy'],
    'Ryze': ['Portal', 'Sage'],
    'Zilean': ['Chrono', 'Frost'],
  }

  const traitCounts = {}
  units.forEach(unit => {
    const traits = UNIT_TRAITS[unit.name] || []
    traits.forEach(trait => {
      traitCounts[trait] = (traitCounts[trait] || 0) + 1
    })
  })

  return Object.entries(traitCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

// Calculate recommendations with contestation
function calculateRecommendations(comps, counts, stats) {
  // Trait performance from personal stats
  const traitPerf = {}
  if (stats?.traits) {
    stats.traits.forEach(t => {
      traitPerf[t.name.toLowerCase()] = t.top4_rate / 100
    })
  }

  return comps.map(comp => {
    // Base score from trait performance (default 0.6 if unknown)
    const baseScore = traitPerf[comp.id] || 0.6

    // Contestation penalty: 15% per player
    const contested = counts[comp.id] || 0
    const penalty = contested * 0.15
    const finalScore = baseScore * (1 - penalty)

    return {
      ...comp,
      baseScore,
      contested,
      finalScore,
    }
  }).sort((a, b) => b.finalScore - a.finalScore)
}

export default App
