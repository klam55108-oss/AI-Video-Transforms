# Professional Dark Theme

A sophisticated dark theme ideal for technical documentation and developer content.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Charcoal | `#1e1e2e` |
| Primary Text | Light Gray | `#cdd6f4` |
| Headings | Lavender | `#b4befe` |
| Accent | Teal | `#94e2d5` |
| Highlights | Peach | `#fab387` |
| Code Blocks | Surface | `#313244` |
| Borders | Overlay | `#6c7086` |

## Typography

- **Headings**: JetBrains Mono Bold, Fira Code Bold, or system monospace
- **Body Text**: Inter, -apple-system, sans-serif
- **Code**: JetBrains Mono, Fira Code, Consolas

## CSS Styling

```css
:root {
  --bg-primary: #1e1e2e;
  --bg-secondary: #313244;
  --text-primary: #cdd6f4;
  --text-secondary: #a6adc8;
  --accent: #94e2d5;
  --heading: #b4befe;
  --highlight: #fab387;
  --border: #6c7086;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: Inter, -apple-system, sans-serif;
  line-height: 1.6;
}

h1, h2, h3 { color: var(--heading); }
a { color: var(--accent); }
code { background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px; }
blockquote { border-left: 3px solid var(--accent); padding-left: 1em; color: var(--text-secondary); }
```

## Best Used For

- Technical documentation
- Developer notes
- API documentation
- Code-heavy content
- Night-time reading
