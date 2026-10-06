"""Xray StatsService client (gRPC generic unary call, no generated stub imports)."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

try:
    import grpc  # type: ignore
except Exception:  # pragma: no cover - grpc optional at import time
    grpc = None

try:
    from ..grpc_gen import xray_stats_pb2 as pb2  # type: ignore
except Exception:  # pragma: no cover - generated code optional
    pb2 = None

QUERY_METHOD = "/xray.app.stats.command.StatsService/QueryStats"


class StatsClient:
    def __init__(self, address: str, timeout: float = 5.0):
        self.address = address
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return grpc is not None and pb2 is not None

    def query(self, pattern: str = "user>>>") -> dict[str, int] | None:
        """Return {stats_name: value} or None when the API is unreachable."""
        if not self.available:
            return None
        try:
            with grpc.insecure_channel(self.address) as channel:
                caller = channel.unary_unary(
                    QUERY_METHOD,
                    request_serializer=pb2.QueryStatsRequest.SerializeToString,
                    response_deserializer=pb2.QueryStatsResponse.FromString,
                )
                response = caller(
                    pb2.QueryStatsRequest(pattern=pattern, reset=False),
                    timeout=self.timeout,
                )
                return {stat.name: stat.value for stat in response.stat}
        except Exception as exc:
            log.debug("stats query failed: %s", exc)
            return None
