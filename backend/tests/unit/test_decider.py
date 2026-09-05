"""Unit tests for the decision tree — pure logic over synthetic Profiles."""

from __future__ import annotations

from backend.core.decide.decider import decide
from backend.core.profile.schema import (
    ActivityInfo,
    BuildInfo,
    GfiInfo,
    Profile,
)


def make_profile(
    stars: int = 50,
    commits_30d: int = 20,
    has_readme: bool = True,
    gfi_count: int = 2,
    license_: str = "Apache-2.0",
    has_contributing: bool = True,
) -> Profile:
    return Profile(
        owner="o",
        repo="r",
        stars=stars,
        license=license_,
        has_readme=has_readme,
        has_contributing=has_contributing,
        build=BuildInfo(),
        gfi=GfiInfo(count=gfi_count),
        activity=ActivityInfo(commits_30d=commits_30d),
    )


def test_promising_healthy_repo():
    p = make_profile()
    suitability, reasons = decide(p)
    assert suitability == "promising"
    assert reasons  # non-empty reasons


def test_avoid_dormant_no_readme():
    p = make_profile(commits_30d=0, has_readme=False)
    suitability, _ = decide(p)
    assert suitability == "avoid"


def test_unclear_when_only_mild_gaps():
    p = make_profile(stars=3, gfi_count=0)
    suitability, _ = decide(p)
    assert suitability == "unclear"


def test_avoid_when_no_license():
    p = make_profile(license_="")
    suitability, _ = decide(p)
    assert suitability != "promising"
