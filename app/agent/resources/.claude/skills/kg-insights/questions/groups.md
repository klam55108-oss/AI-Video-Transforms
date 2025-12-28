# Groups & Clusters Question

Handles questions like:
- "What topic groups exist?"
- "How is my graph organized?"
- "What are the main themes?"
- "Show me clusters"
- "What topics are covered?"

## Why Users Want This

Understanding clusters helps users:
- **See the Big Picture** - Understand overall structure at a glance
- **Find Research Gaps** - Spot under-explored areas
- **Organize Findings** - Group related entities for reporting
- **Discover Themes** - See emergent patterns across sources

## How to Analyze

### Step 1: Group by Entity Type
Start with natural groupings from the domain profile:
- People
- Organizations
- Events
- Concepts
- Locations

### Step 2: Identify Dense Connections
Find entities that are heavily connected to each other:
- Count internal vs external connections
- Entities with mostly internal links = core of a cluster
- Entities with many external links = bridges between clusters

### Step 3: Label Clusters
Name clusters based on:
- Common entity types
- Shared relationships
- Source context

## Example Response

```markdown
## Topic Clusters in Your Graph

I analyzed your Knowledge Graph and found 3 distinct topic groups:

### Cluster Overview

| Cluster | Entities | Key Members | Bridging Entities |
|---------|----------|-------------|-------------------|
| Government Programs | 18 | CIA, MK-Ultra, MKULTRA Subprojects | Sidney Gottlieb |
| Academic Research | 12 | Stanford, McGill, Researchers | Harold Wolff |
| Pharmaceutical Industry | 7 | Eli Lilly, Sandoz, LSD | Albert Hofmann |

### Cluster 1: Government Programs (18 entities)

**Core Members:**
- CIA (Organization)
- MK-Ultra (Project)
- MKULTRA Subproject 68 (Project)
- Operation Midnight Climax (Event)

**Theme:** Covert intelligence programs and their subprojects.

**Internal Connections:** 24 relationships
**External Connections:** 8 relationships (links to Academic Research)

### Cluster 2: Academic Research (12 entities)

**Core Members:**
- Stanford University (Organization)
- McGill University (Organization)
- Dr. Ewen Cameron (Person)
- Harold Wolff (Person)

**Theme:** Universities and researchers involved in funded studies.

**Internal Connections:** 15 relationships
**External Connections:** 11 relationships (links to Government Programs and Pharma)

### Cluster 3: Pharmaceutical Industry (7 entities)

**Core Members:**
- Eli Lilly (Organization)
- Sandoz Laboratories (Organization)
- LSD (Substance)
- Albert Hofmann (Person)

**Theme:** Drug manufacturers and their products used in experiments.

**Internal Connections:** 8 relationships
**External Connections:** 6 relationships

### Bridge Entities

These entities connect multiple clusters:

| Entity | Clusters Connected | Role |
|--------|-------------------|------|
| Sidney Gottlieb | Gov + Academic | Directed programs, worked with universities |
| Harold Wolff | Academic + Gov | Researcher with CIA consulting role |
| LSD | Pharma + Gov + Academic | Substance used across all contexts |

### Why This Matters

This clustering reveals:

- **Three distinct spheres** - Your research covers government, academia, and industry, with clear connections between them.

- **Central bridge figures** - Gottlieb and Wolff appear in multiple contexts, making them key to understanding cross-sector relationships.

- **LSD as connector** - The substance appears across all clusters, suggesting it's the central subject linking these groups.

### Explore Further

- "Who are the key players in Government Programs?" — See top entities in cluster
- "How is Sidney Gottlieb connected to Harold Wolff?" — Explore bridge connections
- "What sources cover Pharmaceutical Industry?" — Find evidence
- "Show me LSD's connections" — Explore the central connector
```

## Handling Different Graph Sizes

### Small Graph (< 20 entities)
```markdown
Your graph has [N] entities - still growing! Here's how they group:

**By Type:**
- [N] People
- [N] Organizations
- [N] Events

As you add more transcripts, I'll be able to identify topic clusters and bridging entities.
```

### Medium Graph (20-50 entities)
Show 2-3 clusters with basic stats.

### Large Graph (50+ entities)
Show full cluster analysis with bridge entities and cross-cluster connections.

## Technical Implementation

1. Get all nodes from graph
2. Group by entity_type as initial clusters
3. For each node, count connections to same-type vs different-type
4. Identify bridge entities (high external connection ratio)
5. Calculate cluster density (internal connections / possible connections)
6. Name clusters based on common properties
7. Present with visualization and stats

## Follow-Up Suggestions (CRITICAL)

**ALWAYS end with a bullet list of quoted queries - this enables clickable cards in the UI.**

**REQUIRED FORMAT:**
```markdown
## Explore Further

- "[query in quotes]" — Description
- "[another query]" — Description
```

| Finding | Suggest Query |
|---------|---------------|
| Clear clusters | `"Who are the key players in [cluster name]?"` |
| Strong bridges | `"How is [bridge entity] connected to both groups?"` |
| Isolated cluster | `"What sources cover [cluster name]?"` |
| Sparse connections | `"Show me the most connected entities"` |
