# ThacKey — Design & UX

Design language, component system, page layouts, and interaction specs for the typing test platform. Built on **Tailwind CSS + shadcn/ui**.

## Design Philosophy

**"Disappear while you type."** The test surface should feel like nothing — no chrome competing for attention, no layout shifts, no distractions. UI only earns pixels before the test (config), after the test (results), or outside it (dashboard/analytics). Inspiration: Monkeytype's minimalism + Linear's polish + our own AI-feedback layer on top.

### Principles
1. **Focus mode by default** — during a test, only text, caret, and minimal live stats exist. Header/nav fade to near-invisible or hide entirely.
2. **Feedback is the differentiator** — any other site gives WPM. ThacKey says *why* you're slow and hands you a test built around it. The "adaptive" affordance must feel intelligent, not gimmicky.
3. **Instant response** — keystroke → character render in <16ms. No optimistic tricks needed since typing is client-side; keep it that way.
4. **One dominant accent** — monochrome base, single accent color reserved for live feedback (correct/incorrect) and primary actions.

## Theme & Tokens

Dark-first (typing tools live in dark mode); light mode supported via CSS variables.

### Color system (shadcn/ui CSS variables, `globals.css`)

```css
:root {
  --background: 240 6% 97%;        /* light: soft off-white */
  --foreground: 240 10% 10%;
  --card: 240 6% 99%;
  --muted: 240 5% 90%;
  --muted-foreground: 240 4% 46%;
  --primary: 24 95% 53%;           /* amber/orange accent */
  --destructive: 0 84% 60%;
  --correct: 142 71% 45%;          /* typing feedback: green */
  --incorrect: 0 84% 60%;          /* typing feedback: red */
  --caret: 24 95% 53%;
  --radius: 0.5rem;
}
.dark {
  --background: 240 10% 4%;
  --foreground: 240 5% 92%;
  --card: 240 8% 8%;
  --muted: 240 6% 14%;
  --muted-foreground: 240 4% 55%;
  --primary: 24 95% 53%;
  --correct: 142 71% 45%;
  --incorrect: 0 72% 58%;
}
```

`correct`/`incorrect`/`caret` are custom additions beyond stock shadcn tokens — register them in `tailwind.config` as semantic colors used **only** for typing feedback (not general UI, which stays monochrome + primary).

### Typography

| Use | Font | Notes |
|---|---|---|
| Typing test text | `JetBrains Mono` (or `Geist Mono`) | Monospace mandatory — consistent advance width keeps caret math simple |
| UI / headings | `Geist` or `Inter` | Clean geometric sans |
| Numbers (stats) | Mono, `tabular-nums` | Prevent digit-width jitter in live WPM counter |

Typing text scale: `text-2xl` desktop / `text-xl` mobile, `leading-relaxed` (~1.75) — readability beats density. Max content width ~`75ch`.

## Component Inventory

### shadcn/ui primitives (install via CLI)
`Button`, `Card`, `Dialog`, `DropdownMenu`, `Select`, `Tabs`, `Toggle`, `Tooltip`, `Badge`, `Progress`, `Separator`, `Skeleton`, `Sonner` (toasts), `Chart` (Recharts), `Sheet` (mobile nav), `Avatar`, `Input`, `Form` (+ react-hook-form for auth forms), `Command` (palette, phase 2).

### Custom components

| Component | Purpose | Notes |
|---|---|---|
| `TypingArea` | Renders target text + caret + per-char state | Core of the app. Each char gets state: `pending` / `correct` / `incorrect` / `extra`. Rerenders must be memoized per-word |
| `Caret` | Blinking block/line caret | CSS animation; pauses blinking while typing (resume after 1s idle) |
| `LiveStats` | WPM / accuracy / timer during test | Compact, `text-muted-foreground`, hides in "zen mode" |
| `TestConfigBar` | Mode select: time (15/30/60/120s), words (10/25/50/100), adaptive | `Toggle`-group style, muted pill design |
| `ResultsChart` | Per-second WPM + error markers | shadcn `Chart`/Recharts line |
| `KeyHeatmap` | Keyboard-shaped heatmap of weak keys | Custom SVG layout; color = weakness score from analytics API |
| `WeaknessCard` | "Your weakest patterns: `th`, `st`, `qu`" | Shows explanation text from `AdaptiveTest.explanation` |
| `AdaptiveCTA` | "Generate a test targeting your weaknesses" button | Primary accent; shows loading `Skeleton` while LLM generates |
| `SessionRow` | History table row | WPM, acc, mode, date, mini sparkline |
| `StatCard` | Dashboard metric tiles | `Card` w/ big mono number + delta vs. previous period |

## Pages & Layouts

### `/` — The Test (home)
```
┌─────────────────────────────────────────────────────┐
│  logo                    dashboard  analytics  [⚙]  │  ← fades during test
│                                                     │
│   [15s] [30s] [60s] | [words] | ✦ adaptive          │  ← config bar
│                                                     │
│        The quick brown fox jumps over the           │
│        lazy dog and runs through the forest▌        │
│        quickly before the rain begins...            │
│                                                     │
│              42 wpm · 97% · 0:32                    │  ← live stats
│                                                     │
│        ── press tab to restart ──                   │
└─────────────────────────────────────────────────────┘
```
- Centered vertically & horizontally; `max-w-4xl`
- Test modes as pill toggles; **✦ adaptive** gets the accent color + sparkle icon to signal "AI"
- On finish: smooth scroll/`Dialog`-free transition → results section expands below (or route to `/results/[id]`)

### `/results/[id]` — Post-test
- Top row: giant WPM + accuracy `StatCard`s
- `ResultsChart` (WPM over time, error markers as red dots)
- `WeaknessCard`: what this session revealed — weakest keys/bigrams
- Primary CTA: **"Practice these weaknesses"** → generates adaptive test → routes to `/` preloaded with it
- Secondary: "Retake" / "New test"

### `/dashboard` — History & Trends
- `StatCard` row: best WPM, avg WPM, avg accuracy, total tests, time typing
- `Tabs`: Overview | History | Records
- WPM trend `Chart` (30-day line), accuracy trend
- `SessionRow` table, paginated; click → `/results/[id]`

### `/analytics` — The AI page (differentiator showcase)
```
┌──────────────────────────────────────────────┐
│  "You've improved on 'e' — now 'th' and     │
│   right-hand symbols are your bottleneck"    │  ← LLM-generated summary
├──────────────────┬───────────────────────────┤
│  KeyHeatmap      │  Weakness list            │
│  (keyboard SVG,  │  ranked chars/bigrams     │
│  red = weak)     │  w/ error% + latency      │
├──────────────────┴───────────────────────────┤
│  Category bars: punctuation ▓▓▓░░ 62% weak   │
│                 left hand  ▓▓░░░ 41%         │
├──────────────────────────────────────────────┤
│  [ ✦ Generate adaptive test ]                │
└──────────────────────────────────────────────┘
```

### `/settings`
- `Tabs`: Profile | Preferences | Data
- Test defaults, theme (dark/light/system), keyboard layout (QWERTY/Dvorak/Colemak — affects analytics mapping)
- Data tab: export keystroke data (JSON), delete account — `destructive` styles, `Dialog` confirm

### `(auth)` — Login / Register
Centered `Card`, `Form` + react-hook-form validation, social login placeholder (phase 2).

## Interaction & Motion

- **Keystroke feedback:** incorrect char turns red instantly; if "forgiving" mode, subtle shake on error — never a sound or modal
- **Caret:** 2px line, `--caret` color, blinks when idle 1s+, glides (CSS `transition: left 80ms`) between positions — a laggy caret makes the whole app feel broken
- **Restart:** `Tab` or `Esc` → fade out text (~150ms), fade in new — standard typing-site muscle memory
- **Page transitions:** subtle `fade`/`slide` via `framer-motion` (add only if needed — start with CSS transitions)
- **Adaptive generation:** `Skeleton` over the typing area + "Building a test around your weak spots…" — set expectations it's doing work
- **Toasts:** `Sonner` for "Session saved", "Adaptive test ready" — bottom-right, auto-dismiss

## UX Flows

**First-time user (anon):**
land → test immediately (no auth wall!) → results → "Sign up to track progress & unlock AI analysis" nudge → register → retroactively claim the session.

**Returning user:**
land → optional adaptive CTA visible if profile exists → test → results → weakness surfaced → one click → adaptive test.

**The magic loop (what we optimize for):**
```
test → results → "you're weak at X" → adaptive test on X
→ results show improvement on X → repeat
```

## Accessibility

- All interactive elements keyboard-reachable; `Tab` is reserved (restart) — document it
- `aria-live="off"` on typing text (screen readers can't handle per-char updates); results announced politely
- Color contrast: `--correct`/`--incorrect` meet 4.5:1 on both themes; never color-only feedback — incorrect chars also get underline/strikethrough option in settings
- `prefers-reduced-motion`: disable caret glide & transitions
- Focus ring visible (`ring-2 ring-primary/50`) outside typing mode

## Responsive

- Test works on mobile (bring-your-own-keyboard caveat) — `TypingArea` uses `inputMode` hidden input trick for mobile keyboards
- Heatmap → simplified top-10 list under `md`
- Dashboard charts stack vertically; nav collapses to `Sheet` hamburger
- Min touch target 44px

## Non-Goals (v1)

- Multiplayer / races, leaderboards
- Real-time collaborative anything
- Gamification (badges, streaks) — phase 2 maybe
- Themes marketplace — just dark/light
