# XXE / XML External Entity Audit Skill

## Overview
XXE occurs when an XML parser processes external entities (DTD) without disabling them, allowing file read / SSRF / DoS.

## Audit Methodology
1. Find XML parsing points: simplexml, DOMDocument, XMLReader, SAXParser, DocumentBuilder, javax.xml, lxml, ElementTree
2. Check parser configuration: entity expansion enabled? DTD loading enabled? external entities allowed?
3. Trace XML input source: file upload, POST body, SOAP, config files, document import
4. Test: SYSTEM "file:///etc/passwd", SYSTEM "http://169.254.169.254/latest/meta-data/", Billion Laughs (entity expansion DoS)

## Common Patterns by Language
- PHP: `simplexml_load_string($xml, ..., LIBXML_NOENT | LIBXML_DTDLOAD)` with `libxml_disable_entity_loader(false)`
- Java: `DocumentBuilderFactory` without `setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`
- Python: `lxml.etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=True))`, `xml.etree` with external entity resolver
- C#: `XmlDocument.LoadXml()` without `XmlResolver = null`

## Key Reminders
- `LIBXML_NOENT` + `LIBXML_DTDLOAD` = entity substitution + DTD load = XXE
- Even without file read (no output), XXE can be used for blind SSRF / port scan
- Billion Laughs: nested entity expansion DoS, even when no external entities
- Check for XXE in: SVG uploads, DOCX/XLSX parsing (they're ZIP+XML), RSS/Atom feeds, config import

## Checklist
- [ ] Are all XML parsers configured with DTD disabled / external entities off?
- [ ] Is user-controlled XML ever parsed (upload, API body, import)?
- [ ] Are error messages leaking parser details?
