import React from 'react';

const SUPPORT_ITEMS = [
  { name: 'Aegis of the Legion', file: 'Aegis of the Legion.png' },
  { name: "Banshee's Veil", file: "Banshee's Veil.png" },
  { name: 'Chalice of Power', file: 'Chalice of Power.png' },
  { name: "Knight's Vow", file: "Knight's Vow.png" },
  { name: 'Locket of the Iron Solari', file: 'Locket of the Iron Solari.png' },
  { name: 'Moonstone Renewer', file: 'Moonstone Renewer.png' },
  { name: 'Needlessly Big Gem', file: 'Needlessly Big Gem.png' },
  { name: 'Obsidian Cleaver', file: 'Obsidian Cleaver.png' },
  { name: "Randuin's Omen", file: "Randuin's Omen.png" },
  { name: 'Shroud of Stillness', file: 'Shroud of Stillness.png' },
  { name: 'The Eternal Flame', file: 'The Eternal Flame.png' },
  { name: 'Unstable Treasure Chest', file: 'Unstable Treasure Chest.png' },
  { name: 'Virtue of the Martyr', file: 'Virtue of the Martyr.png' },
  { name: "Zeke's Herald", file: "Zeke's Herald.png" },
  { name: 'Zephyr', file: 'Zephyr.png' },
  { name: "Zz'Rot Portal", file: "Zz'Rot Portal.png" },
] as const;

export type SupportItemName = (typeof SUPPORT_ITEMS)[number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface SupportItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: SupportItemName) => void;
  className?: string;
}

const SupportItems: React.FC<SupportItemsProps> = ({ inventory, onItemClick, className }) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && item.category !== 'support') continue;
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[491.99px] h-28 p-1 ${className ?? ''}`}
    >
      <div className="grid grid-cols-[repeat(12,32px)] gap-[1px] w-fit">
        {SUPPORT_ITEMS.map((item) => {
          const isOwned = ownedItems.has(item.name);
          const imageSrc = new URL(
            `./images/support item images/${item.file}`,
            import.meta.url,
          ).href;

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
              <img
                src={imageSrc}
                alt={item.name}
                className="h-full w-full object-contain"
                draggable={false}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default SupportItems;
