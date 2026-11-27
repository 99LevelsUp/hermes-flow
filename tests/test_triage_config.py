"""Tests of the triage script's per-project configuration and of pure decision functions.

Standard library only: python3 -m unittest discover -s tests
"""
import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "roadmap-issue-flow", "scripts", "issue-triage.py")
REPO_CONFIG = os.path.join(ROOT, "hermes", "triage-config.json")

spec = importlib.util.spec_from_file_location("issue_triage", SCRIPT)
assert spec and spec.loader
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
# tests never touch the live data directory (log, ledger, state, context)
_DATA = tempfile.mkdtemp(prefix="triage-test-")
for _name in ("HOME", "MIRRORS", "CONTEXT", "LEDGER", "STATE", "LOG"):
    if hasattr(t, _name):
        setattr(t, _name, os.path.join(_DATA, os.path.basename(getattr(t, _name))))
setattr(t, "HOME", _DATA)

STATUS = ("Backlog", "Needs decision", "Reject proposed", "Ready", "In progress", "Done")
NEXT = ("Ideate", "Brainstorm", "Decide", "Debug", "Reject", "Done")


def board(tag, product=("P",), drop_field=None, drop_option=None):
    """A fake projectV2 node; every ID carries tag so tests can tell projects apart."""
    def select(name, options):
        opts = [{"id": f"{tag}-{name}-{o}", "name": o} for o in options if (name, o) != drop_option]
        return {"id": f"{tag}-F-{name}", "name": name, "options": opts}
    fields = [select("Status", STATUS), {"id": f"{tag}-F-Estimate", "name": "Estimate"},
              select("Next step", NEXT), select("Product", product), {"id": f"{tag}-F-Title", "name": "Title"}]
    return {"id": f"{tag}-PROJECT", "fields": {"nodes": [f for f in fields if f["name"] != drop_field]}}


NOT_FOUND = "graphql errors: [{'type': 'NOT_FOUND', 'message': 'Could not resolve to a %s'}]"


def fake_gql(boards, types=("Bug", "Feature", "Task")):
    """Answers discovery queries the way GitHub does: something missing is an error, not empty data."""
    def gql(query, retry=True, **v):
        if query is t.DISCOVER_Q:
            b = boards.get((v["owner"], v["n"]))
            if not b:
                raise RuntimeError(NOT_FOUND % "ProjectV2")
            return {"repositoryOwner": {"projectV2": b}}
        if query is t.TYPES_Q:
            if v["repo"] == "missing":
                raise RuntimeError(NOT_FOUND % "Repository")
            return {"repository": {"issueTypes": {"nodes": [{"id": f"T-{v['owner']}-{n}", "name": n}
                                                             for n in types]}}}
        raise AssertionError(f"unexpected query {query[:40]}")
    return gql


def write_config(data):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def project(owner="o", number=1, repos=None):
    return {"owner": owner, "number": number, "repos": repos or {"a": {}}}


class LoadConfig(unittest.TestCase):
    def load(self, data):
        path = write_config(data)
        try:
            return t.load_config(path)
        finally:
            os.unlink(path)

    def test_repository_configuration_is_valid(self):
        projects = t.load_config(REPO_CONFIG)
        self.assertTrue(projects)
        for p in projects:
            self.assertIsInstance(p.number, int)

    def test_two_projects(self):
        ps = self.load({"projects": [project("o", 1, {"a": {"product": "A"}}), project("o", 2, {"b": {}})]})
        self.assertEqual([(p.owner, p.number, list(p.repos)) for p in ps], [("o", 1, ["a"]), ("o", 2, ["b"])])

    def test_missing_file(self):
        with self.assertRaises(t.ConfigError):
            t.load_config("/nonexistent/config.json")

    def test_invalid_json(self):
        path = write_config({})
        with open(path, "w") as f:
            f.write("{not json")
        try:
            with self.assertRaises(t.ConfigError):
                t.load_config(path)
        finally:
            os.unlink(path)

    def test_rejects_bad_shapes(self):
        for data in ({}, {"projects": []}, {"projects": {}}, {"projects": ["x"]},
                     {"projects": [{"owner": "o", "number": "3", "repos": {"a": {}}}]},
                     {"projects": [{"owner": "", "number": 3, "repos": {"a": {}}}]},
                     {"projects": [{"owner": "o", "number": 3, "repos": {}}]},
                     {"projects": [project(repos={"a": {"labels": ["x"]}})]},
                     {"projects": [project(repos={"a": "x"})]},
                     {"projects": [{"owner": "o", "number": True, "repos": {"a": {}}}]},
                     {"projects": [{"owner": "o", "number": 0, "repos": {"a": {}}}]},
                     {"projects": [{**project(), "extra": 1}]},
                     {"projects": [project()], "other": 1},
                     {"projects": [project(repos={"a": {"label": {}}})]},
                     {"projects": [project(repos={"a": {"product": ["P"]}})]},
                     {"projects": [project(repos={"a": {"labels": {"x": ["y"]}}})]}):
            with self.subTest(data=data), self.assertRaises(t.ConfigError):
                self.load(data)

    def test_repository_names_must_be_unique(self):
        with self.assertRaises(t.ConfigError):
            self.load({"projects": [project("o", 1, {"a": {}}), project("p", 2, {"a": {}})]})


class Discover(unittest.TestCase):
    def discover(self, b, repos=None, types=("Bug", "Feature", "Task")):
        p = t.Project("o", 1, repos or {"a": {"product": "P"}})
        with mock.patch.object(t, "gql", fake_gql({("o", 1): b} if b else {}, types)):
            t.discover(p)
        return p

    def test_ids_by_name(self):
        p = self.discover(board("X"))
        self.assertEqual(p.id, "X-PROJECT")
        self.assertEqual(p.field("Next step"), "X-F-Next step")
        self.assertEqual(p.option("Status", "Reject proposed"), "X-Status-Reject proposed")
        self.assertEqual(p.types["Task"], "T-o-Task")
        self.assertEqual(p.product("a"), "P")

    def test_missing_project(self):
        with self.assertRaises(t.ConfigError):
            self.discover(None)

    def test_missing_required_field(self):
        for name in ("Status", "Estimate", "Next step"):
            with self.subTest(name=name), self.assertRaises(t.ConfigError):
                self.discover(board("X", drop_field=name))

    def test_missing_required_option(self):
        for field, option in (("Status", "Reject proposed"), ("Next step", "Done"), ("Next step", "Debug")):
            with self.subTest(option=option), self.assertRaises(t.ConfigError):
                self.discover(board("X", drop_option=(field, option)))

    def test_missing_issue_type(self):
        with self.assertRaises(t.ConfigError):
            self.discover(board("X"), types=("Bug", "Feature"))

    def test_unknown_repository(self):
        with self.assertRaises(t.ConfigError):
            self.discover(board("X"), repos={"a": {}, "missing": {}})

    def test_outage_is_not_a_configuration_error(self):
        p = t.Project("o", 1, {"a": {}})
        for err, kind in ((t.Outage("502 bad gateway"), t.Outage), (RuntimeError("graphql errors: boom"), RuntimeError)):
            def gql(*a, err=err, **k):
                raise err
            with self.subTest(err=err), mock.patch.object(t, "gql", gql), self.assertRaises(kind) as cm:
                t.discover(p)
            self.assertNotIsInstance(cm.exception, t.ConfigError)

    def test_product_is_optional(self):
        p = self.discover(board("X", drop_field="Product"), repos={"a": {}})
        self.assertIsNone(p.product("a"))

    def test_configured_product_must_exist(self):
        with self.assertRaises(t.ConfigError):
            self.discover(board("X", product=("Other",)))


class Configure(unittest.TestCase):
    """The run-level flow: a bad project is skipped with one notice; the owner hears again only on change."""

    def setUp(self):
        self.state = {"config_noticed": {}}
        self.boards = {("o", 1): board("ONE")}
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "config.json")

    def tearDown(self):
        t.use_projects([])
        self.dir.cleanup()

    def run_once(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)
        notices = []
        try:
            with mock.patch.object(t, "gql", fake_gql(self.boards)):
                t.configure(self.path, self.state, notices)
            return notices, None
        except t.ConfigError as e:
            return notices, e

    def test_skipped_project_noticed_once_and_cleared_when_fixed(self):
        data = {"projects": [project("o", 1, {"a": {}}), project("o", 2, {"b": {}})]}
        notices, err = self.run_once(data)
        self.assertIsNone(err)
        self.assertEqual(len(notices), 1)
        self.assertIn("o/projects/2 skipped", notices[0])
        self.assertEqual([str(p) for p in t.PROJECTS], ["o/projects/1"])
        self.assertEqual(self.run_once(data)[0], [])                   # same problem: silent
        self.boards[("o", 2)] = board("TWO")
        notices, _ = self.run_once(data)
        self.assertEqual((notices, self.state["config_noticed"]), ([], {}))
        self.assertEqual(len(t.PROJECTS), 2)

    def test_broken_configuration_stops_the_run_with_one_notice(self):
        notices, err = self.run_once({"projects": []})
        self.assertIsInstance(err, t.ConfigError)
        self.assertEqual(len(notices), 1)
        self.assertIn("Triage not run", notices[0])
        self.assertEqual(self.run_once({"projects": []})[0], [])
        self.assertEqual(self.run_once({"projects": [project("o", 1)]}), ([], None))
        self.assertEqual(self.state["config_noticed"], {})

    def test_no_project_can_run(self):
        notices, err = self.run_once({"projects": [project("o", 9)]})
        self.assertIsInstance(err, t.ConfigError)
        self.assertEqual(len(notices), 1)


class EvreRoadmapUnchanged(unittest.TestCase):
    """The repository configuration gives the EVƎ roadmap what the script hard-coded before #31."""

    def test_labels_and_products(self):
        p = next(p for p in t.load_config(REPO_CONFIG) if (p.owner, p.number) == ("99LevelsUp", 3))
        common = {"needs-brick", "documentation", "security", "good first issue", "needs-prototype", "needs-bakeoff"}
        self.assertEqual(set(p.labels("ev3-c")), common | {"education", "accessibility"})
        self.assertEqual(set(p.labels("ev3-cockpit")), common)
        self.assertEqual({r: c.get("product") for r, c in p.repos.items()},
                         {"ev3-c": "EVƎ C", "ev3-cockpit": "EVƎ Cockpit"})


class Records(unittest.TestCase):
    def test_any_collaborator_but_no_outsider(self):
        comments = [{"id": 1, "body": "<!-- m -->old", "author_association": "OWNER"},
                    {"id": 2, "body": "<!-- m -->taken over", "author_association": "COLLABORATOR"},
                    {"id": 3, "body": "<!-- m -->forged", "author_association": "NONE"},
                    {"id": 4, "body": "<!-- other -->", "author_association": "OWNER"}]
        self.assertEqual(t.newest_record(comments, "<!-- m -->"), (2, "<!-- m -->taken over"))
        self.assertIsNone(t.newest_record(comments[2:], "<!-- m -->"))


class Labels(unittest.TestCase):
    def setUp(self):
        t.use_projects([t.Project("o", 1, {"a": {"labels": {"needs-brick": "hardware"}}})])

    def tearDown(self):
        t.use_projects([])

    def plan(self, labels, add=(), remove=(), next_step="Brainstorm"):
        issue = {"repo": "a", "labels": list(labels), "status": "Backlog"}
        return t.plan_labels(issue, {"labels_add": list(add), "labels_remove": list(remove), "next_step": next_step})

    def test_agent_alone_when_nothing_needs_a_human(self):
        self.assertEqual(self.plan([], ["good first issue"]), (["good first issue"], []))

    def test_never_agent_alone_when_a_human_is_needed(self):
        for labels, add, step in (([], ["good first issue"], "Decide"),
                                  ([], ["good first issue"], "Ideate"),
                                  ([], ["good first issue", "needs-brick"], "Brainstorm"),
                                  (["help wanted"], ["good first issue"], "Brainstorm")):
            with self.subTest(labels=labels, add=add, step=step):
                self.assertNotIn("good first issue", self.plan(labels, add, next_step=step)[0])

    def test_agent_alone_removed_when_it_no_longer_holds(self):
        self.assertEqual(self.plan(["good first issue"], ["needs-brick"]), (["needs-brick"], ["good first issue"]))
        self.assertEqual(self.plan(["good first issue"], next_step="Decide"), ([], ["good first issue"]))

    def test_idea_and_defaults_are_left_alone(self):
        self.assertEqual(self.plan(["idea", "bug"], ["idea", "wontfix"], ["idea", "bug"]), ([], []))

    def test_contradictions(self):
        self.assertEqual(t.label_contradictions(["bug", "question"], "Feature", "Brainstorm"),
                         ["label bug, but the issue type is Feature",
                          "label question, but the next step is Brainstorm, not Decide"])
        self.assertEqual(t.label_contradictions(["enhancement", "duplicate"], "Bug", "Debug"),
                         ["label enhancement, but the issue type is Bug",
                          "label duplicate, but the next step is Debug, not Reject"])
        self.assertEqual(t.label_contradictions(["bug", "wontfix"], "Bug", "Reject"), [])


class TwoProjects(unittest.TestCase):
    """Writes and lookups go to the issue's own project."""

    def setUp(self):
        self.p1 = t.Project("o", 1, {"a": {"product": "P", "labels": {"hw": "needs hardware"}}, "b": {}})
        self.p2 = t.Project("q", 2, {"c": {}})
        with mock.patch.object(t, "gql", fake_gql({("o", 1): board("ONE"), ("q", 2): board("TWO")})):
            t.discover(self.p1)
            t.discover(self.p2)
        t.use_projects([self.p1, self.p2])

    def tearDown(self):
        t.use_projects([])

    def test_set_field_uses_the_issue_project(self):
        calls = []
        with mock.patch.object(t, "gh", lambda *a, **k: calls.append(a)):
            t.set_field({"repo": "c", "item": "I"}, "Next step", option="Decide")
            t.set_field({"repo": "a", "item": "J"}, "Estimate", number=90)
        self.assertEqual(calls[0], ("project", "item-edit", "--project-id", "TWO-PROJECT", "--id", "I",
                                    "--field-id", "TWO-F-Next step", "--single-select-option-id",
                                    "TWO-Next step-Decide"))
        self.assertEqual(calls[1], ("project", "item-edit", "--project-id", "ONE-PROJECT", "--id", "J",
                                    "--field-id", "ONE-F-Estimate", "--number", "90"))

    def test_issues_api_uses_the_project_owner(self):
        self.assertEqual(t.issues_api({"repo": "c"}, 5, "comments"), "repos/q/c/issues/5/comments")

    def test_node_key_checks_the_owner(self):
        node = {"repository": {"nameWithOwner": "q/c"}, "number": 7}
        self.assertEqual(t.node_key(node), t.issue_key("c", 7))
        self.assertIsNone(t.node_key({"repository": {"nameWithOwner": "o/c"}, "number": 7}))
        self.assertIsNone(t.node_key({"repository": {"nameWithOwner": "o/zzz"}, "number": 7}))

    def test_mentions_stay_within_the_project(self):
        text = "see #3, b#4, c#5 (other project), zzz#6, #3 again and a#9"
        self.assertEqual(t.mention_keys(text, "a"), [t.issue_key("a", 3), t.issue_key("b", 4), t.issue_key("a", 9)])
        self.assertEqual(t.mention_keys("#3 and a#4", "c"), [t.issue_key("c", 3)])

    def test_labels_per_repository(self):
        self.assertIn("hw", t.proj("a").labels("a"))
        self.assertNotIn("hw", t.proj("b").labels("b"))
        self.assertIn("security", t.proj("c").labels("c"))
        issue = {"repo": "b", "labels": [], "status": "Backlog"}
        add, _ = t.plan_labels(issue, {"labels_add": ["hw", "security", "idea", "bug"], "labels_remove": [],
                                       "next_step": "Brainstorm"})
        self.assertEqual(add, ["security"])     # hw belongs to repo a; idea is gone; defaults are not ours

    def test_label_rules_name_the_repository(self):
        text = t.label_rules(self.p1)
        self.assertIn("- hw (only in a): needs hardware", text)
        self.assertNotIn("needs-prototype", text)     # flags are listed separately
        self.assertIn("needs-prototype", t.rules(self.p1))

    def test_product_only_where_configured(self):
        calls = []
        with mock.patch.object(t, "gh", lambda *a, **k: calls.append(a)):
            changes = []
            t.ensure_item({"repo": "a", "item": "I", "product": None, "status": "Backlog"}, False, None, changes)
            t.ensure_item({"repo": "c", "item": "J", "product": None, "status": "Backlog"}, False, None, changes)
        self.assertEqual(changes, ["Product=P"])
        self.assertEqual(len(calls), 1)

    def test_batches_never_mix_projects(self):
        work = [{"mode": "full", "issue": {"repo": r, "key": t.issue_key(r, n), "trusted": True}, "cands": {}}
                for r, n in (("a", 1), ("c", 2), ("b", 3))]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(t, "CONTEXT", d), \
                mock.patch.object(t, "write_context", lambda issue, cands, batch_dir: "f"):
            batches = t.make_batches(work)
        self.assertEqual(sorted(sorted(w["issue"]["repo"] for w in b) for _, b, _ in batches), [["a", "b"], ["c"]])

    def test_candidates_stay_within_the_project(self):
        sibling = {"id": "N", "title": "t", "state": "OPEN", "body": "", "authorAssociation": "OWNER"}
        parent = {"repository": {"nameWithOwner": "o/a"}, "number": 1, "subIssues": {"nodes": [
            {**sibling, "number": 2, "repository": {"nameWithOwner": "o/b"}},
            {**sibling, "number": 3, "repository": {"nameWithOwner": "q/c"}}]}}
        issue = {"key": t.issue_key("a", 5), "repo": "a", "title": "", "body": "", "related": set(), "subs": [],
                 "parent": parent, "related_complete": True, "author_trusted": False, "comments": []}
        with mock.patch.object(t, "hybrid_search", lambda repo, q: []):
            cands, complete = t.find_candidates(issue)
        self.assertEqual(list(cands), [t.issue_key("b", 2)])

    def test_label_names_are_encoded_in_the_path(self):
        calls = []
        with mock.patch.object(t, "gh", lambda *a, **k: calls.append(a)):
            t.apply_labels({"repo": "a", "number": 4}, [], ["good first issue"], False, [])
        self.assertEqual(calls[0][-1], "repos/o/a/issues/4/labels/good%20first%20issue")

    def test_prompt_names_the_project_owner_and_mirrors(self):
        batch = [{"issue": {"repo": "c", "key": t.issue_key("c", 1)}, "context": "x.md"}]
        text = t.prompt_full(batch)
        self.assertIn("of the owner q", text)
        self.assertIn("only the owner, q, can decide", text)
        self.assertIn(os.path.join(t.MIRRORS, "c"), text)
        self.assertNotIn(os.path.join(t.MIRRORS, "a"), text)


def summary(**kw):
    s = dict(key="a#1", open=True, reason=None, next_step=None, estimate=None, item="I", subs_total=0,
             reopened=False, author_trusted=True)
    s.update(kw)
    return s


class WantedMode(unittest.TestCase):
    def test_modes(self):
        state = {"relations_checked": {"a#2": "x"}}
        cases = [
            (summary(), "full"),
            (summary(estimate=60), "full"),
            (summary(estimate=60, next_step="Brainstorm"), "relations"),
            (summary(key="a#2", estimate=60, next_step="Brainstorm"), None),
            (summary(subs_total=2), "umbrella"),
            (summary(next_step="Done"), None),
            (summary(next_step="Done", reopened=True), "full"),
            (summary(open=False, reason="COMPLETED"), "closed"),
            (summary(open=False, next_step="Done"), None),
            (summary(open=False, item=None, reason="COMPLETED", author_trusted=False), None),
            (summary(open=False, item=None, reason="NOT_PLANNED"), None),
        ]
        for s, want in cases:
            with self.subTest(s=s):
                self.assertEqual(t.wanted_mode(s, state), want)


def node(subs=(), estimate=None, status=None, open_=True, reason=None):
    return dict(subs=list(subs), subs_total=len(subs), estimate=estimate, status=status, open=open_, reason=reason)


class UmbrellaPlan(unittest.TestCase):
    def test_sum_and_least_advanced_status(self):
        index = {"u": node(["a", "b", "c"], status="Backlog"),
                 "a": node(estimate=30, status="Ready"),
                 "b": node(estimate=60, status="In progress"),
                 "c": node(estimate=90, open_=False, reason="NOT_PLANNED")}
        self.assertEqual(t.umbrella_plan(index)["u"], (90, 2, 0, "Ready"))

    def test_recursive_and_missing_estimates(self):
        index = {"u": node(["v", "x"]), "v": node(["a", "b"]), "a": node(estimate=10, status="Ready"),
                 "b": node(status="Needs decision"), "x": node(estimate=5, status="Done", open_=False,
                                                                  reason="COMPLETED")}
        plan = t.umbrella_plan(index)
        self.assertEqual(plan["v"], (10, 2, 1, "Needs decision"))
        self.assertEqual(plan["u"], (15, 2, 1, "Needs decision"))

    def test_all_done_stays_in_progress_until_the_final_check(self):
        index = {"u": node(["a"], status="In progress"), "a": node(estimate=10, open_=False, reason="COMPLETED")}
        self.assertEqual(t.umbrella_plan(index)["u"][3], "In progress")

    def test_cycle_and_unknown_children_count_as_missing(self):
        index = {"u": node(["v", "zzz"]), "v": node(["u"])}
        est, counted, missing, _ = t.umbrella_plan(index)["u"]
        self.assertEqual((est, missing), (0, 2))


if __name__ == "__main__":
    unittest.main()
