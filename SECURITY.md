# Security Policy

## Important Disclaimer

> **This code is NOT ready for production deployment.**
>
> CognivAgent is designed for local development and research use only.
> Deploying this application on public infrastructure requires serious security analysis.
>
> **Strong recommendation: Only run on localhost for development and research.**

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **DO NOT** open a public GitHub issue for security vulnerabilities
2. **Email**: Report via [GitHub Security Advisories](https://github.com/costiash/agent-video-to-data/security/advisories/new)
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Target**: Within 30 days for critical issues

## Security Measures

CognivAgent implements several security controls:

### Path Validation
- System paths are blocked: `/etc`, `/usr`, `/bin`, `/sbin`, `/var`, `/boot`, `/sys`, `/proc`, `/dev`
- Path traversal attacks prevented via `Path.resolve()`
- Hidden files restricted by default

### Input Validation
- All API inputs validated via Pydantic models
- UUID v4 format enforced for IDs
- File uploads limited to 500MB with extension whitelist

### XSS Protection
- All user content sanitized via DOMPurify
- Jinja2 auto-escaping enabled
- No `innerHTML` with unsanitized content

### Audit Trail
- Pre/post tool execution logging
- Dangerous operation detection and blocking
- API key patterns redacted from logs

See `app/core/hooks.py` for audit hook implementation details.

### Dangerous Operation Blocking

The following patterns are blocked:
- `rm -rf /` and variants
- `dd if=` (disk operations)
- Fork bombs
- `mkfs.` (filesystem formatting)
- `chmod -R 777 /`
- Pipe-to-shell patterns

## Known Limitations

1. **No Authentication**: The application has no built-in authentication. Anyone with network access can use it.

2. **Session Management**: Sessions are stored locally without encryption.

3. **API Keys**: While API keys are loaded from environment variables (not hardcoded), they could be exposed via:
   - Process listings
   - Debug logs (if enabled)
   - Memory dumps

4. **File Access**: The agent can read/write files within its working directory. Sandboxing is not enforced at the OS level.

5. **External API Calls**: The application makes calls to:
   - Anthropic API (Claude)
   - OpenAI API (gpt-4o-transcribe)
   - YouTube (for video downloads)

## Security Best Practices

When running CognivAgent:

1. **Run locally only** - Do not expose to the internet
2. **Use environment variables** - Never hardcode API keys
3. **Limit file access** - Run in a dedicated directory
4. **Monitor logs** - Watch for suspicious activity
5. **Keep updated** - Apply security patches promptly

## Security Updates

Security updates will be announced via:
- GitHub Security Advisories
- Release notes in CHANGELOG.md

## Contact

For security-related questions that aren't vulnerabilities, open a regular GitHub issue with the `security` label.
