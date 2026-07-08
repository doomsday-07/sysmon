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

### Pre-built Binaries (no Python required)

Download the latest binary for your platform from [GitHub Releases](https://github.com/shadow/sysmon/releases):

| Platform | File | Size |
|----------|------|------|
| macOS (.app bundle) | `sysmon-macos.tar.gz` | ~3.7 MB |
| Linux (.deb package) | `sysmon-linux.deb` | ~3.5 MB |
| Windows (.exe) | `sysmon-windows.zip` | ~3.5 MB |

```bash
# macOS — extract and run the .app
tar -xzf sysmon-macos.tar.gz
open sysmon.app
# Or directly: sysmon.app/Contents/MacOS/sysmon

# Linux — install the .deb
sudo dpkg -i sysmon-linux.deb
sysmon

# Windows — extract and run sysmon.exe
# Extract the .zip and run sysmon.exe
```

### From Source (requires Python 3.9+)

```bash
pip install .
```

Or for development:

```bash
pip install -e ".[dev]"
make build       # build single-file binary
make build-app   # build macOS .app bundle
make build-deb   # build Linux .deb package
```

### Requirements

- Python 3.9+ (only when installing from source)
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
