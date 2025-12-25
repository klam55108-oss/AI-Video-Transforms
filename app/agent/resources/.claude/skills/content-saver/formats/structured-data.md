# Structured Data Format

JSON format for programmatic access and integration.

## Structure

```json
{
  "metadata": {
    "title": "{Title}",
    "source": "{source reference}",
    "date_created": "{YYYY-MM-DD}",
    "content_type": "{summary|notes|key_points|analysis}",
    "source_type": "{video|audio|youtube}"
  },
  "content": {
    "summary": "{Brief summary paragraph}",
    "key_points": [
      "{Point 1}",
      "{Point 2}",
      "{Point 3}"
    ],
    "sections": [
      {
        "title": "{Section title}",
        "content": "{Section content}",
        "timestamp": "{HH:MM:SS if applicable}"
      }
    ],
    "quotes": [
      {
        "text": "{Quote text}",
        "speaker": "{Speaker if known}",
        "timestamp": "{HH:MM:SS if applicable}"
      }
    ],
    "action_items": [
      {
        "task": "{Task description}",
        "priority": "{high|medium|low}",
        "status": "pending"
      }
    ]
  },
  "relationships": {
    "transcript_id": "{8-char ID if available}",
    "kg_project_id": "{project ID if available}"
  }
}
```

## Best Used For

- API integrations
- Database storage
- Further processing
- Data pipelines

## File Extension

`.json`

## Filename Pattern

`{source}_structured_{YYYYMMDD}.json`

## Notes

- Ensure valid JSON (proper escaping of special characters)
- Include null for missing optional fields
- Timestamps in HH:MM:SS format
- ISO 8601 dates (YYYY-MM-DD)
