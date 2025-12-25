# Agent Resources

This directory contains Claude Agent SDK resources for the runtime agent (not Claude Code).

## Structure

```
app/agent/resources/
├── CLAUDE.md                 # Agent instructions (loaded via setting_sources)
├── README.md                 # This file
└── .claude/
    ├── settings.json         # Agent permissions
    └── skills/
        ├── transcription-helper/SKILL.md
        ├── kg-bootstrap/SKILL.md
        └── error-recovery/SKILL.md
```

## How It Works

The `SessionActor` in `app/core/session.py` configures:
- `cwd` → Points to this directory
- `setting_sources=["project"]` → Loads CLAUDE.md from here
- `"Skill"` in `allowed_tools` → Enables skill invocation

## Skills

Skills are reusable workflow templates the agent can invoke:

| Skill | Purpose |
|-------|---------|
| `transcription-helper` | Guides transcription workflow phases |
| `kg-bootstrap` | Knowledge graph project creation flow |
| `content-saver` | Saves generated content with professional formatting |
| `error-recovery` | Structured error handling protocol |

## Adding New Skills

1. Create `skills/{skill-name}/SKILL.md`
2. Follow the skill format (see existing skills for reference)
3. Multi-file skills can include resources in subdirectories (e.g., `formats/`)
4. Skills are auto-discovered by the SDK
