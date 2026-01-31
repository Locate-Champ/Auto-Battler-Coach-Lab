import { useState } from 'react'
import DualBoard, { SAMPLE_PLAYER_UNITS, SAMPLE_OPPONENT_UNITS } from '../DualBoard'
import LiveBoard from '../LiveBoard'
import ItemsBar from '../ItemsBar'
import CraftableItems from '../craftable items'
import ArtifactItems from '../artifact items'
import EmblemItems from '../emblem items'
import RadiantItems from '../radiant items'
import SupportItems from '../support items'
import SetItems from '../set items'
import CompsPanel from '../CompsPanel'
import CoachingPanel from '../CoachingPanel'
import PoolTracker from '../PoolTracker'
import { useGameState } from '../hooks/useGameState'

type ItemTab = 'Craftable' | 'Artifact' | 'Emblem' | 'Radiant' | 'Support' | 'Set'

function App() {
  const [activeTab, setActiveTab] = useState<ItemTab>('Craftable')
  const [useLiveData, setUseLiveData] = useState(false)
  // Get live game state for pool tracking
  const { state: gameState } = useGameState({ enabled: useLiveData })

  return (
    <div className="min-h-screen bg-gray-900 flex justify-center p-8">
      {/* Three-column layout */}
      <div className="flex gap-4 items-start">

        {/* Left: Coaching Panel */}
        <CoachingPanel />

        {/* Center: Boards + Items */}
        <div className="flex flex-col" style={{ width: '787px' }}>
          {/* Toggle for live data */}
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => setUseLiveData(!useLiveData)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                useLiveData
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {useLiveData ? '● LIVE' : '○ Sample Data'}
            </button>
            <span className="text-gray-500 text-xs">
              {useLiveData ? 'Connected to backend' : 'Using demo data'}
            </span>
          </div>

          {/* Board: Live or Sample */}
          {useLiveData ? (
            <LiveBoard showDualBoard={true} />
          ) : (
            <DualBoard
              playerUnits={SAMPLE_PLAYER_UNITS}
              opponentUnits={SAMPLE_OPPONENT_UNITS}
            />
          )}

          {/* Items panel - right-aligned below board */}
          <div
            className="self-end mt-4 rounded-lg overflow-hidden"
            style={{ border: '2px solid #9ca3af' }}
          >
            <ItemsBar defaultTab={activeTab} onTabChange={(tab) => setActiveTab(tab)} />
            <div className="bg-[#232422] flex justify-center py-2">
              {activeTab === 'Craftable' && <CraftableItems />}
              {activeTab === 'Artifact' && <ArtifactItems />}
              {activeTab === 'Emblem' && <EmblemItems />}
              {activeTab === 'Radiant' && <RadiantItems />}
              {activeTab === 'Support' && <SupportItems />}
              {activeTab === 'Set' && <SetItems />}
            </div>
          </div>
        </div>

        {/* Right: Comps Panel + Pool Tracker */}
        <div className="flex flex-col gap-4">
          <CompsPanel />
          <PoolTracker gameState={gameState} />
        </div>
      </div>
    </div>
  )
}

export default App
