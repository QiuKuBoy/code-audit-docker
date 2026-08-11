# Path Traversal Audit Skill

## Overview
Path Traversal occurs when user input is used to construct file paths without validation, allowing access to files outside intended directories.

## Audit Methodology
1. **Find all file operations**: open(), readFile(), fs.read, File()
2. **Trace path origin**: Check if path components come from user input
3. **Check validation**: Look for path normalization, allowlists
4. **Test bypass**: `../`, encoded paths, absolute paths

## Common Patterns

### Python
- `open(user_input)` — direct user path
- `os.path.join(base_dir, user_input)` — join doesn't prevent traversal
- `send_file(user_input)` — Flask file serving
- `send_from_directory(base, user_filename)` — can still traverse

### Node.js
- `fs.readFile(userPath)` — direct user path
- `path.join(baseDir, userInput)` — join doesn't prevent `../`
- `res.sendFile(userInput)` — Express file serving

### Java
- `new File(userInput)` — direct user path
- `Paths.get(basePath, userInput)` — doesn't prevent traversal

## Bypass Techniques
- `../../../etc/passwd` — classic
- `..%2f..%2f..%2f` — URL encoded
- `....//....//` — double encoding / filter bypass
- `/etc/passwd` — absolute path (bypasses join)
- Null byte: `file.txt%00.pdf` (older systems)
- Unicode: `%c0%af` → `/`

## Validation Checklist
- [ ] `os.path.realpath()` checked against base directory?
- [ ] `..` stripped or rejected?
- [ ] Allowlist of filenames?
- [ ] `path.normalize()` result checked?
