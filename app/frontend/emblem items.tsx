import React from 'react';

const EMBLEM_ITEMS = [
  { name: 'Bilgewater Emblem', file: 'Bilgewater Emblem.png' },
  { name: 'Demacia Emblem', file: 'Demacia Emblem.png' },
  { name: 'Freljord Emblem', file: 'Freljord Emblem.png' },
  { name: 'Ionia Emblem', file: 'Ionia Emblem.png' },
  { name: 'Ixtal Emblem', file: 'Ixtal Emblem.png' },
  { name: 'Noxus Emblem', file: 'Noxus Emblem.png' },
  { name: 'Piltover Emblem', file: 'Piltover Emblem.png' },
  { name: 'Void Emblem', file: 'Void Emblem.png' },
  { name: 'Yordle Emblem', file: 'Yordle Emblem.png' },
  { name: 'Zaun Emblem', file: 'Zaun Emblem.png' },
  { name: 'Arcanist Emblem', file: 'Arcanist Emblem.png' },
  { name: 'Bruiser Emblem', file: 'Bruiser Emblem.png' },
  { name: 'Defender Emblem', file: 'Defender Emblem.png' },
  { name: 'Disruptor Emblem', file: 'Disruptor Emblem.png' },
  { name: 'Gunslinger Emblem', file: 'Gunslinger Emblem.png' },
  { name: 'Invoker Emblem', file: 'Invoker Emblem.png' },
  { name: 'Juggernaut Emblem', file: 'Juggernaut Emblem.png' },
  { name: 'Longshot Emblem', file: 'Longshot Emblem.png' },
  { name: 'Quickstriker Emblem', file: 'Quickstriker Emblem.png' },
  { name: 'Slayer Emblem', file: 'Slayer Emblem.png' },
  { name: 'Vanquisher Emblem', file: 'Vanquisher Emblem.png' },
  { name: 'Warden Emblem', file: 'Warden Emblem.png' },
  { name: "Tactician's Cape", file: "Tactician's Cape.png" },
  { name: "Tactician's Crown", file: "Tactician's Crown.png" },
  { name: "Tactician's Shield", file: "Tactician's Shield.png" },
] as const;

export type EmblemItemName = (typeof EMBLEM_ITEMS)[number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface EmblemItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: EmblemItemName) => void;
  className?: string;
}

const EmblemItems: React.FC<EmblemItemsProps> = ({ inventory, onItemClick, className }) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && item.category !== 'emblem') continue;
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[491.99px] h-36 p-1 ${className ?? ''}`}
    >
      <div className="flex flex-wrap justify-center gap-0 max-w-[384px] mx-auto">
        {EMBLEM_ITEMS.map((item) => {
          const isOwned = ownedItems.has(item.name);
          const imageSrc = new URL(
            `./images/emblem items images/${item.file}`,
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

export default EmblemItems;
