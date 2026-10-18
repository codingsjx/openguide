"""Local observation ledger. Validates records; never certifies their truth.

python -m benchmark.user_study init --output path.json
python -m benchmark.user_study summarize path.json --output report.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Task(StrictRecord):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment: str = Field(min_length=1)
    setup_success: str = Field(min_length=1)
    test_success: str = Field(min_length=1)
    issue_success: str = Field(min_length=1)
    organizer_verified: bool = False


class Participant(StrictRecord):
    participant_id: str = Field(pattern=r"^P[0-9]{3}$")
    consent_recorded: bool
    experience: str = Field(min_length=1)
    sequence: Literal["AB", "BA"]
    first_task: str


class Session(StrictRecord):
    participant_id: str
    task_id: str
    condition: Literal["official_docs", "openguide"]
    status: Literal["completed", "timed_out", "withdrawn"]
    elapsed_seconds: int = Field(ge=0)
    setup_ok: bool
    test_ok: bool
    issue_ok: bool
    help_count: int = Field(ge=0)
    wrong_command_count: int = Field(ge=0)
    guide_revision: str = ""
    observation_reference: str = Field(min_length=1)
    notes: str = ""


class Study(StrictRecord):
    schema_version: Literal[1] = 1
    status: Literal["draft", "collecting", "closed"] = "draft"
    time_limit_seconds: int = Field(default=1800, gt=0)
    tasks: list[Task] = Field(default_factory=list)
    participants: list[Participant] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_assignments(self):
        tasks = {task.task_id: task for task in self.tasks}
        people = {person.participant_id: person for person in self.participants}
        if len(tasks) != len(self.tasks) or len(people) != len(self.participants):
            raise ValueError("Duplicate task or participant ID")
        if self.status != "draft" and (len(tasks) != 2 or not all(t.organizer_verified for t in self.tasks)):
            raise ValueError("Collecting requires two organizer-verified tasks")
        for person in self.participants:
            if len(tasks) != 2 or person.first_task not in tasks or not person.consent_recorded:
                raise ValueError("Enrollment requires consent and two assigned tasks")
        seen = set()
        for session in self.sessions:
            key = (session.participant_id, session.task_id)
            person = people.get(session.participant_id)
            if not person or session.task_id not in tasks or key in seen:
                raise ValueError("Unknown or duplicate session")
            seen.add(key)
            first = session.task_id == person.first_task
            expected = "official_docs" if (person.sequence == "AB") == first else "openguide"
            if session.condition != expected:
                raise ValueError("Condition differs from assigned sequence")
            if session.condition == "openguide" and not session.guide_revision.strip():
                raise ValueError("OpenGuide session requires saved guide/version reference")
            if session.status == "timed_out" and session.elapsed_seconds < self.time_limit_seconds:
                raise ValueError("Timeout must reach the prespecified time limit")
            if session.status == "completed" and session.elapsed_seconds > self.time_limit_seconds:
                raise ValueError("Over-limit sessions must be retained as timed_out")
            if session.status == "withdrawn" and not session.notes.strip():
                raise ValueError("Withdrawal requires a recorded reason")
        if self.status == "draft" and self.sessions:
            raise ValueError("Freeze task definitions before recording sessions")
        return self


def summarize(study: Study) -> dict:
    results = {}
    for condition in ("official_docs", "openguide"):
        rows = [s for s in study.sessions if s.condition == condition]
        successes = sum(s.status == "completed" and s.setup_ok and s.test_ok and s.issue_ok for s in rows)
        denominator = len(study.participants)  # includes withdrawal, timeout and missing records
        results[condition] = {
            "assigned": denominator, "observed": len(rows), "missing": denominator - len(rows),
            "successful": successes, "success_rate": successes / denominator if denominator else None,
            "timed_out": sum(s.status == "timed_out" for s in rows),
            "withdrawn": sum(s.status == "withdrawn" for s in rows),
            "observed_elapsed_seconds": [s.elapsed_seconds for s in rows],
            "median_observed_elapsed_seconds": statistics.median(s.elapsed_seconds for s in rows) if rows else None,
            "help_count": sum(s.help_count for s in rows),
            "wrong_command_count": sum(s.wrong_command_count for s in rows),
        }
    return {"status": study.status, "participants": len(study.participants), "conditions": results,
            "independently_verified": False,
            "limitations": ["Manual observations are not independently authenticated.",
                "Missing, withdrawn and timed-out sessions remain in assigned denominators.",
                "Elapsed-time summaries include observed sessions only; inspect missingness and timeout counts.",
                "Descriptive exploratory results do not establish causality or prize eligibility."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("summarize")
    report.add_argument("input", type=Path)
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = Study().model_dump() if args.command == "init" else summarize(Study.model_validate_json(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never silently overwrite a ledger or an existing report.
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
