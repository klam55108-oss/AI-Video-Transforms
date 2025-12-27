# CognivAgent Rebrand Specification

> Instructions for Claude Code to rebrand the project from "Agent Video to Data" / "VideoAgent" to **CognivAgent**.

---

## Overview

| Old | New |
|-----|-----|
| Agent Video to Data | CognivAgent |
| VideoAgent | CognivAgent |
| video-agent | cognivagent |
| Camera icon | Hub-spoke eye icon |

---

## 1. Icon Files

### Source Files (this folder)

```
cognivagent-branding/
├── cognivagent-icon-dark.svg    # Dark theme (32px sidebar)
├── cognivagent-icon-light.svg   # Light theme (32px sidebar)
├── cognivagent-favicon.svg      # Browser tab (16px)
├── cognivagent-icon-128.svg     # README/GitHub (128px)
└── REBRAND_SPEC.md              # This file
```

### Destination

Copy icons to `app/static/`:

```bash
cp cognivagent-icon-dark.svg app/static/icons/
cp cognivagent-icon-light.svg app/static/icons/
cp cognivagent-favicon.svg app/static/icons/
cp cognivagent-icon-128.svg app/static/icons/
```

Create `app/static/icons/` directory if it doesn't exist.

---

## 2. Template Modifications

### `app/templates/index.html`

#### Page Title
```html
<!-- OLD -->
<title>Video to Data | Agent Dashboard</title>

<!-- NEW -->
<title>CognivAgent</title>
```

#### Favicon
```html
<!-- ADD in <head> -->
<link rel="icon" type="image/svg+xml" href="/static/icons/cognivagent-favicon.svg">
```

#### Sidebar Header Logo + Name

Find the sidebar header section containing the camera icon and "VideoAgent" text. Replace with:

```html
<!-- Sidebar logo - switches based on theme -->
<img 
  src="/static/icons/cognivagent-icon-dark.svg" 
  alt="CognivAgent" 
  class="sidebar-logo dark-theme-icon"
  width="32" 
  height="32"
>
<img 
  src="/static/icons/cognivagent-icon-light.svg" 
  alt="CognivAgent" 
  class="sidebar-logo light-theme-icon"
  width="32" 
  height="32"
>
<span class="sidebar-title">CognivAgent</span>
```

Note: If current implementation uses a single icon, add CSS to toggle visibility based on `data-theme` attribute.

---

## 3. CSS Modifications

### `app/static/style.css`

Add theme-aware icon switching (if not already present):

```css
/* Theme-aware sidebar logo */
[data-theme="dark"] .light-theme-icon {
  display: none;
}

[data-theme="dark"] .dark-theme-icon {
  display: block;
}

[data-theme="light"] .dark-theme-icon {
  display: none;
}

[data-theme="light"] .light-theme-icon {
  display: block;
}
```

---

## 4. Agent Resources

### `app/agent/resources/CLAUDE.md`

Update any references to the project name:

```markdown
<!-- OLD -->
# Agent Video to Data

<!-- NEW -->
# CognivAgent
```

### Agent Greeting

Find the system prompt or greeting message. Update:

```
<!-- OLD -->
Hi! I'm COSTA, your transcription assistant powered by gpt-4o-transcribe.

<!-- NEW -->
Hi! I'm your CognivAgent assistant powered by gpt-4o-transcribe.
```

Or if keeping a personality name:

```
Hi! I'm CognivAgent, your AI assistant for video transcription and knowledge extraction.
```

---

## 5. Configuration Files

### `pyproject.toml`

```toml
# OLD
[project]
name = "agent-video-to-data"

# NEW
[project]
name = "cognivagent"
```

### `docker-compose.yml`

```yaml
# OLD
services:
  video-agent:
    container_name: video-agent

# NEW
services:
  cognivagent:
    container_name: cognivagent
```

---

## 6. Documentation

### `README.md`

#### Header
```markdown
<!-- OLD -->
# Agent Video to Data

<!-- NEW -->
# CognivAgent

<p align="center">
  <img src="cognivagent-branding/cognivagent-icon-128.svg" alt="CognivAgent" width="128">
</p>
```

#### Description
```markdown
<!-- OLD -->
> Transform videos into searchable transcripts and knowledge graphs through an intelligent AI chat interface.

<!-- NEW -->
> AI agent that transforms videos into searchable transcripts and knowledge graphs.
```

#### All Text References
Replace all occurrences of:
- "Agent Video to Data" → "CognivAgent"
- "VideoAgent" → "CognivAgent"
- "video-agent" → "cognivagent"

### `CLAUDE.md`

Update the header and any project name references:

```markdown
<!-- OLD -->
# Agent Video to Data

<!-- NEW -->
# CognivAgent
```

---

## 7. JavaScript (if applicable)

### `app/static/js/core/config.js` or similar

If there's a hardcoded app name:

```javascript
// OLD
const APP_NAME = 'VideoAgent';

// NEW
const APP_NAME = 'CognivAgent';
```

---

## 8. Search and Replace Summary

Run these replacements project-wide (case-sensitive):

| Find | Replace |
|------|---------|
| `Agent Video to Data` | `CognivAgent` |
| `VideoAgent` | `CognivAgent` |
| `Video to Data` | `CognivAgent` |
| `video-agent` | `cognivagent` |
| `video_agent` | `cognivagent` |

**Exclude from replacement:**
- `git` history
- `node_modules/`
- `.venv/`
- `__pycache__/`

---

## 9. Verification Checklist

After changes, verify:

- [ ] Browser tab shows new favicon
- [ ] Browser tab title shows "CognivAgent"
- [ ] Sidebar displays new icon (dark theme)
- [ ] Sidebar displays new icon (light theme)
- [ ] Sidebar text shows "CognivAgent"
- [ ] Agent greeting mentions CognivAgent
- [ ] README header has new icon and name
- [ ] `uv run python -m app.main` starts without errors
- [ ] All tests pass: `uv run pytest`

---

## 10. Git Commit

Suggested commit message:

```
feat: rebrand to CognivAgent

- Replace VideoAgent branding with CognivAgent
- Add new hub-spoke eye icon (dark/light themes)
- Update favicon, README header, sidebar
- Update agent greeting and documentation
```

---

## Notes

- The icon uses CSS `currentColor` alternatives are available if needed
- Gradient goes cyan (#00d9ff) → indigo (#6366f1) for dark theme
- Gradient goes amber (#f59e0b) → orange (#ea580c) for light theme
- The "eye" in the center represents the agent watching/processing
- Favicon is simplified for 16px legibility
