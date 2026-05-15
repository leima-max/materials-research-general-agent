---
name: humanizer
version: 2.2.0
description: >
  Remove obvious AI-writing patterns and make text sound natural, specific,
  and human-written while preserving meaning. Use when editing drafts,
  abstracts, introductions, responses, reports, or prose that feels generic,
  inflated, repetitive, or overly polished.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# Humanizer

Use this skill to revise text so it reads like a real person wrote it. Preserve
the user's meaning, facts, technical claims, and intended audience. Do not add
unsupported claims, fake citations, or invented emotion.

## Quick Workflow

1. Identify the target voice: academic, technical, conversational, persuasive,
   reflective, concise, or mixed.
2. Scan for AI-writing patterns: inflated importance, vague abstraction,
   symmetrical phrasing, over-explaining, repeated sentence rhythm, stock
   transitions, and generic praise.
3. Rewrite only what needs rewriting. Keep strong original sentences.
4. Replace vague claims with concrete nouns, actors, methods, constraints, or
   measured uncertainty.
5. Vary sentence length and rhythm without making the text sloppy.
6. Return the revised text first. Add a brief note only when useful.

For a deeper checklist, load `references/patterns.md`.

## Editing Rules

- Preserve technical accuracy and citation boundaries.
- Keep the user's voice where it is already working.
- Remove puffery such as "plays a crucial role", "underscores the importance",
  "delves into", "robust", "seamless", and similar stock phrases unless they
  are genuinely needed.
- Prefer direct verbs over abstract framing.
- Avoid overusing em dashes, three-part lists, parallel contrasts, and summary
  closers that sound formulaic.
- Do not make academic writing casual unless the user asks for that style.
- Do not make casual writing stiff in the name of polish.

## Output Patterns

For short text, return only the revised version.

For longer or high-stakes text, use:

```text
Revised:
...

Notes:
- Changed X to reduce overstatement.
- Kept Y because it was precise.
```

If the user asks for a minimal edit, preserve structure and only fix the
obvious AI markers. If the user asks for a stronger rewrite, reshape sentences
more freely while keeping facts intact.
