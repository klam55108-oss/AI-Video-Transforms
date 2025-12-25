# Vibrant Creative Theme

A bold, energetic theme for creative projects and engaging presentations.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Deep Purple | `#1a1a2e` |
| Primary Text | White | `#ffffff` |
| Headings | Electric Pink | `#e94560` |
| Accent | Cyan | `#0f3460` |
| Highlights | Gold | `#f1c40f` |
| Code Blocks | Dark Blue | `#16213e` |
| Borders | Pink Glow | `#e94560` |

## Typography

- **Headings**: Poppins Bold, Montserrat Bold, sans-serif
- **Body Text**: Nunito, Open Sans, sans-serif
- **Code**: Fira Code, monospace

## CSS Styling

```css
:root {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --text-primary: #ffffff;
  --text-secondary: #a0a0c0;
  --accent: #0f3460;
  --heading: #e94560;
  --highlight: #f1c40f;
  --border: #e94560;
}

body {
  background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  color: var(--text-primary);
  font-family: Nunito, "Open Sans", sans-serif;
  line-height: 1.7;
  padding: 2rem;
}

h1, h2, h3 {
  font-family: Poppins, Montserrat, sans-serif;
  color: var(--heading);
  text-transform: uppercase;
  letter-spacing: 2px;
}
h1 { font-size: 2.5rem; text-align: center; }
a { color: var(--highlight); text-decoration: none; }
a:hover { text-decoration: underline; }
code {
  background: var(--bg-secondary);
  color: var(--highlight);
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
}
blockquote {
  background: var(--bg-secondary);
  border-left: 4px solid var(--heading);
  padding: 1rem 1.5rem;
  border-radius: 0 8px 8px 0;
}
```

## Best Used For

- Creative presentations
- Marketing content
- Social media drafts
- Event summaries
- Brainstorming notes
