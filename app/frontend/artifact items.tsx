import React from 'react';

const ARTIFACT_ITEMS = [
  { name: 'Aegis of Dawn', file: 'Aegis of Dawn.png' },
  { name: 'Aegis of Dusk', file: 'Aegis of Dusk.png' },
  { name: "Blacksmith's Gloves", file: "Blacksmith's Gloves.png" },
  { name: 'Blighting Jewel', file: 'Blighting Jewel.png' },
  { name: 'Cappa Juice', file: 'Cappa Juice.png' },
  { name: 'Corrupt Vampiric Scepter', file: 'Corrupt Vampiric Scepter.png' },
  { name: 'Dawncore', file: 'Dawncore.png' },
  { name: "Death's Defiance", file: "Death's Defiance.png" },
  { name: 'Deathfire Grasp', file: 'Deathfire Grasp.png' },
  { name: 'Diamond Hands', file: 'Diamond Hands.png' },
  { name: 'Eternal Pact', file: 'Eternal Pact.png' },
  { name: 'Eternal Winter', file: 'Eternal Winter.png' },
  { name: 'Fishbones', file: 'Fishbones.png' },
  { name: 'Flickerblades', file: 'Flickerblades.png' },
  { name: 'Forbidden Idol', file: 'Forbidden Idol.png' },
  { name: "Gambler's Blade", file: "Gambler's Blade.png" },
  { name: 'Gold Collector', file: 'Gold Collector.png' },
  { name: 'Hellfire Hatchet', file: 'Hellfire Hatchet.png' },
  { name: 'Horizon Focus', file: 'Horizon Focus.png' },
  { name: 'Hullcrusher', file: 'Hullcrusher.png' },
  { name: 'Infinity Force', file: 'Infinity Force.png' },
  { name: 'Innervating Locket', file: 'Innervating Locket.png' },
  { name: 'Lesser Mirrored Persona', file: 'Lesser Mirrored Persona.png' },
  { name: 'Lich Bane', file: 'Lich Bane.png' },
  { name: 'Lightshield Crest', file: 'Lightshield Crest.png' },
  { name: "Luden's Tempest", file: "Luden's Tempest.png" },
  { name: 'Manazane', file: 'Manazane.png' },
  { name: 'Mending Echoes', file: 'Mending Echoes.png' },
  { name: 'Mirrored Persona', file: 'Mirrored Persona.png' },
  { name: 'Mittens', file: 'Mittens.png' },
  { name: "Mogul's Mail", file: "Mogul's Mail.png" },
  { name: "Prowler's Claw", file: "Prowler's Claw.png" },
  { name: 'Rapid Firecannon', file: 'Rapid Firecannon.png' },
  { name: "Seeker's Armguard", file: "Seeker's Armguard.png" },
  { name: 'Shadow Puppet', file: 'Shadow Puppet.png' },
  { name: 'Silvermere Dawn', file: 'Silvermere Dawn.png' },
  { name: "Sniper's Focus", file: "Sniper's Focus.png" },
  { name: 'Spectral Cutlass', file: 'Spectral Cutlass.png' },
  { name: 'Statikk Shiv', file: 'Statikk Shiv.png' },
  { name: 'Suspicious Trench Coat', file: 'Suspicious Trench Coat.png' },
  { name: 'Talisman Of Ascension', file: 'Talisman Of Ascension.png' },
  { name: 'The Darkin Aegis', file: 'The Darkin Aegis.png' },
  { name: 'The Darkin Bow', file: 'The Darkin Bow.png' },
  { name: 'The Darkin Scythe', file: 'The Darkin Scythe.png' },
  { name: 'The Darkin Staff', file: 'The Darkin Staff.png' },
  { name: 'The Indomitable', file: 'The Indomitable.png' },
  { name: 'Titanic Hydra', file: 'Titanic Hydra.png' },
  { name: "Trickster's Glass", file: "Trickster's Glass.png" },
  { name: 'Unending Despair', file: 'Unending Despair.png' },
  { name: 'Void Gauntlet', file: 'Void Gauntlet.png' },
  { name: "Wit's End", file: "Wit's End.png" },
  { name: "Zhonya's Paradox", file: "Zhonya's Paradox.png" },
] as const;

export type ArtifactItemName = (typeof ARTIFACT_ITEMS)[number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface ArtifactItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: ArtifactItemName) => void;
  className?: string;
}

const ArtifactItems: React.FC<ArtifactItemsProps> = ({ inventory, onItemClick, className }) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && item.category !== 'artifact') continue;
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[491.99px] h-56 p-1 ${className ?? ''}`}
    >
      <div className="flex flex-wrap justify-center gap-0 max-w-[384px] mx-auto">
        {ARTIFACT_ITEMS.map((item) => {
          const isOwned = ownedItems.has(item.name);
          const imageSrc = new URL(
            `./images/artifact items images/${item.file}`,
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

export default ArtifactItems;
