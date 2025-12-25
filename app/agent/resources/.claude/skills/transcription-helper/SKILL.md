---
name: transcription-helper
description: Guides users through video transcription workflow from input to output. Transcribes local video files and YouTube URLs using gpt-4o-transcribe. Use when users want to transcribe videos, audio files, YouTube content, or need help with media-to-text conversion.
---

# Transcription Helper

## Workflow Phases

### Phase 1: Gathering Input
1. Greet briefly and ask for:
   - Video source (local file or YouTube URL)
   - Language (optional — auto-detection available)
   - Domain vocabulary (optional — improves accuracy)
2. Keep it concise. Don't overwhelm with options.

### Phase 2: User Confirmation
ONLY proceed after explicit confirmation ("yes", "proceed", "confirm", "go ahead"):
- If changes requested → return to Phase 1
- If confirmed → proceed to Phase 3

### Phase 3: Transcription
1. Use `transcribe_video` with:
   - `video_source`: File path or YouTube URL
   - `language`: ISO 639-1 code if known (e.g., 'en', 'es', 'zh')
   - `temperature`: 0.0 for consistent results
   - `prompt`: Domain vocabulary if provided
2. Validate results (check for text content, note any splitting)
3. **IMMEDIATELY** use `save_transcript` to:
   - Persist the transcription
   - Get transcript ID for reference
   - Free up context memory

### Phase 4: Results & Follow-up
After successful transcription:
1. Report completion and share transcript ID
2. Show preview (~200 characters)
3. Share metadata (source type, length, splitting info)
4. Present 5 options:

| Option | Description |
|--------|-------------|
| 1. Summarize | Create concise summary with key points |
| 2. Extract Key Points | List main topics and actionable items |
| 3. Show Full | Display complete transcription |
| 4. Save Derived Content | Save summary/notes using `content-saver` skill |
| 5. Build Knowledge Graph | Extract entities and relationships (recommended for rich content) |

Ask: "What would you like me to do with this transcription? Choose 1-5, or describe something else."

**Option 4 Flow:** When user selects "Save Derived Content":
1. First generate the content to save (summary, notes, key points)
2. Invoke `content-saver` skill for format selection
3. The skill handles format templates, filename suggestions, and file saving

## Error Recovery

| Error Type | Troubleshooting |
|------------|-----------------|
| YouTube errors | Check URL validity, video availability, age restrictions |
| File errors | Verify path exists and is valid video format |
| FFmpeg errors | Ensure FFmpeg is installed |
| API errors | Check OPENAI_API_KEY is set correctly |
| Timeout errors | Video may be too long; suggest splitting |
