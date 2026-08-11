# XSS Audit Skill

## Overview
Cross-Site Scripting (XSS) occurs when user input is rendered in HTML without proper escaping.

## Audit Methodology
1. **Find all output points**: Search for template rendering, innerHTML, document.write
2. **Trace input origin**: Check if rendered content comes from user input
3. **Check escaping**: Verify if HTML encoding / CSP is applied
4. **Identify XSS type**: Reflected / Stored / DOM-based

## Common Patterns

### Python (Backend Templates)
- `render_template_string(user_input)` — Flask template injection
- `Markup(user_input)` — unsafe Markup
- `|safe` filter in Jinja2 templates
- Response with `Content-Type: text/html` containing user data

### Node.js
- `res.send(userInput)` without escaping
- `innerHTML = userInput` — DOM XSS
- `dangerouslySetInnerHTML={{__html: userInput}}` — React unsafe
- Template engines with unescaped output: `<%- userInput %>` (EJS)

### Frontend (All frameworks)
- `document.write(userInput)` — DOM XSS
- `element.innerHTML = userInput` — DOM XSS
- `eval(userInput)` — JS injection
- `setTimeout(userInput)` / `setInterval(userInput)` — eval-like

## Key Checks
- Template auto-escaping enabled? (Jinja2: yes by default, EJS: no)
- CSP headers set?
- HttpOnly cookies?
- Input length/character validation?
- Sanitization library used? (DOMPurify, bleach)

## Context-Specific Escaping
- HTML body context: `<` → `&lt;`
- Attribute context: `"` → `&quot;`
- JavaScript context: `\` → `\\`, quotes escaped
- URL context: parameter encoding
