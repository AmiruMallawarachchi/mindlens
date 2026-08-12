# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| v1.0.x | ✅ |

## Reporting a Vulnerability

**MindLens handles sensitive mental health data. Security is our highest priority.**

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** open a public GitHub issue
2. Email: amirunoel8@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if any)

**Response Timeline:**
- Acknowledgment within 24 hours
- Initial assessment within 72 hours
- Fix timeline communicated within 1 week
- Public disclosure coordinated after fix deployment

## Security Measures

### Authentication
- JWT access tokens (15-min expiry, HS256)
- Refresh tokens in httpOnly Secure cookies
- bcrypt password hashing (rounds=12)
- Rate limiting: 5 failed logins → 15-min lockout

### Data Protection
- PII stripped before every model call
- AES-256 encryption at rest (MongoDB Atlas)
- Fernet encryption for sensitive fields (Spotify tokens)
- HTTPS everywhere + WSS for WebSocket

### Input Security
- Pydantic validation at every API boundary
- Message length cap (2000 chars)
- Prompt injection detection
- Content policy enforcement
- XSS prevention (CSP headers)

### Crisis Safety
- 3-layer crisis detection (Regex + DistilBERT + FAISS)
- Threshold: 0.45 (maximize recall)
- ZERO LLM in crisis response (templates only)
- Sri Lankan resources: NIMH 1926, Sumithrayo +94 11 2696666

## Security Checklist for Contributors

- [ ] No secrets in code (use .env)
- [ ] No hardcoded API keys
- [ ] User input never interpolated into system prompts
- [ ] All MongoDB queries filter by user_id from JWT
- [ ] Rate limiting considered for new endpoints
- [ ] PII handling reviewed for new features