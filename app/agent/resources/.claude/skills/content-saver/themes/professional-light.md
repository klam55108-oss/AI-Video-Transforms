# Professional Light Theme

A clean, corporate theme perfect for business documents and formal reports.

## Color Palette

| Role | Color | Hex Code |
|------|-------|----------|
| Background | White | `#ffffff` |
| Primary Text | Dark Gray | `#1f2937` |
| Headings | Navy Blue | `#1e40af` |
| Accent | Royal Blue | `#3b82f6` |
| Highlights | Amber | `#f59e0b` |
| Code Blocks | Light Gray | `#f3f4f6` |
| Borders | Medium Gray | `#d1d5db` |

## Typography

- **Headings**: Georgia, Cambria, serif
- **Body Text**: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif
- **Code**: SF Mono, Monaco, Consolas, monospace

## CSS Styling

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f3f4f6;
  --text-primary: #1f2937;
  --text-secondary: #4b5563;
  --accent: #3b82f6;
  --heading: #1e40af;
  --highlight: #f59e0b;
  --border: #d1d5db;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.7;
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

h1, h2, h3 { color: var(--heading); font-family: Georgia, Cambria, serif; }
a { color: var(--accent); }
code { background: var(--bg-secondary); padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
blockquote { border-left: 4px solid var(--accent); padding-left: 1em; color: var(--text-secondary); font-style: italic; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--border); padding: 0.75rem; text-align: left; }
th { background: var(--bg-secondary); }
```

## Best Used For

- Business reports
- Executive summaries
- Formal documentation
- Client deliverables
- Print-ready documents
