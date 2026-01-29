import { useState } from 'react'
import DualBoard, { SAMPLE_PLAYER_UNITS, SAMPLE_OPPONENT_UNITS } from '../DualBoard'
import ItemsBar from '../ItemsBar'
import CraftableItems from '../craftable items'
import ArtifactItems from '../artifact items'
import EmblemItems from '../emblem items'
import RadiantItems from '../radiant items'
import SupportItems from '../support items'
import SetItems from '../set items'
import CompsPanel from '../CompsPanel'
import CoachingPanel from '../CoachingPanel'

type ItemTab = 'Craftable' | 'Artifact' | 'Emblem' | 'Radiant' | 'Support' | 'Set'

function App() {
  const [activeTab, setActiveTab] = useState<ItemTab>('Craftable')

  return (
    <div className="min-h-screen bg-gray-900 flex justify-center p-8">
      {/* Three-column layout */}
      <div className="flex gap-4 items-start">

        {/* Left: Coaching Panel */}
        <CoachingPanel />

        {/* Center: Boards + Items */}
        <div className="flex flex-col" style={{ width: '787px' }}>
          {/* Dual Board: Opponent (mirrored) + Player */}
          <DualBoard
            playerUnits={SAMPLE_PLAYER_UNITS}
            opponentUnits={SAMPLE_OPPONENT_UNITS}
          />

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

        {/* Right: Comps Panel */}
        <CompsPanel />
      </div>
    </div>
  )
}

export default App
