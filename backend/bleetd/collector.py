"""Fixed, unprivileged remote hardware collector and deterministic parsers."""
import csv
import io
import shlex
from pathlib import Path

from .state import utcnow


def number(value):
    try:
        return float(value.strip())
    except (TypeError, ValueError, AttributeError):
        return None


def counters(text):
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields or not fields[0].startswith("cpu"):
            continue
        try:
            # guest/guest_nice are already counted in user/nice, so exclude them.
            values = [int(value) for value in fields[1:9]]
            result[fields[0]] = (sum(values), sum(values[3:5]))
        except ValueError:
            continue
    return result


def utilization(before, after, key):
    if key not in before or key not in after:
        return None
    total = after[key][0] - before[key][0]
    idle = after[key][1] - before[key][1]
    if total <= 0 or idle < 0:
        return None
    return round(max(0, min(100, (total - idle) / total * 100)), 2)


def parse_nvidia(text):
    result = []
    for fields in csv.reader(io.StringIO(text)):
        if len(fields) != 8:
            continue
        uuid, index, name, usage, total, used, temp, power = (x.strip() for x in fields)
        if not uuid.startswith("GPU-") or not index.isdigit():
            continue
        result.append({"id": uuid, "index": int(index), "name": name, "usage_percent": number(usage), "memory_total_bytes": int(number(total) * 1048576) if number(total) is not None else None, "memory_used_bytes": int(number(used) * 1048576) if number(used) is not None else None, "temperature_c": number(temp), "power_w": number(power), "memory_kind": "dedicated"})
    return result


def parse_linux(raw):
    before, after = counters(raw.get("before", "")), counters(raw.get("after", ""))
    ids = sorted({int(key[3:]) for key in set(before) | set(after) if key[3:].isdigit()} | {int(key) for key in raw.get("topology", {}) if key.isdigit()})
    topology = raw.get("topology", {})
    known = bool(ids) and all(str(i) in topology and len(topology[str(i)]) == 2 and all(x not in (None, "", "-1") for x in topology[str(i)]) for i in ids)
    groups = {}
    for index in ids:
        key = ":".join(map(str, topology[str(index)])) if known else f"logical:{index}"
        groups.setdefault(key, []).append(index)
    cores = []
    for index, (key, logical_ids) in enumerate(groups.items()):
        readings = [utilization(before, after, f"cpu{cpu}") for cpu in logical_ids]
        value = round(sum(readings) / len(readings), 2) if all(x is not None for x in readings) else None
        cores.append({"id": key, "index": index, "logical_ids": logical_ids, "usage_percent": value, "state": "ok" if value is not None else "unknown"})
    memory = {}
    for line in raw.get("meminfo", "").splitlines():
        try:
            key, value = line.split(":", 1)
            memory[key] = int(value.split()[0]) * 1024
        except (ValueError, IndexError):
            continue
    total, available = memory.get("MemTotal"), memory.get("MemAvailable")
    return {"collected_at": raw.get("collected_at") or utcnow(), "platform": "linux", "sample_window_ms": raw.get("sample_window_ms"), "cpu": {"name": raw.get("cpu_name"), "physical_cores": len(cores) if known else None, "logical_cores": len(ids) or None, "topology": "physical" if known else "logical", "usage_percent": utilization(before, after, "cpu"), "cores": cores}, "memory": {"total_bytes": total, "used_bytes": max(0, total - available) if total is not None and available is not None else None, "kind": "ram", "definition": "total - available"}, "gpus": parse_nvidia(raw.get("nvidia", "")), "gpu_error": raw.get("gpu_error"), "stale": False}


def parse_macos(raw):
    count = raw.get("logical_cores")
    unified = raw.get("unified", False)
    return {"collected_at": raw.get("collected_at") or utcnow(), "platform": "darwin", "sample_window_ms": raw.get("sample_window_ms"), "cpu": {"name": raw.get("cpu_name"), "physical_cores": raw.get("physical_cores"), "logical_cores": count, "topology": "logical", "usage_percent": raw.get("cpu_usage"), "cores": [{"id": f"logical:{i}", "index": i, "logical_ids": [i], "usage_percent": None, "state": "unsupported"} for i in range(count or 0)]}, "memory": {"total_bytes": raw.get("total_bytes"), "used_bytes": raw.get("used_bytes"), "kind": "unified" if unified else "ram", "definition": "active + wired + compressed pages"}, "gpus": [{"id": "apple-integrated", "index": 0, "name": raw.get("gpu_name", "Apple integrated GPU"), "usage_percent": None, "memory_total_bytes": None, "memory_used_bytes": None, "temperature_c": None, "power_w": None, "memory_kind": "unified", "state": "unsupported"}] if unified else [], "gpu_error": "GPU utilization unsupported by unprivileged collector", "stale": False}


def collector_command():
    script = Path(__file__).with_name("remote_collector.py").read_text()
    # Fixed code only; neither the script nor the command contains client input.
    return "python3 -c " + shlex.quote(script)


def collect_mounted_linux(proc_root=Path("/host/proc"), sys_cpu_root=Path("/host/sys/devices/system/cpu")):
    """Read explicit host mounts, never implicitly substitute container paths."""
    from .remote_collector import collect_linux
    if not all((proc_root / name).is_file() for name in ("stat", "meminfo", "cpuinfo")) or not sys_cpu_root.is_dir():
        raise ValueError("host proc/sys read-only mounts are unavailable")
    raw = collect_linux(proc_root, sys_cpu_root, include_nvidia=False)
    raw["collected_at"] = utcnow()
    raw["metrics_source"] = "host_proc_sys_mount"
    return raw
