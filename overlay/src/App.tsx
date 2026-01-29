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
    <div className="min-h-screen bg-gray-900 p-4">
      <h1 className="text-white text-2xl mb-4">TFT Coach Overlay</h1>
      <div className="flex flex-col items-center justify-center gap-6 lg:flex-row lg:items-start">
        <BoardBase />
        <div className="flex flex-col items-start">
          <ItemsBar defaultTab={activeTab} onTabChange={(tab) => setActiveTab(tab)} />
          <div className="mt-3">
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
