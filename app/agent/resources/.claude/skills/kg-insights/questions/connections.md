# Connections Question

Handles questions like:
- "How is X connected to Y?"
- "What's the relationship between A and B?"
- "Show me the path from X to Y"
- "Are X and Y related?"

## Why Users Want This

Understanding connections helps users:
- **Trace Influence** - How did information or decisions flow?
- **Discover Hidden Links** - Find non-obvious relationships
- **Build Narratives** - Connect dots for storytelling or research
- **Validate Hypotheses** - Confirm suspected relationships exist

## How to Analyze

### Step 1: Identify Entities
Parse the user's question to extract:
- Source entity (who/what to start from)
- Target entity (who/what to find path to)

### Step 2: Find Paths
Use NetworkX path finding to discover:
- **Shortest Path** - Minimum hops between entities
- **All Paths** - Alternative routes (up to 5)
- **Relationship Types** - What kind of connection at each step

### Step 3: Present Visually
Show the path as a clear chain with relationship labels.

## Example Response

```markdown
## Connection: Sidney Gottlieb to Stanford University

I found a 3-step connection between these entities:

### Path Visualization

```
Sidney Gottlieb
      |
      | worked_for
      v
     CIA
      |
      | funded
      v
 MK-Ultra Subproject 39
      |
      | conducted_at
      v
Stanford University
```

### Step-by-Step Breakdown

| Step | From | Relationship | To | Evidence |
|------|------|--------------|-----|----------|
| 1 | Sidney Gottlieb | worked_for | CIA | "Gottlieb directed the program..." |
| 2 | CIA | funded | MK-Ultra Subproject 39 | "The agency allocated $25,000..." |
| 3 | MK-Ultra Subproject 39 | conducted_at | Stanford University | "Experiments took place at Stanford's..." |

### Why This Matters

This connection reveals:

- **Indirect but significant** - While Gottlieb didn't work directly at Stanford, the funding chain shows his influence extended there through CIA projects.

- **Institutional involvement** - Stanford University was a site for MK-Ultra research, connected through the funding mechanism rather than direct employment.

- **Documented trail** - Each step has evidence from your sources, making this a well-supported connection.

### Explore Further

- "What else did the CIA fund?" — See CIA's other connections
- "Who else worked on MK-Ultra Subproject 39?" — Explore collaborators
- "Show me Stanford University's network" — See all university connections
- "What evidence supports this path?" — View source citations
```

## Alternative Paths

When multiple paths exist, show them:

```markdown
### Alternative Connections

I found 2 paths between these entities:

**Path 1 (shortest - 3 steps):**
Gottlieb -> CIA -> MK-Ultra -> Stanford

**Path 2 (4 steps):**
Gottlieb -> CIA -> Navy -> Research Contract -> Stanford

The shorter path through MK-Ultra appears more direct. Would you like details on the alternative path?
```

## No Connection Found

When entities exist but aren't connected:

```markdown
## No Direct Connection Found

I couldn't find a path between **[Entity A]** and **[Entity B]** in your graph.

This could mean:
- They appear in separate contexts or topics
- The connection exists but hasn't been extracted yet
- They're genuinely unrelated in your source material

### What You Can Try

1. "What is [Entity A] connected to?" - See their network
2. "What is [Entity B] connected to?" - See their network
3. Add more transcripts that might bridge these topics
```

## Technical Implementation

1. Parse entity names from user question
2. Look up nodes by label (case-insensitive)
3. Call `find_paths(source_id, target_id, max_length=5)`
4. For each step, get relationship type from edge
5. Get evidence quotes from RelationshipDetail
6. Format as path visualization + table

## Follow-Up Suggestions (CRITICAL)

**ALWAYS end with a bullet list of quoted queries - this enables clickable cards in the UI.**

**REQUIRED FORMAT:**
```markdown
## Explore Further

- "[query in quotes]" — Description
- "[another query]" — Description
```

| Path Result | Suggest Query |
|-------------|---------------|
| Short path (1-2 steps) | `"What other connections does [entity] have?"` |
| Long path (3+ steps) | `"Are there alternative paths between these?"` |
| Multiple paths | `"Which path is most significant?"` |
| No path | `"What is [entity A] connected to?"` |
