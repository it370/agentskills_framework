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

Optional: `prompt.md` in the same folder to provide custom executor prompt.

Everything after the closing `---` in `skill.md` is free-form documentation for humans and
does not affect runtime behavior.