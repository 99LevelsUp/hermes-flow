# Choosing the model for an automated issue decision

Use when a flow step (estimate, classification, routing, decomposition...) is to
run automatically and the owner wants the cheapest model that is good enough.
The owner decides from the measured table; do not assume a bigger model is needed
(routing turned out easy enough for Haiku low; estimating needed Haiku high).

## Procedure
1. Sample ~30 open issues across both repos and all relevant states (Backlog,
   Needs decision, Ready, bugs, umbrellas with sub-issues, sub-issues). Fix the
   random seed and save `sample.json`.
2. Build one prompt per batch of 10 with the exact rules the production step
   will use and a `--json-schema` for the answer. Pre-fetch each issue (body,
   comments, sub-issues, `git log --grep='#N'`) into context files exactly as
   the production script does, and point the model to those files.
3. Run headless Claude Code per config in the production sandbox (context files
   + `--restricted --tools Read,Grep,Glob --allowedTools Read,Grep,Glob`, see
   SKILL.md Automation pitfalls) so the test measures what will run and no
   model gets a shell: `claude -p "$P" --model M --effort E --output-format json
   --json-schema "$SCHEMA" ... --strict-mcp-config --disable-slash-commands
   --no-session-persistence`, repo mirrors via `--add-dir` (not the owner's
   working copies).
   Configs: haiku and sonnet x low/medium/high, each twice (stability), plus
   opus high once as reference. Run 4 in parallel with
   `xargs -P 4 -L 1 ./run.sh < jobs.txt` as a background terminal job.
   Read the prompt into a variable AFTER `cd` to the script dir, or relative
   prompt paths break.
4. Smoke-test one job first and check `subtype == success` and the
   structured_output count before launching the rest.
5. Score from the JSON: `total_cost_usd`, `duration_ms`, `num_turns`; agreement
   with opus; agreement with ground truth derivable from the owner's existing
   structure (umbrellas -> split, bugs -> Debug, Needs decision -> Decide);
   run1 vs run2 stability; for numbers the median log-ratio to opus and share
   within x1.5. Note cases only good configs catch (e.g. issue already done).
6. Present one table + recommendation (cost per 30 issues, quality columns,
   caveat that costs are API list prices while the owner pays a subscription).
   Prefer folding a new decision into an existing run when the same model
   already reads the issue: near-zero extra cost.
7. Verify nothing changed on GitHub during the test before comparing labels;
   another session may have changed labels concurrently.
