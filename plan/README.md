# Planning Directory Guide

This folder keeps the long-running planning artifacts for the Body Agent project. Each file has a specific purpose so we can evolve the roadmap without losing context.

| File | Purpose |
| --- | --- |
| `initial_idea.md` | Original notes that capture the product vision and motivating use cases. Keep for historical context. |
| `high-level-design.md` | Current architecture blueprint: service layout, data flow, and node responsibilities. Update when major structural decisions change. |
| `update.md` | Running commentary on what we adopted (or rejected) from external reviews and why. Treat as design rationale. |
| `pull_request_template.md` | Active PR stack. Describes the next slice of work, acceptance criteria, and code pointers. Keep this aligned with what’s actually in flight. |
| `ideas.md` | Backlog of forward-looking ideas (symptom flexibility, connectors, etc.). Move items into the PR stack when they’re ready to ship. |

## How to Use

1. **Review `pull_request_template.md` first** – it reflects the current sequence of actionable PRs.
2. **Consult `ideas.md` for scoped concepts** that are not yet scheduled. Promote them when capacity opens up.
3. **Update `high-level-design.md`** when architectural changes land so newcomers have an accurate mental model.
4. **Capture trade-offs in `update.md`** whenever we accept or reject major suggestions (internal or external reviews).

Keeping the docs scoped this way lets us manage the roadmap without drowning in outdated notes.
