# Skill Registry (markdown-driven)

Structure: one folder per skill, e.g. `skills/MySkill/`.

Required: `skill.md` with YAML frontmatter containing at least:

```
---
name: AgentEducation
description: Extracts degree and graduation year from CV text.
requires:
  - cv_text
produces:
  - degree
  - grad_year
  - is_qualified
hitl_enabled: false
prompt: Optional override instructions (or supply via prompt.md)
---
```

Nested data: `requires` and `produces` can use dot-notation paths to read/write inside JSON blobs, e.g. `previousAgentOutput.recession_data.amount`. Paths are resolved when planning, passing inputs to skills, and storing outputs.

Optional: `prompt.md` in the same folder to provide custom executor prompt.

Everything after the closing `---` in `skill.md` is free-form documentation for humans and
does not affect runtime behavior.