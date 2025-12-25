# GitHub Docs Theme

A clean, developer-focused theme inspired by GitHub's documentation. Features excellent code highlighting, alert boxes, and familiar styling for technical content.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Canvas Default | `#ffffff` |
| Surface | Canvas Subtle | `#f6f8fa` |
| Primary Text | Foreground | `#1f2328` |
| Secondary Text | Muted | `#656d76` |
| Headings | Emphasis | `#1f2328` |
| Accent Blue | Link | `#0969da` |
| Accent Green | Success | `#1a7f37` |
| Accent Yellow | Warning | `#9a6700` |
| Accent Red | Danger | `#cf222e` |
| Borders | Border Default | `#d0d7de` |

## Typography

- **Headings**: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
- **Body Text**: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', sans-serif
- **Code**: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace

## CSS Styling

```css
:root {
  /* Light mode (default) */
  --color-canvas-default: #ffffff;
  --color-canvas-subtle: #f6f8fa;
  --color-canvas-inset: #eff2f5;
  --color-fg-default: #1f2328;
  --color-fg-muted: #656d76;
  --color-fg-subtle: #6e7781;
  --color-accent-fg: #0969da;
  --color-success-fg: #1a7f37;
  --color-attention-fg: #9a6700;
  --color-danger-fg: #cf222e;
  --color-border-default: #d0d7de;
  --color-border-muted: #d8dee4;
  --color-neutral-muted: rgba(175, 184, 193, 0.2);
  --color-success-subtle: #dafbe1;
  --color-attention-subtle: #fff8c5;
  --color-danger-subtle: #ffebe9;
  --color-accent-subtle: #ddf4ff;
}

* {
  box-sizing: border-box;
}

body {
  background: var(--color-canvas-default);
  color: var(--color-fg-default);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.5;
  max-width: 1012px;
  margin: 0 auto;
  padding: 2rem;
  word-wrap: break-word;
}

/* === HEADINGS === */
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  line-height: 1.25;
  margin-top: 24px;
  margin-bottom: 16px;
}

h1 {
  font-size: 2rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--color-border-muted);
}

h2 {
  font-size: 1.5rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--color-border-muted);
}

h3 { font-size: 1.25rem; }
h4 { font-size: 1rem; }
h5 { font-size: 0.875rem; }
h6 { font-size: 0.85rem; color: var(--color-fg-muted); }

/* === LINKS === */
a {
  color: var(--color-accent-fg);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* === CODE === */
code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 85%;
  background: var(--color-neutral-muted);
  border-radius: 6px;
  padding: 0.2em 0.4em;
}

pre {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 85%;
  line-height: 1.45;
  background: var(--color-canvas-subtle);
  border-radius: 6px;
  padding: 16px;
  overflow: auto;
  margin: 16px 0;
}

pre code {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 100%;
}

/* === BLOCKQUOTES === */
blockquote {
  margin: 0;
  padding: 0 1rem;
  color: var(--color-fg-muted);
  border-left: 0.25rem solid var(--color-border-default);
}

/* === ALERTS/CALLOUTS === */
.markdown-alert {
  padding: 0.5rem 1rem;
  margin: 16px 0;
  border-radius: 6px;
  border-left: 4px solid;
}

.markdown-alert-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.markdown-alert-note {
  background: var(--color-accent-subtle);
  border-color: var(--color-accent-fg);
}
.markdown-alert-note .markdown-alert-title { color: var(--color-accent-fg); }

.markdown-alert-tip {
  background: var(--color-success-subtle);
  border-color: var(--color-success-fg);
}
.markdown-alert-tip .markdown-alert-title { color: var(--color-success-fg); }

.markdown-alert-important {
  background: #fbefff;
  border-color: #8250df;
}
.markdown-alert-important .markdown-alert-title { color: #8250df; }

.markdown-alert-warning {
  background: var(--color-attention-subtle);
  border-color: var(--color-attention-fg);
}
.markdown-alert-warning .markdown-alert-title { color: var(--color-attention-fg); }

.markdown-alert-caution {
  background: var(--color-danger-subtle);
  border-color: var(--color-danger-fg);
}
.markdown-alert-caution .markdown-alert-title { color: var(--color-danger-fg); }

/* === TABLES === */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

th, td {
  padding: 6px 13px;
  border: 1px solid var(--color-border-default);
}

th {
  font-weight: 600;
  background: var(--color-canvas-subtle);
}

tr:nth-child(2n) {
  background: var(--color-canvas-subtle);
}

/* === LISTS === */
ul, ol {
  padding-left: 2rem;
  margin: 16px 0;
}

li {
  margin: 0.25rem 0;
}

li + li {
  margin-top: 0.25rem;
}

/* === TASK LISTS === */
.task-list-item {
  list-style-type: none;
  margin-left: -1.5rem;
}

.task-list-item input[type="checkbox"] {
  margin-right: 0.5rem;
}

/* === HORIZONTAL RULES === */
hr {
  height: 0.25rem;
  padding: 0;
  margin: 24px 0;
  background: var(--color-border-default);
  border: 0;
}

/* === IMAGES === */
img {
  max-width: 100%;
  border-radius: 6px;
}

/* === LABELS/BADGES === */
.label {
  display: inline-block;
  padding: 0 7px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  border-radius: 2rem;
  border: 1px solid transparent;
}

.label-blue { background: var(--color-accent-subtle); color: var(--color-accent-fg); }
.label-green { background: var(--color-success-subtle); color: var(--color-success-fg); }
.label-yellow { background: var(--color-attention-subtle); color: var(--color-attention-fg); }
.label-red { background: var(--color-danger-subtle); color: var(--color-danger-fg); }
.label-purple { background: #fbefff; color: #8250df; }

/* === KEYBOARD KEYS === */
kbd {
  display: inline-block;
  padding: 3px 5px;
  font-size: 11px;
  line-height: 10px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  color: var(--color-fg-default);
  background: var(--color-canvas-subtle);
  border: 1px solid var(--color-border-default);
  border-radius: 6px;
  box-shadow: inset 0 -1px 0 var(--color-border-default);
}

/* === DEFINITION LISTS === */
dl {
  margin: 16px 0;
}

dt {
  font-weight: 600;
  margin-top: 16px;
}

dd {
  margin-left: 0;
  padding-left: 16px;
  margin-bottom: 8px;
}

/* === DARK MODE === */
@media (prefers-color-scheme: dark) {
  :root {
    --color-canvas-default: #0d1117;
    --color-canvas-subtle: #161b22;
    --color-canvas-inset: #010409;
    --color-fg-default: #e6edf3;
    --color-fg-muted: #8b949e;
    --color-fg-subtle: #6e7681;
    --color-accent-fg: #58a6ff;
    --color-success-fg: #3fb950;
    --color-attention-fg: #d29922;
    --color-danger-fg: #f85149;
    --color-border-default: #30363d;
    --color-border-muted: #21262d;
    --color-neutral-muted: rgba(110, 118, 129, 0.4);
    --color-success-subtle: rgba(46, 160, 67, 0.15);
    --color-attention-subtle: rgba(187, 128, 9, 0.15);
    --color-danger-subtle: rgba(248, 81, 73, 0.15);
    --color-accent-subtle: rgba(56, 139, 253, 0.15);
  }
}

/* === RESPONSIVE === */
@media (max-width: 768px) {
  body { padding: 1rem; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.25rem; }
}

/* === PRINT === */
@media print {
  body { max-width: none; }
  pre { white-space: pre-wrap; }
  .markdown-alert { break-inside: avoid; }
}
```

## Components

### Alert Boxes (GitHub-style)
```html
<div class="markdown-alert markdown-alert-note">
  <p class="markdown-alert-title">📘 Note</p>
  <p>Useful information that users should know.</p>
</div>

<div class="markdown-alert markdown-alert-tip">
  <p class="markdown-alert-title">💡 Tip</p>
  <p>Helpful advice for doing things better.</p>
</div>

<div class="markdown-alert markdown-alert-important">
  <p class="markdown-alert-title">📣 Important</p>
  <p>Key information users need to know.</p>
</div>

<div class="markdown-alert markdown-alert-warning">
  <p class="markdown-alert-title">⚠️ Warning</p>
  <p>Urgent info that needs immediate attention.</p>
</div>

<div class="markdown-alert markdown-alert-caution">
  <p class="markdown-alert-title">🛑 Caution</p>
  <p>Potential negative consequences of an action.</p>
</div>
```

### Labels
```html
<span class="label label-blue">transcript</span>
<span class="label label-green">complete</span>
<span class="label label-purple">featured</span>
```

### Keyboard Shortcuts
```html
<p>Press <kbd>Ctrl</kbd> + <kbd>S</kbd> to save.</p>
```

### Task List
```html
<ul>
  <li class="task-list-item"><input type="checkbox" checked> Completed task</li>
  <li class="task-list-item"><input type="checkbox"> Pending task</li>
</ul>
```

## Best Used For

- Technical documentation
- API references
- README files
- Developer guides
- Open source projects
- Code tutorials
