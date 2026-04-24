"""Shared test fixtures. Force fake redis + ephemeral chroma for all tests."""
import os
import tempfile
from pathlib import Path

import pytest

os.environ["AGENT_RUNTIME__MODE"] = "mock"
os.environ["AGENT_EMBEDDING__MODE"] = "hash"
os.environ["AGENT_USE_FAKE_REDIS"] = "true"
os.environ["AGENT_USE_EPHEMERAL_CHROMA"] = "true"


@pytest.fixture
def tmp_outputs_dir(tmp_path: Path, monkeypatch) -> Path:
    ep = tmp_path / "episodic"
    ch = tmp_path / "chroma"
    ep.mkdir()
    ch.mkdir()
    monkeypatch.setenv("AGENT_MEMORY__EPISODIC__LOG_DIR", str(ep))
    monkeypatch.setenv("AGENT_MEMORY__SEMANTIC__PERSIST_DIR", str(ch))
    monkeypatch.setenv("AGENT_RUNTIME__MODE", "mock")
    monkeypatch.setenv("AGENT_EMBEDDING__MODE", "hash")
    monkeypatch.setenv("AGENT_USE_FAKE_REDIS", "true")
    monkeypatch.setenv("AGENT_USE_EPHEMERAL_CHROMA", "true")
    # force settings reload
    from agent.config import reset_settings
    reset_settings()
    return tmp_path
