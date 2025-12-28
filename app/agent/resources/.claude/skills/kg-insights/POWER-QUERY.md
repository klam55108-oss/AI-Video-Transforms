# Power Query: Smart Suggestions

When users ask "What can I do with this graph?" or seem unsure how to proceed, provide personalized suggestions based on their graph's actual content.

## Trigger Phrases

Invoke this when user says:
- "What can I do with this graph?"
- "What questions can I ask?"
- "Help me explore this"
- "What's possible?"
- "I don't know what to ask"
- "What now?"
- "Show me what I can do"

## How to Generate Suggestions

### Step 1: Analyze the Graph
Use `get_kg_stats` to understand:
- Total entities and relationships
- Entity type distribution
- Relationship type distribution
- Number of sources

### Step 2: Identify Interesting Features

| Feature | Threshold | What It Means |
|---------|-----------|---------------|
| Entity type dominance | >40% one type | Graph has a primary focus |
| High connections | >5 per entity | Densely connected network |
| Multiple sources | >3 sources | Good cross-referencing potential |
| Bridge potential | Mixed types | Can find cross-domain connections |

### Step 3: Generate Personalized Suggestions

Create 3-5 suggestions based on actual graph content:

## Example Response

```markdown
## What You Can Explore

Based on your Knowledge Graph with **47 entities** and **62 relationships**, here are some interesting questions:

### Quick Discoveries

| Suggestion | Why It's Interesting |
|------------|---------------------|
| "Who are the key players?" | Your graph has 5 entities with 8+ connections - find out who they are |
| "How is Sidney Gottlieb connected to Stanford?" | These appear in separate sources - find the hidden link |
| "What topic groups exist?" | You have 3 entity types that might form natural clusters |

### Based on Your Data

**You have 15 People and 8 Organizations** - Try asking:
> "Which people are connected to multiple organizations?"

**Your most-connected entity is 'CIA' (12 connections)** - Explore with:
> "Show me everything connected to the CIA"

**You have 4 sources feeding this graph** - Cross-reference with:
> "What entities appear in multiple sources?"

### Power Queries

These require more analysis but yield deep insights:

1. **Connection Mapping**
   > "Draw the path from [Person A] to [Person B]"

2. **Cluster Analysis**
   > "What bridges the different topic groups?"

3. **Evidence Review**
   > "Which relationships have the highest confidence?"

### What Would You Like to Know?

Pick a suggestion above, or ask your own question! I can analyze:
- **Who** - Key players, people, organizations
- **How** - Connections, paths, relationships
- **What** - Groups, themes, topics
- **Where** - Sources, evidence, citations
```

## Suggestion Templates

### For Small Graphs (< 15 entities)
```markdown
Your graph is just getting started! Here's what you can do:

1. **See your entities** - "List all entities in my graph"
2. **Check connections** - "What relationships exist?"
3. **Add more data** - "Extract from another transcript"

As your graph grows, I'll be able to find patterns, clusters, and hidden connections!
```

### For Medium Graphs (15-50 entities)
```markdown
Your graph has [N] entities - enough to find interesting patterns!

**Try These:**
- "Who are the key players?" (your most-connected entities)
- "How is [Entity A] connected to [Entity B]?"
- "What topic groups exist?"
```

### For Large Graphs (50+ entities)
```markdown
With [N] entities, your graph has rich analysis potential!

**Recommended Explorations:**
1. **Network Analysis** - "Show me the most influential entities"
2. **Path Discovery** - "Find connections between [A] and [B]"
3. **Cluster Mapping** - "What are the main topic clusters?"
4. **Cross-Reference** - "Which entities appear in all sources?"
5. **Evidence Audit** - "Show low-confidence relationships to review"
```

### For Type-Heavy Graphs
If one entity type dominates:
```markdown
Your graph is **[Type]-heavy** ([N]% are [Type]).

**[Type]-Specific Questions:**
- "Which [Type] has the most connections?"
- "How do different [Type]s relate to each other?"
- "What other types connect to [Type]?"

Consider adding sources that cover more [other types] for balance.
```

## Dynamic Entity Insertion

Always use real entity names from the graph:

```python
# Instead of generic placeholders
"How is X connected to Y?"

# Use actual entities
"How is Sidney Gottlieb connected to McGill University?"
```

This makes suggestions immediately actionable.

## Follow-Up After Suggestion

After user picks a suggestion:

1. Answer their question fully
2. End with: "What else would you like to explore?"
3. Offer 2 related follow-ups based on the answer

## Technical Implementation

1. Call `get_kg_stats` with project_id
2. Parse entity counts and relationship types
3. Identify top entities by connection count
4. Select 3-5 suggestion templates based on graph profile
5. Insert real entity names into templates
6. Present as actionable cards
