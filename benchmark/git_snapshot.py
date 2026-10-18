"""Read bounded source documentation from an existing public Git checkout.

No dependency install or repository commands/scripts are executed. Git may
download missing blobs from the checkout's configured remote for sparse clones.
GitHub issues, language bytes, stars and release activity remain unmeasured.
"""
from pathlib import Path
import subprocess
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals, _BUILD_FILES, _DOC_PATHS


def snapshot_from_git(path: Path, owner: str, repo: str, captured_at: str) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(path), *args], timeout=120).decode("utf-8", errors="replace")

    sha = git("rev-parse", "HEAD").strip()
    paths = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    symlinks = [line.split("\t", 1)[1] for line in git("ls-tree", "-r", "HEAD").splitlines() if line.startswith("120000 ")]
    names = {p.lower(): p for p in paths if "/" not in p}
    root_paths = [names[n.lower()] for n in (*_DOC_PATHS, *_BUILD_FILES) if n.lower() in names]
    extra = [p for p in paths if p.lower().endswith((".md", ".rst", ".txt"))
             and any(k in p.lower() for k in ("contribut", "install", "develop", "getting", "usage"))
             and not any(k in p.lower().split("/") for k in ("tests", "test", "vendor", "node_modules"))]
    workflow = [p for p in paths if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    selected = list(dict.fromkeys(root_paths + extra[:12] + workflow[:6]))
    docs = []
    for p in selected:
        text = git("show", f"{sha}:{p}")
        if len(text) <= 200_000:
            docs.append(DocFile(path=p, name=p.split("/")[-1], text=text))
    sig = RawSignals(meta=RepoMeta(owner=owner, repo=repo, default_branch=sha),
        root_entries={p.lower(): p for p in paths if "/" not in p},
        has_docs_dir=any(p.startswith("docs/") for p in paths),
        has_license_file=any(p.lower().startswith("license") for p in root_paths),
        doc_files=docs, file_tree=paths, unavailable_signals=["issues", "stars", "languages", "activity", "license"],
        collection_warnings=["Git 源码快照不包含任务与社区活跃度数据"], symlink_paths=symlinks)
    return {"sha": sha, "captured_at": captured_at, "source": "git-checkout",
        "unmeasured": ["issues", "stars", "language_bytes", "release_activity", "license_spdx"],
        "signals": sig.model_dump()}
