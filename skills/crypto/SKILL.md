# Crypto & Secrets Audit Skill

## Overview
Crypto misuse (weak hashes, hardcoded keys, broken protocols) and secret leakage in source/config.

## Audit Methodology
1. Find cryptographic operations: hash, encrypt, sign, MAC, keygen, JWT, random
2. Check algorithm strength: MD5/SHA1 for passwords (weak), DES/RC4 (broken), ECB mode, static IV, no salt
3. Check key management: hardcoded keys, keys in config committed to repo, keys in frontend JS
4. Check randomness: mt_rand, rand, Math.random for security tokens (predictable)
5. Check JWT: algorithm none accepted, weak secret, no expiry

## Common Vulnerable Patterns
- `md5($password)` / `sha1($password)` without salt
- `password_hash()` missing (plaintext or MD5 storage)
- AES-ECB mode, static IV, key reuse
- Hardcoded `accessKeyId`/`accessKeySecret`/`api_key`/`secret` in source or frontend JS
- `mt_rand()` / `rand()` for tokens, session IDs, OTPs
- JWT `alg: none`, `HS256` with `"secret"` / `"password"` weak secret
- `==` non-constant-time comparison for secrets (timing attack)

## Key Reminders
- Passwords: bcrypt/argon2/scrypt with cost factor; never reversible
- Keys: never in code/config committed; use env vars / KMS / vault; rotate leaked keys
- Randomness: CSPRNG (secrets.token_bytes, random_bytes, SecureRandom) for anything security-relevant
- Constant-time compare: hash_equals, hmac.compare_digest, MessageDigest.isEqual

## Checklist
- [ ] No MD5/SHA1 for passwords (unkeyed hashes for storage)?
- [ ] No hardcoded secrets in source/frontend/config?
- [ ] Security tokens from CSPRNG, not mt_rand/rand?
- [ ] JWT alg restricted (no none), strong secret?
- [ ] Constant-time secret comparison?
