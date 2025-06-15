# tests/conftest.py
"""
Shared fixtures for the test suite.

Key design points
─────────────────
1.  Make project-root importable so `from gossip.gossip import …` works no
    matter where pytest is launched.
2.  Provide stubs for RocksDB calls so the GossipNode code never touches disk.
3.  Let tests opt-in to a fast “always-true” verifier via
    `@pytest.mark.stub_verify`; wallet tests get the real verifier.
"""

from __future__ import annotations
import asyncio
import pathlib
import sys
import pytest

# ─────────────────────────────────────────────────────────────────────────────
#  Ensure the repo root is on sys.path
# ─────────────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))                 # for `import gossip`, `import wallet` …

# Only now import modules that live in the repo
from gossip.gossip import GossipNode


# ────────────────────────────── database stub ───────────────────────────────
@pytest.fixture(autouse=True)
def _stub_database(monkeypatch):
    db: dict[bytes, bytes] = {}

    # patch the original function
    monkeypatch.setattr("database.database.get_db", lambda: db, raising=True)

    # patch every module that imported it under a local name
    monkeypatch.setattr("gossip.gossip.get_db", lambda: db, raising=True)
    monkeypatch.setattr("web.web.get_db",      lambda: db, raising=True)   

    # (height helper unchanged)
    monkeypatch.setattr("database.database.get_current_height",
                        lambda _db: (0, "0"*64), raising=True)
    monkeypatch.setattr("gossip.gossip.get_current_height",
                        lambda _db: (0, "0"*64), raising=True)
    monkeypatch.setattr("web.web.get_current_height",
                        lambda _db: (0, "0"*64), raising=True)
    monkeypatch.setattr("rpc.rpc.get_db", lambda: db, raising=True)
    monkeypatch.setattr("rpc.rpc.get_current_height",
                    lambda _db: (0, "0"*64), raising=True)             
    yield db


# ───────────────────── conditional signature-verify stub ────────────────────
@pytest.fixture(autouse=True)
def _maybe_stub_verify(monkeypatch, request):
    """
    If a test has the marker ``@pytest.mark.stub_verify`` we monkey-patch
    verify_transaction to always return True (both the original and the alias
    imported into gossip.gossip).  Wallet tests omit the marker and therefore
    exercise real post-quantum verification.
    """
    if request.node.get_closest_marker("stub_verify"):
        monkeypatch.setattr("wallet.wallet.verify_transaction",
                            lambda *a, **k: True, raising=True)
        monkeypatch.setattr("gossip.gossip.verify_transaction",
                            lambda *a, **k: True, raising=True)
        monkeypatch.setattr("web.web.verify_transaction",       
                            lambda *a, **k: True, raising=True)
        monkeypatch.setattr("rpc.rpc.verify_transaction",
                    lambda *a, **k: True, raising=True)


# ───────────────────────── event-loop fixture (nice to have) ─────────────────
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─────────────────────────── dummy StreamWriter ─────────────────────────────
@pytest.fixture
def dummy_writer():
    """Minimal stand-in for asyncio.StreamWriter used by GossipNode tests."""
    class _Writer:
        def __init__(self):
            self.buffer = bytearray()
            self.closed = False

        def write(self, data):
            self.buffer.extend(data)

        async def drain(self):
            pass

        def get_extra_info(self, _):
            return ("dummy-ip", 0)

        def close(self):
            self.closed = True

        async def wait_closed(self):
            pass

    return _Writer()


# ─────────────────────────── GossipNode fixture ─────────────────────────────
@pytest.fixture
def node():
    """Fresh GossipNode for each test (no real network)."""
    return GossipNode(node_id="unit-test-node")
