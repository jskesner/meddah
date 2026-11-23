# Security Policy

## Supported Versions

During pre-1.0 development (`v0.x.0`), security fixes are applied directly to the `main` trunk branch and the latest tagged minor milestone.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.**

If you discover a security issue—especially involving:
- **AST formula / ruleset sandbox escapes**
- **Zip-slip or archive extraction vulnerabilities** in `.rpgrules` / `.rpgworld` / `.rpgcampaign` / `.rpgcharacter` ingestion
- **SSRF or anti-DDoS bypasses** in `url_ingestor.py`
- **Multiplayer Fog-of-War leaks, RBAC privilege escalation, or `MEDDAH_ADMIN_TOKEN` handling**
- **Electron renderer isolation / CSP bypasses**

Please use GitHub's **Private Vulnerability Reporting** ("Security" tab $\rightarrow$ "Report a vulnerability" on the repository) so the issue can be investigated and patched before public disclosure.
