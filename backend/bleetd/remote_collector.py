"""Standalone read-only Python 3 helper, sent verbatim to allowlisted SSH hosts."""
import datetime
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path


def read(path):
    try:
        return Path(path).read_text()
    except (OSError, UnicodeError):
        return ""


def run(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=3, check=False)
        return result.stdout[:1_000_000] if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def integer(argv):
    value = run(argv).strip()
    return int(value) if value.isdigit() else None


def collect_linux(proc_root=Path("/proc"), sys_cpu_root=Path("/sys/devices/system/cpu"), include_nvidia=True):
    result = {"platform": "linux"}
    result["before"] = read(proc_root / "stat")
    start = time.monotonic()
    time.sleep(0.5)
    result["after"] = read(proc_root / "stat")
    result["sample_window_ms"] = round((time.monotonic() - start) * 1000)
    result["meminfo"] = read(proc_root / "meminfo")
    cpu = read(proc_root / "cpuinfo")
    match = re.search(r"^(?:model name|Hardware)\s*:\s*(.+)$", cpu, re.M)
    result["cpu_name"] = match.group(1).strip() if match else platform.machine()
    result["topology"] = {}
    for path in sys_cpu_root.glob("cpu[0-9]*"):
        index = path.name[3:]
        if index.isdigit():
            result["topology"][index] = [read(path / "topology/physical_package_id").strip(), read(path / "topology/core_id").strip()]
    result["nvidia"] = run(["nvidia-smi", "--query-gpu=uuid,index,name,utilization.gpu,memory.total,memory.used,temperature.gpu,power.draw", "--format=csv,noheader,nounits"]) if include_nvidia else ""
    result["gpu_error"] = None if result["nvidia"] else "NVIDIA metrics unavailable or no NVIDIA GPU"
    return result


def collect():
    result = {"platform": platform.system().lower()}
    if result["platform"] == "linux":
        result = collect_linux()
    elif result["platform"] == "darwin":
        result["cpu_name"] = run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or platform.machine()
        result["logical_cores"] = integer(["sysctl", "-n", "hw.logicalcpu"])
        result["physical_cores"] = integer(["sysctl", "-n", "hw.physicalcpu"])
        result["total_bytes"] = integer(["sysctl", "-n", "hw.memsize"])
        result["unified"] = "Apple" in result["cpu_name"]
        vm = run(["vm_stat"])
        page_match = re.search(r"page size of (\d+) bytes", vm)
        pages = dict((key.strip(), int(value)) for key, value in re.findall(r"^([^:\n]+):\s*(\d+)", vm, re.M))
        keys = ["Pages active", "Pages wired down", "Pages occupied by compressor"]
        result["used_bytes"] = sum(pages[key] for key in keys) * int(page_match.group(1)) if page_match and all(key in pages for key in keys) else None
        top = run(["top", "-l", "2", "-n", "0", "-s", "1"])
        samples = re.findall(r"CPU usage:.*?([\d.]+)% idle", top)
        result["cpu_usage"] = round(100 - float(samples[-1]), 2) if samples else None
        result["sample_window_ms"] = 1000
    else:
        raise RuntimeError("unsupported platform")
    result["collected_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return result


if __name__ == "__main__":
    print(json.dumps(collect()))
