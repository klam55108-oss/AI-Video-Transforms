# Key Players Question

Handles questions like:
- "Who are the key players?"
- "What are the most important entities?"
- "Who appears most often?"
- "Show me the main people/organizations"

## Why Users Want This

When building a Knowledge Graph from multiple sources, users want to:
- **Focus Research** - Know where to dig deeper first
- **Identify Patterns** - See who or what keeps coming up
- **Find Entry Points** - Start exploring from well-connected entities
- **Validate Coverage** - Confirm their sources cover expected topics

## How to Analyze

### Step 1: Get Graph Statistics
Use `get_kg_stats` to retrieve:
- Entity counts by type
- Relationship counts by type
- Source distribution

### Step 2: Rank by Connections
Entities are "key players" based on:

| Method | What It Measures | Plain Language |
|--------|------------------|----------------|
| **Connection Count** | Number of relationships | "Most connected" |
| **Source Appearances** | How many sources mention them | "Most referenced" |
| **Bridge Score** | Connects otherwise separate groups | "Links different topics" |

### Step 3: Present Results

## Example Response

```markdown
## Key Players in Your Graph

I analyzed your Knowledge Graph and found the most influential entities:

### By Connections (Most Well-Connected)

| Entity | Type | Connections | Role |
|--------|------|-------------|------|
| Sidney Gottlieb | Person | 15 | Central figure with ties to multiple organizations |
| CIA | Organization | 12 | Connected to many individuals and projects |
| MK-Ultra | Project | 9 | Hub linking researchers and institutions |

### By Source Coverage (Most Referenced)

| Entity | Type | Sources | Notes |
|--------|------|---------|-------|
| Sidney Gottlieb | Person | 4/5 | Appears in 80% of your transcripts |
| Operation Midnight Climax | Event | 3/5 | Referenced in 60% of sources |

### Why This Matters

These findings suggest:

- **Sidney Gottlieb** is a central figure worth investigating further. Their high connection count means they link many other entities together.

- **CIA** as an organization serves as a hub, connecting people, projects, and events. Exploring its edges will reveal the network structure.

- **MK-Ultra** appears to be a key project that ties together multiple researchers and institutions mentioned across your sources.

### Explore Further

- "Show me Sidney Gottlieb's connections" — See their full network
- "How is CIA connected to MK-Ultra?" — Trace the relationship
- "What sources mention Sidney Gottlieb?" — Find evidence
- "What topic clusters exist?" — Discover groupings
```

## Follow-Up Suggestions (CRITICAL)

**ALWAYS end with a bullet list of quoted queries - this enables clickable cards in the UI.**

The frontend parses these and creates interactive suggestion buttons.

**REQUIRED FORMAT:**
```markdown
## Explore Further

- "[query in quotes]" — Description
- "[another query]" — Description
```

| If User Seems... | Suggest Query |
|------------------|---------------|
| Interested in a person | `"Show me [name]'s connections"` |
| Curious about connections | `"How is [A] connected to [B]?"` |
| Wanting more context | `"What sources mention [entity]?"` |
| Looking for patterns | `"What topic clusters exist?"` |

## Technical Implementation

When the agent receives a key players question:

1. Call `get_kg_stats` with `project_id`
2. Parse entity type breakdown
3. For top entities, get connection counts from graph
4. Format as ranked table
5. Add "Why This Matters" explanation
6. Include 2-3 follow-up questions using actual entity names from the graph

## Handling Edge Cases

| Case | Response |
|------|----------|
| Only 1-2 entities | "Your graph is still small. Add more transcripts to find patterns." |
| All entities equal | "No single entity dominates - your topics are evenly distributed." |
| One type dominates | "Your graph is heavy on [type]. Consider sources with more [other types]." |
