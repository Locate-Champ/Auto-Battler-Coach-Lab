import React from 'react';

const SET_ITEMS = [
  { name: '90 Caliber Nets', file: '90 Caliber Nets.png' },
  { name: 'Blast Shield', file: 'Blast Shield.png' },
  { name: 'Continuum Cogs', file: 'Continuum Cogs.png' },
  { name: 'Electrical Overload', file: 'Electrical Overload.png' },
  { name: 'E.M.P.', file: 'E.M.P..png' },
  { name: 'Overclocked Capacitors', file: 'Overclocked Capacitors.png' },
  { name: 'Tuned Oscillator', file: 'Tuned Oscillator.png' },
  { name: 'Acceleration Gate', file: 'Acceleration Gate.png' },
  { name: 'Gigantification Ray', file: 'Gigantification Ray.png' },
  { name: 'Kinetic Barrier', file: 'Kinetic Barrier.png' },
  { name: 'Magnetron Coil', file: 'Magnetron Coil.png' },
  { name: 'Micro-Rockets', file: 'Micro-Rockets.png' },
  { name: 'Armor Nullifier', file: 'Armor Nullifier.png' },
  { name: 'Echo Engine', file: 'Echo Engine.png' },
  { name: 'Mining Drill', file: 'Mining Drill.png' },
  { name: 'Superior Lifeform', file: 'Superior Lifeform.png' },
  { name: 'Upgrade!', file: 'Upgrade!.png' },
  { name: "Captain's Brew", file: "Captain's Brew.png" },
  { name: 'Lucky Doubloon', file: 'Lucky Doubloon.png' },
  { name: 'Barknuckles', file: 'Barknuckles.png' },
  { name: 'Blackmarket Explosives', file: 'Blackmarket Explosives.png' },
  { name: "Cutthroat's Cutlass", file: "Cutthroat's Cutlass.png" },
  { name: "Dead Man's Dagger", file: "Dead Man's Dagger.png" },
  { name: "First Mate's Flintlock", file: "First Mate's Flintlock.png" },
  { name: "Pile O' Citrus", file: "Pile O' Citrus.png" },
  { name: "Captain's Hat", file: "Captain's Hat.png" },
  { name: 'Crown of Demacia', file: 'Crown of Demacia.png' },
  { name: 'Dreadway Cannon', file: 'Dreadway Cannon.png' },
  { name: 'Frame', file: 'Frame.png' },
  { name: 'Haunted Spyglass', file: 'Haunted Spyglass.png' },
  { name: 'Momentum Drive', file: 'Momentum Drive.png' },
  { name: 'Unstable Core', file: 'Unstable Core.png' },
  { name: 'Voltage Conduit', file: 'Voltage Conduit.png' },
] as const;

export type SetItemName = (typeof SET_ITEMS)[number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface SetItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: SetItemName) => void;
  className?: string;
}

const SetItems: React.FC<SetItemsProps> = ({ inventory, onItemClick, className }) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && item.category !== 'set') continue;
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[491.99px] h-36 p-1 ${className ?? ''}`}
    >
      <div className="grid grid-cols-[repeat(12,32px)] gap-[1px] w-fit">
        {SET_ITEMS.map((item) => {
          const isOwned = ownedItems.has(item.name);
          const imageSrc = item.file
            ? new URL(`./images/set item images/${item.file}`, import.meta.url).href
            : undefined;

          return (
            <button
              key={item.name}
              type="button"
              data-layer={item.name}
              title={item.name}
              aria-pressed={isOwned}
              onClick={onItemClick ? () => onItemClick(item.name) : undefined}
              className={[
                'h-8 w-8 rounded-[4px] transition',
                'ring-1 ring-transparent',
                isOwned
                  ? 'opacity-100 ring-2 ring-[#fab964] shadow-[0_0_8px_rgba(250,185,100,0.65)]'
                  : 'opacity-75 hover:opacity-100',
              ].join(' ')}
            >
              {imageSrc ? (
                <img
                  src={imageSrc}
                  alt={item.name}
                  className="h-full w-full object-contain"
                  draggable={false}
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center rounded-[4px] bg-[#1e1f1c] text-[8px] font-semibold text-white">
                  Frame
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default SetItems;
