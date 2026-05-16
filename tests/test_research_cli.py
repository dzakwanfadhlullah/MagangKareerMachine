"""CLI tests for research command."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from typer.testing import CliRunner
    from engine.cli import app
    HAS_TYPER = True
except ModuleNotFoundError:
    CliRunner = None
    app = None
    HAS_TYPER = False


def test_research_cli_test_module_loads_without_typer():
    assert True


@pytest.mark.skipif(not HAS_TYPER, reason="typer is not installed in this interpreter")
def test_research_cli_requires_query_or_target():
    result = CliRunner().invoke(app, ["research", "--profile", "fast"])

    assert result.exit_code == 1
    assert "Isi --query atau --target-category" in result.output


@pytest.mark.skipif(not HAS_TYPER, reason="typer is not installed in this interpreter")
def test_research_cli_calls_pipeline(monkeypatch):
    called = {}

    def fake_run_research_pipeline(**kwargs):
        called.update(kwargs)
        return 0

    monkeypatch.setattr("engine.cli.run_research_pipeline", fake_run_research_pipeline)

    result = CliRunner().invoke(app, [
        "research",
        "--query", "frontend developer intern",
        "--target-category", "frontend",
        "--profile", "fast",
        "--max-fetch", "5",
    ])

    assert result.exit_code == 0
    assert called["query"] == "frontend developer intern"
    assert called["target_category"] == "frontend"
    assert called["profile"] == "fast"
    assert called["max_fetch"] == 5
