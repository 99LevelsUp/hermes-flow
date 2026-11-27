# hermes-flow

Hermes Agent tooling for running GitHub roadmaps of the owner's projects.

- `skills/roadmap-issue-flow/` - the process from idea to release with Compound Engineering and
  GitHub (`SKILL.md`, step table in `references/flow.md`, model choice in
  `references/model-selection.md`) and the triage script `scripts/issue-triage.py`.
- `hermes/cron/` - definitions of the Hermes cron jobs that run the scripts.
- `tools/` - deployment and one-off maintenance scripts.

## What runs

A Hermes cron job (`issue-triage`, every 15 minutes, script only) keeps the roadmap triaged:

- new issues get an Estimate (minutes), issue type, labels, related-issue links, the Next step and
  a triage record comment;
- umbrella issues get the sum of their sub-issues' estimates and the status of their least
  advanced sub-issue;
- closed issues get a closing record;
- every estimate change is appended to the issue's estimate history.

The model is Claude Haiku in a read-only sandbox; the script does every write. Details and the
safety rules are in the skill.

## Deploy

On the main checkout, after a merge:

```
tools/deploy.sh          # copies the skill and the cron script into ~/.hermes
```

Agents: read `AGENTS.md` first.
