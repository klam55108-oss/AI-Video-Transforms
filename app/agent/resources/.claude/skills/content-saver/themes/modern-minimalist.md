# Modern Minimalist Theme

A sleek, distraction-free theme with generous whitespace and clean typography.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | Off-White | `#fafafa` |
| Primary Text | Near Black | `#171717` |
| Headings | Pure Black | `#000000` |
| Accent | Emerald | `#10b981` |
| Highlights | Subtle Gray | `#e5e5e5` |
| Code Blocks | Light Warm | `#f5f5f4` |
| Borders | Whisper | `#e5e5e5` |

## Typography

- **Headings**: Inter Bold, Helvetica Neue Bold, sans-serif
- **Body Text**: Inter, system-ui, sans-serif
- **Code**: IBM Plex Mono, monospace

## CSS Styling

```css
:root {
  --bg-primary: #fafafa;
  --bg-secondary: #f5f5f4;
  --text-primary: #171717;
  --text-secondary: #525252;
  --accent: #10b981;
  --heading: #000000;
  --highlight: #e5e5e5;
  --border: #e5e5e5;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: Inter, system-ui, sans-serif;
  line-height: 1.8;
  max-width: 680px;
  margin: 0 auto;
  padding: 3rem 1.5rem;
  font-size: 1.1rem;
}

h1 { font-size: 2.5rem; font-weight: 700; margin-top: 3rem; }
h2 { font-size: 1.75rem; font-weight: 600; margin-top: 2.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
h3 { font-size: 1.25rem; font-weight: 600; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--bg-secondary); padding: 3px 8px; border-radius: 4px; font-size: 0.9em; }
blockquote { margin: 2rem 0; padding: 1rem 1.5rem; background: var(--bg-secondary); border-radius: 8px; }
```

## Best Used For

- Blog posts
- Personal notes
- Creative writing
- Clean presentations
- Modern web content
