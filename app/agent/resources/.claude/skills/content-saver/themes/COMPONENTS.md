# Shared Theme Components

A library of reusable UI components that work across all themes. Copy and adapt these patterns for consistent, professional output.

## Quick Reference

| Component | Purpose | Compatible Themes |
|-----------|---------|-------------------|
| Callouts | Highlight important information | All |
| Badges/Tags | Categorize and label content | All |
| Cards | Group related information | Glassmorphism, Notion, Neural AI |
| Tables | Structured data display | All |
| Code Blocks | Display code with syntax context | All |
| Progress Indicators | Show completion status | Terminal, Neural AI |
| Toggles/Accordions | Collapsible sections | Notion, GitHub |
| Timestamps | Date/time metadata | All |
| Key-Value Properties | Metadata display | Notion, GitHub |

---

## Callouts / Alerts

Universal information callouts that adapt to each theme's color system.

### Basic Structure
```html
<div class="callout callout-{type}">
  <div class="callout-icon">{emoji}</div>
  <div class="callout-content">
    <strong>{Title}:</strong> {Message content here}
  </div>
</div>
```

### Types and Usage

| Type | Icon | Use Case |
|------|------|----------|
| `info` / `note` | `ℹ️` or `📘` | General information, neutral tips |
| `tip` / `success` | `💡` or `✅` | Best practices, positive outcomes |
| `warning` / `caution` | `⚠️` | Potential issues, things to watch |
| `danger` / `error` | `🛑` or `❌` | Critical warnings, errors |
| `important` | `📣` | Key information that shouldn't be missed |

### Examples by Theme

**GitHub Docs Style:**
```html
<div class="markdown-alert markdown-alert-note">
  <p class="markdown-alert-title">📘 Note</p>
  <p>This feature requires API version 2.0 or higher.</p>
</div>
```

**Notion Style:**
```html
<div class="callout callout-blue">
  <div class="callout-icon">💡</div>
  <div class="callout-content">
    <p><strong>Tip:</strong> Use keyboard shortcuts for faster navigation.</p>
  </div>
</div>
```

**Terminal Style:**
```html
<div class="status status-info">[INFO] Processing transcript data...</div>
<div class="status status-success">[OK] Operation completed.</div>
<div class="status status-warning">[WARN] Rate limit approaching.</div>
<div class="status status-error">[ERR] Connection failed.</div>
```

---

## Badges / Tags / Labels

Inline labels for categorization and status.

### Structure
```html
<span class="badge badge-{color}">{Label Text}</span>
<!-- or -->
<span class="tag tag-{color}">{Label Text}</span>
<!-- or -->
<span class="label label-{color}">{Label Text}</span>
```

### Color Options

| Color | Semantic Meaning |
|-------|------------------|
| `blue` / `primary` | Default, informational |
| `green` / `success` | Complete, approved, active |
| `yellow` / `warning` / `amber` | Pending, needs attention |
| `red` / `danger` / `error` | Failed, rejected, critical |
| `purple` / `accent` | Featured, special, premium |
| `gray` / `muted` | Archived, inactive, deprecated |

### Examples by Theme

**GitHub Style:**
```html
<span class="label label-blue">documentation</span>
<span class="label label-green">complete</span>
<span class="label label-purple">featured</span>
```

**Glassmorphism Style:**
```html
<span class="badge">Default</span>
<span class="badge badge-accent">Featured</span>
<span class="badge badge-success">Complete</span>
```

**Terminal Style:**
```html
<span class="tag tag-green">active</span>
<span class="tag tag-amber">pending</span>
<span class="tag tag-red">offline</span>
```

---

## Cards / Containers

Grouped content sections with visual separation.

### Basic Structure
```html
<div class="card">
  <h4 class="card-title">{Title}</h4>
  <div class="card-content">
    {Content here}
  </div>
</div>
```

### Glassmorphism Card (Hover Effect)
```html
<div class="card">
  <h4 style="margin-top: 0; color: var(--highlight);">Key Insight</h4>
  <p>Important finding from the analysis...</p>
</div>
```

### Neural AI Data Card
```html
<div style="background: var(--bg-surface); border: 1px solid var(--border-glow); border-radius: 12px; padding: 1.5rem;">
  <h4 style="margin-top: 0;">Metrics</h4>
  <p>Content analysis results...</p>
</div>
```

### ASCII Box (Terminal)
```html
<div class="ascii-box" data-title="─ SUMMARY ─">
  <p>Key findings from the analysis...</p>
</div>
```

---

## Metadata Properties

Display key-value pairs for document metadata.

### Notion Style Properties
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
    <span class="property-name">Status</span>
    <span class="property-value">
      <span class="tag tag-green">Complete</span>
    </span>
  </div>
  <div class="property">
    <span class="property-name">Tags</span>
    <span class="property-value">
      <span class="tag tag-blue">Research</span>
      <span class="tag tag-purple">AI</span>
    </span>
  </div>
</div>
```

### Simple Table Format (All Themes)
```html
<table>
  <tr><th>Property</th><th>Value</th></tr>
  <tr><td>Duration</td><td>45:32</td></tr>
  <tr><td>Words</td><td>7,234</td></tr>
  <tr><td>Speakers</td><td>2</td></tr>
</table>
```

---

## Toggle / Accordion Sections

Collapsible content for long documents.

### HTML5 Details Element (Universal)
```html
<details>
  <summary>Click to expand</summary>
  <p>Hidden content revealed here...</p>
</details>
```

### Notion Style Toggle
```html
<details class="toggle">
  <summary class="toggle-header">Section Title</summary>
  <div class="toggle-content">
    <p>Expandable content goes here...</p>
  </div>
</details>
```

---

## Progress Indicators

Show completion or processing status.

### Text-Based (Terminal)
```html
<div class="progress-bar">
  [████████████████████░░░░░░░░░░░░░░░░░░░░] 47%
</div>
```

### Visual Bar (Modern Themes)
```html
<div style="background: var(--bg-secondary); border-radius: 4px; overflow: hidden; height: 8px;">
  <div style="background: var(--accent); width: 75%; height: 100%;"></div>
</div>
<p style="font-size: 0.85rem; color: var(--text-secondary);">75% Complete</p>
```

---

## Timestamps

Date and time display patterns.

### Inline Timestamp
```html
<time datetime="2024-12-25T10:30:00Z">December 25, 2024 at 10:30 AM</time>
```

### Relative Time Style
```html
<span style="color: var(--text-secondary); font-size: 0.85rem;">
  Updated 2 hours ago
</span>
```

### Video Timestamp Link
```html
<a href="#t=1234">[20:34]</a> Speaker begins discussing key topic...
```

---

## Task Lists / Checklists

Track completion of items.

### GitHub Style
```html
<ul>
  <li class="task-list-item"><label><input type="checkbox" checked disabled> Completed task</label></li>
  <li class="task-list-item"><label><input type="checkbox" disabled> Pending task</label></li>
</ul>
```

### Notion Style
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

---

## Keyboard Shortcuts

Display keyboard keys and shortcuts.

### Standard Format
```html
<p>Press <kbd>Ctrl</kbd> + <kbd>S</kbd> to save.</p>
<p>Use <kbd>Space</kbd> to pause/play.</p>
```

---

## Quotations and Citations

Attribute quotes and references.

### Blockquote with Attribution
```html
<blockquote>
  <p>"The key insight from this analysis is..."</p>
  <footer>— Speaker Name, <cite>Video Title</cite></footer>
</blockquote>
```

### Academic Citation
```html
<p>As noted in the transcript<sup><a href="#ref1">[1]</a></sup>, the main finding was...</p>

<hr>
<div class="footnotes">
  <p id="ref1"><sup>1</sup> Source: Video Transcript, timestamp 12:34</p>
</div>
```

---

## Best Practices

### 1. Semantic HTML First
Always use semantic HTML elements where possible:
- `<article>` for main content
- `<section>` for logical groupings
- `<aside>` for supplementary information
- `<nav>` for navigation
- `<time>` for dates/times
- `<abbr>` for abbreviations
- `<mark>` for highlights

### 2. Accessibility
- Include `alt` text for images
- Use sufficient color contrast
- Don't rely solely on color to convey meaning
- Ensure interactive elements are keyboard accessible

### 3. Print Compatibility
All themes include print styles. Components degrade gracefully:
- Colors convert to grayscale appropriately
- Backgrounds simplify for ink saving
- Interactive elements display statically

### 4. Responsive Design
Components are designed to work on all screen sizes:
- Flexible widths using percentages or max-width
- Appropriate padding adjustments for mobile
- Readable font sizes on small screens

---

## Theme Selection Guide

| Content Type | Recommended Theme |
|--------------|-------------------|
| Technical documentation | GitHub Docs |
| Meeting notes | Notion Style |
| Research papers | Academic |
| Product reports | Glassmorphism |
| AI/ML content | Neural AI |
| Developer logs | Terminal Hacker |
| Business documents | Professional Light/Dark |
| Creative briefs | Vibrant Creative |
