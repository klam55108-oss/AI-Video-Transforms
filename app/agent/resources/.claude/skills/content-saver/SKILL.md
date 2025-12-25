---
name: content-saver
description: Guides users through saving generated content (summaries, notes, key points) to professionally formatted and themed files. Use when users want to save, export, or persist content generated during the session, choose Option 4 after transcription, apply styling/themes to saved content, or explicitly ask to save summaries, notes, or derived content.
---

# Content Saver

This skill provides professional formatting templates AND visual themes for saving generated content to files. Content can include summaries, notes, key points, analysis, or any text derived from transcriptions.

## Purpose

When users want to save session content to files, this skill ensures:
- Consistent, professional formatting
- Visual theming with colors, typography, and styling
- Appropriate file naming conventions
- Clear structure based on content type
- Proper metadata inclusion

## Available Formats

The following formats are available in the `formats/` directory:

| Format | Best For | Extension |
|--------|----------|-----------|
| **Executive Summary** | Business stakeholders, quick overviews | `.md` |
| **Detailed Notes** | Research, reference documentation | `.md` |
| **Key Points** | Quick reference, action items | `.md` |
| **Structured Data** | Integration, further processing | `.json` |
| **Plain Text** | Universal compatibility | `.txt` |

## Available Themes

The following themes are available in the `themes/` directory:

| Theme | Best For | Style |
|-------|----------|-------|
| **Professional Dark** | Technical docs, developer content | Dark background, teal accents |
| **Professional Light** | Business reports, formal docs | Clean white, navy headings |
| **Modern Minimalist** | Blog posts, clean presentations | Off-white, generous whitespace |
| **Academic** | Research papers, scholarly content | Warm sepia, serif typography |
| **Vibrant Creative** | Marketing, creative projects | Bold purple/pink, energetic |

Each theme includes:
- Color palette with hex codes
- Typography recommendations (headings, body, code)
- CSS styling for HTML/web rendering
- Use case guidance

## Workflow

### Step 1: Identify Content to Save
Confirm what content the user wants to save:
- Summary of a transcription?
- Key points extracted?
- Analysis or notes?
- Full derived content?

If content doesn't exist yet, offer to generate it first.

### Step 2: Present Format Options
Display the available formats:

```
## Save Content — Choose a Format

I can save your content in these formats:

1. **Executive Summary** — Professional markdown with metadata
2. **Detailed Notes** — Comprehensive documentation format
3. **Key Points** — Bulleted action items and takeaways
4. **Structured Data** — JSON for programmatic use
5. **Plain Text** — Simple, universal format

Which format would you like? (1-5)
```

### Step 3: Present Theme Options
After format selection, offer theming:

```
## Apply a Theme (Optional)

Would you like to apply a visual theme? Themes add styling for colors,
typography, and visual hierarchy.

1. **Professional Dark** — Sleek dark mode for technical content
2. **Professional Light** — Clean corporate styling
3. **Modern Minimalist** — Elegant simplicity
4. **Academic** — Scholarly with serif fonts
5. **Vibrant Creative** — Bold and energetic
6. **No Theme** — Plain formatting only

Which theme? (1-6, or describe a custom style)
```

### Step 4: Get User Confirmation
After format and theme selection:
- Read the format template from `formats/` directory
- Read the theme template from `themes/` directory (if selected)
- Show a preview of how the content will be structured and styled
- Confirm filename with user (suggest based on source + date)

### Step 5: Apply Format, Theme & Save
1. Structure the content according to the chosen format template
2. Apply theme styling:
   - For Markdown: Add CSS in `<style>` block or HTML wrapper
   - For HTML: Embed full CSS styling
   - For JSON: Include theme metadata in output
   - For Plain Text: Skip theme (not applicable)
3. Generate appropriate filename:
   - Pattern: `{source-name}_{content-type}_{YYYYMMDD}.{ext}`
   - Example: `tech-interview_summary_20250125.md`
4. Use `write_file` tool to save
5. Confirm save location and offer next steps

## Themed Output Examples

### Markdown with Theme
When saving markdown with a theme, wrap content in an HTML structure:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{Document Title}</title>
  <style>
    /* Theme CSS from themes/{theme-name}.md */
  </style>
</head>
<body>
  <!-- Formatted markdown content rendered as HTML -->
</body>
</html>
```

Save as `.html` instead of `.md` when theme is applied.

### Pure Markdown (No Theme)
When no theme is selected, save as standard `.md`:

```markdown
# {Title}

**Date:** {YYYY-MM-DD}
**Source:** {source reference}

---

{Formatted content following template}
```

## Format Details

Each format template is defined in the `formats/` directory:

### Executive Summary (`formats/executive-summary.md`)
Professional markdown with:
- Title and date
- Source reference
- Key takeaways (bulleted)
- Brief summary paragraph
- Notable quotes (if relevant)

### Detailed Notes (`formats/detailed-notes.md`)
Comprehensive documentation with:
- Header with metadata
- Table of contents
- Sectioned content
- Timestamps/references
- Source attribution

### Key Points (`formats/key-points.md`)
Action-oriented format with:
- Bulleted main points
- Action items
- Important quotes
- Quick reference sections

### Structured Data (`formats/structured-data.md`)
JSON schema with:
- Metadata object
- Content sections
- Timestamps
- Relationships

### Plain Text (`formats/plain-text.md`)
Simple format with:
- Title line
- Date
- Content blocks
- Source reference

## Theme Details

Each theme template in `themes/` directory includes:

### Professional Dark (`themes/professional-dark.md`)
- Dark charcoal background (#1e1e2e)
- Teal accents, lavender headings
- Monospace fonts for technical feel
- Best for: Developer docs, API notes

### Professional Light (`themes/professional-light.md`)
- Clean white background
- Navy headings, royal blue accents
- Serif headings, sans-serif body
- Best for: Business reports, client docs

### Modern Minimalist (`themes/modern-minimalist.md`)
- Off-white with generous whitespace
- Emerald accents, near-black text
- Inter font, narrow content width
- Best for: Blog posts, personal notes

### Academic (`themes/academic.md`)
- Warm parchment tones
- Serif typography throughout
- Footnote styling, citations
- Best for: Research, scholarly work

### Vibrant Creative (`themes/vibrant-creative.md`)
- Deep purple gradient background
- Electric pink headings, gold highlights
- Bold sans-serif, uppercase headings
- Best for: Creative, marketing content

## Custom Themes

If none of the preset themes fit, create a custom theme:

1. Ask user for preferences:
   - Light or dark mode?
   - Preferred accent color?
   - Formal or casual typography?
2. Generate a custom theme following the template structure
3. Apply to output as with preset themes

## Critical Rules

1. **Always Confirm Before Saving** — Never save without user confirmation of format, theme, and filename
2. **Preserve Original Content** — Don't modify the meaning when applying formatting
3. **Include Metadata** — Always include source reference, date, and content type
4. **Suggest Meaningful Names** — Use descriptive filenames based on content
5. **Match Theme to Content** — Suggest appropriate themes based on content type
6. **Report Success Clearly** — After saving, confirm path and offer follow-up options

## Error Handling

| Error | Resolution |
|-------|------------|
| No content to save | Offer to generate content first |
| Invalid filename | Suggest sanitized alternative |
| Write failure | Report error, suggest alternative path |
| Permission denied | Check file path is within allowed directories |
| Theme not found | Fall back to no theme, notify user |

## After Saving

Present follow-up options:
```
Content saved to: `{filepath}`

Applied: {format name} format with {theme name} theme

Would you like to:
1. Save in another format/theme
2. Save additional content
3. Return to transcription options
```
