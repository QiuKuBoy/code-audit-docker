# Info Disclosure / Sensitive Data Leak Audit Skill

## Overview
Sensitive information exposure: debug endpoints, stack traces, verbose errors, config exposure, PII leakage, directory listing.

## Audit Methodology
1. Find debug/admin endpoints: /debug, /actuator, /health, /status, phpinfo, error_reporting(E_ALL)
2. Check error handling: stack traces / SQL errors / internal paths returned to client
3. Check config exposure: .env served, config.js with secrets, backup files (.bak, .swp, .old)
4. Check API responses: over-fetching (password hashes, tokens, internal fields returned)
5. Check logs: sensitive data written to accessible logs

## Common Vulnerable Patterns
- `Actuator /health` or `/env` unauthenticated (Spring)
- `error_reporting(E_ALL)` + display_errors=On in production
- SQL error message returned to client (`SQL错误: ...`)
- `config.js` / `config.json` with API keys served statically
- Backup files: `config.php.bak`, `.git` directory exposed, `.env` accessible
- API returns full DB rows including password fields
- `phpinfo()` / `/server-status` public

## Key Reminders
- Display errors only in dev; log errors server-side
- Never return internal paths / SQL / stack traces to clients
- Verify `.env`, `.git`, backups are blocked by web server config
- API responses: field-level allowlist, never `SELECT *` to client
- Check for sensitive data in client-side JS bundles

## Checklist
- [ ] Debug endpoints (actuator, debug, status) not exposed / authenticated?
- [ ] Error messages don't leak internals (paths, SQL, stack)?
- [ ] `.env` / `.git` / backups not web-accessible?
- [ ] API responses field-allowlisted (no password/hash/token fields)?
- [ ] No secrets in frontend bundle / static JS?
