# TFT Coach Companion - Project Knowledge Base

## Overview
Real-time TFT coaching companion app that reads board state from Riot API and provides composition recommendations based on meta statistics.

---

## UI Layout (3-Column Design)

```
+------------------+-------------------------+-------------------+
|  LEFT (240px)    |   CENTER (flex)         |  RIGHT (280px)    |
+------------------+-------------------------+-------------------+
|  Traits Panel    |   Hexagonal Board       |  Recommended      |
|  - Unit count    |   (7x4 hex grid)        |  Comps            |
|  - Board cost    |   Live from Riot API    |  - Medal ranking  |
|  - Trait list    |                         |  - Score %        |
|                  |                         |  - Contest warn   |
|  Lobby Tracker   |   Item Suggestions      |                   |
|  - Comp names    |   BUILD | AVOID columns |  Priority Units   |
|  - [-] n [+]     |   Item + % rows         |  - Name + cost    |
|  - Status icons  |                         |  - Top4 rate      |
+------------------+-------------------------+-------------------+
```

---

## Color System

### Backgrounds
| Name | Hex | Usage |
|------|-----|-------|
| bg-primary | #030712 | Main app background |
| bg-secondary | #111827 | Panel backgrounds |
| bg-card | #1f2937 | Card/elevated surfaces |
| bg-hover | #374151 | Hover states |

### Accent
| Name | Hex |
|------|-----|
| cyan-primary | #00d4ff |
| cyan-muted | #0891b2 |

### Champion Cost Tiers
| Cost | Border | Glow |
|------|--------|------|
| 1 | #6b7280 | rgba(107,114,128,0.5) |
| 2 | #22c55e | rgba(34,197,94,0.5) |
| 3 | #3b82f6 | rgba(59,130,246,0.5) |
| 4 | #a855f7 | rgba(168,85,247,0.5) |
| 5 | #eab308 | rgba(234,179,8,0.5) |

### Status/Tier Colors
| Type | S/Success | A | B/Info | C | D | F/Danger |
|------|-----------|---|--------|---|---|----------|
| Hex | #eab308 | #22c55e | #3b82f6 | #6b7280 | #f97316 | #ef4444 |

---

## Typography
- **Font**: Inter, system-ui, sans-serif
- **App title**: 20px bold cyan
- **Panel header**: 14px bold cyan
- **Body**: 14px normal #e5e7eb
- **Small**: 12px #9ca3af
- **Champion name**: 9px white with shadow

---

## Hex Unit Component (64x72px)
```
+------------------------+
|     [item] [item]      |  <- 16x16px slots
|        ★★★             |  <- 10px gold stars
|      /------\          |
|     /  IMG   \         |  <- 56x48px hexagon
|    |         |         |     clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)
|     \       /          |     border: 2px [cost color]
|      \-----/           |
|       Name             |  <- 9px white, text-shadow
+------------------------+
```

---

## Data Structures

### State Variables
```javascript
units = [
  { row: 0, col: 1, name: "Ornn", cost: 5, stars: 2, items: [] },
  { row: 0, col: 3, name: "Sett", cost: 5, stars: 1, items: [] },
  ...
]

compCounts = { harvester: 1, soulbound: 0, blacksmith: 2, ... }

traits = [{ name: "Blacksmith", count: 1 }, ...]  // derived

boardCost = sum(unit.cost * unit.stars)  // derived
```

### Performance Data Structures
```javascript
TRAIT_PERFORMANCE = {
  "Harvester": { top4: 0.88, tier: "S" },
  "Bilgewater": { top4: 0.07, tier: "F", avoid: true },
  ...
}

CARRY_PERFORMANCE = {
  "Fiddlesticks": { cost: 5, top4: 1.00, tier: "S" },
  "Ornn": { cost: 5, top4: 1.00, tier: "S" },
  ...
}

ITEM_PERFORMANCE = {
  "Blue Buff": { top4: 0.86, tier: "S" },
  "Infinity Edge": { top4: 0.20, tier: "F" },
  ...
}

COMP_ARCHETYPES = [
  { id: "harvester", name: "Harvester/Fiddle", traits: [...], color: "..." },
  ...
]
```

---

## Recommendation Algorithm

```
For each comp archetype:
1. BASE SCORE = avg(TRAIT_PERFORMANCE[trait].top4) for all traits
2. CONTESTATION PENALTY = compCounts[comp.id] * 0.15  (15% per player)
3. FINAL SCORE = baseScore * (1 - penalty)
4. Sort by finalScore DESC
5. Display top 4
```

Example: Harvester base 88%, 1 player contesting -> 88% * 0.85 = 74.8%

---

## Performance Data (Set 16.3)

### Top Carries (by Top4 Rate)
| Champion | Cost | Top4% | Avg Place |
|----------|------|-------|-----------|
| Fiddlesticks | 5 | 100% | 1.75 |
| Ornn | 5 | 100% | 2.14 |
| Sett | 5 | 100% | 2.67 |
| Zilean | 5 | 80% | 3.40 |
| Thresh | 5 | 80% | 3.80 |
| Azir | 5 | 75% | 4.50 |
| Ryze | 5 | 70% | 3.40 |
| Garen | 4 | 67% | 3.50 |
| Lucian & Senna | 5 | 67% | 3.22 |

### Top Items (by Top4 Rate)
| Item | Top4% | Avg Place |
|------|-------|-----------|
| Protector's Vow | 100% | 1.75 |
| Zaun Emblem | 100% | 2.60 |
| Edge of Night | 100% | 2.67 |
| Spirit Visage | 89% | 3.00 |
| Blue Buff | 86% | 2.71 |
| Tactician's Crown | 86% | 3.00 |
| Morellonomicon | 77% | 3.62 |
| Dragon's Claw | 75% | 3.42 |
| Bramble Vest | 73% | 3.27 |

### Avoid Items (Low Top4%)
| Item | Top4% | Avg Place |
|------|-------|-----------|
| Warmog's Armor | 0% | 6.20 |
| Infinity Edge | 20% | 5.60 |
| Giant Slayer | 25% | 5.42 |
| Sunfire Cape | 25% | 4.50 |

### Top Traits (by Top4 Rate)
| Trait | Top4% | Avg Place |
|-------|-------|-----------|
| Warden 4 | 100% | 2.67 |
| Shadow Isles 4 | 100% | 3.00 |
| Harvester (Fiddle) | 88% | 2.52 |
| The Boss (Sett) | 88% | 2.63 |
| Ionia 2 | 83% | 2.83 |
| Chronokeeper (Zilean) | 83% | 3.08 |
| Vanquisher 3 | 83% | 3.17 |
| Shurima 1 | 83% | 3.83 |
| Zaun 3 | 80% | 3.40 |

### Avoid Traits (Low Top4%)
| Trait | Top4% | Avg Place |
|-------|-------|-----------|
| Bilgewater 3 | 7% | 5.71 |
| Noxus 2 | 33% | 6.00 |
| Vanquisher 2 | 33% | 5.33 |
| Void 1 | 36% | 5.23 |
| Demacia 2 | 36% | 4.91 |

---

## Asset URLs

### Champion Portraits
```
Primary: https://raw.communitydragon.org/latest/game/assets/characters/tft16_{champion}/hud/tft16_{champion}_square.tft_set16.png

Fallback: https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_{champion}_square.tft_set16.png
```

**Naming**: lowercase, no spaces, no apostrophes
- "Miss Fortune" -> "missfortune"
- "Kai'Sa" -> "kaisa"
- "Lucian & Senna" -> "luciansenna"

---

## Lobby Tracker Status Icons
| Count | Icon | Color |
|-------|------|-------|
| 0 (open) | check | #22c55e |
| 1 (contested) | warning | #eab308 |
| 2+ (avoid) | stop | #ef4444 |

---

## Hex Board Layout
- 4 rows x 7 columns
- Odd rows offset 32px right
- Vertical row overlap: -8px
- Total size: ~480x280px

---

## Key Component Hierarchy
```
TFTCoachCompanion
├── Header (title, subtitle, status dot)
└── Main Grid (12-col)
    ├── Left (col-span-3)
    │   ├── TraitsPanel -> TraitRow[]
    │   └── LobbyTracker -> CompRow[] (with Counter)
    ├── Center (col-span-6)
    │   ├── HexBoard -> HexUnit[] / EmptyHex[]
    │   └── ItemSuggestions -> ItemRow[]
    └── Right (col-span-3)
        ├── ModelSuggestions -> SuggestionCard[]
        └── PriorityUnits -> UnitRow[]
```

---

## Data Sources
- **Riot API**: Live board state (3s poll)
- **CommunityDragon**: Champion/item/trait definitions
- **Meta TFT**: Composition statistics, build variations, item performance

---

## Figma Component Priority
1. HexUnit - Champion in hex with items/stars/portrait
2. PanelCard - Reusable container with header
3. TierBadge - S/A/B/C/D/F variants
4. TraitRow - Name + badge + count
5. CompCounter - Status icon + name + [-]n[+]
6. SuggestionCard - Medal + name + score
7. ItemRow - Name + percentage (build/avoid variants)
