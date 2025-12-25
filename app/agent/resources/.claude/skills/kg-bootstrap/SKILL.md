---
name: kg-bootstrap
description: Creates and bootstraps Knowledge Graph projects from video transcripts. Extracts entities (people, organizations, concepts) and relationships into searchable graphs. Use when users want to build a knowledge graph, extract entities, analyze connections between people/organizations, or select Option 5 after transcription.
---

# Knowledge Graph Bootstrap

## Step-by-Step Workflow

### Step 1: Check Existing Projects
Use `list_kg_projects` first:
- If projects exist → Ask: "Would you like to add to an existing project or create a new one?"
- If no projects → Proceed to Step 2

### Step 2: Create New Project (if needed)
Ask for a project name describing the research domain:
> "What would you like to call this Knowledge Graph project?"
> Examples: 'Tech Industry Interviews', 'Climate Research', 'Company History'

Use `create_kg_project` and report the project ID.

### Step 3: Bootstrap Domain Profile
**This is where the magic happens:**

Explain: "I'll analyze your transcript to discover entity types (people, organizations, concepts) and relationships."

Use `bootstrap_kg_project` with:
- `project_id`: The newly created ID
- `transcript`: Full transcript text (use `get_transcript` if needed)
- `title`: Video/source title

### Step 4: Present Bootstrap Results
Format results conversationally:

```
## Knowledge Graph Bootstrap Complete!

**Project:** [Name]
**Confidence:** [X]%

### Entity Types Discovered ([N])
- **Person**: Individuals mentioned
- **Company**: Organizations, startups
- [etc.]

### Relationship Types ([N])
- **works_at**: Employment relationships
- **founded**: Company founding
- [etc.]

### Key Entities Found ([N])
- [Entity Name] ([Type])
- [etc.]

Your Knowledge Graph is ready! Would you like me to:
1. Extract entities from another transcript
2. View current graph statistics
3. Export the graph data
```

### Step 5: Continue Building
For subsequent transcripts on a bootstrapped project:
- Use `extract_to_kg` directly (no re-bootstrap needed)
- Show what was added vs. what already existed
- Offer to continue with more transcripts

## Critical Rules

- A project MUST be bootstrapped before extraction
- Bootstrap happens ONCE per project (first transcript only)
- Always show progress in chat — user shouldn't need to check sidebar
- The sidebar syncs automatically, but chat is the primary interface
