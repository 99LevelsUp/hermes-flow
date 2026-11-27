"""One-time: estimate-history comments from the triage ledger (issues without one yet)."""
import collections, importlib.util as u, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

s = u.spec_from_file_location("t", __import__("pathlib").Path(__file__).resolve().parent.parent / "skills/roadmap-issue-flow/scripts/issue-triage.py")
t = u.module_from_spec(s)
s.loader.exec_module(t)
DRY = "--dry-run" in sys.argv

rows = collections.defaultdict(list)
for line in open(t.LEDGER):
    x = json.loads(line)
    if x.get("stage") != "triage" or not x.get("minutes") or str(x.get("dry_run")).lower() == "true":
        continue
    basis = x.get("rationale") or (x.get("record") or {}).get("estimate_basis") or ""
    rows[(x["repo"], int(x["issue"]))].append((x["ts"], int(float(x["minutes"])), basis))


def one(item):
    (repo, number), entries = item
    issue = {"repo": repo, "number": number}
    if t.find_comment(issue, t.ESTIMATES_MARK):
        return f"{repo}#{number}: has history, skipped"
    lines, prev = [], None
    for i, (ts, minutes, basis) in enumerate(sorted(entries)):
        date = datetime.fromisoformat(ts).astimezone().strftime("%d.%m.%Y")
        lines.append(t.estimate_row(date, "Triage" if i == 0 else "Triage (again)", minutes, prev, basis))
        prev = minutes
    body = t.finish_body([t.ESTIMATE_HEADER + "\n" + "\n".join(lines)])
    if DRY:
        return body if (repo, number) == ("ev3-c", 23) else f"{repo}#{number}: {len(lines)} rows (dry)"
    t.upsert_comment(issue, t.ESTIMATES_MARK, body)
    __import__("time").sleep(4)
    return f"{repo}#{number}: {len(lines)} rows"


items = sorted(rows.items())
if DRY:
    items = [i for i in items if i[0] in (("ev3-c", 23), ("ev3-cockpit", 90))]
with ThreadPoolExecutor(1) as ex:
    out = list(ex.map(one, items))
print("\n".join(out[:5]), f"\n... {len(out)} issues")
