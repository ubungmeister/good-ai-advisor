# Issue tracker: GitHub

Issues and specs for this repo live in GitHub Issues. Use the `gh` CLI, which infers `ubungmeister/good-ai-advisor` from this clone.

## Conventions

- Create: `gh issue create --title "..." --body "..."`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open`; add label or state filters as needed.
- Comment, label, and close with `gh issue comment`, `gh issue edit --add-label` / `--remove-label`, and `gh issue close`.
- Link sub-issues with `gh issue create --parent <number>` or `gh issue edit <parent> --add-sub-issue <child>`. If unavailable, use `Part of #<parent>` in the child body.
- Record blockers with GitHub issue dependencies (`--blocked-by` / `--add-blocked-by`). If unavailable, write `Blocked by: #<number>` in the issue body.
- Before creating issues, verify the target is `ubungmeister/good-ai-advisor`; never file into `mattpocock/skills`.

## Pull requests as a triage surface

**No.** External PRs are not included in the triage queue by default.

## Wayfinding

Use a `wayfinder:map` issue for the map and linked child issues labeled `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`. Assign claimed work to the driving developer; record blockers using the conventions above.
