# Figma Community Resources for Auto-Battler Coach Companion

## BEST RESOURCES FOR YOUR PROJECT

Your app needs: dark theme, gaming aesthetic, dashboard components, data visualization, hexagon shapes, counters/steppers, and card layouts.

---

## DASHBOARDS & ANALYTICS (High Priority)

### 1. Analytics Dashboard Dark Mode - MingCute
**URL:** https://www.figma.com/community/file/1132250387709963790/analytics-dashboard-dark-mode-mingcute
**Why:** Clean dark mode analytics dashboard with stat cards and modern layout

### 2. Data Visualization Charts - Dark Mode
**URL:** https://www.figma.com/community/file/1060951969983411754/data-visualization-charts-dark-mode
**Why:** Pre-built chart components for dark interfaces - perfect for win rate displays

### 3. Data Visualization Graphs/Charts Kit
**URL:** https://www.figma.com/community/file/1199721318228257277/data-visualization-graphs-charts-kit
**Why:** Includes dark/light modes, auto-layout, and variants

### 4. Modern Analytics Dashboard
**URL:** https://www.figma.com/community/file/1301828690694156375/modern-analytics-dashboard
**Why:** Real-time update style, intuitive visualizations

### 5. Sleek Dashboard Designs for Data Visualization
**URL:** https://www.figma.com/community/file/1293672969334455314/sleek-dashboard-designs-for-data-visualization
**Why:** Performance analytics focus, key metrics display

---

## GAMING UI KITS (High Priority)

### 1. Game UX Kit
**URL:** https://www.figma.com/community/file/1460785931676185568/game-ux-kit
**Why:** Designed specifically for game interfaces and wireframes

### 2. Free Game UI Kit
**URL:** https://www.figma.com/community/file/1065913909118984412/free-game-ui-kit
**Why:** Game-specific UI elements and patterns

### 3. Mobile Game UI Kit
**URL:** https://www.figma.com/community/file/1441544279070693348/mobile-game-ui-kit
**Why:** Mobile-first game UI components

### 4. Game Dashboard UI Design
**URL:** https://www.figma.com/community/file/1441992955405134134/game-dashboard-ui-design
**Why:** Game dashboard specific layout inspiration

### 5. Gemu - Game Store App UI Kit
**URL:** https://www.figma.com/community/file/1218050956619277205/gemu-game-store-app-ui-kit
**Why:** 156 screens, dark/light themes, gaming aesthetic

### 6. UI Kit - Game Portal - Vixaplay
**URL:** https://www.figma.com/community/file/1268515272328894240/ui-kit-game-portal-vixaplay
**Why:** Gaming and social experience UI patterns

---

## COMPONENT LIBRARIES (Medium Priority)

### 1. Components Library - Light & Dark Mode
**URL:** https://www.figma.com/community/file/1131119460069711481/components-library-light-dark-mode
**Why:** Base components (buttons, inputs, cards) with dark mode

### 2. Dark Mode Cards
**URL:** https://www.figma.com/community/file/913435324775694479/dark-mode-cards
**Why:** Article cards, buttons, banners - all dark themed

### 3. Cards Components
**URL:** https://www.figma.com/community/file/1213402617631550819/cards-components
**Why:** Dashboard cards, SaaS cards - great for panels

### 4. Dark Theme UI Elements Design
**URL:** https://www.figma.com/community/file/1280430558372841942/dark-theme-ui-elements-design
**Why:** Modern Figma features (properties, auto-layout, variants)

### 5. Material Dark Theme Design Kit
**URL:** https://www.figma.com/community/file/787036571667088922/material-dark-theme-design-kit
**Why:** Material design dark theme component library

### 6. Stepper Component
**URL:** https://www.figma.com/community/file/1165798487502683301/stepper-component
**Why:** Counter/stepper UI - perfect for lobby tracker +/- buttons

---

## LEARNING RESOURCES

### Figma Best Practices - Components & Libraries
**URL:** https://www.figma.com/best-practices/components-styles-and-shared-libraries/
**Why:** Official guide on building reusable components, variants, and design systems

### Free UI Components Library
**URL:** https://www.figma.com/community/ui-kits/components
**Why:** Browse 1000+ community components

---

## RECOMMENDED WORKFLOW

### Step 1: Set Up Your File
1. Create new Figma file
2. Set up color variables (use my color palette from spec)
3. Set up text styles (Inter font, my type scale)
4. Create a "Components" page

### Step 2: Build Base Components (in this order)
1. **TierBadge** - S/A/B/C/D/F pill badges
2. **StatusDot** - Connection indicator
3. **PanelCard** - Reusable container with header
4. **Counter** - [-] n [+] buttons
5. **TraitRow** - Name + badge + count
6. **ItemRow** - Name + percentage
7. **UnitRow** - Priority unit display
8. **SuggestionCard** - Medal + name + score
9. **EmptyHex** - Empty board slot
10. **HexUnit** - Champion in hex (most complex)
11. **HexBoard** - 7x4 grid of hexes

### Step 3: Assemble Panels
1. TraitsPanel (uses PanelCard, TraitRow)
2. LobbyTracker (uses PanelCard, Counter)
3. ModelSuggestions (uses PanelCard, SuggestionCard)
4. PriorityUnits (uses PanelCard, UnitRow)
5. ItemSuggestions (uses PanelCard, ItemRow)

### Step 4: Build Main Layout
1. Header bar
2. 3-column grid
3. Place panels in columns
4. Add HexBoard to center

### Step 5: Create Variants
- HexUnit variants: 1-5 cost (different border colors)
- TierBadge variants: S/A/B/C/D/F
- StatusIcon variants: OK/WARN/FIX
- Counter states: default/hover/active

---

## FIGMA TIPS FOR THIS PROJECT

### Creating Hexagons
In Figma, you can create hexagons by:
1. Use the Polygon tool (P)
2. Set sides to 6
3. Rotate 90 degrees for flat-top hexagon (auto-battler style)
4. Or use Frame with clip-path in CSS when exporting

### Auto Layout for Panels
- Use auto layout on PanelCard for consistent spacing
- Set padding: 12px
- Gap between items: 8px
- Direction: Vertical

### Color Variables
Create variables for:
- `bg/primary`, `bg/secondary`, `bg/card`
- `text/primary`, `text/secondary`, `text/muted`
- `accent/cyan`, `status/success`, `status/warning`, `status/danger`
- `tier/1-cost`, `tier/2-cost`, etc.

### Component Properties
Use boolean properties for:
- HexUnit: hasItems (show/hide item slots)
- SuggestionCard: isContested (show warning)
- TraitRow: showBadge

Use instance swap for:
- TierBadge in TraitRow
- StatusIcon in CompRow

---

## QUICK LINKS

| Resource | Link |
|----------|------|
| Analytics Dark Mode | https://www.figma.com/community/file/1132250387709963790 |
| Data Viz Dark Mode | https://www.figma.com/community/file/1060951969983411754 |
| Game UX Kit | https://www.figma.com/community/file/1460785931676185568 |
| Dark Mode Cards | https://www.figma.com/community/file/913435324775694479 |
| Components Library | https://www.figma.com/community/file/1131119460069711481 |
| Stepper Component | https://www.figma.com/community/file/1165798487502683301 |
| Figma Best Practices | https://www.figma.com/best-practices/components-styles-and-shared-libraries |

