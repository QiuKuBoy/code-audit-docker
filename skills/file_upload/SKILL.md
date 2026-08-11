# File Upload Audit Skill

## Overview
File upload vulnerabilities allow arbitrary file upload → webshell / RCE, stored XSS, malware hosting, DoS.

## Audit Methodology
1. Find upload endpoints: multipart form, move_uploaded_file, saveFile, writeFile, upload APIs
2. Check extension validation: blacklist (bypassable) vs whitelist? Case sensitivity? Double extension? Null byte?
3. Check content validation: MIME type from client (spoofable) vs magic bytes? Image re-encoding?
4. Check storage location: web-accessible? Executable directory? Filename user-controlled?
5. Check downstream usage: uploaded file included/executed? Served with correct Content-Type?

## Common Bypass Patterns
- Blacklist bypass: `.phtml`, `.php5`, `.pht`, `.shtml`, `.asp`, `.aspx`, `.jsp`, `.jspx`, `.war`
- Case bypass: `.PhP`, `.pHp`
- Double extension: `shell.php.jpg` (if server misconfigured), `shell.jpg.php` (Apache handler)
- Null byte (old PHP): `shell.php%00.jpg`
- Whitespace/dot: `shell.php.`, `shell.php `, `shell.php%20`
- Content-Type spoof: `Content-Type: image/jpeg` with PHP payload
- Magic bytes spoof: `GIF89a` header + payload

## Key Reminders
- Blacklist is NEVER sufficient — always use whitelist of allowed extensions
- Validate file content with magic bytes (getimagesize for images), not client MIME
- Store uploads outside web root or in a directory with script execution disabled
- Randomize stored filenames; never trust original name
- Check uploaded file usage downstream (include → LFI/RCE chain)

## Checklist
- [ ] Whitelist (not blacklist) extension validation?
- [ ] Content validated via magic bytes / re-encoding?
- [ ] Filename randomized server-side?
- [ ] Upload dir has script execution disabled / outside web root?
- [ ] Uploaded files never included/executed?
