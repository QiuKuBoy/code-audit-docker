# Authentication Bypass Audit Skill

## Overview
Authentication Bypass occurs when authentication mechanisms can be circumvented, allowing unauthorized access.

## Audit Methodology
1. **Map all auth endpoints**: login, register, password reset, token refresh
2. **Check credential verification**: Are passwords properly hashed and compared?
3. **Test bypass techniques**: default credentials, empty passwords, SQL injection in login
4. **Check session management**: token generation, expiration, invalidation

## Common Patterns

### Weak Authentication
- Plain text password storage / comparison
- `if user_input_password == stored_password` — timing attack
- Default/empty credentials: `admin/admin`, `admin/password`
- Comment-based bypass: `admin'--` in SQL login query

### JWT Issues
- `algorithm: none` accepted — no signature verification
- Hardcoded/weak secret keys
- Token not expired / no expiration check
- Sensitive data in payload (not encrypted)

### Session Issues
- Predictable session IDs
- Session fixation (no rotation after login)
- No session timeout
- Cookie without HttpOnly/Secure/SameSite

### OAuth / SSO Issues
- Redirect URI not validated
- State parameter missing (CSRF)
- Token leakage via referrer header
- Insufficient scope checking

## Checklist
- [ ] Passwords hashed with bcrypt/argon2 (not MD5/SHA1)?
- [ ] Constant-time comparison for passwords?
- [ ] Rate limiting on login?
- [ ] Account lockout after N failed attempts?
- [ ] Session token rotated after login?
- [ ] JWT algorithm restricted (not none)?
- [ ] HTTPS enforced for auth endpoints?
