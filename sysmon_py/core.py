from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CPUInfo:
    model: str = ""
    cores: int = 0
    logical_cores: int = 0
    freq_mhz: float = 0.0
    usage_pct: float = 0.0


@dataclass
class MemInfo:
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    cached_bytes: int = 0
    used_pct: float = 0.0
    swap_total: int = 0
    swap_used: int = 0


@dataclass
class DiskInfo:
    path: str = ""
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    used_pct: float = 0.0


@dataclass
class TempInfo:
    cpu_celsius: float = -1.0


@dataclass
class GPUInfo:
    model: str = ""
    vram_bytes: int = 0
    core_clock_mhz: float = 0.0
    mem_clock_mhz: float = 0.0
    temp_celsius: float = -1.0
    usage_pct: float = -1.0


@dataclass
class BatteryInfo:
    charge_pct: float = -1.0
    cycles: int = -1
    condition: str = ""
    charging: bool = False


@dataclass
class PowerInfo:
    system_watts: float = -1.0


@dataclass
class Info:
    cpu: CPUInfo = field(default_factory=CPUInfo)
    mem: MemInfo = field(default_factory=MemInfo)
    disk: DiskInfo = field(default_factory=DiskInfo)
    temp: TempInfo = field(default_factory=TempInfo)
    gpu: GPUInfo = field(default_factory=GPUInfo)
    battery: BatteryInfo = field(default_factory=BatteryInfo)
    power: PowerInfo = field(default_factory=PowerInfo)


def run_cmd(name: str, args: list[str], timeout: float = 5.0) -> str:
    try:
        result = subprocess.run(
            [name] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def parse_uint(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, TypeError):
        return 0


def parse_float(s: str) -> float:
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return 0.0


def bytes_str(b: int) -> str:
    if b == 0:
        return "0"
    unit = 1024
    if b < unit:
        return f"{b} B"
    div, exp = unit, 0
    n = b // unit
    while n >= unit:
        div *= unit
        exp += 1
        n //= unit
    return f"{b / div:.1f} {'KMGTPE'[exp]}B"


def freq_str(mhz: float) -> str:
    if mhz <= 0:
        return ""
    if mhz >= 1000:
        return f"{mhz / 1000:.2f} GHz"
    return f"{mhz:.0f} MHz"


def pct_str(pct: float) -> str:
    if pct < 0:
        return ""
    return f"{pct:.0f}%"


def bar(pct: float, w: int = 8) -> str:
    if pct < 0:
        return ""
    filled = int(pct * w / 100.0)
    filled = max(0, min(w, filled))
    return "\u2588" * filled + "\u2591" * (w - filled)
