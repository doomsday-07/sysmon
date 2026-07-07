# sysmon

Lightweight cross-platform system monitor CLI. Shows CPU, memory, disk, temperature, GPU, battery, and power usage.

**Zero external dependencies** — pure Python stdlib.

## Supported Platforms

| Platform | Status |
|----------|--------|
| macOS (Intel & Apple Silicon) | Supported |
| Linux (x86_64, ARM) | Supported |
| Windows (x86_64) | Supported |

## Installation

```bash
pip install .
```

Or for development:

```bash
pip install -e .
```

### Requirements

- Python 3.9+
- No external packages needed

## Usage

```bash
sysmon                # live mode, refreshes every 1s
sysmon -o             # snapshot once then exit
sysmon -j             # JSON output (pipe to jq)
sysmon -i 3           # refresh every 3 seconds
sysmon -o -n          # one shot, no ANSI colors
sysmon -v             # show version
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-i` | `1` | Refresh interval in seconds |
| `-o` | `false` | Print once then exit |
| `-j` | `false` | JSON output (one line per sample) |
| `-v` | `false` | Print version and exit |

## Example Output

```
sysmon  refresh: 1s
CPU  Apple M5                     10C/10T              10% ░░░░░░░░░░
MEM  12.2 GB / 24.0 GB            Cache: 825.0 MB      51% █████░░░░░
DSK  11.7 GB / 460.4 GB                                 6% ░░░░░░░░░░
TMP  Normal
GPU  Apple M5                     24.0 GB
```

## Data Sources by Platform

| Metric | Linux | macOS | Windows |
|--------|-------|-------|---------|
| CPU model | `/proc/cpuinfo` | `sysctl` | `wmic` |
| CPU usage | `/proc/stat` delta | `kern.cp_time` / `ps` | `wmic` |
| Memory | `/proc/meminfo` | `vm_stat` + `sysctl` | `wmic` |
| Disk | `df` | `df` | `wmic` |
| Temperature | `/sys/class/thermal` | `powermetrics` / `pmset` | WMI `MSAcpi_ThermalZoneTemperature` |
| GPU | `nvidia-smi` | `system_profiler` | `nvidia-smi` / `wmic` |

## License

MIT
