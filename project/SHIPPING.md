# Shipping Playbook

This playbook keeps every change tied to a user outcome. Use it alongside `project/roadmap/pr-stack.md` whenever you scope work or open a PR.

## Definition of Done (DoD)

A feature or bug fix is considered shipped only when **all** of the following hold:

1. **Story → Acceptance → Demo**: The work references a user story, has explicit acceptance criteria, and includes a runnable demo script.
2. **Test-first mindset**: At least one automated test would fail without the change (unit, integration, or e2e). Patch-only refactors must document why tests are unaffected.
3. **Docs & example**: Update relevant docs (README, `AGENTS.md`, roadmap/pr-stack, config) and include an example `curl` (or equivalent) that exercises the behavior.

## Kill Switch

If a task cannot produce a demo within five calendar days, reduce scope or move it to **Parked**. Call it out in the PR and add a follow-up issue with the next concrete step.

## Demo First

Every PR must contain a 60–90 second “how to try it” section (see the PR template). Fill in the template—replace the placeholder comments and remove the `# TODO` block. If demo steps are missing, you’re still planning—not shipping.

## Finish Mode Labels

Use repository labels to reflect state:

- `finish-mode` — actively working toward demo/DoD.
- `demo-ready` — demo steps verified; awaiting review.
- `spike` — time-boxed exploration; must end with Keep / Cut / Convert decision.
- `blocked` — external dependency or decision needed.

Move cards on the project board with columns **Now / Next / Later / Parked**. Items in **Now** must already have demo steps and acceptance criteria.

## Repo Rules (Body Agent specifics)

- **Graph nodes**: no new node without documenting inputs/outputs in `AGENTS.md` and adding an integration test for its happy path.
- **Answer generator**: each new sub-intent requires a deterministic demo query in EN/HE.
- **Retrieval changes**: add a failing test that turns green with the change (e.g., interaction alert flow).

Keep this doc updated when our delivery habits evolve. Small tweaks beat stale process docs.
