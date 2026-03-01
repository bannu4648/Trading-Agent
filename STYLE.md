# Code Style & Structure Standard — Trading Agent FYP

## Module-Level Docstring
Every file starts with a short docstring (2–5 lines max):
- What the module does (one line)
- Any important design note (one line)
- No author/date headers (git handles that)

## Imports
Grouped in this order, one blank line between groups:
1. stdlib
2. third-party (langchain, groq, yfinance, pandas...)
3. local project imports

## Constants
- SCREAMING_SNAKE_CASE
- One-line comment on the same line if the value isn't obvious
- Group related constants together with a blank line between groups

## Classes
- One class per module where possible
- Docstring on the class itself (2–5 lines, what it does + what it does NOT do)
- __init__ always defines self.logger = logging.getLogger(__name__)
- Public methods: run() / validate() / review() — named by what they do, not "execute"
- Private helpers: _snake_case prefix

## Method Docstrings
- Args / Returns only when the signature isn't self-evident
- Skip docstrings entirely on trivial <5-line helpers

## Comments
- Should sound like a grad student wrote them
- Explain WHY, not WHAT (the code shows what)
- Casual but clear — no corporate speak
- Only add comments where something non-obvious is happening

## Logging
- Always: logger = logging.getLogger(__name__) at module level
- Format: [module_tag] message — keeps log grep-able
- INFO for normal flow, WARNING for degraded but handled, ERROR for failures

## Error Handling
- Every public method wraps its main work in try/except
- On failure, log the error and return a safe fallback value
- Never silently swallow exceptions — always log them

## Type Hints
- Use them on all public method signatures
- For internal helpers, use them only when the type is non-obvious
- Use `from __future__ import annotations` for cleaner forward references
