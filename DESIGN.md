# Design System — Firewatch

## Product Context
- **What this is:** Campsite availability monitoring tool that alerts users when sold-out dates become available
- **Who it's for:** Campers frustrated by Recreation.gov's limited availability, particularly for popular locations
- **Space/industry:** Camping reservation tech (civic tech meets consumer camping)
- **Project type:** Web app (dashboard + monitoring tool)

## Aesthetic Direction
- **Direction:** Information-Dense Utility
- **Decoration level:** Intentional (texture, depth, real data primacy)
- **Mood:** Trustworthy, effective, information-rich. Shows you what you need to know without fluff. Polished but not precious. Functional personality.
- **Anti-patterns to avoid:**
  - Generic stock photos or placeholder images
  - Centered card layouts with excessive whitespace
  - Decoration for decoration's sake
  - AI-generated looking uniformity

## Visual Hierarchy Principles
1. **Information first**: Availability status, dates, and site numbers are the hero elements
2. **Real data only**: Only show images if they're from Recreation.gov API. No placeholders.
3. **Dense but scannable**: Pack more information per screen, but with clear visual hierarchy
4. **Asymmetry for purpose**: Sidebar navigation, mixed column widths - but not random

## Typography
- **Display:** Instrument Sans 700, 32-48px (page titles only)
- **Headings:** Instrument Sans 600, 18-24px (section titles, card titles)
- **Body:** Instrument Sans 400-500, 16px (primary content)
- **Labels:** Instrument Sans 500-600, 14px (UI labels, metadata)
- **Data:** Instrument Sans 400 with tabular-nums, 14px (dates, site numbers, stats)
- **Loading:**
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  ```

## Color (Functional, Not Decorative)
Colors convey meaning in context:

**Primary palette:**
- `#059669` (forest green) — Available dates, success states, active watches
- `#ea580c` (campfire orange) — Alerts, urgent notifications, sites found
- `#0891b2` (mountain cyan) — Informational highlights, links

**Neutrals (warm, high contrast):**
- `#1c1917` — primary text, dark surfaces
- `#57534e` — secondary text
- `#78716c` — tertiary text, disabled states
- `#d6d3d1` — borders, dividers
- `#e7e5e4` — subtle backgrounds
- `#fafaf9` — page background
- `#ffffff` — elevated surfaces (cards, modals)

**Semantic (only where meaningful):**
- Success: `#059669` (green) — site became available
- Warning: `#f59e0b` (amber) — watch expiring soon
- Error: `#dc2626` (red) — check failed, API down
- Info: `#0891b2` (cyan) — status updates

**Dark mode:** `#1c1917` base, `#292524` elevated, reduce saturation 20%

## Layout System

**Structure:**
- **Sidebar + main content** (not centered cards)
- Sidebar: 280px fixed width, dark background (`#1c1917`)
- Main: Fluid, max-width 1280px, 32-48px padding
- Responsive: sidebar collapses to top bar < 1024px

**Grid patterns:**
- **Asymmetric two-column:** 2fr + 1fr (main content + sidebar widget)
- **Card grids:** CSS Grid with minmax(320px, 1fr) for flexible wrapping
- **Dense layouts:** Reduce gaps to 16px between cards, 24px between sections

**Spacing scale:** 4, 8, 12, 16, 24, 32, 48, 64px

**Border radius:**
- Buttons/inputs: 6px (subtle, not rounded)
- Cards: 8px
- Modals/elevated surfaces: 12px

## Images (Real or Nothing)

**Source:** Recreation.gov API `preview_image_url` field ONLY

**Rules:**
1. If `preview_image_url` exists → show it (280×210px, 4:3 aspect ratio)
2. If `preview_image_url` is null → show solid color card with campground initials
3. Never use placeholder or stock photos
4. Image loading: blur-up (10px thumbnail → full res), lazy load below fold

**Fallback pattern:**
```css
.campground-image {
  background: linear-gradient(135deg, #059669 0%, #0891b2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  font-weight: 700;
  color: rgba(255,255,255,0.4);
}
```
Content: First two letters of campground name (e.g., "YO" for Yosemite)

**Engineering requirement:** Scrape real `preview_image_url` from Recreation.gov for every campground in the database. Do not ship image features until this is complete.

## Depth & Texture

**Background grain:**
```css
background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' /%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
```

**Card shadows (subtle, functional):**
- Default: `0 1px 3px rgba(0,0,0,0.08)`
- Hover: `0 2px 8px rgba(0,0,0,0.12)`
- Elevated (modals): `0 8px 24px rgba(0,0,0,0.15)`

**No excessive shadows** - keep depth subtle

## Information Density

**What to show per campground card:**
- Campground name + location (city, state)
- Date range with night count
- Watch status badge (active, alerted, paused)
- Mini availability calendar (14-day view, color-coded)
- Site numbers being watched
- Primary action button(s)

**What NOT to show:**
- Generic descriptions
- Star ratings (not relevant)
- Pricing (user cares about availability first)
- Excessive metadata

**Calendar color coding:**
```css
.day-available { background: #d1fae5; color: #065f46; }
.day-sold-out { background: #fee2e2; color: #991b1b; }
.day-disabled { background: #f5f5f4; color: #d6d3d1; }
```

## Motion (Subtle, Not Showy)

**Transitions:** 150-200ms ease-out for all state changes
**Hover effects:** 
- Cards: `translateY(-2px)` + shadow increase
- Buttons: slight shadow increase only
**No animations:** Loading states use skeleton screens, not spinners
**No bounce:** Removed playful easing - keep it professional

## Components

### Sidebar Navigation
- Dark background (`#1c1917`)
- Logo at top
- Nav items with hover states
- Quick stats panel at bottom
- Sticky positioning

### Alert Banners
- Only show when actionable (site found, check failed)
- Gradient backgrounds for urgency
- Dismissible
- Icon + title + detail text

### Campground Cards
- Image (real) or fallback (initials on gradient)
- Status badge (top-right)
- Date range with night count
- Mini calendar (14-day window)
- Site info (which sites watched)
- Action buttons

### Activity Feed
- Recent checks and findings
- Icon (success ✓, info ↻, error ✗)
- Title + detail + timestamp
- Reverse chronological

### Empty States
- Clear next action
- No illustrations - just text
- Example: "No watches yet. Search for a campground to get started."

## Polish Details That Matter

1. **Tabular numerals everywhere** - dates, site numbers, stats all align
2. **Consistent icon style** - use text symbols (✓, ✗, ↻) not icon fonts
3. **Button disabled states** - 50% opacity, no hover
4. **Focus states** - 2px outline in primary color
5. **Loading states** - skeleton screens matching content structure
6. **Error messages** - specific, actionable (not "something went wrong")

## Implementation Notes

**Required before shipping image features:**
- [ ] Scrape `preview_image_url` for all campgrounds in database
- [ ] Implement fallback pattern (initials on gradient) for missing images
- [ ] Test image loading performance (lazy load, blur-up)
- [ ] Verify no placeholder/stock photos are used

**CSS approach:**
- CSS Grid for layouts (not flexbox)
- CSS custom properties for theming
- Tailwind utility classes OK for prototyping, extract to components for production

**Accessibility:**
- Color is not the only indicator (labels + color)
- Focus states visible
- Keyboard navigation works
- ARIA labels where needed

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-19 | Initial (Utilitarian) | Too spartan |
| 2026-03-19 | Revised (Organic/Outdoor) | Too generic, "AI generated" |
| 2026-03-19 | Revised (Lived-In Tool) | Better but rough edges, fake images |
| 2026-03-19 | Final (Information-Dense Utility) | Real images only (from API) or fallback to initials. Dense but polished. Functional personality without roughness. Engineering must scrape real Recreation.gov images before shipping image features. No placeholder photos. |
