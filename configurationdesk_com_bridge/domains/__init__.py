"""Domain COM wrapper modules.

All functions in these modules:
- Run exclusively on the STA thread (via dispatch())
- Take a connection object as first parameter
- Return JSON-safe dicts/lists (never COM objects)
- Raise BridgeError subclasses on failure
"""
