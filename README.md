# hermes-flow

Hermes Agent tooling for running GitHub roadmaps of the owner's projects.

- `skills/roadmap-issue-flow/` - the process from idea to release with Compound Engineering and
  GitHub (`SKILL.md`, step table in `references/flow.md`, model choice in
  `references/model-selection.md`) and the triage script `scripts/issue-triage.py`.
- `hermes/cron/` - definitions of the Hermes cron jobs that run the scripts.
- `hermes/triage-config.json` - which GitHub projects and repositories the triage serves.
- `tools/` - deployment and one-off maintenance scripts.

## What runs

A Hermes cron job (`issue-triage`, every 15 minutes, script only) keeps the configured roadmaps
triaged:

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
tools/deploy.sh          # copies the skill, the cron script and the configuration into ~/.hermes
```

## Configuration

`hermes/triage-config.json` lists the GitHub Projects (v2) the triage serves and their repositories:

```json
{"projects": [{"owner": "<user or organization>", "number": 1,
               "repos": {"<repo>": {"product": "<option of the Product field>",
                                    "labels": {"<label>": "<when triage may set it>"}}}}]}
```

`product` and `labels` are optional; repository names must be unique across the file. The script
looks up the project's fields by name at every run. Required: Status (Backlog, Needs decision,
Reject proposed, Ready, In progress, Done), Estimate (number) and Next step (Ideate, Brainstorm,
Decide, Debug, Reject, Done), and the owner's issue types Bug, Feature and Task. A project missing
any of them is skipped with one notice; the others keep running.

Agents: read `AGENTS.md` first.

## License

MIT, see `LICENSE`.
