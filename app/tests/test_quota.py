"""Traffic accounting and quota enforcement tests."""
from __future__ import annotations

from datetime import datetime

from smhpanel.models import Client, Inbound
from smhpanel.services.helpers import HelperRunner
from smhpanel.services.traffic import DeltaTracker, TrafficEngine


def test_delta_tracker_reset_handling():
    tracker = DeltaTracker()
    assert tracker.delta("k", 100) == 0  # first observation
    assert tracker.delta("k", 150) == 50
    assert tracker.delta("k", 150) == 0
    assert tracker.delta("k", 30) == 30  # counter reset
    assert tracker.delta("k", 40) == 10


def _make_inbound(factory, tag: str, port: int) -> int:
    with factory() as session:
        row = Inbound(tag=tag, protocol="vless", port=port, params={})
        session.add(row)
        session.commit()
        return row.id


def test_poll_accumulates_and_handles_reset(app_env, monkeypatch):
    cfg, factory = app_env
    inbound_id = _make_inbound(factory, "v1", 10001)
    with factory() as session:
        client = Client(
            inbound_id=inbound_id,
            name="A",
            credential="uuid",
            email_tag="v1.1",
            sub_token="tok1",
        )
        session.add(client)
        session.commit()
        client_id = client.id

    engine = TrafficEngine(cfg, factory, HelperRunner(cfg))

    monkeypatch.setattr(
        engine.stats,
        "query",
        lambda pattern="user>>>": {
            "user>>>v1.1>>>traffic>>>uplink": 1000,
            "user>>>v1.1>>>traffic>>>downlink": 2000,
        },
    )
    engine.poll_once()
    with factory() as session:
        row = session.get(Client, client_id)
        assert row.up_bytes == 0 and row.down_bytes == 0  # first observation

    monkeypatch.setattr(
        engine.stats,
        "query",
        lambda pattern="user>>>": {
            "user>>>v1.1>>>traffic>>>uplink": 1500,
            "user>>>v1.1>>>traffic>>>downlink": 2600,
        },
    )
    engine.poll_once()
    with factory() as session:
        row = session.get(Client, client_id)
        assert row.up_bytes == 500 and row.down_bytes == 600

    # xray restart -> counters reset to zero; delta must equal current value
    monkeypatch.setattr(
        engine.stats,
        "query",
        lambda pattern="user>>>": {
            "user>>>v1.1>>>traffic>>>uplink": 100,
            "user>>>v1.1>>>traffic>>>downlink": 200,
        },
    )
    engine.poll_once()
    with factory() as session:
        row = session.get(Client, client_id)
        assert row.up_bytes == 600 and row.down_bytes == 800


def test_enforce_disables_over_quota_and_expired(app_env):
    cfg, factory = app_env
    inbound_id = _make_inbound(factory, "v2", 10002)
    with factory() as session:
        over = Client(
            inbound_id=inbound_id,
            name="over",
            credential="u1",
            email_tag="v2.1",
            sub_token="t1",
            quota_gb=1,
            up_bytes=2 * 1024**3,
        )
        expired = Client(
            inbound_id=inbound_id,
            name="exp",
            credential="u2",
            email_tag="v2.2",
            sub_token="t2",
            expiry=datetime(2020, 1, 1),
        )
        fine = Client(
            inbound_id=inbound_id,
            name="fine",
            credential="u3",
            email_tag="v2.3",
            sub_token="t3",
            quota_gb=100,
        )
        session.add_all([over, expired, fine])
        session.commit()

    engine = TrafficEngine(cfg, factory, HelperRunner(cfg))
    assert engine.enforce_once() is True
    with factory() as session:
        assert (
            session.query(Client).filter_by(name="over").first().disabled_reason
            == "quota"
        )
        assert (
            session.query(Client).filter_by(name="exp").first().disabled_reason
            == "expiry"
        )
        fine_row = session.query(Client).filter_by(name="fine").first()
        assert fine_row.enabled is True and fine_row.disabled_reason is None
    # nothing left to disable on the second pass
    assert engine.enforce_once() is False
