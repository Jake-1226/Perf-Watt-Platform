# Benchmark System Architecture

The benchmark system consists of a Python orchestrator that deploys and controls a Bash script agent on remote servers to execute various workloads while collecting telemetry data.

## Overview

```
Operator Machine                Remote Server
┌─────────────────┐           ┌─────────────────┐
│ FastAPI Backend  │  SSH/SFTP │  bench_agent.sh │
│ BenchmarkOrchestrator ───────► │  (Bash Script)  │
│                 │           │                 │
│ - Deploy agent  │           │ - Install deps  │
│ - Run phases    │           │ - Build HPL     │
│ - Stream logs   │           │ - Execute FIO    │
│ - Cleanup       │           │ - Run stress-ng  │
└─────────────────┘           └─────────────────┘
```

## Benchmark Agent (`bench_agent.sh`)

The benchmark agent is a 350-line Bash script that gets deployed to `/tmp/bench_agent.sh` on the remote server. It handles all local benchmark execution.

### Agent Actions

| Action | Purpose | Key Operations |
|--------|---------|----------------|
| `install_deps` | Install required packages | `apt-get install`, verify tools |
| `setup_hpl` | Build HPL from source | Download, configure, make, fix ownership |
| `run_hpl` | Execute HPL benchmark | Multiple parallel instances with CPU pinning |
| `run_fio` | Run storage I/O benchmark | Generate config, execute randrw workload |
| `run_stress_ng` | CPU stress testing | `stress-ng --cpu` with core count |
| `sysinfo` | Collect system information | Dump CPU, memory, disks, BIOS details |

### Agent Architecture

```bash
#!/bin/bash
# Performance benchmark agent — deployed by perf-platform
set -uo pipefail

ACTION="$1"
shift

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [AGENT] $*"; }

# Sudo helper: uses SUDO_PASS env var if available, otherwise plain sudo
do_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif [ -n "${SUDO_PASS:-}" ]; then
        echo "$SUDO_PASS" | sudo -S "$@" 2>&1
    else
        sudo "$@" 2>&1
    fi
}

case "$ACTION" in
    install_deps) ... ;;
    setup_hpl) ... ;;
    run_hpl) ... ;;
    run_fio) ... ;;
    run_stress_ng) ... ;;
    sysinfo) ... ;;
    *) echo "Unknown action: $ACTION" ;;
esac
```

## HPL (High Performance Linpack)

### HPL Build Process

```bash
# 1. Download HPL 2.3
wget -q http://www.netlib.org/benchmark/hpl/hpl-2.3.tar.gz
tar -xzf hpl-2.3.tar.gz && mv hpl-2.3 hpl

# 2. Configure Make.Linux
# Detect MPI paths, BLAS library
MPI_INC="/usr/lib/x86_64-linux-gnu/openmpi/include"
MPI_LIB="/usr/lib/x86_64-linux-gnu/openmpi/lib"
BLAS_LIB="-lopenblas"

# 3. Build
make arch=Linux

# 4. Fix ownership (critical for HPL.dat write access)
do_sudo chown -R "${REAL_USER}:${REAL_USER}" "$HPL_DIR"
```

### HPL Execution Strategy

**Problem**: `mpirun ./xhpl` segfaults due to vendor/system MPI version mismatch.

**Solution**: Run multiple parallel `./xhpl` instances directly with CPU pinning:

```bash
# Determine instance count based on cores
TOTAL=$(nproc)
if [ "$CORES" -le 4 ]; then
    INSTANCES=1; THREADS_PER=$CORES
elif [ "$CORES" -le 16 ]; then
    INSTANCES=2; THREADS_PER=$(( CORES / 2 ))
elif [ "$CORES" -le 48 ]; then
    INSTANCES=4; THREADS_PER=$(( CORES / 4 ))
else
    INSTANCES=8; THREADS_PER=$(( CORES / 8 ))
fi

# Calculate matrix size (60% of memory per instance)
MEM=$(free -b | awk '/^Mem:/{print $2}')
MEM_PER=$(( MEM / INSTANCES ))
N_RAW=$(echo "sqrt($MEM_PER * 0.6 / 8)" | bc 2>/dev/null || echo "40000")
N=$(( (N_RAW / 192) * 192 ))  # Round to block size
[ "$N" -lt 5000 ] && N=5000
[ "$N" -gt 80000 ] && N=80000

# Run parallel instances with CPU pinning
for i in $(seq 0 $((INSTANCES - 1))); do
    CORE_START=$(( i * THREADS_PER ))
    CORE_END=$(( CORE_START + THREADS_PER - 1 ))
    (
        cd "/tmp/hpl_inst_$i"
        export OPENBLAS_NUM_THREADS=$THREADS_PER
        timeout "$T" taskset -c "${CORE_START}-${CORE_END}" ./xhpl > output.log 2>&1
    ) &
done
```

### HPL Configuration

Each instance gets its own `HPL.dat`:

```
HPLinpack benchmark input file
Innovative Computing Laboratory, University of Tennessee
HPL.out      output file name (if any)
6            device out (6=stdout,7=stderr,file)
1            # of problems sizes (N)
${N}         Ns
1            # of NBs
${NB}        NBs
0            PMAP process mapping (0=Row-,1=Column-major)
1            # of process grids (P x Q)
1            Ps
1            Qs
16.0         threshold
1            # of panel fact
2            PFACTs (0=left, 1=Crout, 2=Right)
1            # of recursive stopping criterium
4            NBMINs (>= 1)
1            # of panels in recursion
2            NDIVs
1            # of recursive panel fact.
1            RFACTs (0=left, 1=Crout, 2=Right)
1            # of broadcast
1            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)
1            # of lookahead depth
1            DEPTHs (>=0)
2            SWAP (0=bin-exch,1=long,2=mix)
64           swapping threshold
0            L1 in (0=transposed,1=no-transposed) form
0            U  in (0=transposed,1=no-transposed) form
1            Equilibration (0=no,1=yes)
8            memory alignment in double (> 0)
```

## FIO (Flexible I/O Tester)

### FIO Target Discovery

Automatic discovery of NVMe data drives:

```bash
# Find all mounted /mnt/nvme* dirs with at least 1GB free
df -BG /mnt/nvme* 2>/dev/null | awk 'NR>1 && $4+0>=2 {print $6}' | sort
```

**Reference Server Results:**

| Drive | Size | Mount | Free | Included | Reason |
|-------|------|-------|------|----------|--------|
| nvme4n1 | 894G | /, /boot | 894G | ❌ | OS drive (not under /mnt) |
| nvme0n1p1 | 1G | /mnt/nvme0n1p1 | <2G | ❌ | <2GB free |
| nvme1n1p1 | 94M | /mnt/nvme1n1p1 | <2G | ❌ | <2GB free |
| nvme2n1 | 3.5T | /mnt/nvme2n1 | 3.5T | ✅ | Data drive |
| nvme3n1 | 3.5T | /mnt/nvme3n1 | 3.5T | ✅ | Data drive |
| nvme5n1 | 3.5T | /mnt/nvme5n1 | 3.5T | ✅ | Data drive |
| nvme6n1 | 3.5T | /mnt/nvme6n1 | 3.5T | ✅ | Data drive |
| nvme7n1 | 3.5T | /mnt/nvme7n1 | 3.5T | ✅ | Data drive |
| nvme8n1 | 3.5T | /mnt/nvme8n1 | 3.5T | ✅ | Data drive |
| nvme9n1 | 3.5T | /mnt/nvme9n1 | 3.5T | ✅ | Data drive |
| nvme10n1 | 3.5T | /mnt/nvme10n1 | 3.5T | ✅ | Data drive |

**Result: 8 data drives stressed in parallel**

### FIO Configuration Generation

```bash
# Parameters based on load percentage
LOAD_PCT="$1"; DURATION="$2"; TARGETS="${3:-/tmp/fio_test}"
IODEPTH=64; BS="128k"; SIZE="256M"
[ "$LOAD_PCT" -lt 100 ] && IODEPTH=8 && SIZE="128M"

# Validate targets
VALID_TARGETS=""
for TGT in $TARGETS; do
    if [ -d "$TGT" ] && [ -w "$TGT" ]; then
        VALID_TARGETS="$VALID_TARGETS $TGT"
    fi
done
if [ -z "$VALID_TARGETS" ]; then
    mkdir -p /tmp/fio_test
    VALID_TARGETS="/tmp/fio_test"
fi

# Generate FIO config file
cat > "$FIO_CFG" << FIOEOF
[global]
ioengine=libaio
direct=1
runtime=${DURATION}
time_based=1
group_reporting=1
iodepth=${IODEPTH}
bs=${BS}
create_on_open=1
fallocate=none
FIOEOF

# Add one job per target
IDX=0
for TGT in $VALID_TARGETS; do
    cat >> "$FIO_CFG" << FIOEOF

[randrw-${IDX}]
directory=${TGT}
rw=randrw
rwmixread=50
size=${SIZE}
numjobs=1
name=randrw-${IDX}
FIOEOF
    IDX=$((IDX + 1))
done
```

### FIO Execution

```bash
log "FIO: load=$LOAD_PCT%, targets=$VALID_TARGETS, iodepth=$IODEPTH, duration=${DURATION}s"
fio "$FIO_CFG" 2>&1 || true
log "FIO done"
```

### FIO Performance Characteristics

| Load | iodepth | Block Size | File Size | CPU Usage | Disk Util |
|------|---------|------------|-----------|-----------|-----------|
| 100% | 64 | 128k | 256M | ~7% | 98.9% |
| 50% | 8 | 128k | 128M | ~6% | 98.6% |

## stress-ng (CPU Stress Testing)

### stress-ng Configuration

```bash
run_stress_ng)
    CORES="$1"; DURATION="$2"; STRESSOR="${3:-cpu}"
    log "stress-ng: stressor=$STRESSOR, cores=$CORES, duration=${DURATION}s"
    if command -v stress-ng &>/dev/null; then
        stress-ng --$STRESSOR "$CORES" --timeout "${DURATION}s" --metrics-brief 2>&1 || true
    else
        log "stress-ng not found, falling back to dd-based CPU stress"
        # Fallback: use dd + yes for CPU stress
        PIDS=""
        for i in $(seq 1 $CORES); do
            yes > /dev/null 2>&1 &
            PIDS="$PIDS $!"
        done
        sleep "$DURATION"
        for p in $PIDS; do kill $p 2>/dev/null; done
        wait 2>/dev/null || true
    fi
    log "stress-ng done"
    ;;
```

### CPU Utilization Control

| Target | Command | Workers | Result |
|--------|---------|---------|--------|
| 100% CPU | `stress-ng --cpu 96 --timeout 30s` | 96 | **100.0%** |
| 50% CPU | `stress-ng --cpu 48 --timeout 30s` | 48 | **50.0%** |
| Custom | `stress-ng --cpu <cores> --timeout <duration>s` | <cores> | ~target% |

**Why stress-ng instead of HPL for CPU:**
- HPL `mpirun` segfaults due to MPI version mismatch
- Direct `./xhpl` doesn't effectively use multiple cores
- stress-ng provides precise CPU utilization control
- stress-ng is more portable and reliable

## Benchmark Orchestration

### Phase Execution Flow

```python
class BenchmarkOrchestrator:
    def run_test_sequence(self, config: dict):
        """Execute all phases in sequence."""
        phases = config["phases"]
        
        for phase_cfg in phases:
            phase_name = phase_cfg["name"]
            phase_type = phase_cfg["type"]
            duration = phase_cfg["duration"]
            
            self.current_phase = phase_name
            self._log(f"Starting phase: {phase_name}")
            
            # Execute phase based on type
            if phase_type == "hpl_100":
                cores = phase_cfg.get("cores", total_cores)
                self._run_benchmark(
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    duration, phase_name)
            elif phase_type == "fio_100":
                self._run_benchmark(
                    self._sudo_cmd(f"run_fio 100 {duration} '{fio_targets}'"),
                    duration, phase_name)
            elif phase_type == "hpl_fio_100":
                cores = phase_cfg.get("cores", total_cores)
                self._run_parallel([
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    self._sudo_cmd(f"run_fio 100 {duration} '{fio_targets}'")
                ], duration, phase_name)
```

### Parallel Execution

For combined CPU + I/O phases:

```python
def _run_parallel(self, cmds: list, duration: int, phase: str):
    """Run multiple benchmark commands in parallel."""
    threads = []
    for i, cmd in enumerate(cmds):
        # Use double quotes for bash -c to preserve single quotes in cmd
        escaped = cmd.replace('"', '\\"')
        bg_cmd = f'nohup bash -c "{escaped}" > /tmp/bench_par_{i}.log 2>&1 &'
        self.ssh.os_exec(bg_cmd, timeout=10)
        self._log(f"  [{phase}] Started parallel job {i+1}")

    # Wait for duration
    self._wait(duration)

    # Kill parallel jobs
    try:
        self.ssh.os_exec(
            "pkill -TERM -f bench_agent 2>/dev/null; "
            "pkill -TERM -f stress-ng 2>/dev/null; "
            "pkill -TERM -f fio 2>/dev/null", timeout=10)
    except:
        pass
```

### Command Wrapping

All benchmark commands are wrapped with sudo support:

```python
def _sudo_cmd(self, cmd: str) -> str:
    """Wrap a bench_agent command with SUDO_PASS env var."""
    if self.os_pass:
        return f"SUDO_PASS='{self.os_pass}' bash /tmp/bench_agent.sh {cmd}"
    return f"sudo bash /tmp/bench_agent.sh {cmd}"
```

## Test Phases

### Default 8-Phase Sequence

| # | Phase Name | Type | Duration | What Happens |
|---|---|---|---|---|
| 1 | `01_idle_baseline` | `idle` | 10s | No workload — baseline measurement |
| 2 | `02_hpl_100pct` | `hpl_100` | 30s | `stress-ng --cpu <total_cores>` |
| 3 | `03_hpl_50pct` | `hpl_50` | 30s | `stress-ng --cpu <half_cores>` |
| 4 | `04_fio_100pct` | `fio_100` | 30s | FIO randrw, iodepth=64 on all data drives |
| 5 | `05_fio_50pct` | `fio_50` | 30s | FIO randrw, iodepth=8 on all data drives |
| 6 | `06_hpl_fio_100pct` | `hpl_fio_100` | 30s | stress-ng + FIO simultaneously |
| 7 | `07_hpl_fio_50pct` | `hpl_fio_50` | 30s | stress-ng + FIO simultaneously |
| 8 | `08_idle_cooldown` | `idle` | 10s | Cool-down — return to baseline |

### Phase Types

| Type | Command | CPU Target | I/O Target | Parallel |
|---|---|---|---|---|
| `idle` | `sleep <duration>` | ~0% | — | No |
| `hpl_100` | `run_stress_ng <total_cores> <duration> cpu` | **100%** | — | No |
| `hpl_50` | `run_stress_ng <half_cores> <duration> cpu` | **50%** | — | No |
| `fio_100` | `run_fio 100 <duration> <targets>` | ~7% | All drives | No |
| `fio_50` | `run_fio 50 <duration> <targets>` | ~6% | All drives | No |
| `hpl_fio_100` | `run_stress_ng` + `run_fio` | ~100% | All drives | Yes |
| `hpl_fio_50` | `run_stress_ng` + `run_fio` | ~50% | All drives | Yes |

### Custom Phase Configuration

Phases can be customized via the UI:

```json
{
  "phases": [
    {
      "name": "custom_cpu_test",
      "type": "hpl_100",
      "duration": 60,
      "cores": 48
    },
    {
      "name": "custom_io_test",
      "type": "fio_100",
      "duration": 45,
      "targets": "/mnt/nvme2n1 /mnt/nvme3n1"
    }
  ]
}
```

## Performance Verification

### Verified Results (96-core server)

| Phase | Measured CPU | Measured I/O | Notes |
|---|---|---|---|
| idle_baseline | 0.0% | — | Clean baseline |
| hpl_100pct | **100.0%** | — | 96 stress-ng workers |
| hpl_50pct | **50.0%** | — | 48 stress-ng workers |
| fio_100pct | 6.8% | 15.5 GiB/s R+W | 8 NVMe drives, 98.9% util |
| fio_50pct | 6.2% | 15.5 GiB/s R+W | 8 NVMe drives, 98.6% util |
| hpl_fio_100pct | ~99.5% | + FIO concurrent | Both running simultaneously |
| hpl_fio_50pct | ~53.7% | + FIO concurrent | Both running simultaneously |
| idle_cooldown | 0.0% | — | Return to baseline |

### FIO Performance Details

**8x 3.5TB NVMe Configuration:**
- **Sequential read**: ~15.5 GiB/s aggregate
- **Sequential write**: ~15.5 GiB/s aggregate  
- **Random IOPS**: High (varies by iodepth)
- **CPU overhead**: 6-8% (I/O bound)
- **Disk utilization**: 98-99%

### stress-ng Performance Details

**CPU Utilization Control:**
- **Precision**: ±1% of target
- **Stability**: Consistent throughout phase
- **Overhead**: Minimal system impact
- **Scalability**: Works from 1 to 96+ cores

## Error Handling and Recovery

### Common Benchmark Errors

#### HPL Build Failure

```bash
# Symptoms
ERROR: HPL build failed

# Troubleshooting
ssh user@server "ls -la ~/hpl/bin/Linux/"
ssh user@server "ldd ~/hpl/bin/Linux/xhpl"

# Recovery
rm -rf ~/hpl
# Re-run setup_hpl
```

#### FIO Target Errors

```bash
# Symptoms
FIO: No valid targets found in '/mnt/nvme*', using /tmp/fio_test

# Troubleshooting
ssh user@server "df -h /mnt/nvme*"
ssh user@server "mount | grep nvme"

# Recovery
# Check drive mounts and permissions
# Ensure drives are mounted and writable
```

#### stress-ng Missing

```bash
# Symptoms
stress-ng not found, falling back to dd-based CPU stress

# Recovery
ssh user@server "sudo apt-get install stress-ng"
# Or let platform install automatically
```

### Process Cleanup

The orchestrator automatically cleans up processes:

```python
def stop(self):
    """Stop all running benchmarks and clean up."""
    self._stop_event.set()
    
    # Kill remote processes
    try:
        self.ssh.os_exec(
            "pkill -TERM -f bench_agent 2>/dev/null; "
            "pkill -TERM -f stress-ng 2>/dev/null; "
            "pkill -TERM -f fio 2>/dev/null; "
            "pkill -TERM -f xhpl 2>/dev/null", timeout=10)
    except:
        pass
```

### Log Analysis

Benchmark logs are streamed in real-time and stored:

```bash
# View live logs via UI or API
curl http://localhost:8001/api/test/logs

# Check specific phase logs
grep "02_hpl_100pct" /tmp/bench_agent.log

# Verify FIO performance
grep "randrw" /tmp/bench_par_*.log | grep "IOPS"
```

---

*For the complete benchmark agent script, see `backend/benchmarks.py` in the source code.*
