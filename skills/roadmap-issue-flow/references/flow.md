# Flow steps (from the owner's artifact, 24.11.2026)

Format: step | Status | what | CE tools | GitHub tools | result.

## Decision session (owner + agent, no code)

1. Product direction | - | milestones and their order; once, then on change of direction
   CE: ce-strategy creates/updates STRATEGY.md -> milestone order
   GH: Milestones (same name across repos merges in roadmap); Projects v2 Roadmap view by milestone
   Result: an idea gets a milestone; unclear -> "Later / backlog".

2. Idea becomes an issue | Backlog | every idea surviving ideation is one issue
   CE: ce-ideate generates and scores ideas; each survivor gets an issue
   GH: gh issue create (English, ## What / ## Why, label idea, Source: line); gh issue list --search for duplicates (similar = comment); Auto-add puts it on board as Backlog; issue type Bug/Feature/Task (kind labels bug/enhancement/task no longer exist); labels documentation + idea needs-brick

3. Triage and priority | Backlog (outside ideas -> Needs decision; Reject -> Reject proposed) | owner orders the queue; Priority decides what is brainstormed next
   Automated part (cron issue-triage, see SKILL.md): first Estimate (minutes) + estimate-history row, issue type, labels, relates-to links, Next step (Ideate / Brainstorm / Decide / Debug / Reject; Done for closed issues), flags needs-prototype / needs-bakeoff, and a triage record comment for the next agent; umbrellas get Estimate = sum and Status = least advanced sub-issue.
   CE: none for Priority (owner's decision)
   GH: Priority P1 now / P2 next / P3 later / P4 doubtful (close candidate), Product field; views Board (status), Table (product), Roadmap (milestone); gh project item-edit for bulk. Only the owner closes (gh issue close --reason "not planned") a P4 or Reject proposed item, or moves it back.

3b. Decomposition | Backlog | Next step = Ideate: one sub-issue per separate problem, ordered, hard prerequisites as blocked-by; parent becomes umbrella
   CE: ce-ideate (creates the sub-issues directly, unestimated; triage estimates and routes them next round); then the umbrella's consistency check: do the sub-issues together cover the request without gaps or overlaps? Refined estimates go into the estimate history.
   GH: sub-issues (addSubIssue / reprioritizeSubIssue), addBlockedBy; limits 100 children, 8 levels; clear the umbrella's Next step (triage also does it). Sub-issues of an outside author's issue get `Source: <repo>#N (outside author)`.

4. Brainstorm a specific issue | Backlog | Takes the highest-priority Backlog issue whose Next step is Brainstorm, Decide or Debug (Ideate -> step 3b; Reject / Reject proposed -> skip, owner's call; outside ideas only after the owner approved them). Started when the owner asks or by the worker who takes an item to In progress. Ends in Ready, Needs decision, or Reject proposed. Next step Decide -> ce-pov first; Debug -> ce-debug first.
   CE: ce-brainstorm (scope boundaries + verification); ce-pov for bigger decisions (also other-model panel); ce-prototype / ce-bakeoff when variants must be tried
   Related issues: read the live links with GraphQL (`relatesTo`, see SKILL.md Environment facts). For each OPEN related issue decide whether it is bundled into this work (one session, one branch, >=1 own commit per issue, one PR closing all); record the decision and reason in the brainstorm comment of each bundled issue and move them through the gate together; exceptions (separate PRs) are recorded here. CLOSED related issues are history only (earlier decisions and code).
   GH: gh issue view --json ...; gh issue edit --body at the end; requirements doc in repo linked by Source:; refined Estimate + estimate-history row; brainstorm comment with marker.
   Done when nothing is pending: issue body is an unambiguous spec.

5. Questions for the owner | Needs decision | decisions, accounts, tokens, hardware; independent questions = separate issues
   CE: ce-pov backs the recommendation; ce-prototype shows a variant
   GH: ## Decision (options + recommendation); Status Needs decision (owner's queue on Board); owner answers in his own comment -> write ## Decided (what, why, date, link to the owner's comment); gh issue edit body accordingly; Next step = Brainstorm
   Then back to brainstorm. Outside ideas wait here for the owner's approval (-> Backlog) or closing.

6. GATE before Ready | Needs decision/Backlog -> Ready | not brainstormed + not ce-doc-review'd stays Backlog even with Decision done
   CE: ce-doc-review on requirements doc + issue body, apply findings; owner-level findings -> Needs decision
   GH: gh issue edit --remove-label idea + milestone; Status Ready; gh issue comment with review result

7. Ready queue | Ready | specs waiting for a worker
   CE: ce-handoff passes between sessions what moved to Ready (survives a crash)
   GH: Board order by owner drag; new goes to the end; cross-repo deps "Blocked by owner/repo#N"
   Worker takes from the top.

## Work session (Ready queue, code is written here)

8. Take an item | In progress | own branch + own worktree per item or bundle, items in parallel
   CE: ce-worktree; ce-debug first when the issue type is Bug or Next step is Debug; ce-plan sized to item
   For an outside author's issue: check the body did not change since the gate (else back to Backlog).
   GH: Status In progress; gh issue develop N --checkout; gh issue edit --add-assignee; sub-issues show progress
   Meanwhile brainstorm of the next issue starts.

9. Implementation and tests | In progress | tests verified to fail without the fix; frequent commits
   CE: ce-work (incl. local verification); ce-commit; ce-debug for unknown test failures
   GH: gh pr create --draft early for CI; Actions (build, tests, lint, cargo-deny); gh run watch --exit-status
   New work found on the way = new issue.

10. GATE before merge, part 1 | In progress | simplify first so review sees the final state
   CE: ce-simplify-code (prune tests/comments that carry nothing; behaviour must not disappear)
   GH: gh pr diff
   Applies to every resolved issue, even docs/CI.

11. GATE before merge, part 2 | In progress | review the item's diff, fix findings, re-run tests
   CE: ce-code-review; ce-resolve-pr-feedback; ce-setup produces CODING_STANDARDS.md and REVIEW.md from PR history (feeds review)
   GH: gh pr review + inline comments; branch protection + required checks; (optional: Claude Ship beta as second voice)
   Owner-level findings -> Needs decision.

12. Pull request and babysitting | In progress | one PR per resolved item or bundle, "Closes #N" for each issue; the work sets the final Estimate (actual cost) + estimate-history row
   CE: ce-commit-push-pr; ce-babysit-pr until mergeable (also Dependabot PRs); ce-resolve-pr-feedback for owner comments
   GH: gh pr ready; gh pr checks --watch; gh pr view --comments; Dependabot weekly cargo/npm/Actions PRs

13. Merge and close | Done | merge closes issue, Status set automatically (merge only with the owner's go-ahead)
   GH: gh pr merge; Closes #N; Project workflows Item closed -> Done, PR merged -> Done (UI only); gh issue list --state closed to check; triage then writes the closing record and Next step Done. When the last sub-issue of an umbrella is done: the umbrella's final check of the whole, then Done; the owner closes it.

14. Lessons into the repo | Done | non-trivial lesson in the cheapest durable form, in the repo not memory
   CE: ce-compound (test, lint rule, standard, note)
   GH: lesson goes as another PR; new work from it = new issue

15. Milestone close and release | Done | when all milestone items are done; afterwards outside users file issues
   CE: ce-retro (agent work retrospective, papercuts -> issues); ce-explain (period summary for release notes); ce-sweep (triage outside users' new issues)
   GH: milestone 100 % and close; gh release create with attestations; private vulnerability reporting + SECURITY.md; gh project item-list for stats
   Next milestone per STRATEGY.md.

## Loops back
- Review / CI -> In progress: findings or red CI send the item back; gates repeat.
- Gate -> Needs decision: owner-level findings are not decided in code; issue gets ## Decision and waits.
- Discovered work -> Backlog: new issue, possibly straight to Needs decision.
- Any step -> Reject proposed: pointless idea, duplicate, or not actually a bug; the owner closes it as "not planned" or moves it back.

## Possible extensions (researched, NOT in the flow, untested)
- Label `ready` triggers a GitHub Action that sets Status (no projects_v2_item webhook for user projects).
- Nightly run over the Ready queue opening draft PRs (must not bypass ce-simplify-code and ce-code-review).
- Claude Ship (Anthropic beta) as complement to ce-code-review.
- Linear instead of issues (not for EVƎ).
- gh-pm extension for bulk triage by Status/Priority.
