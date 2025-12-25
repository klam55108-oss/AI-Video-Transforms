# Notion Style Theme

A clean, productivity-focused theme inspired by Notion's elegant interface. Features toggle blocks, callout boxes, and exceptional readability.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Warm White | `#ffffff` |
| Surface | Soft Gray | `#f7f6f3` |
| Primary Text | Rich Black | `#37352f` |
| Secondary Text | Warm Gray | `#787774` |
| Headings | Deep Brown | `#37352f` |
| Accent Blue | Notion Blue | `#2383e2` |
| Accent Red | Notion Red | `#eb5757` |
| Accent Green | Notion Green | `#0f7b6c` |
| Accent Purple | Notion Purple | `#9065b0` |
| Accent Yellow | Notion Yellow | `#dfab01` |
| Borders | Light Gray | `#e9e9e7` |

## Typography

- **Headings**: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif
- **Body Text**: 'Segoe UI', -apple-system, system-ui, sans-serif
- **Code**: 'SFMono-Regular', 'Roboto Mono', Menlo, monospace

## CSS Styling

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f7f6f3;
  --bg-tertiary: #f1f1ef;
  --text-primary: #37352f;
  --text-secondary: #787774;
  --text-muted: #9b9a97;
  --accent-blue: #2383e2;
  --accent-red: #eb5757;
  --accent-green: #0f7b6c;
  --accent-purple: #9065b0;
  --accent-yellow: #dfab01;
  --accent-orange: #d9730d;
  --accent-pink: #c14c8a;
  --border: #e9e9e7;
  --callout-blue: #e7f3ff;
  --callout-red: #ffe7e7;
  --callout-green: #e7f7f2;
  --callout-yellow: #fef9e7;
  --callout-purple: #f4e8fb;
}

* {
  box-sizing: border-box;
}

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, system-ui, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  max-width: 850px;
  margin: 0 auto;
  padding: 4rem 2rem;
  -webkit-font-smoothing: antialiased;
}

/* === HEADINGS === */
h1, h2, h3, h4 {
  color: var(--text-primary);
  font-weight: 600;
  margin-top: 2rem;
  margin-bottom: 0.5rem;
}

h1 {
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-top: 0;
  margin-bottom: 0.25rem;
}

h1 + p {
  color: var(--text-secondary);
  font-size: 1.1rem;
  margin-bottom: 2rem;
}

h2 {
  font-size: 1.5rem;
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

h3 {
  font-size: 1.25rem;
}

h4 {
  font-size: 1rem;
  color: var(--text-secondary);
}

/* === PARAGRAPHS === */
p {
  margin: 0.5rem 0;
}

/* === LINKS === */
a {
  color: var(--text-primary);
  text-decoration: underline;
  text-decoration-color: var(--border);
  text-underline-offset: 2px;
  transition: text-decoration-color 0.2s;
}

a:hover {
  text-decoration-color: var(--text-primary);
}

/* === CODE === */
code {
  font-family: 'SFMono-Regular', 'Roboto Mono', monospace;
  background: var(--bg-tertiary);
  color: var(--accent-red);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
}

pre {
  background: var(--bg-secondary);
  border-radius: 6px;
  padding: 1rem 1.25rem;
  overflow-x: auto;
  margin: 1rem 0;
  border: 1px solid var(--border);
}

pre code {
  background: none;
  color: var(--text-primary);
  padding: 0;
}

/* === BLOCKQUOTES === */
blockquote {
  margin: 1rem 0;
  padding: 0 0 0 1rem;
  border-left: 3px solid var(--border);
  color: var(--text-secondary);
}

/* === CALLOUT BOXES === */
.callout {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-radius: 6px;
  margin: 1rem 0;
  align-items: flex-start;
}

.callout-icon {
  font-size: 1.25rem;
  line-height: 1.5;
  flex-shrink: 0;
}

.callout-content {
  flex: 1;
}

.callout-content p {
  margin: 0;
}

.callout-blue { background: var(--callout-blue); }
.callout-red { background: var(--callout-red); }
.callout-green { background: var(--callout-green); }
.callout-yellow { background: var(--callout-yellow); }
.callout-purple { background: var(--callout-purple); }

/* === TOGGLE BLOCKS === */
.toggle {
  border: 1px solid var(--border);
  border-radius: 6px;
  margin: 0.5rem 0;
}

.toggle-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  font-weight: 500;
}

.toggle-header::before {
  content: '▶';
  font-size: 0.7em;
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.toggle[open] .toggle-header::before {
  transform: rotate(90deg);
}

.toggle-content {
  padding: 0 1rem 1rem 2rem;
  color: var(--text-secondary);
}

/* === TABLES === */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  font-size: 0.95rem;
}

th, td {
  text-align: left;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
}

th {
  background: var(--bg-secondary);
  font-weight: 600;
}

/* === LISTS === */
ul, ol {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}

li {
  margin: 0.25rem 0;
}

/* === CHECKBOX LISTS === */
.todo-list {
  list-style: none;
  padding-left: 0;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0.5rem 0;
}

.todo-checkbox {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--text-secondary);
  border-radius: 3px;
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.todo-item.completed .todo-checkbox {
  background: var(--accent-blue);
  border-color: var(--accent-blue);
}

.todo-item.completed .todo-text {
  text-decoration: line-through;
  color: var(--text-muted);
}

/* === TAGS/BADGES === */
.tag {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 500;
}

.tag-blue { background: var(--callout-blue); color: var(--accent-blue); }
.tag-red { background: var(--callout-red); color: var(--accent-red); }
.tag-green { background: var(--callout-green); color: var(--accent-green); }
.tag-yellow { background: var(--callout-yellow); color: var(--accent-orange); }
.tag-purple { background: var(--callout-purple); color: var(--accent-purple); }

/* === DIVIDERS === */
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}

/* === PAGE PROPERTIES === */
.properties {
  background: var(--bg-secondary);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 2rem;
}

.property {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 0;
  font-size: 0.95rem;
}

.property-name {
  color: var(--text-muted);
  min-width: 120px;
}

.property-value {
  color: var(--text-primary);
}

/* === RESPONSIVE === */
@media (max-width: 768px) {
  body { padding: 2rem 1rem; }
  h1 { font-size: 2rem; }
}

/* === PRINT === */
@media print {
  body { max-width: none; padding: 1rem; }
  .toggle-content { display: block !important; }
  .callout { break-inside: avoid; }
}
```

## Components

### Callout Box
```html
<div class="callout callout-blue">
  <div class="callout-icon">💡</div>
  <div class="callout-content">
    <p><strong>Tip:</strong> This is an important insight from the transcript.</p>
  </div>
</div>
```

### Toggle Block
```html
<details class="toggle">
  <summary class="toggle-header">Click to expand details</summary>
  <div class="toggle-content">
    <p>Hidden content revealed here...</p>
  </div>
</details>
```

### Page Properties
```html
<div class="properties">
  <div class="property">
    <span class="property-name">Source</span>
    <span class="property-value">Video Transcript</span>
  </div>
  <div class="property">
    <span class="property-name">Date</span>
    <span class="property-value">December 2024</span>
  </div>
  <div class="property">
    <span class="property-name">Tags</span>
    <span class="property-value">
      <span class="tag tag-blue">Research</span>
      <span class="tag tag-green">Complete</span>
    </span>
  </div>
</div>
```

### Todo List
```html
<ul class="todo-list">
  <li class="todo-item completed">
    <div class="todo-checkbox"></div>
    <span class="todo-text">Review transcript</span>
  </li>
  <li class="todo-item">
    <div class="todo-checkbox"></div>
    <span class="todo-text">Extract key points</span>
  </li>
</ul>
```

## Best Used For

- Personal knowledge bases
- Meeting notes
- Project documentation
- Study materials
- Wiki-style content
- Collaborative documents
