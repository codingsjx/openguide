"""Metrics used by L2/L3 to score a generated guide against a golden guide.

All metrics are rule-based and deterministic. They operate on normalised text so
the same computed numbers can be re-derived by an independent script (evidence
for the "可验证" narrative).

Definitions:
- step_coverage  : fraction of golden steps that have a matching generated step
- evidence_hit   : fraction of generated *command steps* whose evidence.source
                   resolves to a real file in the repo (verified offline)
- command_exec   : fraction of generated command steps whose command can be
                   executed against a local clone (best-effort; may be skipped)
- command_correct: fraction of generated command steps whose command matches the
                   golden reference command for that step's stage — this is the
                   "semantic correctness" dimension (跑对没有，而非只是跑得动)
- assert_rate    : fraction of generated steps with a non-empty `evidence`,
                   i.e. NOT the "missing/unknown" fallback

`elapsed_s` is wall-clock generation time for the repo, recorded by the runner
(not by `compute`). It is what backs the "成本/延迟" column of the L3 ablation:
the layered pipeline does more work per repo, so the comparison must show the
latency it costs, not just the quality it buys.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from benchmark.golden.schema import GoldenGuide
from benchmark.schema import GeneratedGuide

_MISSING_KINDS = {"missing", "unknown"}

# Issue refs: "#42" | "issues/42" | "pull/42" | a full github issue URL.
_ISSUE_URL_RE = re.compile(r"github\.com/[^/]+/[^/]+/issues/(\d{1,6})")
_ISSUE_PATH_RE = re.compile(r"^(?:issues|pull)/(\d{1,6})$")


def _norm(s: str) -> str:
    """Lowercase, strip punctuation/backticks and collapse whitespace."""
    s = s.replace("`", "").lower()
    s = re.sub(r"[^\w\s/.-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    """Meaningful tokens from a normalised title (drop 1-char fragments)."""
    return {t for t in re.findall(r"[a-z0-9一-鿿]+", s) if len(t) >= 2}


def _stage_of(stage: str) -> str:
    """Normalise 'A 环境搭建' / 'B 测试基线' / 'A' to the stage letter."""
    return (stage or "").strip().split()[0].upper()


def _step_matches(g_step, gen_steps) -> bool:
    """A generated step 'covers' a golden step when they share the same stage
    (A/B/C/D) AND either their titles share a meaningful token or the generated
    step's command shares a verb with the golden reference command.

    This replaces the old 'title substring' rule, which was too strict — it
    treated '运行测试套件' vs '运行测试基线' as no match and reported 0% coverage.
    """
    g_stage = _stage_of(g_step.stage)
    g_tokens = _tokens(_norm(g_step.title))
    for gs in gen_steps:
        if _stage_of(gs.stage) != g_stage:
            continue
        # Title-token overlap.
        if g_tokens and g_tokens & _tokens(_norm(gs.title)):
            return True
        # Command-verb overlap (tolerates flag/whitespace drift).
        if gs.command:
            g_verb = _norm(gs.command).split()
            for ref in g_step.expected_commands:
                r = _norm(ref).split()
                if g_verb and r and g_verb[0] == r[0]:
                    return True
    return False


def _path_in_repo(path: str, available_paths: set[str]) -> bool:
    """Exact repo-relative path lookup (case-insensitive).

    Deliberately NOT a prefix match: `docs/whatever.md` must not count as "hit"
    merely because a `docs` directory exists somewhere in the tree. A fabricated
    filename should fail to resolve, so 无证据不宣称 is actually measurable.
    """
    p = path.lstrip("/").lower()
    if not p:
        return False
    # Both sides are normalised: callers may hand us real on-disk paths, which
    # carry the repo's own casing (Makefile vs makefile).
    normalised = {a.lower() for a in available_paths}
    if p in normalised:
        return True
    # Tolerate a leading-dot difference ("/.github/x" vs ".github/x").
    return p.lstrip(".") in normalised


def _evidence_valid(ev_source: str, available_paths: set[str], issue_numbers: set[str] | None = None) -> bool:
    """Does evidence.source resolve to something real in the repo?

    Accepts BOTH kinds the pipeline can emit:
    - a repo file path "path#L22"  -> must exist exactly in available_paths
    - an issue reference "#42" / "issues/42" / a github issue URL -> must be a
      real issue number we listed during recon (V4 chunks are anchored this way,
      so excluding them made every issue-backed step unscoreable).
    """
    src = (ev_source or "").strip()
    if not src:
        return False
    issue_numbers = issue_numbers or set()

    m = _ISSUE_URL_RE.search(src)
    if m:
        return m.group(1) in issue_numbers
    if src.startswith("#") and src[1:].isdigit():
        return src[1:] in issue_numbers
    m2 = _ISSUE_PATH_RE.match(src.split("#", 1)[0].strip("/"))
    if m2:
        return m2.group(1) in issue_numbers

    if src.startswith(("http://", "https://")):
        return False  # a bare URL is not a verifiable in-repo source
    return _path_in_repo(src.split("#", 1)[0], available_paths)


def _command_matches_stage(gen_cmd: str, golden_commands: list[str]) -> bool:
    """Does a generated command match any golden reference command for the same
    step? Normalise both, then require a shared *verb* (first token) — this
    catches 'pip install' vs 'pytest' drift while tolerating flag/whitespace
    differences. If the golden step has no reference commands, the generated
    command cannot be 'correct' (there is nothing to match against)."""
    if not golden_commands:
        return False
    g = _norm(gen_cmd)
    for ref in golden_commands:
        r = _norm(ref)
        if not r:
            continue
        # Exact or substring match is the strong signal.
        if g == r or r in g or g in r:
            return True
        # Verb-level match: 'python -m pytest tests' vs 'pytest -q' share 'pytest'.
        g_verb = g.split()[0]
        r_verb = r.split()[0]
        if g_verb == r_verb:
            return True
    return False


@dataclass
class MetricsResult:
    n_golden: int = 0
    n_gen: int = 0
    step_coverage: float = 0.0
    evidence_hit: float = 0.0
    command_exec: float = 0.0
    command_correct: float = 0.0
    assert_rate: float = 1.0  # if no steps, treat as no assertions
    missing_commands: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0  # wall-clock generation time, filled by the runner


def compute(
    golden: GoldenGuide,
    generated: GeneratedGuide,
    available_paths: set[str] | None = None,
    issue_numbers: set[str] | None = None,
) -> MetricsResult:
    available_paths = available_paths or set()
    r = MetricsResult(n_golden=len(golden.steps), n_gen=len(generated.stages))
    if not golden.steps:
        return r

    covered = sum(1 for gs in golden.steps if _step_matches(gs, generated.stages))
    r.step_coverage = covered / len(golden.steps)

    # Evidence hit across ALL generated steps, not just command-carrying ones.
    # The C (选 issue) / D (首 PR) stages carry no command but are exactly where
    # evidence matters most — excluding them made the 证据命中率 blind to the
    # steps most prone to fabrication. Steps with no evidence at all score as
    # misses rather than being dropped from the denominator.
    if generated.stages:
        hits = sum(
            1
            for s in generated.stages
            if _evidence_valid(s.evidence.source, available_paths, issue_numbers)
        )
        r.evidence_hit = hits / len(generated.stages)

    # Assert rate: non-missing evidence across all generated steps.
    if generated.stages:
        with_evidence = sum(
            1 for s in generated.stages if s.evidence.kind not in _MISSING_KINDS
        )
        r.assert_rate = with_evidence / len(generated.stages)

    # Command executable: the real rate is measured by the runner (which has a
    # shell + a clone) and injected via `m.command_exec = exec_rate`. Here we
    # only collect commands that cannot be executed because they are empty.
    for s in generated.stages:
        if s.command and not s.command.strip():
            r.missing_commands.append(s.title)

    # Command correctness: does each generated command match the golden
    # reference command for its stage? Build a stage -> reference-commands map.
    cmd_steps = [s for s in generated.stages if s.command]
    ref_by_stage: dict[str, list[str]] = {}
    for gs in golden.steps:
        ref_by_stage.setdefault(gs.stage.split()[0], []).extend(gs.expected_commands)
    if cmd_steps:
        correct = sum(
            1
            for s in cmd_steps
            if _command_matches_stage(s.command, ref_by_stage.get(s.stage, []))
        )
        r.command_correct = correct / len(cmd_steps)
    return r


def merge_summary(results: list[MetricsResult]) -> dict:
    """Aggregate a list of per-repo metrics into one summary dict."""
    if not results:
        return {}
    keys = ["step_coverage", "evidence_hit", "command_exec", "command_correct", "assert_rate"]
    agg: dict[str, float] = {}
    for k in keys:
        vals = [getattr(r, k) for r in results]
        agg[k] = round(sum(vals) / len(vals), 3)
    agg["n_repos"] = len(results)
    agg["total_golden_steps"] = sum(r.n_golden for r in results)
    agg["total_gen_steps"] = sum(r.n_gen for r in results)
    # Latency: per-repo mean (comparable across arms) + total (cost of the run).
    agg["elapsed_s_mean"] = round(sum(r.elapsed_s for r in results) / len(results), 2)
    agg["elapsed_s_total"] = round(sum(r.elapsed_s for r in results), 2)
    return agg
