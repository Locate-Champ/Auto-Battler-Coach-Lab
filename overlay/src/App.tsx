import { useState } from 'react'
import BoardBase from '../boardbase'
import ItemsBar from '../ItemsBar'
import CraftableItems from '../craftable items'
import ArtifactItems from '../artifact items'
import EmblemItems from '../emblem items'
import RadiantItems from '../radiant items'
import SupportItems from '../support items'
import SetItems from '../set items'

type ItemTab = 'Craftable' | 'Artifact' | 'Emblem' | 'Radiant' | 'Support' | 'Set'

function App() {
  const [activeTab, setActiveTab] = useState<ItemTab>('Craftable')

  return (
    <div className="min-h-screen bg-gray-900 flex justify-center p-8">
      {/* Container matched to board width for alignment */}
      <div className="flex flex-col" style={{ width: '787px' }}>
        {/* Board - centered by parent flex */}
        <BoardBase />

        {/* Items panel - right-aligned below board */}
        <div className="self-end mt-4">
          <ItemsBar defaultTab={activeTab} onTabChange={(tab) => setActiveTab(tab)} />
          <div className="mt-2">
            {activeTab === 'Craftable' && <CraftableItems />}
            {activeTab === 'Artifact' && <ArtifactItems />}
            {activeTab === 'Emblem' && <EmblemItems />}
            {activeTab === 'Radiant' && <RadiantItems />}
            {activeTab === 'Support' && <SupportItems />}
            {activeTab === 'Set' && <SetItems />}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
