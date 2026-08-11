# SSRF Audit Skill

## Overview
Server-Side Request Forgery (SSRF) occurs when an application makes HTTP requests to user-specified URLs without proper validation.

## Audit Methodology
1. **Find all HTTP request points**: Search for requests.get(), http.Get(), fetch(), urllib
2. **Trace URL origin**: Check if URL or hostname comes from user input
3. **Check validation**: Look for allowlists/blocklists, URL parsing validation
4. **Test bypass**: Check for cloud metadata (169.254.169.254), localhost, internal IPs

## Common Patterns

### Python
- `requests.get(user_url)` — direct user URL
- `urllib.request.urlopen(user_input)` — urllib
- `httpx.AsyncClient().get(url)` — httpx
- `aiohttp.ClientSession().get(url)` — aiohttp

### Node.js
- `fetch(req.body.url)` — fetch API
- `axios.get(userUrl)` — axios
- `http.get(url)` — native http

### Java
- `URL(userInput).openConnection()` — URL class
- `HttpClient.newHttpClient().send(request)` — HttpClient
- `RestTemplate.getForObject(url, ...)` — RestTemplate

## Bypass Techniques to Check
- IP encoding: `127.0.0.1` → `0x7f000001`, `2130706433`, `017700000001`
- DNS rebinding
- URL parser confusion: `http://evil@127.0.0.1`
- Cloud metadata: `169.254.169.254` (AWS/Azure/GCP)
- Redirect chains: external URL redirects to internal
- IPv6: `[::1]`, `[::ffff:127.0.0.1]`

## Validation Checklist
- [ ] URL scheme restricted to http/https?
- [ ] Hostname resolved and checked against internal IP ranges?
- [ ] Redirect following disabled or validated?
- [ ] DNS rebinding protection (resolve → connect to same IP)?
- [ ] Blocklist for metadata endpoints?
