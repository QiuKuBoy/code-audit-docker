# RCE / Command Injection Audit Skill

## Overview
Command injection occurs when user input reaches OS command execution sinks. RCE is the highest-impact finding class.

## Audit Methodology
1. Find command execution sinks: exec, system, shell_exec, passthru, proc_open, popen, subprocess, os.system, Runtime.exec, ProcessBuilder, child_process, execFile
2. Trace input to sink: does the input reach the command string without escaping/filtering?
3. Check filters: are they blacklists (bypassable) or proper whitelists / argument arrays?
4. Assess impact: web shell write, reverse shell, data exfiltration, privilege escalation

## Common Patterns by Language
- PHP: `exec("ping -c 2 " . $_POST['ip'])` — direct concat
- Python: `os.system(f"ping {ip}")`, `subprocess.call("ls " + path, shell=True)` — shell=True is the red flag
- Java: `Runtime.getRuntime().exec("ping " + host)` — no argument array
- Node: `child_process.exec("ls " + path)` — exec uses shell; execFile doesn't
- Go: `exec.Command("sh", "-c", "ping "+ip)` — shell form

## Filter Bypass Techniques (to check if a filter exists)
- Shell metacharacters: `; | & && || \n %0a` 
- Space bypass: `${IFS}`, `$IFS$9`, tab `%09`, `{cat,/etc/passwd}` brace expansion
- Blacklist bypass: case changes, variable interpolation, `$(...)`, backticks, newline
- `--` separator, path concatenation

## Key Reminders
- Prefer argument-array APIs (execFile, subprocess list form, ProcessBuilder list) — no shell interpretation
- `shell=True` / `-c` / string exec = vulnerable by default
- Even "blind" command injection (no output reflection) is exploitable via time-based or outbound exfil

## Checklist
- [ ] All OS command calls use argument arrays (no shell string)?
- [ ] If shell string required: strict whitelist validation on all inputs?
- [ ] No user input in file paths passed to commands?
- [ ] Commands run with least privilege?
