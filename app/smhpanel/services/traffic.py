"""Traffic accounting: stats polling, lifetime accumulation, quota enforcement."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from .stats_client import StatsClient
from .wireguard import WireGuardManager

log = logging.getLogger(__name__)

POLL_INTERVAL = 10
ENFORCE_EVERY = 6  # ~60s at a 10s tick
SAMPLE_RETENTION_DAYS = 7
GB = 1024 ** 3


class DeltaTracker:
    """Converts cumulative counters into deltas, handling counter resets."""

    def __init__(self):
        self.last: dict[str, int] = {}

    def delta(self, key: str, current: int) -> int:
        prev = self.last.get(key)
        self.last[key] = current
        if prev is None:
            return 0
        if current >= prev:
            return current - prev
        return max(current, 0)  # counter was reset (xray restart / usage reset)


class TrafficEngine:
    def __init__(self, config, session_factory, runner, apply_cb=None):
        self.config = config
        self.session_factory = session_factory
        self.runner = runner
        self.apply_cb = apply_cb
        self.stats = StatsClient(
            config.paths().get("stats_api") or "127.0.0.1:10085",
            timeout=2.0 if config.is_dev() else 5.0,
        )
        self.wg = WireGuardManager(config, session_factory, runner)
        self.tracker = DeltaTracker()
        self._ticks = 0
        self._last_prune = 0.0
        self._task: "asyncio.Task | None" = None

    # ----- async loop -----------------------------------------------------
    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:  # pragma: no cover - timing loop
        while True:
            try:
                await asyncio.to_thread(self.poll_once)
                self._ticks += 1
                if self._ticks % ENFORCE_EVERY == 0:
                    await asyncio.to_thread(self.enforce_once)
            except Exception:
                log.exception("traffic loop iteration failed")
            await asyncio.sleep(POLL_INTERVAL)

    # ----- sync core (unit-testable) ---------------------------------------
    def poll_once(self) -> None:
        from ..models import Client

        cycle_up = cycle_down = 0
        stats = self.stats.query("user>>>")

        with self.session_factory() as session:
            clients = session.query(Client).all()

            if stats:
                counters: dict[tuple[str, str], int] = {}
                for name, value in stats.items():
                    parts = name.split(">>>")
                    if len(parts) == 4 and parts[0] == "user" and parts[2] == "traffic":
                        counters[(parts[1], parts[3])] = value
                for client in clients:
                    if client.inbound is None or client.inbound.is_wireguard:
                        continue
                    up = counters.get((client.email_tag, "uplink"))
                    down = counters.get((client.email_tag, "downlink"))
                    if up is None and down is None:
                        continue
                    d_up = self.tracker.delta(f"x:{client.email_tag}:up", up or 0)
                    d_down = self.tracker.delta(f"x:{client.email_tag}:down", down or 0)
                    client.up_bytes = (client.up_bytes or 0) + d_up
                    client.down_bytes = (client.down_bytes or 0) + d_down
                    cycle_up += d_up
                    cycle_down += d_down

            wg_clients = [
                c
                for c in clients
                if c.inbound is not None and c.inbound.is_wireguard and c.enabled
            ]
            if wg_clients and self.config.get("wireguard.enabled", True):
                dump = self.wg.show()
                for client in wg_clients:
                    pub = (client.extra or {}).get("wg_public")
                    info = dump.get(pub) if pub else None
                    if not info:
                        continue
                    d_up = self.tracker.delta(f"w:{pub}:rx", info["rx"])
                    d_down = self.tracker.delta(f"w:{pub}:tx", info["tx"])
                    client.up_bytes = (client.up_bytes or 0) + d_up
                    client.down_bytes = (client.down_bytes or 0) + d_down
                    cycle_up += d_up
                    cycle_down += d_down

            self._record_sample(session, cycle_up, cycle_down)
            session.commit()

    def _record_sample(self, session, up: int, down: int) -> None:
        from ..models import TrafficSample

        if up or down:
            minute = int(time.time() // 60) * 60
            row = (
                session.query(TrafficSample)
                .filter(TrafficSample.ts_minute == minute)
                .first()
            )
            if row is None:
                session.add(TrafficSample(ts_minute=minute, up=up, down=down))
            else:
                row.up += up
                row.down += down

        now = time.time()
        if now - self._last_prune > 3600:
            self._last_prune = now
            cutoff = int(now) - SAMPLE_RETENTION_DAYS * 86400
            session.query(TrafficSample).filter(
                TrafficSample.ts_minute < cutoff
            ).delete()

    def enforce_once(self) -> bool:
        """Disable clients that exceeded quota/expiry. Returns True if changed."""
        from ..models import AuditLog, Client

        changed = False
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.session_factory() as session:
            clients = session.query(Client).filter(Client.enabled.is_(True)).all()
            for client in clients:
                reason = None
                total = (client.up_bytes or 0) + (client.down_bytes or 0)
                if (
                    client.quota_gb
                    and client.quota_gb > 0
                    and total >= int(client.quota_gb * GB)
                ):
                    reason = "quota"
                elif client.expiry and now > client.expiry:
                    reason = "expiry"
                if reason:
                    client.enabled = False
                    client.disabled_reason = reason
                    session.add(
                        AuditLog(
                            actor="system",
                            action="client.auto_disable",
                            detail=f"{client.name} ({reason})",
                        )
                    )
                    changed = True
            session.commit()

        if changed and self.apply_cb is not None:
            try:
                self.apply_cb()
            except Exception:  # pragma: no cover - defensive
                log.exception("apply after enforcement failed")
        return changed
