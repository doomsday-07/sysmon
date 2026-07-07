from __future__ import annotations

import shutil
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


def _wmic(query: str) -> str:
    return run_cmd("wmic", query.split())


def get_cpu() -> CPUInfo:
    info = CPUInfo()

    out = _wmic("cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 5:
            info.model = parts[1]
            info.cores = parse_uint(parts[2])
            info.logical_cores = parse_uint(parts[3])
            info.freq_mhz = parse_float(parts[4])

    out = _wmic("cpu get LoadPercentage /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 2:
            info.usage_pct = parse_float(parts[1])

    if info.logical_cores == 0:
        info.logical_cores = info.cores
    return info


def get_mem() -> MemInfo:
    mem = MemInfo()

    out = _wmic("OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 2:
            total_kb = parse_uint(parts[1])
            mem.total_bytes = total_kb * 1024
        if len(parts) >= 3:
            free_kb = parse_uint(parts[2])
            mem.free_bytes = free_kb * 1024
        mem.used_bytes = mem.total_bytes - mem.free_bytes
        if mem.total_bytes > 0:
            mem.used_pct = 100.0 * mem.used_bytes / mem.total_bytes

    out = _wmic("pagefile get AllocatedBaseSize,CurrentUsage /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 3:
            total_mb = parse_uint(parts[1])
            used_mb = parse_uint(parts[2])
            mem.swap_total = total_mb * 1024 * 1024
            mem.swap_used = used_mb * 1024 * 1024

    return mem


def get_disk() -> DiskInfo:
    d = DiskInfo()
    out = _wmic("LogicalDisk where DriveType=3 get DeviceID,Size,FreeSpace /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 3:
            d.path = parts[1].strip()
            d.total_bytes = parse_uint(parts[2])
            d.free_bytes = parse_uint(parts[3])
            d.used_bytes = d.total_bytes - d.free_bytes
            if d.total_bytes > 0:
                d.used_pct = 100.0 * d.used_bytes / d.total_bytes
    return d


def get_temp() -> TempInfo:
    t = TempInfo()
    t.cpu_celsius = -1

    out = _wmic(r'/namespace:\\root\wmi path MSAcpi_ThermalZoneTemperature get CurrentTemperature /format:csv')
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) >= 2:
            v = parse_float(parts[1])
            if v > 0:
                t.cpu_celsius = v / 10.0 - 273.15
                return t

    out = _wmic("path Win32_PerfFormattedData_Counters_ThermalZoneInformation get Temperature /format:csv")
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) >= 2:
            v = parse_float(parts[1])
            if v > 0:
                t.cpu_celsius = v / 10.0
                return t

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

    out = _wmic("path Win32_VideoController get Name,AdapterRAM /format:csv")
    lines = out.splitlines()
    if len(lines) >= 2:
        parts = lines[1].split(",")
        if len(parts) >= 3:
            g.model = parts[1]
            g.vram_bytes = parse_uint(parts[2])

    return g


def get_battery() -> BatteryInfo:
    b = BatteryInfo()

    out = _wmic("path Win32_Battery get EstimatedChargeRemaining,BatteryStatus,CycleCount /format:csv")
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) < 3:
            continue
        if parts[0] == "" or parts[0] == "Node":
            continue
        v = parse_float(parts[1])
        if 0 <= v <= 100:
            b.charge_pct = v
        b.cycles = parse_uint(parts[2])
        if len(parts) >= 3:
            status = parse_uint(parts[2])
            b.charging = status == 2 or status == 3
        break

    return b


def get_power() -> PowerInfo:
    return PowerInfo()
