# Terminal Hacker Theme

A retro terminal/hacker aesthetic with phosphor green text, CRT effects, and nostalgic command-line styling reminiscent of classic computing.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Terminal Black | `#0c0c0c` |
| Surface | Slightly Lighter | `#1a1a1a` |
| Primary Text | Phosphor Green | `#33ff33` |
| Secondary Text | Dim Green | `#22aa22` |
| Headings | Bright Green | `#00ff00` |
| Accent | Matrix Green | `#00ff41` |
| Warning | Amber CRT | `#ffb000` |
| Error | Red Alert | `#ff3333` |
| Borders | Dark Green | `#0a3d0a` |
| Selection | Green Highlight | `rgba(0, 255, 65, 0.2)` |

## Typography

- **Headings**: 'VT323', 'Share Tech Mono', monospace (authentic terminal look)
- **Body Text**: 'Fira Code', 'Source Code Pro', monospace
- **Code**: 'IBM Plex Mono', 'Courier New', monospace

## CSS Styling

```css
/*
 * External CDN Dependencies: Google Fonts (VT323, Fira Code, Share Tech Mono)
 * Fallback fonts ensure the theme works in offline/restricted environments:
 * - Headings: Falls back to Share Tech Mono, then monospace
 * - Body: Falls back to Source Code Pro, then monospace
 * - Code: Falls back to Courier New, then monospace
 */
@import url('https://fonts.googleapis.com/css2?family=VT323&family=Fira+Code:wght@400;500&family=Share+Tech+Mono&display=swap');

:root {
  --bg-primary: #0c0c0c;
  --bg-surface: #1a1a1a;
  --bg-elevated: #242424;
  --text-primary: #33ff33;
  --text-secondary: #22aa22;
  --text-dim: #117711;
  --accent: #00ff41;
  --accent-bright: #00ff00;
  --warning: #ffb000;
  --error: #ff3333;
  --border: #0a3d0a;
  --selection: rgba(0, 255, 65, 0.2);
  --scanline: rgba(0, 0, 0, 0.1);
}

* {
  box-sizing: border-box;
}

/* === CRT EFFECTS === */
body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Fira Code', 'Source Code Pro', monospace;
  font-size: 15px;
  line-height: 1.6;
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
  min-height: 100vh;
  position: relative;
}

/* Scanlines overlay */
body::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    var(--scanline) 2px,
    var(--scanline) 4px
  );
  pointer-events: none;
  z-index: 1000;
}

/* CRT glow effect */
body::after {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(ellipse at center, transparent 0%, rgba(0, 0, 0, 0.3) 100%);
  pointer-events: none;
  z-index: 999;
}

/* === SELECTION === */
::selection {
  background: var(--selection);
  color: var(--accent-bright);
}

/* === HEADINGS === */
h1, h2, h3, h4 {
  font-family: 'VT323', 'Share Tech Mono', monospace;
  color: var(--accent-bright);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-shadow: 0 0 10px var(--accent), 0 0 20px var(--accent);
}

h1 {
  font-size: 2.5rem;
  text-align: center;
  margin-bottom: 0.5rem;
  animation: flicker 0.15s infinite;
}

h1::before {
  content: '> ';
  color: var(--text-secondary);
}

h2 {
  font-size: 1.75rem;
  margin-top: 3rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px dashed var(--border);
}

h2::before {
  content: '## ';
  color: var(--text-dim);
}

h3 {
  font-size: 1.25rem;
  color: var(--text-primary);
}

h3::before {
  content: '### ';
  color: var(--text-dim);
}

/* === PARAGRAPHS === */
p {
  margin: 1rem 0;
}

/* === LINKS === */
a {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px dashed var(--accent);
  transition: all 0.2s ease;
}

a:hover {
  color: var(--accent-bright);
  text-shadow: 0 0 8px var(--accent);
  border-bottom-style: solid;
}

a::before {
  content: '[';
  color: var(--text-dim);
}

a::after {
  content: ']';
  color: var(--text-dim);
}

/* === CODE === */
code {
  font-family: 'IBM Plex Mono', 'Courier New', monospace;
  background: var(--bg-surface);
  color: var(--warning);
  padding: 0.2em 0.4em;
  border: 1px solid var(--border);
  font-size: 0.95em;
}

pre {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  padding: 1.5rem;
  overflow-x: auto;
  margin: 1.5rem 0;
  position: relative;
}

pre::before {
  content: '$ cat output.txt';
  display: block;
  color: var(--text-dim);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed var(--border);
  font-size: 0.85rem;
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
  border-left: 3px solid var(--warning);
  margin: 1.5rem 0;
  padding: 1rem 1.5rem;
  position: relative;
}

blockquote::before {
  content: '/*';
  position: absolute;
  top: 0.5rem;
  left: 0.75rem;
  color: var(--text-dim);
  font-size: 0.8rem;
}

blockquote::after {
  content: '*/';
  position: absolute;
  bottom: 0.5rem;
  right: 0.75rem;
  color: var(--text-dim);
  font-size: 0.8rem;
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
  font-size: 0.9rem;
}

th {
  background: var(--bg-surface);
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.75rem 1rem;
  text-align: left;
  border: 1px solid var(--border);
}

td {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
}

tr:nth-child(2n) {
  background: var(--bg-surface);
}

/* === LISTS === */
ul, ol {
  padding-left: 0;
  list-style: none;
}

li {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
  position: relative;
}

ul li::before {
  content: '>';
  position: absolute;
  left: 0;
  color: var(--accent);
}

ol {
  counter-reset: terminal-counter;
}

ol li {
  counter-increment: terminal-counter;
}

ol li::before {
  content: counter(terminal-counter, decimal-leading-zero) '.';
  position: absolute;
  left: 0;
  color: var(--text-dim);
  font-size: 0.85em;
}

/* === COMMAND PROMPT === */
.prompt {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  font-family: 'Fira Code', monospace;
}

.prompt-line {
  display: flex;
  align-items: center;
  margin: 0.25rem 0;
}

.prompt-symbol {
  color: var(--accent);
  margin-right: 0.5rem;
}

.prompt-path {
  color: var(--text-secondary);
  margin-right: 0.5rem;
}

.prompt-command {
  color: var(--text-primary);
}

/* === STATUS MESSAGES === */
.status {
  padding: 0.75rem 1rem;
  margin: 1rem 0;
  border-left: 3px solid;
  font-family: 'Fira Code', monospace;
}

.status::before {
  font-weight: bold;
  margin-right: 0.5rem;
}

.status-success {
  border-color: var(--accent);
  background: rgba(0, 255, 65, 0.05);
}

.status-success::before {
  content: '[OK]';
  color: var(--accent);
}

.status-warning {
  border-color: var(--warning);
  background: rgba(255, 176, 0, 0.05);
}

.status-warning::before {
  content: '[WARN]';
  color: var(--warning);
}

.status-error {
  border-color: var(--error);
  background: rgba(255, 51, 51, 0.05);
}

.status-error::before {
  content: '[ERR]';
  color: var(--error);
}

.status-info {
  border-color: var(--text-secondary);
  background: rgba(34, 170, 34, 0.05);
}

.status-info::before {
  content: '[INFO]';
  color: var(--text-secondary);
}

/* === PROGRESS BAR === */
.progress-bar {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  padding: 0.5rem;
  margin: 1rem 0;
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}

.progress-bar-fill {
  background: var(--accent);
  height: 4px;
  margin-top: 0.5rem;
  box-shadow: 0 0 10px var(--accent);
}

/* === ASCII BOX === */
.ascii-box {
  border: 1px solid var(--border);
  padding: 1rem;
  margin: 1rem 0;
  position: relative;
}

.ascii-box::before {
  content: '+' attr(data-title) '+';
  position: absolute;
  top: -0.75rem;
  left: 1rem;
  background: var(--bg-primary);
  padding: 0 0.5rem;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

/* === BADGES/TAGS (Non-interactive labels) === */
.tag {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  font-size: 0.8rem;
  font-family: 'Fira Code', monospace;
  border: 1px solid var(--border);
  margin-right: 0.5rem;
  cursor: default;
  user-select: none;
}

.tag::before {
  content: '<';
  color: var(--text-dim);
}

.tag::after {
  content: '>';
  color: var(--text-dim);
}

.tag-green { color: var(--accent); border-color: var(--accent); }
.tag-amber { color: var(--warning); border-color: var(--warning); }
.tag-red { color: var(--error); border-color: var(--error); }

/* === ANIMATIONS === */
@keyframes flicker {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.95; }
}

@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.cursor::after {
  content: '_';
  animation: cursor-blink 1s infinite;
  color: var(--accent);
}

/* === HORIZONTAL RULES === */
hr {
  border: none;
  height: 1px;
  background: var(--border);
  margin: 2rem 0;
  position: relative;
}

hr::before {
  content: '─────────────────────────────────────────────────────────────────────';
  position: absolute;
  left: 0;
  color: var(--border);
  overflow: hidden;
  width: 100%;
}

/* === RESPONSIVE === */
@media (max-width: 768px) {
  body { padding: 1rem; font-size: 14px; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.25rem; }

  /* Reduce CRT effects on mobile for performance */
  body::before { display: none; }
}

/* === PRINT === */
@media print {
  body {
    background: white;
    color: black;
  }
  body::before, body::after { display: none; }
  h1, h2, h3 { color: black; text-shadow: none; }
  a { color: #0066cc; }
  code { background: #f0f0f0; }
}
```

## Components

### Command Prompt
```html
<div class="prompt">
  <div class="prompt-line">
    <span class="prompt-symbol">$</span>
    <span class="prompt-path">~/documents</span>
    <span class="prompt-command">cat transcript.txt</span>
  </div>
</div>
```

### Status Messages
```html
<div class="status status-success">Operation completed successfully.</div>
<div class="status status-warning">Proceed with caution.</div>
<div class="status status-error">Connection failed. Retry?</div>
<div class="status status-info">Processing transcript data...</div>
```

### Progress Bar
```html
<div class="progress-bar">
  [████████████████████░░░░░░░░░░░░░░░░░░░░] 47%
  <div class="progress-bar-fill" style="width: 47%;"></div>
</div>
```

### ASCII Box
```html
<div class="ascii-box" data-title="─ SUMMARY ─">
  <p>Key findings from the analysis...</p>
</div>
```

### Tags
```html
<span class="tag tag-green">complete</span>
<span class="tag tag-amber">pending</span>
<span class="tag tag-red">failed</span>
```

### Blinking Cursor
```html
<p class="cursor">Awaiting input</p>
```

## Best Used For

- Developer logs
- System documentation
- Retro/nostalgic content
- Hacker-themed presentations
- CLI tool documentation
- Technical debugging reports
