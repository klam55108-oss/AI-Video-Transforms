---
name: content-saver
description: Guides users through saving generated content (summaries, notes, key points) to professionally formatted and themed files. Use when users want to save, export, or persist content generated during the session, choose Option 4 after transcription, apply styling/themes to saved content, or explicitly ask to save summaries, notes, or derived content.
---

# Content Saver

This skill provides professional formatting templates AND visual themes for saving generated content to files. Content can include summaries, notes, key points, analysis, or any text derived from transcriptions.

## Available Formats

| Format | File | Best For |
|--------|------|----------|
| **Executive Summary** | `formats/executive-summary.md` | Business stakeholders |
| **Detailed Notes** | `formats/detailed-notes.md` | Research, reference |
| **Key Points** | `formats/key-points.md` | Quick reference |
| **Structured Data** | `formats/structured-data.md` | Integration, JSON |
| **Plain Text** | `formats/plain-text.md` | Universal compatibility |

## Available Themes

| Theme | File | Style |
|-------|------|-------|
| **Professional Dark** | `themes/professional-dark.md` | Dark mode, teal accents |
| **Professional Light** | `themes/professional-light.md` | Clean, navy headings |
| **Modern Minimalist** | `themes/modern-minimalist.md` | Off-white, whitespace |
| **Academic** | `themes/academic.md` | Warm sepia, serif fonts |
| **Vibrant Creative** | `themes/vibrant-creative.md` | Bold purple/pink |

## Workflow

### Step 1: Identify Content
Confirm what content the user wants to save (summary, key points, notes, analysis).
If content doesn't exist yet, offer to generate it first.

### Step 2: Present Format Options
```
## Save Content — Choose a Format

1. **Executive Summary** — Professional markdown with metadata
2. **Detailed Notes** — Comprehensive documentation format
3. **Key Points** — Bulleted action items and takeaways
4. **Structured Data** — JSON for programmatic use
5. **Plain Text** — Simple, universal format

Which format would you like? (1-5)
```

### Step 3: Present Theme Options
```
## Apply a Theme (Optional)

1. **Professional Dark** — Sleek dark mode
2. **Professional Light** — Clean corporate styling
3. **Modern Minimalist** — Elegant simplicity
4. **Academic** — Scholarly with serif fonts
5. **Vibrant Creative** — Bold and energetic
6. **No Theme** — Plain formatting only

Which theme? (1-6)
```

### Step 4: Apply Template & Save
1. **Read the template**: Use Read tool on `formats/{format-name}.md`
2. **Read the theme** (if selected): Use Read tool on `themes/{theme-name}.md`
3. Structure content according to the format template
4. Apply theme CSS/styling from theme file
5. Generate filename: `{source}_{type}_{YYYYMMDD}.{ext}`
6. Save with `write_file` tool
7. Confirm save and offer next steps

## Themed Output

When theme is applied, wrap content in HTML:
```html
<!DOCTYPE html>
<html>
<head>
  <style>/* CSS from theme file */</style>
</head>
<body><!-- Formatted content --></body>
</html>
```
Save as `.html` instead of `.md` when themed.

## Critical Rules

1. **Always Confirm** — Never save without confirming format, theme, filename
2. **Read Templates On-Demand** — Use Read tool to fetch specific format/theme files
3. **Preserve Content** — Don't modify meaning when formatting
4. **Include Metadata** — Source reference, date, content type
5. **Report Success** — Confirm path and offer follow-up

## Error Handling

| Error | Resolution |
|-------|------------|
| No content to save | Offer to generate first |
| Write failure | Report error, suggest alternative |
| Template not found | Use Read tool on correct path |
