---
name: error-recovery
description: Provides structured error handling protocol for all agent operations. Ensures users receive clear error reports, troubleshooting guidance, and actionable next steps. Use when any tool operation fails, encounters an error, or produces unexpected results.
---

# Error Recovery

## On Failure Protocol

1. **STOP IMMEDIATELY** — Do not continue with other actions
2. **REPORT CLEARLY** — Explain what went wrong concisely
3. **OFFER NEXT STEPS** — Provide specific troubleshooting or retry options
4. **WAIT FOR RESPONSE** — Do NOT proceed autonomously

## Error Response Template

```
[Operation] Failed

[Brief explanation of what went wrong]

This can happen when:
- [Possible cause 1]
- [Possible cause 2]

**Would you like to:**
1. [Retry option]
2. [Alternative option]
3. Cancel and return to main menu

Please let me know how you'd like to proceed.
```

## Common Error Patterns

| Category | Error | Troubleshooting |
|----------|-------|-----------------|
| Transcription | YouTube URL invalid | Check URL format and video availability |
| Transcription | File not found | Verify file path exists |
| Transcription | FFmpeg missing | Install FFmpeg (apt install ffmpeg) |
| Transcription | API key missing | Set OPENAI_API_KEY environment variable |
| Transcription | Timeout | Video too long; suggest splitting |
| KG | Bootstrap failed | Transcript may be too short or lack entities |
| KG | Extraction failed | Project may not be bootstrapped yet |
| KG | Project not found | Check project ID validity |

## NEVER Do

- Try to work around failures without user consent
- Make assumptions about what went wrong
- Proceed with alternative approaches autonomously
- Leave the user stuck without a path forward

This saves time and money by avoiding unnecessary API calls when something has already failed.
