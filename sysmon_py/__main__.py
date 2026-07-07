from __future__ import annotations

import argparse
import json
import platform
import signal
import sys
import time

from .core import (
    Info,
    CPUInfo,
    MemInfo,
    DiskInfo,
    TempInfo,
    GPUInfo,
    BatteryInfo,
    PowerInfo,
    bytes_str,
    freq_str,
    pct_str,
    bar,
)

VERSION = "0.1.0"

LOGO = [
    "sssysmon??//////",
    "= :X x: OOOO |\\  |",
    "= : x : O  O | \\ |",
    "= :   : OOOO |  \\|",
    "=::::::::::::>>",
    "\t\t\t[]",
    "\t\t\t[]",
    "\t\t\t[]",
    '\\nsysmon"*m">',
]


def _get_platform_module():
    system = platform.system()
    if system == "Linux":
        from . import linux
        return linux
    elif system == "Darwin":
        from . import darwin
        return darwin
    elif system == "Windows":
        from . import windows
        return windows
    else:
        print(f"Unsupported platform: {system}", file=sys.stderr)
        sys.exit(1)


def refresh(mod) -> Info:
    return Info(
        cpu=mod.get_cpu(),
        mem=mod.get_mem(),
        disk=mod.get_disk(),
        temp=mod.get_temp(),
        gpu=mod.get_gpu(),
        battery=mod.get_battery(),
        power=mod.get_power(),
    )


def expand_tabs(s: str) -> str:
    return s.replace("\t", "    ")


def format_info_lines(info: Info, interval: int) -> list[str]:
    lines: list[str] = []

    lines.append(f"sysmon  refresh: {interval}s")

    cores = f"{info.cpu.cores}C/{info.cpu.logical_cores}T"
    cpct = pct_str(info.cpu.usage_pct)
    cfreq = freq_str(info.cpu.freq_mhz)
    sec = cores
    if cfreq:
        sec += " " + cfreq
    lines.append(f"CPU  {info.cpu.model}  {sec}  {cpct} {bar(info.cpu.usage_pct)}")

    mem_str = f"{bytes_str(info.mem.used_bytes)} / {bytes_str(info.mem.total_bytes)}"
    mem_sec = ""
    if info.mem.cached_bytes > 0:
        mem_sec = "Cache: " + bytes_str(info.mem.cached_bytes)
    lines.append(f"MEM  {mem_str}  {mem_sec}  {pct_str(info.mem.used_pct)} {bar(info.mem.used_pct)}")

    if info.mem.swap_total > 0:
        swp_str = f"{bytes_str(info.mem.swap_used)} / {bytes_str(info.mem.swap_total)}"
        swp_pct = 100.0 * info.mem.swap_used / info.mem.swap_total
        lines.append(f"SWP  {swp_str}  {pct_str(swp_pct)}")

    if info.disk.total_bytes > 0:
        dsk_str = f"{bytes_str(info.disk.used_bytes)} / {bytes_str(info.disk.total_bytes)}"
        lines.append(f"DSK  {dsk_str}  {pct_str(info.disk.used_pct)} {bar(info.disk.used_pct)}")

    cpu_t = info.temp.cpu_celsius
    if cpu_t >= 0:
        lines.append(f"TMP  CPU: {cpu_t:.0f}\u00b0C")
    elif cpu_t == -2:
        lines.append("TMP  Normal")
    elif cpu_t == -3:
        lines.append("TMP  Moderate")
    elif cpu_t == -4:
        lines.append("TMP  Heavy")
    elif cpu_t == -5:
        lines.append("TMP  Critical")

    if info.battery.charge_pct >= 0:
        bat_stat = "Discharging"
        if info.battery.charging and info.battery.charge_pct >= 100:
            bat_stat = "Charged"
        elif info.battery.charging:
            bat_stat = "Charging"
        bat_sec = ""
        if info.battery.cycles >= 0:
            bat_sec = f"{info.battery.cycles} cycles"
        if info.battery.condition and info.battery.condition != "Normal":
            if bat_sec:
                bat_sec += " "
            bat_sec += info.battery.condition
        lines.append(f"BAT  {bat_stat}  {bat_sec}  {pct_str(info.battery.charge_pct)} {bar(info.battery.charge_pct)}")

    if info.power.system_watts >= 0:
        lines.append(f"PWR  {info.power.system_watts:.1f} W")

    if info.gpu.model:
        gpu_sec = ""
        if info.gpu.vram_bytes > 0:
            gpu_sec = bytes_str(info.gpu.vram_bytes)
            if info.gpu.model.startswith("Apple"):
                gpu_sec += " Unified"
        if info.gpu.core_clock_mhz > 0:
            if gpu_sec:
                gpu_sec += "  "
            gpu_sec += freq_str(info.gpu.core_clock_mhz)

        lines.append(f"GPU  {info.gpu.model}  {gpu_sec}  {pct_str(info.gpu.usage_pct)} {bar(info.gpu.usage_pct)}")

        ext: list[str] = []
        if info.gpu.mem_clock_mhz > 0:
            ext.append("Mem: " + freq_str(info.gpu.mem_clock_mhz))
        if info.gpu.temp_celsius >= 0:
            ext.append(f"{info.gpu.temp_celsius:.0f}\u00b0C")
        if ext:
            lines.append(f"GPU  {'  '.join(ext)}")

    return lines


def print_info(info: Info, interval: int) -> None:
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()

    lines = format_info_lines(info, interval)
    max_logo = len(LOGO)
    logo_col = 28

    for i in range(max(len(lines), max_logo)):
        logo_line = ""
        if i < max_logo:
            logo_line = expand_tabs(LOGO[i])
        info_line = ""
        if i < len(lines):
            info_line = lines[i]
        if logo_line and info_line:
            n = max(0, logo_col - len(logo_line))
            print(f"{logo_line}{' ' * n}{info_line}")
        elif logo_line:
            print(logo_line)
        elif info_line:
            print(f"{' ' * logo_col}{info_line}")
        else:
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight system monitor")
    parser.add_argument("-v", action="store_true", help="print version and exit")
    parser.add_argument("-i", type=int, default=1, help="refresh interval in seconds (default: 1)")
    parser.add_argument("-o", action="store_true", help="print once and exit")
    parser.add_argument("-j", action="store_true", help="JSON output (one line per sample)")
    args = parser.parse_args()

    if args.v:
        print(f"sysmon {VERSION}")
        return

    mod = _get_platform_module()

    def handler(signum, frame):
        print()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    if args.o:
        info = refresh(mod)
        if args.j:
            print(json.dumps(_info_to_dict(info)))
        else:
            print_info(info, args.i)
        return

    info = refresh(mod)
    if args.j:
        print(json.dumps(_info_to_dict(info)))
    else:
        print_info(info, args.i)

    while True:
        time.sleep(args.i)
        info = refresh(mod)
        if args.j:
            print(json.dumps(_info_to_dict(info)))
        else:
            print_info(info, args.i)


def _info_to_dict(info: Info) -> dict:
    from dataclasses import asdict
    return asdict(info)


if __name__ == "__main__":
    main()
