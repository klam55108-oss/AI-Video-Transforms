# Neural AI Theme

A futuristic, cyberpunk-inspired theme with glowing accents, subtle animations, and a high-tech aesthetic perfect for AI/ML content.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Deep Space | `#0a0a0f` |
| Surface | Neural Dark | `#12121a` |
| Primary Text | Ice White | `#e8e8ed` |
| Headings | Cyan Glow | `#00d4ff` |
| Accent | Electric Purple | `#a855f7` |
| Highlights | Neon Green | `#22c55e` |
| Warning | Amber Pulse | `#f59e0b` |
| Code Blocks | Matrix Dark | `#0d0d14` |
| Borders | Glow Line | `#1e3a5f` |

## Typography

- **Headings**: 'Orbitron', 'Rajdhani', sans-serif (futuristic geometric)
- **Body Text**: 'Inter', 'Roboto', system-ui, sans-serif
- **Code**: 'JetBrains Mono', 'Fira Code', monospace

## CSS Styling

```css
/*
 * External CDN Dependencies: Google Fonts (Orbitron, Inter, JetBrains Mono)
 * Fallback fonts ensure the theme works in offline/restricted environments:
 * - Headings: Falls back to system sans-serif
 * - Body: Falls back to system-ui
 * - Code: Falls back to monospace
 */
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-primary: #0a0a0f;
  --bg-surface: #12121a;
  --bg-elevated: #1a1a24;
  --text-primary: #e8e8ed;
  --text-secondary: #9ca3af;
  --text-muted: #6b7280;
  --accent-cyan: #00d4ff;
  --accent-purple: #a855f7;
  --accent-green: #22c55e;
  --accent-amber: #f59e0b;
  --border-glow: #1e3a5f;
  --glow-cyan: rgba(0, 212, 255, 0.15);
  --glow-purple: rgba(168, 85, 247, 0.15);
}

* {
  box-sizing: border-box;
}

body {
  background: var(--bg-primary);
  background-image:
    radial-gradient(ellipse at top, var(--glow-purple) 0%, transparent 50%),
    radial-gradient(ellipse at bottom right, var(--glow-cyan) 0%, transparent 50%);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, sans-serif;
  line-height: 1.7;
  max-width: 900px;
  margin: 0 auto;
  padding: 3rem 2rem;
  min-height: 100vh;
}

/* === HEADINGS === */
h1, h2, h3, h4 {
  font-family: 'Orbitron', sans-serif;
  color: var(--accent-cyan);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  position: relative;
}

h1 {
  font-size: 2.5rem;
  text-align: center;
  margin-bottom: 2rem;
  text-shadow: 0 0 30px var(--glow-cyan);
  animation: glowPulse 3s ease-in-out infinite;
}

h2 {
  font-size: 1.5rem;
  margin-top: 3rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--border-glow);
  background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

h3 {
  font-size: 1.2rem;
  color: var(--accent-purple);
}

/* === LINKS === */
a {
  color: var(--accent-cyan);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: all 0.3s ease;
}

a:hover {
  border-bottom-color: var(--accent-cyan);
  text-shadow: 0 0 10px var(--glow-cyan);
}

/* === CODE === */
code {
  font-family: 'JetBrains Mono', monospace;
  background: var(--bg-surface);
  color: var(--accent-green);
  padding: 0.2em 0.5em;
  border-radius: 4px;
  font-size: 0.9em;
  border: 1px solid var(--border-glow);
}

pre {
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  padding: 1.5rem;
  overflow-x: auto;
  position: relative;
}

pre::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple), var(--accent-green));
}

pre code {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-primary);
}

/* === BLOCKQUOTES === */
blockquote {
  background: var(--bg-surface);
  border-left: 4px solid var(--accent-purple);
  margin: 1.5rem 0;
  padding: 1rem 1.5rem;
  border-radius: 0 8px 8px 0;
  box-shadow: 0 0 20px var(--glow-purple);
}

blockquote p {
  margin: 0;
  color: var(--text-secondary);
  font-style: italic;
}

/* === TABLES === */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 2rem 0;
  background: var(--bg-surface);
  border-radius: 8px;
  overflow: hidden;
}

th {
  background: linear-gradient(135deg, var(--bg-elevated), var(--bg-surface));
  color: var(--accent-cyan);
  font-family: 'Orbitron', sans-serif;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 1rem;
  text-align: left;
}

td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-glow);
}

tr:hover {
  background: var(--bg-elevated);
}

/* === LISTS === */
ul, ol {
  padding-left: 1.5rem;
}

li {
  margin: 0.5rem 0;
  position: relative;
}

ul li::marker {
  color: var(--accent-cyan);
}

ol li::marker {
  color: var(--accent-purple);
  font-weight: 600;
}

/* === CALLOUTS === */
.callout {
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  margin: 1.5rem 0;
  border-left: 4px solid;
}

.callout-info { border-color: var(--accent-cyan); }
.callout-success { border-color: var(--accent-green); }
.callout-warning { border-color: var(--accent-amber); }
.callout-error { border-color: #ef4444; }

/* === BADGES === */
.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge-primary { background: var(--glow-cyan); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); }
.badge-secondary { background: var(--glow-purple); color: var(--accent-purple); border: 1px solid var(--accent-purple); }

/* === ANIMATIONS === */
@keyframes glowPulse {
  0%, 100% { text-shadow: 0 0 20px var(--glow-cyan); }
  50% { text-shadow: 0 0 40px var(--glow-cyan), 0 0 60px var(--glow-purple); }
}

/* === RESPONSIVE === */
@media (max-width: 768px) {
  body { padding: 1.5rem 1rem; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.25rem; }
}

/* === PRINT === */
@media print {
  body { background: white; color: black; }
  h1, h2, h3 { color: #1a1a2e; text-shadow: none; }
  a { color: #2563eb; }
}
```

## Components

### Status Badge
```html
<span class="badge badge-primary">AI Generated</span>
<span class="badge badge-secondary">Transcript</span>
```

### Info Callout
```html
<div class="callout callout-info">
  <strong>Neural Analysis:</strong> Key insights detected in this segment.
</div>
```

### Data Card
```html
<div style="background: var(--bg-surface); border: 1px solid var(--border-glow); border-radius: 12px; padding: 1.5rem;">
  <h4 style="margin-top: 0;">Metrics</h4>
  <p>Content analysis results...</p>
</div>
```

## Best Used For

- AI/ML documentation
- Technical analysis reports
- Data science notebooks
- Futuristic presentations
- Developer portfolios
- Tech startup content
