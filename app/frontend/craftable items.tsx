import React from 'react';

// Item data organized by category
const ITEM_CATEGORIES = {
  Tank: [
    { name: "Protector's Vow", file: "Protector's Vow.png" },
    { name: 'Spirit Visage', file: 'Spirit Visage.png' },
    { name: 'Crownguard', file: 'Crownguard.png' },
    { name: 'Steadfast Heart', file: 'Steadfast Heart.png' },
    { name: 'Bramble Vest', file: 'Bramble Vest.png' },
    { name: 'Gargoyle Stoneplate', file: 'Gargoyle Stoneplate.png' },
    { name: "Dragon's Claw", file: "Dragon's Claw.png" },
    { name: "Warmog's Armor", file: "Warmog's Armor.png" },
  ],
  AD: [
    { name: "Kraken's Fury", file: "Kraken's Fury.png" },
    { name: 'Deathblade', file: 'Deathblade.png' },
    { name: 'Infinity Edge', file: 'Infinity Edge.png' },
  ],
  Utility: [
    { name: 'Evenshroud', file: 'Evenshroud.png' },
    { name: 'Last Whisper', file: 'Last Whisper.png' },
    { name: 'Ionic Spark', file: 'Ionic Spark.png' },
    { name: 'Void Staff', file: 'Void Staff.png' },
    { name: 'Sunfire Cape', file: 'Sunfire Cape.png' },
    { name: 'Red Buff', file: 'Red Buff.png' },
    { name: 'Morellonomicon', file: 'Morellonomicon.png' },
  ],
  AP: [
    { name: "Nashor's Tooth", file: "Nashor's Tooth.png" },
    { name: "Archangel's Staff", file: "Archangel's Staff.png" },
    { name: "Rabadon's Deathcap", file: "Rabadon's Deathcap.png" },
    { name: 'Jeweled Gauntlet', file: 'Jeweled Gauntlet.png' },
  ],
  Melee: [
    { name: "Titan's Resolve", file: "Titan's Resolve.png" },
    { name: 'Edge of Night', file: 'Edge of Night.png' },
    { name: "Sterak's Gage", file: "Sterak's Gage.png" },
    { name: 'Quicksilver', file: 'Quicksilver.png' },
  ],
  Omnivamp: [
    { name: 'Hand Of Justice', file: 'Hand Of Justice.png' },
    { name: 'Hextech Gunblade', file: 'Hextech Gunblade.png' },
    { name: 'Bloodthirster', file: 'Bloodthirster.png' },
  ],
  Mana: [
    { name: 'Blue Buff', file: 'Blue Buff.png' },
    { name: 'Spear of Shojin', file: 'Spear of Shojin.png' },
    { name: 'Adaptive Helm', file: 'Adaptive Helm.png' },
  ],
  'Any Carry': [
    { name: "Guinsoo's Rageblade", file: "Guinsoo's Rageblade.png" },
    { name: 'Giant Slayer', file: 'Giant Slayer.png' },
    { name: "Striker's Flail", file: "Striker's Flail.png" },
    { name: "Thief's Gloves", file: "Thief's Gloves.png" },
  ],
  Component: [
    { name: 'B.F. Sword', file: 'B.F. Sword.png' },
    { name: 'Chain Vest', file: 'Chain Vest.png' },
    { name: 'Frying Pan', file: 'Frying Pan.png' },
    { name: "Giant's Belt", file: "Giant's Belt.png" },
    { name: 'Needlessly Large Rod', file: 'Needlessly Large Rod.png' },
    { name: 'Negatron Cloak', file: 'Negatron Cloak.png' },
    { name: 'Recurve Bow', file: 'Recurve Bow.png' },
    { name: 'Sparring Gloves', file: 'Sparring Gloves.png' },
    { name: 'Spatula', file: 'Spatula.png' },
    { name: 'Tear of the Goddess', file: 'Tear of the Goddess.png' },
  ],
} as const;

type CategoryName = keyof typeof ITEM_CATEGORIES;
export type CraftableItemName = (typeof ITEM_CATEGORIES)[CategoryName][number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface CraftableItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: CraftableItemName) => void;
  className?: string;
}

// Reusable ItemGroup component
interface ItemGroupProps {
  title: string;
  items: readonly { name: string; file: string }[];
  ownedItems: Map<string, number>;
  onItemClick?: (item: string) => void;
}

const ItemGroup: React.FC<ItemGroupProps> = ({ title, items, ownedItems, onItemClick }) => (
  <div className="flex flex-col items-center px-1 py-0.5 outline outline-1 outline-offset-[-1px]" style={{ outlineColor: 'rgba(255,255,255,0.2)' }}>
    <div className="text-sm leading-5" style={{ fontFamily: 'Google Sans Code, monospace', color: 'rgba(255,255,255,0.87)' }}>
      {title}
    </div>
    <div className="flex flex-wrap justify-center gap-0">
      {items.map((item) => {
        const isOwned = ownedItems.has(item.name);
        const imageSrc = new URL(
          `./images/craftable items images/${item.file}`,
          import.meta.url,
        ).href;

        return (
          <button
            key={item.name}
            type="button"
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

const CraftableItems: React.FC<CraftableItemsProps> = ({
  inventory,
  onItemClick,
  className,
}) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && !['craftable', 'component'].includes(item.category)) {
        continue;
      }
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div className={`flex flex-col items-center gap-1 py-2 ${className ?? ''}`}>
      {/* Row 1: Tank + AD */}
      <div className="flex gap-2 justify-center">
        <ItemGroup title="Tank" items={ITEM_CATEGORIES.Tank} ownedItems={ownedItems} onItemClick={onItemClick} />
        <ItemGroup title="AD" items={ITEM_CATEGORIES.AD} ownedItems={ownedItems} onItemClick={onItemClick} />
      </div>

      {/* Row 2: Utility + AP */}
      <div className="flex gap-2 justify-center">
        <ItemGroup title="Utility" items={ITEM_CATEGORIES.Utility} ownedItems={ownedItems} onItemClick={onItemClick} />
        <ItemGroup title="AP" items={ITEM_CATEGORIES.AP} ownedItems={ownedItems} onItemClick={onItemClick} />
      </div>

      {/* Row 3: Melee + Omnivamp + Mana */}
      <div className="flex gap-2 justify-center">
        <ItemGroup title="Melee" items={ITEM_CATEGORIES.Melee} ownedItems={ownedItems} onItemClick={onItemClick} />
        <ItemGroup title="Omnivamp" items={ITEM_CATEGORIES.Omnivamp} ownedItems={ownedItems} onItemClick={onItemClick} />
        <ItemGroup title="Mana" items={ITEM_CATEGORIES.Mana} ownedItems={ownedItems} onItemClick={onItemClick} />
      </div>

      {/* Row 4: Any Carry */}
      <ItemGroup title="Any Carry" items={ITEM_CATEGORIES['Any Carry']} ownedItems={ownedItems} onItemClick={onItemClick} />

      {/* Row 5: Component */}
      <ItemGroup title="Component" items={ITEM_CATEGORIES.Component} ownedItems={ownedItems} onItemClick={onItemClick} />
    </div>
  );
};

export default CraftableItems;
