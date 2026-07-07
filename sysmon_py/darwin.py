from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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

_prev_ticks_total: int = 0
_prev_ticks_idle: int = 0

_gpu_cache: Optional[GPUInfo] = None


@dataclass
class _PMData:
    cpu_temp: float = -1.0
    gpu_util: float = -1.0
    gpu_temp: float = -1.0


_pm_cache = _PMData()
_pm_cache_time: float = 0


def _run_timeout(name: str, args: list[str] | None = None, timeout: float = 3.0) -> str:
    if args is None:
        args = []
    return run_cmd(name, args, timeout=timeout)


def _run_privileged(name: str, args: list[str]) -> str:
    if os.geteuid() == 0:
        return _run_timeout(name, args)
    return run_cmd("sudo", ["-n", name] + args)


def _get_pm() -> _PMData:
    global _pm_cache, _pm_cache_time
    if time.monotonic() - _pm_cache_time < 2:
        return _pm_cache
    _pm_cache = _PMData()
    _pm_cache_time = time.monotonic()

    if not _which("powermetrics"):
        return _pm_cache

    variants = [
        ["--samplers", "cpu_power,gpu_power", "-n", "1"],
        ["--samplers", "cpu_power", "--samplers", "gpu_power", "-n", "1"],
        ["-A", "-n", "1"],
        ["--samplers", "all", "-n", "1"],
        ["--samplers", "smc,gpu_dvfs", "-n", "1"],
        ["--samplers", "smc", "--samplers", "gpu_dvfs", "-n", "1"],
        ["--samplers", "smc", "-n", "1"],
        ["--samplers", "power", "-n", "1"],
        ["-n", "1"],
    ]

    out = ""
    for v in variants:
        out = _run_privileged("powermetrics", v)
        if out:
            break
    if not out:
        return _pm_cache

    temp_keywords = ("cpu", "gpu", "die", "temp", "thermal", "sensor", "pmu", "soc")

    for line in out.splitlines():
        line = line.strip()
        lower = line.lower()

        temp = _extract_temp(line)
        if temp >= 0:
            if any(kw in lower for kw in ("cpu", "die")):
                _pm_cache.cpu_temp = temp
            if "gpu" in lower:
                _pm_cache.gpu_temp = temp
            continue

        has_kw = any(kw in lower for kw in temp_keywords)
        if has_kw:
            t = _extract_number_temp(line)
            if t >= 0:
                if any(kw in lower for kw in ("cpu", "die")):
                    _pm_cache.cpu_temp = t
                if "gpu" in lower:
                    _pm_cache.gpu_temp = t

        if "gpu busy" in lower:
            parts = line.split()
            for p in parts:
                v = parse_float(p.rstrip("%"))
                if 0 <= v <= 100:
                    _pm_cache.gpu_util = v
                    break

    return _pm_cache


def _extract_temp(line: str) -> float:
    for f in line.split():
        clean = f.rstrip("°C").rstrip("℃")
        v = parse_float(clean)
        if 0 < v < 150 and ("°" in f or "℃" in f):
            return v
    return -1


def _extract_number_temp(line: str) -> float:
    for f in line.split():
        v = parse_float(f)
        if 20 <= v <= 110:
            return v
    return -1


def _which(cmd: str) -> bool:
    import shutil
    return shutil.which(cmd) is not None


def _cpu_usage_from_ps() -> float:
    out = _run_timeout("ps", ["-A", "-o", "%cpu"])
    if not out:
        return -1
    total = sum(parse_float(line) for line in out.splitlines())
    ncpu = parse_float(_run_timeout("sysctl", ["-n", "hw.logicalcpu"]))
    if ncpu <= 0:
        ncpu = 1
    pct = total / ncpu
    return max(0.0, min(100.0, pct))


def get_cpu() -> CPUInfo:
    global _prev_ticks_total, _prev_ticks_idle
    info = CPUInfo(usage_pct=-1)

    info.model = _run_timeout("sysctl", ["-n", "machdep.cpu.brand_string"])
    info.cores = parse_uint(_run_timeout("sysctl", ["-n", "hw.physicalcpu"]))
    info.logical_cores = parse_uint(_run_timeout("sysctl", ["-n", "hw.logicalcpu"]))

    f = _run_timeout("sysctl", ["-n", "hw.cpufrequency"])
    if f:
        info.freq_mhz = parse_float(f) / 1_000_000

    out = _run_timeout("sysctl", ["-n", "kern.cp_time"])
    if out:
        parts = out.split()
        if len(parts) >= 4:
            user = parse_uint(parts[0])
            nice = parse_uint(parts[1])
            system = parse_uint(parts[2])
            idle = parse_uint(parts[3])
            total = user + nice + system + idle
            if _prev_ticks_total > 0:
                d_total = total - _prev_ticks_total
                d_idle = idle - _prev_ticks_idle
                if d_total > 0:
                    pct = 100.0 * (d_total - d_idle) / d_total
                    info.usage_pct = max(0.0, min(100.0, pct))
            _prev_ticks_total = total
            _prev_ticks_idle = idle
    else:
        info.usage_pct = _cpu_usage_from_ps()

    if not info.model:
        info.model = _run_timeout("sysctl", ["-n", "hw.model"])
    return info


def _clean_num(line: str) -> str:
    parts = line.split(":", 1)
    if len(parts) != 2:
        return ""
    return parts[1].strip().rstrip(".")


def get_mem() -> MemInfo:
    mem = MemInfo()

    total = _run_timeout("sysctl", ["-n", "hw.memsize"])
    mem.total_bytes = parse_uint(total)

    out = _run_timeout("vm_stat")
    if not out:
        return mem

    page_size = 16384
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("page size of"):
            parts = line.split()
            if len(parts) >= 4:
                page_size = parse_uint(parts[3].rstrip("."))

    pages_free = pages_active = pages_inactive = 0
    pages_speculative = pages_wired = pages_compressed = 0
    pages_file_backed = pages_purgeable = 0

    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Pages free:"):
            pages_free = parse_uint(_clean_num(line))
        elif line.startswith("Pages active:"):
            pages_active = parse_uint(_clean_num(line))
        elif line.startswith("Pages inactive:"):
            pages_inactive = parse_uint(_clean_num(line))
        elif line.startswith("Pages speculative:"):
            pages_speculative = parse_uint(_clean_num(line))
        elif line.startswith("Pages wired down:"):
            pages_wired = parse_uint(_clean_num(line))
        elif line.startswith("Pages occupied by compressor:"):
            pages_compressed = parse_uint(_clean_num(line))
        elif line.startswith("Pages file backed:"):
            pages_file_backed = parse_uint(_clean_num(line))
        elif line.startswith("Pages purgeable:"):
            pages_purgeable = parse_uint(_clean_num(line))
            mem.cached_bytes = pages_purgeable * page_size

    free_pages = pages_free + pages_inactive + pages_speculative
    used_pages = pages_active + pages_wired + pages_compressed
    total_pages = free_pages + used_pages

    if mem.total_bytes == 0:
        mem.total_bytes = total_pages * page_size
    if mem.cached_bytes == 0 and pages_file_backed > 0:
        mem.cached_bytes = pages_file_backed * page_size
    mem.free_bytes = free_pages * page_size
    mem.used_bytes = mem.total_bytes - mem.free_bytes
    if mem.total_bytes > 0:
        mem.used_pct = 100.0 * mem.used_bytes / mem.total_bytes

    return mem


def get_disk() -> DiskInfo:
    d = DiskInfo()
    for p in ["/System/Volumes/Data", "/"]:
        out = _run_timeout("df", ["-k", p])
        if not out:
            continue
        lines = out.splitlines()
        if len(lines) < 2:
            continue
        fields = lines[1].split()
        if len(fields) >= 9:
            d.path = fields[8]
            d.total_bytes = parse_uint(fields[1]) * 1024
            d.used_bytes = parse_uint(fields[2]) * 1024
            d.free_bytes = parse_uint(fields[3]) * 1024
            d.used_pct = parse_float(fields[4].rstrip("%"))
            if d.total_bytes > 0:
                return d
    return d


def get_temp() -> TempInfo:
    t = TempInfo()
    t.cpu_celsius = -1

    level = _run_timeout("sysctl", ["-n", "machdep.xcpm.cpu_thermal_level"])
    if level:
        l = parse_float(level)
        if 0 <= l <= 127:
            t.cpu_celsius = 30.0 + (l / 127.0) * 70.0
            return t

    pm = _get_pm()
    if pm.cpu_temp >= 0:
        t.cpu_celsius = pm.cpu_temp
        return t

    out = _run_timeout("pmset", ["-g", "therm"])
    if out:
        idx = out.find("Thermal Warning Level = ")
        if idx >= 0:
            s = out[idx + 24:]
            nl = s.find("\n")
            if nl >= 0:
                s = s[:nl]
            s = s.strip()
            lvl = parse_float(s)
            mapping = {0: -2, 1: -3, 2: -4}
            t.cpu_celsius = mapping.get(int(lvl), -5 if lvl >= 3 else -1)
            return t
        if "No thermal warning" in out:
            t.cpu_celsius = -2
            return t

    return t


def _parse_vram(s: str) -> int:
    s = s.strip()
    mult = 1
    if s.endswith("GB"):
        mult = 1024 * 1024 * 1024
        s = s[:-2]
    elif s.endswith("MB"):
        mult = 1024 * 1024
        s = s[:-2]
    return int(parse_float(s) * mult)


def get_gpu() -> GPUInfo:
    global _gpu_cache
    if _gpu_cache is None:
        _gpu_cache = GPUInfo()
        out = _run_timeout("system_profiler", ["SPDisplaysDataType"])
        if out:
            lines = out.splitlines()
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith("Chipset Model:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        _gpu_cache.model = parts[1].strip()
                if line.startswith("VRAM (Total):"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        _gpu_cache.vram_bytes = _parse_vram(parts[1])
                if "GB" in line and "Unified" in line and not _gpu_cache.model:
                    if i > 0:
                        prev = lines[i - 1].strip()
                        if prev.startswith("Chipset Model:") or not _gpu_cache.model:
                            parts = prev.split(":", 1)
                            if len(parts) == 2:
                                _gpu_cache.model = parts[1].strip()
                    fields = line.split()
                    for j, f in enumerate(fields):
                        if f == "GB" and j > 0:
                            v = parse_uint(fields[j - 1])
                            _gpu_cache.vram_bytes = v * 1024 * 1024 * 1024

            if _gpu_cache.vram_bytes == 0 and "Apple" in _gpu_cache.model:
                total = parse_uint(_run_timeout("sysctl", ["-n", "hw.memsize"]))
                _gpu_cache.vram_bytes = total

            if not _gpu_cache.model:
                ioreg = _run_timeout("ioreg", ["-r", "-c", "IOAccelerator", "-n", "AppleGraphicsControl"])
                if ioreg:
                    for line in ioreg.splitlines():
                        line = line.strip()
                        if '"model"' in line:
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                _gpu_cache.model = parts[1].strip().strip('"')

    g = GPUInfo(
        model=_gpu_cache.model,
        vram_bytes=_gpu_cache.vram_bytes,
        core_clock_mhz=_gpu_cache.core_clock_mhz,
        mem_clock_mhz=_gpu_cache.mem_clock_mhz,
        temp_celsius=_gpu_cache.temp_celsius,
        usage_pct=_gpu_cache.usage_pct,
    )

    pm = _get_pm()
    if pm.gpu_temp >= 0:
        g.temp_celsius = pm.gpu_temp
    if pm.gpu_util >= 0:
        g.usage_pct = pm.gpu_util
    return g


def get_battery() -> BatteryInfo:
    b = BatteryInfo()

    out = _run_timeout("system_profiler", ["SPPowerDataType"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Cycle Count:"):
                b.cycles = parse_uint(line.removeprefix("Cycle Count:"))
            elif line.startswith("Condition:"):
                b.condition = line.removeprefix("Condition:").strip()
            elif line.startswith("Charge Remaining (mAh):") or line.startswith("State of Charge (%):"):
                key = line.split(":")[0] + ":"
                v = parse_float(line.removeprefix(key))
                if 0 <= v <= 100:
                    b.charge_pct = v

    out = _run_timeout("pmset", ["-g", "batt"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if ";" not in line:
                continue
            parts = line.split("\t")
            for p in parts:
                p = p.strip()
                if "%" in p:
                    pct_str = p[:p.index("%")]
                    v = parse_float(pct_str)
                    if 0 <= v <= 100:
                        b.charge_pct = v
                    break
            if "discharging" in line:
                b.charging = False
            elif "charging" in line or "charged;" in line:
                b.charging = True
            break

    return b


def get_power() -> PowerInfo:
    p = PowerInfo()

    out = _run_privileged("powermetrics", ["--samplers", "power", "-i", "1000", "-n", "1"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Combined Power (CPU + GPU + ANE):"):
                rest = line.removeprefix("Combined Power (CPU + GPU + ANE):").strip()
                if rest.endswith("mW"):
                    mw = parse_float(rest[:-2])
                    if mw > 0:
                        p.system_watts = mw / 1000.0
                break
        if p.system_watts >= 0:
            return p

    out = _run_timeout("ioreg", ["-r", "-c", "AppleSmartBattery"])
    if out:
        idx = out.find('"SystemLoad"=')
        if idx >= 0:
            rest = out[idx + 13:]
            end = min(rest.find(","), rest.find("}")) if "," in rest or "}" in rest else len(rest)
            v = parse_float(rest[:end])
            if v > 0:
                p.system_watts = v / 1000.0

    return p
