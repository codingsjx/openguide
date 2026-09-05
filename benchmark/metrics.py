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
- assert_rate    : fraction of generated steps with a non-empty `evidence`,
                   i.e. NOT the "missing/unknown" fallback
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from benchmark.golden.schema import GoldenGuide
from benchmark.schema import GeneratedGuide

_MISSING_KINDS = {"missing", "unknown"}


def _norm(s: str) -> str:
    """Lowercase, strip punctuation/backticks and collapse whitespace."""
    s = s.replace("`", "").lower()
    s = re.sub(r"[^\w\s/.-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _step_matches(g_step, gen_steps) -> bool:
    """A generated step 'covers' a golden step if its title/summary shares a
    core keyword (norm over first words). Exact-enough matching is tuned for
    deterministic results, not fuzzy semantics."""
    target = _norm(g_step.title)
    for gs in gen_steps:
        cand = _norm(gs.title)
        if target and (target in cand or cand in target):
            return True
        # Also allow matching on expected_commands substring when title thin.
        for cmd in g_step.expected_commands:
            if cmd and _norm(cmd) in cand:
                return True
    return False


def _evidence_valid(ev_source: str, available_paths: set[str]) -> bool:
    """Check evidence.source 'path#L' resolves to a known repo file (ignore L)."""
    if not ev_source or ev_source.startswith(("http", "issue", "#", "https://github.com")):
        return False
    path = ev_source.split("#", 1)[0].lstrip("/")
    # Heuristic: known root file/dir prefix. Exact match preferred.
    return any(path == p or path.startswith(p + "/") for p in available_paths)


@dataclass
class MetricsResult:
    n_golden: int = 0
    n_gen: int = 0
    step_coverage: float = 0.0
    evidence_hit: float = 0.0
    command_exec: float = 0.0
    assert_rate: float = 1.0  # if no steps, treat as no assertions
    missing_commands: list[str] = field(default_factory=list)


def compute(
    golden: GoldenGuide,
    generated: GeneratedGuide,
    available_paths: set[str] | None = None,
) -> MetricsResult:
    available_paths = available_paths or set()
    r = MetricsResult(n_golden=len(golden.steps), n_gen=len(generated.stages))
    if not golden.steps:
        return r

    covered = sum(1 for gs in golden.steps if _step_matches(gs, generated.stages))
    r.step_coverage = covered / len(golden.steps)

    # Evidence hit across generated command steps (those carrying a command).
    cmd_steps = [s for s in generated.stages if s.command]
    if cmd_steps:
        hits = sum(1 for s in cmd_steps if _evidence_valid(s.evidence.source, available_paths))
        r.evidence_hit = hits / len(cmd_steps)

    # Assert rate: non-missing evidence across all generated steps.
    if generated.stages:
        with_evidence = sum(
            1 for s in generated.stages if s.evidence.kind not in _MISSING_KINDS
        )
        r.assert_rate = with_evidence / len(generated.stages)

    # Command executable: for python repos we cannot truly run here; report as
    # 0% with the missing list, so L3/offline runner can fill from a real shell.
    for s in generated.stages:
        if s.command and not s.command.strip():
            r.missing_commands.append(s.title)
    if cmd_steps and not r.missing_commands and r.evidence_hit < 1.0:
        pass  # fill real exec rate in the offline runner
    return r


def merge_summary(results: list[MetricsResult]) -> dict:
    """Aggregate a list of per-repo metrics into one summary dict."""
    if not results:
        return {}
    keys = ["step_coverage", "evidence_hit", "command_exec", "assert_rate"]
    agg: dict[str, float] = {}
    for k in keys:
        vals = [getattr(r, k) for r in results]
        agg[k] = round(sum(vals) / len(vals), 3)
    agg["n_repos"] = len(results)
    agg["total_golden_steps"] = sum(r.n_golden for r in results)
    agg["total_gen_steps"] = sum(r.n_gen for r in results)
    return agg
