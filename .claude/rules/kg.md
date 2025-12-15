---
paths: app/kg/**/*.py, app/services/kg_service.py
---

# Knowledge Graph Patterns

## Module Structure

| File | Purpose |
|------|---------|
| `domain.py` | Bootstrap/project models (ThingType, DomainProfile, KGProject) |
| `models.py` | Graph storage models (Node, Edge, Source, RelationshipDetail) |
| `schemas.py` | Claude extraction output schemas (ExtractedEntity, ExtractionResult) |
| `knowledge_base.py` | NetworkX graph wrapper with query methods |
| `persistence.py` | JSON/GraphML serialization |
| `tools/bootstrap.py` | Domain inference from first video |
| `tools/extraction.py` | Entity/relationship extraction |
| `prompts/` | Bootstrap and extraction prompt templates |

## Domain Models (domain.py)

### Bootstrap Phase
```python
ThingType      # Entity categories (Person, Organization, etc.)
ConnectionType # Relationship types (worked_for, funded_by, etc.)
SeedEntity     # Key entities for naming consistency
DomainProfile  # Auto-inferred domain configuration
```

### Project Lifecycle
```python
ProjectState   # CREATED → BOOTSTRAPPING → ACTIVE → STABLE
KGProject      # User-facing research project wrapper
Discovery      # New findings awaiting user confirmation
DiscoveryStatus # PENDING → CONFIRMED/REJECTED
```

## Storage Models (models.py)

```python
Node           # Graph node with type, properties
Edge           # Graph edge with relationship type
Source         # Video/transcript source tracking
RelationshipDetail # Rich relationship metadata
```

## Extraction Schemas (schemas.py)

```python
ExtractedEntity      # Claude extraction output for entities
ExtractedRelationship # Claude extraction output for relationships
ExtractionResult     # Combined extraction response
```

## KnowledgeBase (knowledge_base.py)

NetworkX-based graph storage:

```python
kb = KnowledgeBase()

# Add nodes/edges
kb.add_node(node)
kb.add_edge(edge)

# Query
kb.get_node(node_id)
kb.get_neighbors(node_id)
kb.get_nodes_by_type("Person")

# Export
kb.to_graphml()
kb.to_json()
```

## Service Pattern (kg_service.py)

```python
class KnowledgeGraphService:
    def __init__(self, data_path: Path):
        self.data_path = data_path

    async def create_project(self, name: str) -> KGProject
    async def bootstrap_project(self, project_id: str, transcript: str, ...) -> DomainProfile
    async def extract_knowledge(self, project_id: str, transcript: str, ...) -> ExtractionResult
    async def get_project(self, project_id: str) -> KGProject | None
```

## Bootstrap Workflow

1. **Create Project** — `POST /kg/projects`
2. **Bootstrap** — First transcript triggers domain inference
3. **Preview** — Show discovered types/entities
4. **Confirm** — User approves/rejects discoveries
5. **Active** — Subsequent transcripts use confirmed schema

## Critical Rules

- ALWAYS use DomainProfile for extraction context
- NEVER extract without a bootstrapped domain
- ALWAYS validate project state before operations
- NEVER store raw API responses — use Pydantic models

## Extraction Prompts

Located in `app/kg/prompts/`:

```python
# Bootstrap prompt - infer domain from first video
BOOTSTRAP_PROMPT = """Analyze this transcript and identify:
- Entity types to extract
- Relationship types to track
- Key entities for naming consistency
..."""

# Extraction prompt - use domain profile for consistency
EXTRACTION_PROMPT = """Extract entities and relationships
using the following domain profile:
{domain_profile}
..."""
```

## Testing

- Domain models: `test_kg_domain.py`
- Knowledge base: `test_kg_knowledge_base.py`
- Service: `test_kg_service.py`, `test_kg_service_extraction.py`
- Tools: `test_kg_tools.py`, `test_kg_extraction_tool.py`
- API: `test_kg_api.py`, `test_kg_api_extraction.py`
- E2E: `test_kg_e2e_flow.py`
