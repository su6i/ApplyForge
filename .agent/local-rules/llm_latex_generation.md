# LLM & LaTeX Generation Workflow

> Engineering rule for the cover-letter / CV pipeline. Applies whenever an LLM
> produces structured LaTeX content that is later injected into `.tex` templates.
> (Origin: bug fixed in `src/pipeline/latex_builder.py` — multi-paragraph `cl_body`.)

## ❌ The Problem: The "Escaping & Regex" Trap
When generating structured LaTeX content using an LLM (e.g. cover letters with distinct
paragraphs), a common anti-pattern is asking the LLM to insert custom delimiters
(e.g. `[PARAGRAPH_BREAK]`) or relying on string linebreaks (`\n\n`).

This is extremely fragile because the text passes through multiple parsing layers:
1. LLM string generation
2. JSON deserialization
3. Custom LaTeX character escaping (`latex_escape`)
4. Python's `re.sub` regex replacement

Replacing delimiters with LaTeX newline commands like `\\[0.3cm]` inside a `re.sub()`
replacement string causes the regex engine to consume the backslashes, yielding malformed
LaTeX (e.g. `\[0.3cm]`, interpreted as inline math and dropped) and breaking formatting.

## ✅ The Solution: Native Arrays & Safe Interpolation
Decouple the logical structure from the string-replacement mechanics:

1. **LLM Output as Array:** In the JSON schema prompt, instruct the LLM to output a native
   JSON array of strings (`list[str]`) for multi-paragraph fields, not a single string.
   *Example:* `"cl_body": ["Paragraph 1", "Paragraph 2"]`
2. **Python-Native Join:** Apply `latex_escape` to each paragraph, then join with Python's
   native join — not via the LLM or regex:
   *Example:* `r"\\[0.3cm]".join(latex_escape(p) for p in paragraphs)`
3. **Lambda for Regex Replace:** When inserting the assembled string into the `.tex` template
   with `re.sub()`, **NEVER** pass the string directly as `repl` (the regex engine processes
   its backslashes). Use a lambda:
   *Example:* `re.sub(pattern, lambda m, r=repl_text: m.group(1) + r + m.group(2), template)`

This guarantees 1:1 verbatim insertion of the LaTeX and eliminates backslash-parsing bugs.
