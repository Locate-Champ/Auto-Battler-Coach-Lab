/**
 * Transforms backend board_units data to overlay PositionedUnit format
 */

import type { BoardUnitData } from '../hooks/useGameState';
import type { PositionedUnit, ChampionCost, UnitItem } from '../HexUnitOverlay';

// Champion cost lookup (TFT Set 16)
// Generated from data/game_data/set16_champions_shop_16_3.jsonl
// Last updated: 2026-02-04
const CHAMPION_COSTS: Record<string, ChampionCost> = {
  // 1-cost
  'TFT16_Anivia': 1,
  'TFT16_Blitzcrank': 1,
  'TFT16_Briar': 1,
  'TFT16_Caitlyn': 1,
  'TFT16_Illaoi': 1,
  'TFT16_JarvanIV': 1,
  'TFT16_Jhin': 1,
  'TFT16_KogMaw': 1,
  'TFT16_Lulu': 1,
  'TFT16_PiltoverInvention': 1,
  'TFT16_Qiyana': 1,
  'TFT16_Rumble': 1,
  'TFT16_Shen': 1,
  'TFT16_Sona': 1,
  'TFT16_Viego': 1,

  // 2-cost
  'TFT16_Aphelios': 2,
  'TFT16_Ashe': 2,
  'TFT16_Bard': 2,
  'TFT16_ChoGath': 2,
  'TFT16_Ekko': 2,
  'TFT16_Graves': 2,
  'TFT16_Neeko': 2,
  'TFT16_Orianna': 2,
  'TFT16_Poppy': 2,
  'TFT16_RekSai': 2,
  'TFT16_Sion': 2,
  'TFT16_Teemo': 2,
  'TFT16_Tristana': 2,
  'TFT16_Tryndamere': 2,
  'TFT16_TwistedFate': 2,
  'TFT16_Vi': 2,
  'TFT16_XinZhao': 2,
  'TFT16_Yasuo': 2,
  'TFT16_Yorick': 2,

  // 3-cost
  'TFT16_Ahri': 3,
  'TFT16_Darius': 3,
  'TFT16_DrMundo': 3,
  'TFT16_Draven': 3,
  'TFT16_Gangplank': 3,
  'TFT16_Gwen': 3,
  'TFT16_Jinx': 3,
  'TFT16_Kennen': 3,
  'TFT16_Kobuko': 3,
  'TFT16_Leblanc': 3,
  'TFT16_Leona': 3,
  'TFT16_Loris': 3,
  'TFT16_Malzahar': 3,
  'TFT16_Milio': 3,
  'TFT16_Nautilus': 3,
  'TFT16_Sejuani': 3,
  'TFT16_Vayne': 3,
  'TFT16_Zoe': 3,

  // 4-cost
  'TFT16_Ambessa': 4,
  'TFT16_BelVeth': 4,
  'TFT16_Braum': 4,
  'TFT16_Diana': 4,
  'TFT16_Fizz': 4,
  'TFT16_Garen': 4,
  'TFT16_Kaisa': 4,
  'TFT16_Kalista': 4,
  'TFT16_Lissandra': 4,
  'TFT16_Lux': 4,
  'TFT16_MissFortune': 4,
  'TFT16_Nasus': 4,
  'TFT16_Nidalee': 4,
  'TFT16_Renekton': 4,
  'TFT16_RiftHerald': 4,
  'TFT16_Seraphine': 4,
  'TFT16_Singed': 4,
  'TFT16_Skarner': 4,
  'TFT16_Swain': 4,
  'TFT16_Taric': 4,
  'TFT16_Veigar': 4,
  'TFT16_Warwick': 4,
  'TFT16_Wukong': 4,
  'TFT16_Yone': 4,
  'TFT16_Yunara': 4,

  // 5-cost
  'TFT16_Aatrox': 5,
  'TFT16_Annie': 5,
  'TFT16_AurelionSol': 5,
  'TFT16_Azir': 5,
  'TFT16_BaronNashor': 5,
  'TFT16_Brock': 5,
  'TFT16_Fiddlesticks': 5,
  'TFT16_Galio': 5,
  'TFT16_Kindred': 5,
  'TFT16_Lucian': 5,
  'TFT16_Mel': 5,
  'TFT16_Ornn': 5,
  'TFT16_Ryze': 5,
  'TFT16_Sett': 5,
  'TFT16_Shyvana': 5,
  'TFT16_Sylas': 5,
  'TFT16_THex': 5,
  'TFT16_TahmKench': 5,
  'TFT16_Thresh': 5,
  'TFT16_Volibear': 5,
  'TFT16_Xerath': 5,
  'TFT16_Zaahen': 5,
  'TFT16_Ziggs': 5,
  'TFT16_Zilean': 5,
};

// Item ID to display name and image file mapping
const ITEM_MAPPINGS: Record<string, { name: string; imageFile: string }> = {
  // Components
  'TFT_Item_BFSword': { name: 'BF Sword', imageFile: 'BF Sword.png' },
  'TFT_Item_ChainVest': { name: 'Chain Vest', imageFile: 'Chain Vest.png' },
  'TFT_Item_GiantsBelt': { name: "Giant's Belt", imageFile: "Giant's Belt.png" },
  'TFT_Item_NeedlesslyLargeRod': { name: 'Needlessly Large Rod', imageFile: 'Needlessly Large Rod.png' },
  'TFT_Item_NegatronCloak': { name: 'Negatron Cloak', imageFile: 'Negatron Cloak.png' },
  'TFT_Item_RecurveBow': { name: 'Recurve Bow', imageFile: 'Recurve Bow.png' },
  'TFT_Item_SparringGloves': { name: 'Sparring Gloves', imageFile: 'Sparring Gloves.png' },
  'TFT_Item_Spatula': { name: 'Spatula', imageFile: 'Spatula.png' },
  'TFT_Item_TearOfTheGoddess': { name: 'Tear of the Goddess', imageFile: 'Tear of the Goddess.png' },

  // Completed Items
  'TFT_Item_ArchangelsStaff': { name: "Archangel's Staff", imageFile: "Archangel's Staff.png" },
  'TFT_Item_Bloodthirster': { name: 'Bloodthirster', imageFile: 'Bloodthirster.png' },
  'TFT_Item_BlueBuff': { name: 'Blue Buff', imageFile: 'Blue Buff.png' },
  'TFT_Item_BrambleVest': { name: 'Bramble Vest', imageFile: 'Bramble Vest.png' },
  'TFT_Item_Deathblade': { name: 'Deathblade', imageFile: 'Deathblade.png' },
  'TFT_Item_DragonsClaw': { name: "Dragon's Claw", imageFile: "Dragon's Claw.png" },
  'TFT_Item_EdgeOfNight': { name: 'Edge of Night', imageFile: 'Edge of Night.png' },
  'TFT_Item_GargoyleStoneplate': { name: 'Gargoyle Stoneplate', imageFile: 'Gargoyle Stoneplate.png' },
  'TFT_Item_GiantSlayer': { name: 'Giant Slayer', imageFile: 'Giant Slayer.png' },
  'TFT_Item_GuardianAngel': { name: 'Guardian Angel', imageFile: 'Guardian Angel.png' },
  'TFT_Item_GuinsoosRageblade': { name: "Guinsoo's Rageblade", imageFile: "Guinsoo's Rageblade.png" },
  'TFT_Item_HandOfJustice': { name: 'Hand of Justice', imageFile: 'Hand of Justice.png' },
  'TFT_Item_HextechGunblade': { name: 'Hextech Gunblade', imageFile: 'Hextech Gunblade.png' },
  'TFT_Item_InfinityEdge': { name: 'Infinity Edge', imageFile: 'Infinity Edge.png' },
  'TFT_Item_IonicSpark': { name: 'Ionic Spark', imageFile: 'Ionic Spark.png' },
  'TFT_Item_JeweledGauntlet': { name: 'Jeweled Gauntlet', imageFile: 'Jeweled Gauntlet.png' },
  'TFT_Item_LastWhisper': { name: 'Last Whisper', imageFile: 'Last Whisper.png' },
  'TFT_Item_Morellonomicon': { name: 'Morellonomicon', imageFile: 'Morellonomicon.png' },
  'TFT_Item_NashorsTooth': { name: "Nashor's Tooth", imageFile: "Nashor's Tooth.png" },
  'TFT_Item_PowerGauntlet': { name: 'Quicksilver', imageFile: 'Quicksilver.png' },
  'TFT_Item_RabadonsDeathcap': { name: "Rabadon's Deathcap", imageFile: "Rabadon's Deathcap.png" },
  'TFT_Item_RapidFireCannon': { name: 'Rapid Firecannon', imageFile: 'Rapid Firecannon.png' },
  'TFT_Item_Redemption': { name: 'Redemption', imageFile: 'Redemption.png' },
  'TFT_Item_RunaansHurricane': { name: "Runaan's Hurricane", imageFile: "Runaan's Hurricane.png" },
  'TFT_Item_SpearOfShojin': { name: 'Spear of Shojin', imageFile: 'Spear of Shojin.png' },
  'TFT_Item_StatikkShiv': { name: 'Statikk Shiv', imageFile: 'Statikk Shiv.png' },
  'TFT_Item_SunfireCape': { name: 'Sunfire Cape', imageFile: 'Sunfire Cape.png' },
  'TFT_Item_ThiefsGloves': { name: "Thief's Gloves", imageFile: "Thief's Gloves.png" },
  'TFT_Item_TitansResolve': { name: "Titan's Resolve", imageFile: "Titan's Resolve.png" },
  'TFT_Item_Warmogs': { name: "Warmog's Armor", imageFile: "Warmog's Armor.png" },
  'TFT_Item_ZekesHerald': { name: "Zeke's Herald", imageFile: "Zeke's Herald.png" },
  'TFT_Item_Zephyr': { name: 'Zephyr', imageFile: 'Zephyr.png' },
};

/**
 * Get champion cost from character ID
 */
export function getChampionCost(characterId: string): ChampionCost {
  return CHAMPION_COSTS[characterId] || 1;
}

/**
 * Get champion display name from character ID
 */
export function getChampionName(characterId: string): string {
  // Strip TFT16_ prefix and return
  const match = characterId.match(/^TFT\d+_(.+)$/);
  return match ? match[1] : characterId;
}

/**
 * Parse item ID to UnitItem format
 */
export function parseItem(itemId: string): UnitItem | null {
  if (!itemId) return null;

  // Check if we have a direct mapping
  const mapping = ITEM_MAPPINGS[itemId];
  if (mapping) {
    return mapping;
  }

  // Fallback: try to extract name from item ID
  // TFT_Item_BFSword -> BF Sword (approximate)
  const match = itemId.match(/^TFT_Item_(.+)$/);
  if (match) {
    const name = match[1]
      .replace(/([A-Z])/g, ' $1')
      .trim();
    return {
      name,
      imageFile: `${name}.png`,
    };
  }

  // Handle set-specific items (TFT16_...)
  const setMatch = itemId.match(/^TFT\d+_(.+)$/);
  if (setMatch) {
    return {
      name: setMatch[1],
      imageFile: `${setMatch[1]}.png`,
    };
  }

  return null;
}

/**
 * Transform backend board_units to overlay PositionedUnit format
 */
export function transformBoardUnits(units: BoardUnitData[]): PositionedUnit[] {
  return units
    .filter((unit) => unit.position !== null)
    .map((unit) => ({
      id: unit.id || `unit-${unit.character_id}`,
      name: getChampionName(unit.character_id),
      cost: getChampionCost(unit.character_id),
      stars: (unit.stars || 1) as 1 | 2 | 3,
      items: unit.items
        .map(parseItem)
        .filter((item): item is UnitItem => item !== null),
      position: {
        row: unit.position!.row,
        col: unit.position!.col,
      },
    }));
}

export default transformBoardUnits;
