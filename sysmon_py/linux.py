from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .core import (
    CPUInfo,
    DiskInfo,
    GPUInfo,
    MemInfo,
    PowerInfo,
    BatteryInfo,
    TempInfo,
    run_cmd,
    parse_float,
    parse_uint,
)

_prev_total: int = 0
_prev_idle: int = 0


def get_cpu() -> CPUInfo:
    info = CPUInfo()

    # Model
    try:
        data = Path("/proc/cpuinfo").read_text()
        for line in data.splitlines():
            if line.startswith("model name"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    info.model = parts[1].strip()
                break
    except OSError:
        pass

    # Cores
    try:
        data = Path("/proc/cpuinfo").read_text()
        cores = 0
        logical = 0
        core_ids: dict[int, bool] = {}
        for line in data.splitlines():
            line = line.strip()
            if line.startswith("processor"):
                logical += 1
            if line.startswith("cpu cores"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    cores = parse_uint(parts[1])
            if line.startswith("core id"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    core_ids[parse_uint(parts[1])] = True
        if cores > 0:
            info.cores = cores
        else:
            info.cores = len(core_ids)
        if info.cores == 0:
            info.cores = logical
        info.logical_cores = logical
    except OSError:
        pass

    # Frequency
    try:
        data = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read_text()
        info.freq_mhz = parse_float(data.strip()) / 1000.0
    except OSError:
        try:
            data = Path("/proc/cpuinfo").read_text()
            for line in data.splitlines():
                if line.startswith("cpu MHz"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        info.freq_mhz = parse_float(parts[1])
                    break
        except OSError:
            pass

    # Usage via /proc/stat delta
    info.usage_pct = _read_cpu_usage()
    return info


def _read_cpu_usage() -> float:
    global _prev_total, _prev_idle
    try:
        data = Path("/proc/stat").read_text()
        line = data.splitlines()[0]
        parts = line.split()
        if len(parts) < 5:
            return -1
        user = parse_uint(parts[1])
        nice = parse_uint(parts[2])
        system = parse_uint(parts[3])
        idle = parse_uint(parts[4])
        iowait = parse_uint(parts[5]) if len(parts) > 5 else 0
        irq = parse_uint(parts[6]) if len(parts) > 6 else 0
        softirq = parse_uint(parts[7]) if len(parts) > 7 else 0
        steal = parse_uint(parts[8]) if len(parts) > 8 else 0

        total = user + nice + system + idle + iowait + irq + softirq + steal
        if _prev_total == 0:
            _prev_total = total
            _prev_idle = idle
            return -1
        d_total = total - _prev_total
        d_idle = idle - _prev_idle
        _prev_total = total
        _prev_idle = idle
        if d_total == 0:
            return 0.0
        pct = 100.0 * (d_total - d_idle) / d_total
        return max(0.0, min(100.0, pct))
    except OSError:
        return -1


def get_mem() -> MemInfo:
    mem = MemInfo()
    try:
        data = Path("/proc/meminfo").read_text()
        m: dict[str, int] = {}
        for line in data.splitlines():
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            key = parts[0]
            val = parts[1].strip().removesuffix(" kB")
            m[key] = parse_uint(val) * 1024

        mem.total_bytes = m.get("MemTotal", 0)
        mem.cached_bytes = m.get("Buffers", 0) + m.get("Cached", 0)
        mem.free_bytes = m.get("MemFree", 0)
        avail = m.get("MemAvailable", 0)
        if avail > 0:
            mem.used_bytes = mem.total_bytes - avail
        else:
            mem.used_bytes = mem.total_bytes - mem.free_bytes - mem.cached_bytes
        if mem.total_bytes > 0:
            mem.used_pct = 100.0 * mem.used_bytes / mem.total_bytes
        mem.swap_total = m.get("SwapTotal", 0)
        mem.swap_used = mem.swap_total - m.get("SwapFree", 0)
    except OSError:
        pass
    return mem


def get_disk() -> DiskInfo:
    d = DiskInfo()
    out = run_cmd("df", ["-k", "/"])
    if not out:
        return d
    lines = out.splitlines()
    if len(lines) < 2:
        return d
    fields = lines[1].split()
    if len(fields) >= 6:
        d.path = fields[5]
        d.total_bytes = parse_uint(fields[1]) * 1024
        d.used_bytes = parse_uint(fields[2]) * 1024
        d.free_bytes = parse_uint(fields[3]) * 1024
        d.used_pct = parse_float(fields[4].rstrip("%"))
    return d


def get_temp() -> TempInfo:
    t = TempInfo()
    t.cpu_celsius = -1

    thermal_dir = Path("/sys/class/thermal")
    if not thermal_dir.is_dir():
        return t

    first = -1.0
    for zone in sorted(thermal_dir.iterdir()):
        name = zone.name
        if not name.startswith("thermal_zone"):
            continue
        try:
            ttype = (zone / "type").read_text().strip()
            temp_raw = (zone / "temp").read_text().strip()
        except OSError:
            continue
        v = parse_float(temp_raw) / 1000.0
        if v < 0 or v > 200:
            continue
        if first < 0:
            first = v
        lower = ttype.lower()
        if any(kw in lower for kw in ("cpu", "pkg", "x86", "acpitz")):
            t.cpu_celsius = v
            return t

    if first >= 0:
        t.cpu_celsius = first
    return t


def get_gpu() -> GPUInfo:
    g = GPUInfo()
    if shutil.which("nvidia-smi"):
        out = run_cmd("nvidia-smi", [
            "--query-gpu=name,temperature.gpu,clocks.current.graphics,"
            "clocks.current.memory,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ])
        if out:
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 7:
                g.model = parts[0]
                g.temp_celsius = parse_float(parts[1])
                g.core_clock_mhz = parse_float(parts[2])
                g.mem_clock_mhz = parse_float(parts[3])
                g.vram_bytes = int(parse_float(parts[4]) * 1024 * 1024)
                g.usage_pct = parse_float(parts[6])
    return g


def get_battery() -> BatteryInfo:
    b = BatteryInfo()
    base = Path("/sys/class/power_supply/BAT0")
    if not base.is_dir():
        return b

    def _read_int(p: Path) -> int:
        try:
            return parse_uint(p.read_text().strip())
        except OSError:
            return 0

    def _read_str(p: Path) -> str:
        try:
            return p.read_text().strip()
        except OSError:
            return ""

    charge_full = _read_int(base / "charge_full")
    charge_now = _read_int(base / "charge_now")
    energy_full = _read_int(base / "energy_full")
    energy_now = _read_int(base / "energy_now")

    full = 0
    now = 0
    if charge_full > 0:
        full, now = charge_full, charge_now
    elif energy_full > 0:
        full, now = energy_full, energy_now

    if full > 0:
        b.charge_pct = now * 100.0 / full

    if _read_str(base / "status") == "Charging":
        b.charging = True

    cycle_str = _read_str(base / "cycle_count")
    if cycle_str:
        b.cycles = parse_uint(cycle_str)

    b.condition = _read_str(base / "health")
    return b


def get_power() -> PowerInfo:
    return PowerInfo()
