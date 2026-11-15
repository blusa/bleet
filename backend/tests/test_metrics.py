import asyncio
import json

import pytest


def test_linux_counter_topology_memory_nvidia_parsing():
    from bleetd.collector import parse_linux
    raw = {
        "before": "cpu 100 0 100 800 0 0 0 0 0 0\ncpu0 50 0 50 400\ncpu1 50 0 50 400\n",
        "after": "cpu 150 0 150 900 0 0 0 0 0 0\ncpu0 50 0 50 500\ncpu1 100 0 100 400\n",
        "topology": {"0": ["0", "0"], "1": ["0", "0"]},
        "cpu_name": "Example CPU",
        "meminfo": "MemTotal: 1000 kB\nMemAvailable: 250 kB\n",
        "nvidia": "GPU-abc, 0, NVIDIA Example, 50, 1000, 250, 61, 42.5\nGPU-def, 1, NVIDIA Other, [N/A], 2000, 0, [N/A], [N/A]\n",
        "collected_at": "2026-11-15T00:00:00Z", "sample_window_ms": 1000,
    }
    metrics = parse_linux(raw)
    assert metrics["cpu"]["usage_percent"] == 50
    assert metrics["cpu"]["physical_cores"] == 1
    assert metrics["cpu"]["cores"][0]["logical_ids"] == [0, 1]
    assert metrics["cpu"]["cores"][0]["usage_percent"] == 50
    assert metrics["memory"] == {"total_bytes": 1024000, "used_bytes": 768000, "kind": "ram", "definition": "total - available"}
    assert metrics["gpus"][0]["id"] == "GPU-abc"
    assert metrics["gpus"][0]["memory_total_bytes"] == 1048576000
    assert metrics["gpus"][1]["usage_percent"] is None


def test_missing_linux_counters_remain_unknown():
    from bleetd.collector import parse_linux
    metrics = parse_linux({"before": "", "after": "", "meminfo": "", "nvidia": "", "topology": {}, "cpu_name": None})
    assert metrics["cpu"]["usage_percent"] is None
    assert metrics["memory"]["used_bytes"] is None
    assert metrics["gpus"] == []


def test_macos_unified_memory_and_unknown_gpu():
    from bleetd.collector import parse_macos
    metrics = parse_macos({"cpu_name": "Apple M4", "logical_cores": 10, "physical_cores": 10, "total_bytes": 16000, "used_bytes": 6000, "cpu_usage": 12, "unified": True})
    assert metrics["memory"]["kind"] == "unified"
    assert metrics["gpus"][0]["usage_percent"] is None
    assert metrics["gpus"][0]["memory_total_bytes"] is None
    assert metrics["cpu"]["topology"] == "logical"


@pytest.mark.asyncio
async def test_failure_preserves_cached_measurement_time_and_inventory(tmp_path):
    from bleetd.config import Config, Host
    from bleetd.services import Gateway
    from bleetd.state import State
    class SSH:
        failure = False
        calls = 0
        async def run(self, host, command, **kwargs):
            self.calls += 1
            await asyncio.sleep(0.01)
            if self.failure:
                raise TimeoutError("secret inaccessible")
            return json.dumps({"platform": "linux", "collected_at": "2026-11-15T00:00:00Z", "before": "", "after": "", "topology": {}, "meminfo": "", "nvidia": ""})
    ssh = SSH()
    config = Config(state_dir=tmp_path, hosts=[Host(id="ts:brak", name="BRAK", address="brak", ssh_target="brak")], cache_seconds=0)
    gateway = Gateway(config, State(tmp_path / "s.db"), ssh=ssh)
    first = await gateway.snapshot()
    assert first["hosts"][0]["metrics"]["collected_at"] == "2026-11-15T00:00:00Z"
    ssh.failure = True
    later = await gateway.snapshot()
    host = later["hosts"][0]
    assert host["metrics"]["collected_at"] == "2026-11-15T00:00:00Z"
    assert host["metrics"]["stale"] is True
    assert host["status"] == "degraded"
    assert host["network_online"] is None
    assert "secret" not in host["metrics_error"]


@pytest.mark.asyncio
async def test_simultaneous_snapshot_requests_coalesce(tmp_path):
    from bleetd.config import Config, Host
    from bleetd.services import Gateway
    from bleetd.state import State
    class SSH:
        calls = 0
        async def run(self, host, command, **kwargs):
            self.calls += 1
            await asyncio.sleep(.03)
            return json.dumps({"platform": "linux", "before": "", "after": "", "topology": {}, "meminfo": "", "nvidia": ""})
    ssh = SSH()
    gateway = Gateway(Config(state_dir=tmp_path, hosts=[Host(id="h", name="h", address="h", ssh_target="h")]), State(tmp_path / "s.db"), ssh=ssh)
    await asyncio.gather(*[gateway.snapshot() for _ in range(10)])
    assert ssh.calls == 1


def test_mounted_linux_reads_explicit_host_files_and_never_falls_back(tmp_path):
    from bleetd.collector import collect_mounted_linux, parse_linux
    proc = tmp_path / "proc"
    sys_cpu = tmp_path / "cpu"
    proc.mkdir()
    topology = sys_cpu / "cpu0" / "topology"
    topology.mkdir(parents=True)
    (proc / "stat").write_text("cpu 1 2 3 4\ncpu0 1 2 3 4\n")
    (proc / "meminfo").write_text("MemTotal: 2000 kB\nMemAvailable: 500 kB\n")
    (proc / "cpuinfo").write_text("model name : Host CPU\n")
    (topology / "physical_package_id").write_text("0")
    (topology / "core_id").write_text("0")
    raw = collect_mounted_linux(proc, sys_cpu)
    metrics = parse_linux(raw)
    assert metrics["memory"]["total_bytes"] == 2048000
    assert metrics["memory"]["used_bytes"] == 1536000
    assert metrics["cpu"]["name"] == "Host CPU"
    assert metrics["cpu"]["physical_cores"] == 1
    assert raw["metrics_source"] == "host_proc_sys_mount"
    assert raw["nvidia"] == ""
    with pytest.raises(ValueError):
        collect_mounted_linux(tmp_path / "absent", sys_cpu)


def test_only_one_host_can_claim_mounted_host_identity(tmp_path):
    from bleetd.config import Config, Host
    with pytest.raises(ValueError):
        Config(hosts=[Host(id=identity, name=identity, address=identity, ssh_target=identity, collector="mounted_linux") for identity in ("one", "two")])
