from backend.core.github.parse import parse_github_url

import pytest


def test_full_url():
    assert parse_github_url("https://github.com/psf/requests") == ("psf", "requests")


def test_url_with_branch_path():
    assert parse_github_url("https://github.com/psf/requests/tree/main") == ("psf", "requests")


def test_trailing_slash():
    assert parse_github_url("https://github.com/psf/requests/") == ("psf", "requests")


def test_shorthand():
    assert parse_github_url("psf/requests") == ("psf", "requests")


def test_www_host():
    assert parse_github_url("https://www.github.com/psf/requests") == ("psf", "requests")


def test_rejects_non_github():
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/a/b")


def test_rejects_garbage():
    with pytest.raises(ValueError):
        parse_github_url("not a url at all")


def test_rejects_empty():
    with pytest.raises(ValueError):
        parse_github_url("")
