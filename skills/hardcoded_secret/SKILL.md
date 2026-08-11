# Hardcoded Secret / Credential Leak Audit Skill

## Overview
Hardcoded credentials (API keys, passwords, tokens, private keys) in source code, config files, or frontend assets.

## Audit Methodology
1. Search for key/secret/password/token assignments across all files (including non-source: .env, config, JS)
2. Check config files committed to repo with real values (not placeholders)
3. Check frontend JS/bundles for cloud credentials (OSS/S3 access keys, Firebase keys)
4. Check for private keys (BEGIN PRIVATE KEY, BEGIN RSA PRIVATE KEY)
5. Verify secret rotation: leaked keys should be revoked

## Search Patterns
- `accessKeyId`, `accessKeySecret`, `secret_key`, `api_key`, `apikey`, `client_secret`
- `password =`, `passwd`, `pwd =`, `db_password`
- `token =`, `auth_token`, `Bearer `, `private_key`
- `-----BEGIN` (private keys)
- AK/SK patterns: `AKIA[0-9A-Z]{16}` (AWS), `AK_...`, `SK_...`

## Key Reminders
- A hardcoded secret is only a finding if it appears to be a REAL value (not placeholder "xxx" / "your_key_here")
- Check whether the file is web-accessible (static JS) — that escalates severity
- Check .git history for removed-but-committed secrets
- Default passwords in code (admin/admin) also count

## Checklist
- [ ] No real credentials in source / config / frontend?
- [ ] No private keys in repo?
- [ ] Secrets use env vars / vault / KMS with no defaults?
- [ ] No cloud access keys in frontend JS?
