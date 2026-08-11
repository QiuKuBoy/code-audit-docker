# Deserialization Audit Skill

## Overview
Insecure Deserialization occurs when untrusted data is deserialized without validation, potentially leading to RCE.

## Audit Methodology
1. **Find all deserialization points**: pickle.loads(), json.parse with reviver, unserialize()
2. **Trace data origin**: Check if serialized data comes from user input
3. **Check safety measures**: Look for type checking, allowlists, signed data
4. **Identify gadget chains**: For Java, check library versions for known chains

## Common Patterns by Language

### Python
- `pickle.loads(user_data)` — CRITICAL: arbitrary code execution
- `yaml.load(user_data)` — use `yaml.safe_load()` instead
- `marshal.loads(user_data)` — similar to pickle
- `shelve.open()` — uses pickle internally

### Java
- `ObjectInputStream.readObject()` — classic Java deserialization
- `XMLDecoder.readObject()` — XML-based deserialization
- Fastjson: `JSON.parseObject(userInput)` — check autotype
- Jackson: `readValue()` with polymorphic types
- XStream: `fromXML(userInput)`

### Node.js
- `node-serialize.unserialize(userInput)` — RCE via IIFE
- `serialize-javascript` with `unsafe: true`

### PHP
- `unserialize(userInput)` — PHP object injection
- `__wakeup()`, `__destruct()` magic methods exploitation

### .NET
- `BinaryFormatter.Deserialize()` — known unsafe
- `JavaScriptSerializer.Deserialize()` with type info
- `XmlSerializer` with known gadgets

## Key Checks
- [ ] Is the deserialization library safe? (pickle = never safe)
- [ ] Is the data authenticated/signed?
- [ ] Are allowed types restricted (allowlist)?
- [ ] Are vulnerable library versions present? (commons-collections, fastjson)
- [ ] Is there a type filter / deserialization filter?
