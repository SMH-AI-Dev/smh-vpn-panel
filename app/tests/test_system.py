"""System status / server specifications snapshot tests."""
from __future__ import annotations

from smhpanel.services.helpers import HelperRunner
from smhpanel.services.system import snapshot
from smhpanel.services.xray_manager import XrayManager


def test_snapshot_includes_specs_and_memory_details(app_env):
    cfg, factory = app_env
    runner = HelperRunner(cfg)
    manager = XrayManager(cfg, factory, runner)

    data = snapshot(cfg, runner, factory, manager)

    for key in ("services", "mem", "swap", "disk", "specs", "counts", "uptime_sec"):
        assert key in data, f"missing key: {key}"

    # server specifications
    specs = data["specs"]
    for key in (
        "hostname",
        "os",
        "kernel",
        "arch",
        "cpu_model",
        "cores_physical",
        "cores_logical",
        "cpu_freq_mhz",
        "load_avg",
    ):
        assert key in specs, f"missing spec: {key}"
    assert isinstance(specs["hostname"], str) and specs["hostname"]
    assert isinstance(specs["os"], str) and specs["os"]
    assert isinstance(specs["kernel"], str) and specs["kernel"]
    assert specs["cores_logical"] and specs["cores_logical"] > 0

    # memory details: total / used / free / available / percent
    mem = data["mem"]
    assert mem["total"] > 0
    assert 0 <= mem["used"] <= mem["total"]
    assert mem["free"] >= 0
    assert mem["available"] >= 0
    assert 0 <= mem["percent"] <= 100

    # swap + disk details
    assert data["swap"]["total"] >= 0
    assert "percent" in data["swap"]
    disk = data["disk"]
    assert disk["total"] > 0
    assert disk["free"] >= 0
    assert 0 <= disk["percent"] <= 100

    # service states are present
    assert data["services"]["panel"] == "active"
    assert "xray" in data["services"]
