# Glassmorphism Theme

A stunning modern theme featuring frosted glass effects, soft gradients, and elegant transparency for a premium, contemporary feel.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background Gradient Start | Soft Lavender | `#667eea` |
| Background Gradient End | Coral Pink | `#f093fb` |
| Glass Surface | White Alpha | `rgba(255,255,255,0.15)` |
| Primary Text | Deep Slate | `#1e293b` |
| Headings | Pure White | `#ffffff` |
| Accent | Indigo | `#6366f1` |
| Highlights | Amber Glow | `#fbbf24` |
| Borders | Frost Line | `rgba(255,255,255,0.3)` |

## Typography

- **Headings**: 'Plus Jakarta Sans', 'DM Sans', sans-serif
- **Body Text**: 'Inter', system-ui, sans-serif
- **Code**: 'Fira Code', 'SF Mono', monospace

## CSS Styling

```css
/*
 * External CDN Dependencies: Google Fonts (Plus Jakarta Sans, Inter, Fira Code)
 * Fallback fonts ensure the theme works in offline/restricted environments:
 * - Headings: Falls back to DM Sans, then system sans-serif
 * - Body: Falls back to system-ui
 * - Code: Falls back to SF Mono, then monospace
 */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700&family=Inter:wght@400;500;600&family=Fira+Code:wght@400;500&display=swap');

:root {
  --gradient-start: #667eea;
  --gradient-end: #f093fb;
  --glass-bg: rgba(255, 255, 255, 0.15);
  --glass-bg-strong: rgba(255, 255, 255, 0.25);
  --glass-border: rgba(255, 255, 255, 0.3);
  --glass-shadow: rgba(31, 38, 135, 0.2);
  --text-dark: #1e293b;
  --text-light: #ffffff;
  --text-muted: rgba(255, 255, 255, 0.8);
  --accent: #6366f1;
  --accent-light: #818cf8;
  --highlight: #fbbf24;
  --success: #34d399;
  --error: #f87171;
}

* {
  box-sizing: border-box;
}

body {
  min-height: 100vh;
  background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
  background-attachment: fixed;
  color: var(--text-light);
  font-family: 'Inter', system-ui, sans-serif;
  line-height: 1.7;
  padding: 3rem 2rem;
}

/* === GLASS CONTAINER === */
.glass-container, article, main {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 24px;
  padding: 3rem;
  max-width: 900px;
  margin: 0 auto;
  box-shadow:
    0 8px 32px var(--glass-shadow),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

/* === HEADINGS === */
h1, h2, h3, h4 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: var(--text-light);
  font-weight: 700;
}

h1 {
  font-size: 2.75rem;
  text-align: center;
  margin-bottom: 0.5rem;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.15);
  letter-spacing: -0.02em;
}

h1 + p {
  text-align: center;
  color: var(--text-muted);
  font-size: 1.1rem;
  margin-bottom: 3rem;
}

h2 {
  font-size: 1.75rem;
  margin-top: 3rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--glass-border);
}

h3 {
  font-size: 1.25rem;
  color: var(--text-muted);
}

/* === LINKS === */
a {
  color: var(--highlight);
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
}

a:hover {
  color: #fcd34d;
  text-shadow: 0 0 20px rgba(251, 191, 36, 0.5);
}

/* === CODE === */
code {
  font-family: 'Fira Code', monospace;
  background: var(--glass-bg-strong);
  color: var(--text-light);
  padding: 0.2em 0.5em;
  border-radius: 6px;
  font-size: 0.9em;
  border: 1px solid var(--glass-border);
}

pre {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.5rem;
  overflow-x: auto;
  margin: 1.5rem 0;
}

pre code {
  background: none;
  border: none;
  padding: 0;
}

/* === BLOCKQUOTES === */
blockquote {
  background: var(--glass-bg-strong);
  border-left: 4px solid var(--highlight);
  border-radius: 0 16px 16px 0;
  margin: 2rem 0;
  padding: 1.5rem 2rem;
  backdrop-filter: blur(10px);
}

blockquote p {
  margin: 0;
  font-style: italic;
  color: var(--text-muted);
}

/* === TABLES === */
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 2rem 0;
  background: var(--glass-bg);
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--glass-border);
}

th {
  background: var(--glass-bg-strong);
  color: var(--text-light);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 600;
  padding: 1rem 1.25rem;
  text-align: left;
}

td {
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--glass-border);
}

tr:hover td {
  background: var(--glass-bg);
}

/* === LISTS === */
ul, ol {
  padding-left: 1.5rem;
}

li {
  margin: 0.75rem 0;
}

li::marker {
  color: var(--highlight);
}

/* === GLASS CARDS === */
.card {
  background: var(--glass-bg);
  backdrop-filter: blur(15px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.5rem;
  margin: 1rem 0;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px var(--glass-shadow);
}

/* === BADGES === */
.badge {
  display: inline-block;
  padding: 0.35rem 0.9rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
  background: var(--glass-bg-strong);
  border: 1px solid var(--glass-border);
  color: var(--text-light);
  backdrop-filter: blur(10px);
}

.badge-accent {
  background: rgba(99, 102, 241, 0.3);
  border-color: var(--accent);
  color: var(--accent-light);
}

.badge-success {
  background: rgba(52, 211, 153, 0.2);
  border-color: var(--success);
  color: var(--success);
}

/* === BUTTONS === */
.btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background: var(--glass-bg-strong);
  backdrop-filter: blur(10px);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  color: var(--text-light);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn:hover {
  background: var(--glass-bg);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px var(--glass-shadow);
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  border: none;
}

/* === DIVIDERS === */
hr {
  border: none;
  height: 1px;
  background: var(--glass-border);
  margin: 2rem 0;
}

/* === CALLOUTS === */
.callout {
  background: var(--glass-bg);
  backdrop-filter: blur(15px);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  margin: 1.5rem 0;
  border-left: 4px solid;
}

.callout-info { border-color: var(--accent-light); }
.callout-success { border-color: var(--success); }
.callout-warning { border-color: var(--highlight); }
.callout-error { border-color: var(--error); }

/* === RESPONSIVE === */
@media (max-width: 768px) {
  body { padding: 1rem; }
  .glass-container, article, main { padding: 1.5rem; border-radius: 16px; }
  h1 { font-size: 2rem; }
  h2 { font-size: 1.5rem; }
}

/* === PRINT === */
@media print {
  body { background: white; color: #1e293b; }
  .glass-container, article, main {
    background: #f8fafc;
    backdrop-filter: none;
    box-shadow: none;
    border: 1px solid #e2e8f0;
  }
  h1, h2, h3 { color: #1e293b; }
}
```

## Components

### Glass Card
```html
<div class="card">
  <h4 style="margin-top: 0; color: var(--highlight);">Key Insight</h4>
  <p>Important finding from the analysis...</p>
</div>
```

### Frosted Badge
```html
<span class="badge">Transcript</span>
<span class="badge badge-accent">Featured</span>
<span class="badge badge-success">Complete</span>
```

### Glass Button
```html
<button class="btn">View Details</button>
<button class="btn btn-primary">Download</button>
```

### Info Callout
```html
<div class="callout callout-info">
  <strong>Note:</strong> This section contains key takeaways.
</div>
```

## Best Used For

- Modern portfolios
- Product documentation
- Landing page content
- Creative briefs
- Design presentations
- Premium reports
