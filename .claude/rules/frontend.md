---
paths: app/static/**/*.*, app/templates/**/*.*
---

# Frontend Conventions

## Stack
- Tailwind CSS via CDN (no build step)
- Vanilla JavaScript (no frameworks)
- Jinja2 templates in `app/templates/`

## Session Management
- Store session ID in `sessionStorage` (tab isolation)
- Generate UUID v4 client-side for new sessions
- Poll `/status/{id}` for agent processing state

## Security (CRITICAL)

- ALWAYS use DOMPurify for XSS sanitization on rendered content
- NEVER trust user input in DOM manipulation
- ALWAYS escape dynamic content in Jinja2: `{{ variable }}`
- NEVER use `innerHTML` with unsanitized content

## API Communication
- Use `fetch()` for all API calls
- Handle loading/error states in UI
- Show cost/usage data from response headers

## File Uploads
- Max 500MB file size
- Allowed extensions: mp4, mkv, avi, mov, webm, m4v
- Use FormData for multipart uploads
