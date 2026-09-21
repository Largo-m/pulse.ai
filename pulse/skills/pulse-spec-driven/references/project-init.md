# Project Initialization

**Trigger:** "Initialize project", "Setup project", "Start new project"

## Process

Gather project vision using the topics below. Follow [user-input.md](user-input.md): analyze the codebase and existing docs first, draft what you can infer, then stop only when mandatory fields are missing.

**Output:** Use the exact 4-question structure from the canonical template in [SKILL.md](../SKILL.md#user-input-cli) and [user-input.md](user-input.md). Wrap in ` ```text ` fence. One option per line — never inline.

**Topics to cover (batch as CLI questions when blocked):**

1. What are you building?
2. Who is it for and what problem does it solve?
3. What tech stack are you using? (if known)
4. What's in scope for v1? What's explicitly excluded?
5. Critical constraints? (timeline, technical, resources)

**Stop asking when:** Vision, goals, and boundaries are clear enough to write PROJECT.md.

**Do not** start with a conversational interview or spread questions across multiple turns before doing autonomous work.

## Output: .pulse/specs/project/PROJECT.md

**Structure:**

```markdown
# [Project Name]

**Vision:** [1-2 sentence description]
**For:** [target users]
**Solves:** [core problem being addressed]

## Goals

- [Primary goal with measurable success metric]
- [Secondary goal with measurable success metric]

## Tech Stack

**Core:**

- Framework: [name + version]
- Language: [name + version]
- Database: [name]

**Key dependencies:** [3-5 critical libraries/frameworks]

## Scope

**v1 includes:**

- [Core capability 1]
- [Core capability 2]
- [Core capability 3]

**Explicitly out of scope:**

- [What is NOT being built]
- [What is NOT being built]

## Constraints

- Timeline: [if applicable]
- Technical: [if applicable]
- Resources: [if applicable]
```

**Size limit:** 2,000 tokens (~1,200 words)

**Validation:**

- Vision clear in 1-2 sentences?
- Goals have measurable outcomes?
- Scope boundaries explicit?
