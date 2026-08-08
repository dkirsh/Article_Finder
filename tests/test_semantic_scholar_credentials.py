from __future__ import annotations

from pathlib import Path

import yaml

import config.loader as config_loader
from search.bibliographer import SemanticScholarSearcher


def test_tracked_settings_do_not_contain_semantic_scholar_key() -> None:
    settings = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "config" / "settings.yaml").read_text()
    )

    assert settings["apis"]["semantic_scholar"]["api_key"] is None


def test_explicit_key_has_highest_precedence(monkeypatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "environment-value")
    monkeypatch.setattr(config_loader, "get", lambda _key: "local-value")

    client = SemanticScholarSearcher(api_key="explicit-value")

    assert client.api_key == "explicit-value"
    assert client.session.headers["x-api-key"] == "explicit-value"


def test_environment_key_precedes_local_config(monkeypatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "environment-value")
    monkeypatch.setattr(config_loader, "get", lambda _key: "local-value")

    assert SemanticScholarSearcher().api_key == "environment-value"


def test_ignored_local_config_is_supported_as_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.setattr(config_loader, "get", lambda _key: "local-value")

    assert SemanticScholarSearcher().api_key == "local-value"
