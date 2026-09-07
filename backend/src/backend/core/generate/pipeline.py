"""Guide-generation pipeline (module 3).

Flow: enrich repo signals -> build perspective index -> for each stage A..D
retrieve the evidence snippets relevant to that stage -> ask the LLM to fill
GuideStep JSON -> post-verify every step's evidence against the repo (无证据
不宣称) -> return a Guide.

Two execution modes:
- `llm=True` (default): call the configured LLM via prompts.py.
- `llm=False` / no key: fall back to a *deterministic heuristic generator*
  (rules + retrieved snippets) so the API + demo work offline and CI can
  exercise the pipeline without a key. Benchmark L2 can score this too, making
  the "without an LLM key" path honest rather than skipped.
"""

from __future__ import annotations

from backend.core.decide.decider import decide
from backend.core.generate.evidence import available_sources, resolve_evidence_source
from backend.core.generate.llm import LLMClient, LLMUnavailable
from backend.core.generate.prompts import build_stage_messages, step_from_llm_json
from backend.core.generate.schemas import Evidence, Guide, GuideStep
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex
from backend.core.profile.builder import build_profile

_STAGE_LABELS = {"A": "环境搭建", "B": "测试基线", "C": "挑选 issue", "D": "首次 PR 路径"}

# Which perspectives each stage should retrieve from.
_STAGE_PERSPECTIVES = {
    "A": "setup",
    "B": "test",
    "C": "issue",
    "D": "contribute",
}


def build_guide(
    sig: RawSignals,
    index: RepoIndex | None = None,
    use_llm: bool = True,
) -> Guide:
    profile = build_profile(sig)
    suitability, reasons = decide(profile)
    repo_url = f"https://github.com/{profile.owner}/{profile.repo}"
    guide = Guide(
        repo_url=repo_url,
        owner=profile.owner,
        repo=profile.repo,
        unsuitable=(suitability == "avoid"),
        reasons=reasons,
    )
    if suitability == "avoid":
        return guide  # 不适合则只给理由，不硬生成（帮新手避坑）

    index = index or _build_index(sig)
    steps: list[GuideStep] = []
    step_id = 1

    if use_llm:
        try:
            client = LLMClient()
            if client.available():
                steps = _generate_with_llm(sig, index, client, start_id=step_id)
            else:
                steps = _generate_heuristic(sig, index, start_id=step_id)
        except LLMUnavailable:
            steps = _generate_heuristic(sig, index, start_id=step_id)
    else:
        steps = _generate_heuristic(sig, index, start_id=step_id)

    guide.steps = _verify_and_relabel(sig, steps)
    # Second pass: try to find a real source for still-missing steps by
    # re-searching the index with the step's own title/command.
    guide.steps = _backfill_evidence(sig, index, guide.steps)
    return guide


def _build_index(sig: RawSignals) -> RepoIndex:
    idx = RepoIndex(sig.meta.owner, sig.meta.repo)
    idx.index(sig)
    return idx


def _retrieve_for_stage(index: RepoIndex, stage: str, query: str) -> list[dict]:
    kind = _STAGE_PERSPECTIVES.get(stage, "setup")
    res = index.search(query, kind=kind, top_k=4)
    out: list[dict] = []
    for h in res.hits:
        # Prefer the chunk's real repo source (file path or issue ref) over the
        # perspective code; fall back to perspective only as a last resort.
        src = (h.meta or {}).get("source") or h.perspective
        kind_meta = (h.meta or {}).get("kind") or "file"
        out.append({"source": src, "text": h.text, "meta_kind": kind_meta})
    return out


def _generate_with_llm(sig, index, client, start_id: int) -> list[GuideStep]:
    """Stage-by-stage LLM generation, one request per stage."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        messages = build_stage_messages(stage, snippets)
        try:
            obj = client.chat_json(messages, temperature=0.2, max_tokens=1800)
        except LLMUnavailable:
            return out + _generate_heuristic(sig, index, start_id=sid)
        items = obj.get("steps") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            items = [obj]
        for it in items:
            st = step_from_llm_json(stage, it if isinstance(it, dict) else {}, sid)
            if st is None:
                continue
            st.step_id = sid
            sid += 1
            out.append(st)
    return out


_STAGE_QUERIES = {
    "A": "how to install dependencies and get the project running locally",
    "B": "how to run the test suite",
    "C": "good first issue for a new contributor to pick up",
    "D": "contribution workflow fork clone branch commit pull request",
}


def _generate_heuristic(sig: RawSignals, index: RepoIndex, start_id: int) -> list[GuideStep]:
    """Deterministic fallback: build steps from retrieved snippets by keyword."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        text = " ".join(s["text"] for s in snippets).lower()
        step = _heuristic_one(sig, stage, snippets, text)
        if step:
            step.step_id = sid
            sid += 1
            out.append(step)
    return out


_TITLES = {
    "A": "本地搭建并跑起来",
    "B": "运行测试基线",
    "C": "挑一个 good-first-issue",
    "D": "提交首个 PR",
}


def _heuristic_one(sig, stage: str, snippets: list[dict], text: str) -> GuideStep | None:
    """Deterministic fallback: honest steps + a real command if one is found.

    Scans line-by-line for shell commands (anchored, case-sensitive) so prose
    like "Python 3.10+" is not mistaken for a command. Evidence is attributed
    only when the snippet maps to a real source; otherwise kind=missing
    (无证据不宣称).
    """
    import re

    cmds: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        stripped = re.sub(r"^[$>]\s*", "", line).strip()
        # Match command prefixes as they actually appear in docs.
        if re.match(r"^(pip|python|python3|npm|npx|yarn|pnpm|cargo|make|git|docker|go)\b", stripped):
            cleaned = stripped.split("```")[0].strip()
            if cleaned and len(cleaned) < 140:
                cmds.append(cleaned)
        if len(cmds) >= 2:
            break
    seen: set[str] = set()
    cmds = [c for c in cmds if not (c in seen or seen.add(c))]

    expected = (
        f"运行 {cmds[0]} 并确认成功（无报错）" if cmds else "见仓库原文确认成功标志"
    )
    # Attribute real source from the first snippet when it maps to a file/issue;
    # perspective codes (v1..v4) are not real sources.
    ev_source = ""
    ev_kind = "missing"
    for s in snippets:
        src = s.get("source", "")
        mkind = s.get("meta_kind", "file")
        if mkind in ("file", "issue") and src and not src.startswith("v"):
            ev_source = src
            ev_kind = mkind
            break
    return GuideStep(
        step_id=0,
        stage=stage,  # type: ignore[arg-type]
        stage_label=_STAGE_LABELS[stage],
        title=_TITLES[stage],
        command=cmds[0] if cmds else None,
        expected=expected,
        fail_hints=["如卡住，把报错贴给 OpenGuide 的‘报错了’追问"],
        # Heuristic fallback marks evidence missing only when no real source is
        # retrievable (无证据不宣称).
        evidence=Evidence(kind=ev_kind, source=ev_source, quote=""),  # type: ignore[arg-type]
    )


def _verify_and_relabel(sig: RawSignals, steps: list[GuideStep]) -> list[GuideStep]:
    """Post-check every evidence against the repo; downgrade unverifiable ones.

    Perspective codes (v1..v4) and other non-repo identifiers are not accepted
    as evidence sources — only real file paths / issue refs we fetched pass.
    """
    avail = available_sources(sig)
    issue_nums = {i.get("number") for i in sig.issues if i.get("pull_request") is None}
    out: list[GuideStep] = []
    for st in steps:
        ev = st.evidence
        if ev.kind == "missing":
            out.append(st)
            continue
        # Reject perspective-code sources outright.
        if ev.source in {"v1", "v2", "v3", "v4"}:
            st.evidence = Evidence(kind="missing", source="", quote="")
            out.append(st)
            continue
        if ev.kind == "issue":
            num = ev.source.lstrip("#")
            if num.isdigit() and int(num) in issue_nums:
                out.append(st)
                continue
            st.evidence = Evidence(kind="missing", source="", quote="")
            out.append(st)
            continue
        # file: check source path exists in what we fetched.
        norm = ev.source.split("#", 1)[0].lower().strip("/")
        blob = __import__("re").search(r"blob/[^/]+/(.+)", ev.source.lower())
        if blob:
            norm = blob.group(1).split("#", 1)[0]
        if norm in avail or any(norm.startswith(p + "/") for p in avail):
            out.append(st)
            continue
        st.evidence = Evidence(kind="missing", source="", quote="")
        out.append(st)
    return out


def _backfill_evidence(sig, index: RepoIndex, steps: list[GuideStep]) -> list[GuideStep]:
    """For missing-evidence steps, search within the *stage-relevant*
    perspective(s) and attach a real repo source if one is retrievable.

    Precision over recall: the search is scoped to the perspective that stage
    is generated from (A/B -> v3 可执行路径, C -> v4 issue 槽位, D -> v1 约定),
    so a backfilled source is the file/issue that actually backs that kind of
    step — not whatever ranks highest in the whole index. Honest rule: if no
    real source surfaces, keep missing (无证据不宣称).
    """
    if not index:
        return steps
    # stage -> perspectives to scope the backfill search to.
    stage_perspectives = {"A": "setup", "B": "test", "C": "issue", "D": "contribute"}
    out: list[GuideStep] = []
    for st in steps:
        if st.evidence.kind != "missing":
            out.append(st)
            continue
        # Build a retrieval query from title + command.
        query = " ".join(filter(None, [st.title, st.command or "", st.expected]))
        if st.stage == "C" or "issue" in (st.title or "").lower():
            query += " good first issue first contribution"
        query = query.replace("-", " ").strip()
        if not query:
            out.append(st)
            continue
        kind = stage_perspectives.get(st.stage, "setup")
        try:
            res = index.search(query, kind=kind, top_k=4)
        except Exception:  # noqa: BLE001 - never let backfill crash generation
            out.append(st)
            continue
        found = None
        for h in res.hits:
            meta = h.meta or {}
            src = meta.get("source") or ""
            mkind = meta.get("kind") or "file"
            # Only real file/issue sources count; perspective codes are not.
            if mkind in ("file", "issue") and src and not src.startswith("v"):
                found = (src, mkind)
                break
        if found:
            src, mkind = found
            st.evidence = Evidence(kind=mkind, source=src, quote="")  # type: ignore[arg-type]
        out.append(st)
    return out
