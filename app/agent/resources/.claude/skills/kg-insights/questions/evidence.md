# Evidence Question

Handles questions like:
- "Where is X mentioned?"
- "What sources talk about Y?"
- "Show me evidence for this relationship"
- "Where did you get this information?"
- "Cite your sources for X"

## Why Users Want This

Evidence tracing helps users:
- **Verify Claims** - Confirm extracted information is accurate
- **Find Original Context** - Read the full passage for nuance
- **Build Citations** - Reference sources in their own work
- **Assess Confidence** - Understand extraction reliability

## How to Analyze

### Step 1: Identify What Needs Evidence
Parse user question for:
- Entity name (where is X mentioned?)
- Relationship type (evidence for X worked at Y)
- General claim (sources about topic)

### Step 2: Trace to Sources
For each entity or relationship:
- Get source_ids from the Node or RelationshipDetail
- Look up Source objects for metadata
- Retrieve evidence quotes if available

### Step 3: Present with Confidence
Show sources with:
- Title/filename
- Confidence score
- Direct quotes
- Timestamp if available

## Example Response

```markdown
## Evidence for "Sidney Gottlieb worked for CIA"

I found this relationship mentioned in 3 sources:

### Source Citations

| Source | Confidence | Quote |
|--------|------------|-------|
| MK-Ultra Documentary Transcript | 95% | "Sidney Gottlieb, who directed the CIA's MK-Ultra program from 1953 to 1973..." |
| Congressional Testimony (1977) | 98% | "Dr. Gottlieb served as Chief of the Technical Services Staff, a division of the Central Intelligence Agency..." |
| Cold War Research Overview | 87% | "The Agency's chief scientist, Gottlieb, oversaw a vast network of experiments..." |

### Evidence Details

**Primary Source: Congressional Testimony (1977)**
```
"Dr. Gottlieb served as Chief of the Technical Services Staff,
a division of the Central Intelligence Agency, where he
supervised the development of poisons, drug experiments,
and mind control research programs."
```
*Confidence: 98%* - Direct testimony with specific role title.

**Supporting Source: MK-Ultra Documentary**
```
"Sidney Gottlieb, who directed the CIA's MK-Ultra program
from 1953 to 1973, was known within the agency as the
'Black Sorcerer' for his work on chemical interrogation methods."
```
*Confidence: 95%* - Documentary corroborates with dates and nickname.

### Why This Matters

This relationship is well-supported because:

- **Multiple sources** - Mentioned across 3 different transcripts
- **High confidence** - Average confidence of 93%
- **Specific details** - Sources include dates, titles, and context
- **Official record** - Congressional testimony provides authoritative confirmation

### Confidence Levels Explained

| Level | Range | Meaning |
|-------|-------|---------|
| High | 90-100% | Explicit statement, easy to verify |
| Medium | 70-89% | Implied or contextual reference |
| Low | 50-69% | Inferred from related information |

### Explore Further

- "What else is in Congressional Testimony?" — See all entities from this source
- "Show me MK-Ultra's connections" — Explore the program's network
- "What low-confidence relationships exist?" — Find items to verify
- "Who are the key players?" — See most important entities
```

## Entity Evidence (Where Is X Mentioned?)

```markdown
## Sources Mentioning "Dr. Ewen Cameron"

This entity appears in 4 sources:

| Source | Mentions | Context |
|--------|----------|---------|
| McGill Experiments | 12 | Primary subject of documentary |
| Congressional Testimony | 3 | Referenced in questioning |
| Sleep Room Documentary | 8 | Featured in historical narrative |
| Academic Paper Review | 2 | Cited in research overview |

### Key Quotes by Source

**McGill Experiments:**
> "Dr. Ewen Cameron, head of the Allan Memorial Institute, developed what he called 'psychic driving' - a technique involving repeated audio messages..."

**Congressional Testimony:**
> "The committee heard testimony regarding experiments conducted by Dr. Cameron at McGill University..."

### Explore Further

- "Show me Dr. Ewen Cameron's connections" — See full network
- "How is Dr. Cameron connected to CIA?" — Trace the path
- "What topic clusters exist?" — See how entities group
```

## Low Confidence Warnings

When confidence is low:

```markdown
**Note:** This relationship has lower confidence (68%).

The extraction was based on contextual inference rather than explicit statement:
> "The research team, including scientists from the university, worked on classified projects..."

Consider verifying in the original source or adding more transcripts that explicitly confirm this connection.
```

## Technical Implementation

1. Parse entity/relationship from question
2. For entities: Get node, retrieve segment_ids and source references
3. For relationships: Get edge, get RelationshipDetail.evidence
4. Look up Source objects for metadata
5. Calculate average confidence if multiple sources
6. Format with quotes and confidence scores

## Handling Missing Evidence

```markdown
## Evidence Not Available

I don't have source evidence stored for this information.

This can happen when:
- The entity was extracted without quote capture
- Evidence was trimmed during processing
- The relationship is inferred rather than stated

### What You Can Try

1. "Show me sources about [entity]" - Find where they appear
2. Use `get_transcript` to read the original source
3. Re-extract with enhanced evidence capture
```

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
| High confidence | `"What else is mentioned in [source]?"` |
| Low confidence | `"Find additional sources about [entity]"` |
| Single source | `"Are there other sources that mention [entity]?"` |
| Multiple sources | `"Which source has the most detail about [entity]?"` |
