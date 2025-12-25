# Academic Theme

A scholarly theme designed for research papers, citations, and academic content.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Warm White | `#fffef9` |
| Primary Text | Dark Sepia | `#3d3929` |
| Headings | Deep Brown | `#5c4d3c` |
| Accent | Academic Blue | `#2563eb` |
| Highlights | Cream | `#fef3c7` |
| Code Blocks | Parchment | `#fef9e7` |
| Borders | Warm Gray | `#d4c8b8` |

## Typography

- **Headings**: Crimson Pro, Times New Roman, serif
- **Body Text**: Source Serif Pro, Georgia, serif
- **Code**: Source Code Pro, Courier New, monospace

## CSS Styling

```css
:root {
  --bg-primary: #fffef9;
  --bg-secondary: #fef9e7;
  --text-primary: #3d3929;
  --text-secondary: #5c5344;
  --accent: #2563eb;
  --heading: #5c4d3c;
  --highlight: #fef3c7;
  --border: #d4c8b8;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: "Source Serif Pro", Georgia, serif;
  line-height: 1.9;
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem;
  font-size: 1.05rem;
}

h1, h2, h3 { font-family: "Crimson Pro", "Times New Roman", serif; color: var(--heading); }
h1 { font-size: 2rem; text-align: center; margin-bottom: 0.5rem; }
h2 { font-size: 1.5rem; margin-top: 2rem; border-bottom: 2px solid var(--border); }
a { color: var(--accent); }
blockquote {
  font-style: italic;
  margin: 1.5rem 2rem;
  padding-left: 1rem;
  border-left: 3px solid var(--border);
}
sup { font-size: 0.75em; }
.footnote { font-size: 0.9rem; color: var(--text-secondary); }
```

## Best Used For

- Research papers
- Literature reviews
- Academic notes
- Citations and references
- Scholarly articles
