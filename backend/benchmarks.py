"""
Benchmark orchestrator — manages running HPL, FIO, stress-ng on remote server.
Leverages the patterns from power_draw_test.sh but orchestrated from Python.
"""

import time
import threading
from typing import Optional, Callable

from . import telemetry


# Remote script that gets deployed to the server to run benchmarks
BENCHMARK_AGENT_SCRIPT = r'''#!/bin/bash
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

install_deps)
    log "Installing dependencies..."
    export DEBIAN_FRONTEND=noninteractive
    do_sudo apt-get update -qq 2>&1 || true
    do_sudo apt-get install -y -qq build-essential gfortran libopenmpi-dev openmpi-bin \
        wget curl git pkg-config libaio-dev libz-dev sysstat libopenblas-dev bc stress-ng fio 2>&1 || true
    # Verify critical tools
    for t in stress-ng fio mpirun bc; do
        if command -v $t &>/dev/null; then
            log "  $t: OK"
        else
            log "  $t: MISSING"
        fi
    done
    log "Dependencies installed"
    ;;

setup_hpl)
    HPL_DIR="$HOME/hpl"
    # Force rebuild if binary exists but is not writable dir (root-owned)
    if [ -f "$HPL_DIR/bin/Linux/xhpl" ]; then
        if [ -w "$HPL_DIR/bin/Linux/" ]; then
            log "HPL already built at $HPL_DIR/bin/Linux/xhpl"
            exit 0
        else
            log "HPL dir not writable, rebuilding..."
            do_sudo rm -rf "$HPL_DIR"
        fi
    fi
    cd "$HOME"
    [ -d hpl ] && do_sudo rm -rf hpl
    wget -q http://www.netlib.org/benchmark/hpl/hpl-2.3.tar.gz
    tar -xzf hpl-2.3.tar.gz && mv hpl-2.3 hpl && rm hpl-2.3.tar.gz
    cd hpl
    # Detect MPI
    MPI_INC="/usr/lib/x86_64-linux-gnu/openmpi/include"
    MPI_LIB="/usr/lib/x86_64-linux-gnu/openmpi/lib"
    [ ! -d "$MPI_INC" ] && MPI_INC=$(mpicc --showme:compile 2>/dev/null | grep -oP '(?<=-I)\S+' | head -1)
    [ ! -d "$MPI_LIB" ] && MPI_LIB=$(mpicc --showme:link 2>/dev/null | grep -oP '(?<=-L)\S+' | head -1)
    BLAS_DIR="/usr/lib/x86_64-linux-gnu"
    BLAS_LIB="-lopenblas"
    cat > Make.Linux << MAKEEOF
SHELL        = /bin/sh
CD           = cd
CP           = cp
LN_S         = ln -s
MKDIR        = mkdir
RM           = /bin/rm -f
TOUCH        = touch
ARCH         = Linux
TOPdir       = $HPL_DIR
INCdir       = \$(TOPdir)/include
BINdir       = \$(TOPdir)/bin/\$(ARCH)
LIBdir       = \$(TOPdir)/lib/\$(ARCH)
HPLlib       = \$(LIBdir)/libhpl.a
MPdir        = /usr
MPinc        = -I${MPI_INC}
MPlib        = -L${MPI_LIB} -lmpi
LAdir        = ${BLAS_DIR}
LAinc        =
LAlib        = -L\$(LAdir) ${BLAS_LIB} -lm
HPL_INCLUDES = -I\$(INCdir) -I\$(INCdir)/\$(ARCH) \$(LAinc) \$(MPinc)
HPL_LIBS     = \$(HPLlib) \$(LAlib) \$(MPlib)
HPL_OPTS     =
HPL_DEFS     = \$(HPL_OPTS) \$(HPL_INCLUDES)
CC           = mpicc
CCNOOPT      = \$(HPL_DEFS)
CCFLAGS      = \$(HPL_DEFS) -fomit-frame-pointer -O3 -funroll-loops -W -Wall
LINKER       = mpicc
LINKFLAGS    = \$(CCFLAGS)
ARCHIVER     = ar
ARFLAGS      = r
RANLIB       = echo
MAKEEOF
    make arch=Linux 2>&1
    if [ -f "bin/Linux/xhpl" ]; then
        # Ensure the entire hpl dir is owned by the current user so HPL.dat can be written
        REAL_USER=$(whoami)
        if [ "$REAL_USER" = "root" ] && [ -n "${SUDO_USER:-}" ]; then
            REAL_USER="$SUDO_USER"
        fi
        # If we ran as root via do_sudo, fix ownership
        if [ "$(id -u)" -eq 0 ] || [ -n "${SUDO_PASS:-}" ]; then
            do_sudo chown -R "${REAL_USER}:${REAL_USER}" "$HPL_DIR" 2>/dev/null || true
        fi
        log "HPL built successfully (owner: $REAL_USER)"
    else
        log "ERROR: HPL build failed"
        exit 1
    fi
    ;;

run_hpl)
    CORES="$1"; DURATION="$2"
    HPL_DIR="$HOME/hpl/bin/Linux"
    if [ ! -f "$HPL_DIR/xhpl" ]; then
        log "HPL not built yet, building..."
        SUDO_PASS="${SUDO_PASS:-}" bash /tmp/bench_agent.sh setup_hpl
    fi
    # Fix permissions if dir not writable (previous root-owned build)
    if [ ! -w "$HPL_DIR" ]; then
        log "HPL dir not writable, fixing permissions..."
        do_sudo chown -R "$(whoami):$(whoami)" "$HOME/hpl" 2>/dev/null || true
        if [ ! -w "$HPL_DIR" ]; then
            log "Still not writable, forcing HPL rebuild..."
            do_sudo rm -rf "$HOME/hpl"
            SUDO_PASS="${SUDO_PASS:-}" bash /tmp/bench_agent.sh setup_hpl
        fi
    fi

    export OMP_NUM_THREADS=1
    export OPENBLAS_NUM_THREADS=1
    export GOTO_NUM_THREADS=1
    ulimit -s unlimited 2>/dev/null || ulimit -s 65536 2>/dev/null || true

    # Strategy: run multiple parallel xhpl instances directly (no mpirun).
    # Each instance uses 1 MPI rank with OMP_NUM_THREADS=1 but OpenBLAS
    # will use multiple threads. We pin groups of cores to each instance.
    # This avoids mpirun segfaults from vendor/system MPI version mismatches.
    TOTAL=$(nproc)
    # Decide how many parallel instances and threads per instance
    if [ "$CORES" -le 4 ]; then
        INSTANCES=1
        THREADS_PER=$CORES
    elif [ "$CORES" -le 16 ]; then
        INSTANCES=2
        THREADS_PER=$(( CORES / 2 ))
    elif [ "$CORES" -le 48 ]; then
        INSTANCES=4
        THREADS_PER=$(( CORES / 4 ))
    else
        INSTANCES=8
        THREADS_PER=$(( CORES / 8 ))
    fi

    # Calculate HPL problem size per instance
    # Use ~60% of memory per instance so the solve runs longer than the phase
    # duration. HPL will be killed by timeout, keeping CPU at 100% throughout.
    MEM=$(free -b | awk '/^Mem:/{print $2}')
    MEM_PER=$(( MEM / INSTANCES ))
    NB=192
    N_RAW=$(echo "sqrt($MEM_PER * 0.6 / 8)" | bc 2>/dev/null || echo "40000")
    N=$(( (N_RAW / NB) * NB ))
    [ "$N" -lt 5000 ] && N=5000
    [ "$N" -gt 80000 ] && N=80000

    log "HPL: $INSTANCES instances x $THREADS_PER threads, N=$N, ~$(( N*N*8/1024/1024 ))MB matrix/instance"

    # Create work dirs per instance
    for i in $(seq 0 $((INSTANCES - 1))); do
        WDIR="/tmp/hpl_inst_$i"
        mkdir -p "$WDIR"
        cp "$HPL_DIR/xhpl" "$WDIR/"
        cat > "$WDIR/HPL.dat" << HPLEOF
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
HPLEOF
    done

    END_TIME=$(( $(date +%s) + DURATION ))
    RUN=0
    while [ "$(date +%s)" -lt "$END_TIME" ]; do
        RUN=$((RUN + 1))
        REMAINING=$((END_TIME - $(date +%s)))
        [ "$REMAINING" -le 0 ] && break
        T=$REMAINING; [ "$T" -gt 600 ] && T=600
        log "HPL run #$RUN ($REMAINING s left, $INSTANCES instances x $THREADS_PER threads)"

        PIDS=""
        for i in $(seq 0 $((INSTANCES - 1))); do
            WDIR="/tmp/hpl_inst_$i"
            CORE_START=$(( i * THREADS_PER ))
            CORE_END=$(( CORE_START + THREADS_PER - 1 ))
            [ "$CORE_END" -ge "$TOTAL" ] && CORE_END=$((TOTAL - 1))
            (
                cd "$WDIR"
                export OPENBLAS_NUM_THREADS=$THREADS_PER
                export GOTO_NUM_THREADS=$THREADS_PER
                export OMP_NUM_THREADS=$THREADS_PER
                timeout "$T" taskset -c "${CORE_START}-${CORE_END}" ./xhpl > "$WDIR/output.log" 2>&1
            ) &
            PIDS="$PIDS $!"
        done

        # Wait for all instances
        for P in $PIDS; do
            wait "$P" 2>/dev/null
        done

        # Show summary from first instance
        if [ -f "/tmp/hpl_inst_0/output.log" ]; then
            GFLOPS=$(grep -oP '[\d.]+e[+-]?\d+' /tmp/hpl_inst_0/output.log 2>/dev/null | tail -1)
            PASSED=$(grep -c 'PASSED' /tmp/hpl_inst_0/output.log 2>/dev/null)
            log "HPL run #$RUN: inst0 gflops=$GFLOPS passed=$PASSED"
        fi
    done
    log "HPL done after $RUN runs ($INSTANCES instances)"
    # Cleanup
    rm -rf /tmp/hpl_inst_* 2>/dev/null
    ;;

run_fio)
    LOAD_PCT="$1"; DURATION="$2"; TARGETS="${3:-/tmp/fio_test}"
    IODEPTH=64; BS="128k"; SIZE="256M"
    [ "$LOAD_PCT" -lt 100 ] && IODEPTH=8 && SIZE="128M"

    # Validate and fix targets — use /tmp/fio_test as safe fallback
    VALID_TARGETS=""
    for TGT in $TARGETS; do
        if [ -d "$TGT" ] && [ -w "$TGT" ]; then
            VALID_TARGETS="$VALID_TARGETS $TGT"
        fi
    done
    if [ -z "$VALID_TARGETS" ]; then
        log "FIO: No valid targets found in '$TARGETS', using /tmp/fio_test"
        mkdir -p /tmp/fio_test
        VALID_TARGETS="/tmp/fio_test"
    fi

    FIO_CFG="/tmp/fio_bench.fio"
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
    log "FIO: load=$LOAD_PCT%, targets=$VALID_TARGETS, iodepth=$IODEPTH, duration=${DURATION}s"
    fio "$FIO_CFG" 2>&1 || true
    log "FIO done"
    ;;

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

sysinfo)
    echo "=== HOSTNAME ===" && hostname
    echo "=== OS ===" && cat /etc/os-release 2>/dev/null | head -4
    echo "=== KERNEL ===" && uname -r
    echo "=== CPU ===" && lscpu | grep -E 'Model name|Socket|Core|Thread|CPU\(s\)' | head -10
    echo "=== MEMORY ===" && free -h
    echo "=== DISKS ===" && lsblk -d -o NAME,SIZE,TYPE,MODEL | head -20
    echo "=== NVME ===" && lsblk -ndo NAME,SIZE,TYPE | awk '$3=="disk" && $1~/^nvme/ {print}'
    echo "=== NETWORK ===" && ip -4 addr show | grep inet | head -5
    echo "=== DMI ===" && do_sudo dmidecode -s system-product-name 2>/dev/null; do_sudo dmidecode -s system-serial-number 2>/dev/null; do_sudo dmidecode -s system-manufacturer 2>/dev/null
    ;;

*)
    echo "Unknown action: $ACTION"
    echo "Usage: $0 {install_deps|setup_hpl|run_hpl|run_fio|run_stress_ng|sysinfo}"
    exit 1
    ;;
esac
'''


class BenchmarkOrchestrator:
    """Orchestrates benchmark execution on the remote server."""

    def __init__(self, ssh_manager, os_pass: str = ""):
        self.ssh = ssh_manager
        self.os_pass = os_pass  # needed for sudo -S
        self._current_phase: str = "idle"
        self.running: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.log_lines: list = []
        self.log_callback: Optional[Callable] = None
        self._phase_change_callback: Optional[Callable] = None
        self._completion_callback: Optional[Callable] = None

    @property
    def current_phase(self) -> str:
        return self._current_phase

    @current_phase.setter
    def current_phase(self, value: str):
        self._current_phase = value
        if self._phase_change_callback:
            try:
                self._phase_change_callback(value)
            except:
                pass

    def _sudo_cmd(self, cmd: str) -> str:
        """Wrap a bench_agent command with SUDO_PASS env var."""
        if self.os_pass:
            return f"SUDO_PASS='{self.os_pass}' bash /tmp/bench_agent.sh {cmd}"
        return f"sudo bash /tmp/bench_agent.sh {cmd}"

    def deploy_agent(self) -> bool:
        """Deploy the benchmark agent script to the remote server."""
        try:
            # Write agent script via SFTP
            sftp = self.ssh.os_client.open_sftp()
            with sftp.open("/tmp/bench_agent.sh", "w") as f:
                f.write(BENCHMARK_AGENT_SCRIPT)
            sftp.close()
            self.ssh.os_exec("chmod +x /tmp/bench_agent.sh")
            self._log("Benchmark agent deployed")
            return True
        except Exception as e:
            self._log(f"Failed to deploy agent: {e}")
            return False

    def install_deps(self) -> str:
        """Install benchmark dependencies on the server."""
        self._log("Installing dependencies (this may take a minute)...")
        out, err, rc = self.ssh.os_exec(
            self._sudo_cmd("install_deps"), timeout=300)
        self._log(f"Dependencies install exit={rc}")
        if out:
            for line in out.strip().split("\n")[-5:]:
                self._log(f"  {line}")
        return out + err

    def setup_hpl(self) -> str:
        """Build HPL on the server."""
        self._log("Building HPL...")
        out, err, rc = self.ssh.os_exec(
            self._sudo_cmd("setup_hpl"), timeout=600)
        self._log(f"HPL setup exit={rc}")
        return out + err

    def run_test_sequence(self, config: dict):
        """Run the full test sequence in a background thread."""
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_sequence,
                                        args=(config,), daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the running test sequence."""
        self._stop_event.set()
        self.running = False
        # Kill any running benchmarks on the server
        try:
            self.ssh.os_exec("pkill -TERM -f bench_agent 2>/dev/null; "
                             "pkill -TERM -f mpirun 2>/dev/null; "
                             "pkill -TERM -f xhpl 2>/dev/null; "
                             "pkill -TERM -f fio 2>/dev/null; "
                             "pkill -TERM -f stress-ng 2>/dev/null", timeout=10)
        except:
            pass

    def _run_sequence(self, config: dict):
        """Execute the test sequence."""
        self.running = True
        phases = config.get("phases", [])
        phase_duration = config.get("phase_duration", 30)
        rest_duration = config.get("rest_duration", 10)
        total_cores = config.get("total_cores", 4)
        half_cores = total_cores // 2
        fio_targets = config.get("fio_targets", "/tmp")

        self._log(f"Starting test sequence: {len(phases)} phases, "
                  f"{phase_duration}s each, {rest_duration}s rest")

        # Auto-install missing dependencies before running benchmarks
        self.current_phase = "installing_deps"
        self._log("Installing/verifying benchmark dependencies...")
        try:
            self.install_deps()
        except Exception as e:
            self._log(f"WARNING: Dep install issue: {e}")

        telemetry.store_benchmark_event(
            "startup", "sequence_start", "all",
            f"Starting {len(phases)} phases", config)

        for i, phase_cfg in enumerate(phases):
            if self._stop_event.is_set():
                break

            phase_name = phase_cfg.get("name", f"phase_{i+1}")
            phase_type = phase_cfg.get("type", "idle")
            duration = phase_cfg.get("duration", phase_duration)

            self.current_phase = phase_name
            self._log(f"\n{'='*60}")
            self._log(f"PHASE {i+1}/{len(phases)}: {phase_name} ({phase_type})")
            self._log(f"Duration: {duration}s")
            self._log(f"{'='*60}")

            telemetry.store_benchmark_event(
                phase_name, "phase_start", phase_type,
                f"Starting phase {i+1}/{len(phases)}")

            if phase_type == "idle":
                self._wait(duration)

            elif phase_type == "hpl_100":
                cores = phase_cfg.get("cores", total_cores)
                self._run_benchmark(
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    duration, phase_name)

            elif phase_type == "hpl_50":
                cores = phase_cfg.get("cores", half_cores)
                self._run_benchmark(
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    duration, phase_name)

            elif phase_type == "fio_100":
                self._run_benchmark(
                    self._sudo_cmd(f"run_fio 100 {duration} '{fio_targets}'"),
                    duration, phase_name)

            elif phase_type == "fio_50":
                self._run_benchmark(
                    self._sudo_cmd(f"run_fio 50 {duration} '{fio_targets}'"),
                    duration, phase_name)

            elif phase_type == "hpl_fio_100":
                cores = phase_cfg.get("cores", total_cores)
                self._run_parallel([
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    self._sudo_cmd(f"run_fio 100 {duration} '{fio_targets}'")
                ], duration, phase_name)

            elif phase_type == "hpl_fio_50":
                cores = phase_cfg.get("cores", half_cores)
                self._run_parallel([
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} cpu"),
                    self._sudo_cmd(f"run_fio 50 {duration} '{fio_targets}'")
                ], duration, phase_name)

            elif phase_type == "stress_ng":
                stressor = phase_cfg.get("stressor", "cpu")
                cores = phase_cfg.get("cores", total_cores)
                self._run_benchmark(
                    self._sudo_cmd(f"run_stress_ng {cores} {duration} {stressor}"),
                    duration, phase_name)

            elif phase_type == "custom":
                cmd = phase_cfg.get("command", "echo 'no command'")
                self._run_benchmark(cmd, duration, phase_name)

            telemetry.store_benchmark_event(
                phase_name, "phase_end", phase_type, f"Phase {phase_name} complete")

            # Rest period between phases
            if i < len(phases) - 1 and rest_duration > 0 and not self._stop_event.is_set():
                self.current_phase = f"rest_after_{phase_name}"
                self._log(f"  Rest period: {rest_duration}s")
                self._wait(rest_duration)

        self.current_phase = "complete"
        self.running = False
        telemetry.store_benchmark_event(
            "complete", "sequence_end", "all", "Test sequence complete")
        self._log("\n" + "="*60)
        self._log("TEST SEQUENCE COMPLETE")
        self._log("="*60)
        if self._completion_callback:
            try:
                self._completion_callback()
            except:
                pass

    def _run_benchmark(self, cmd: str, duration: int, phase: str):
        """Run a single benchmark command with streaming output."""
        def on_line(line):
            self._log(f"  [{phase}] {line}")

        try:
            self.ssh.os_exec_stream(cmd, callback=on_line,
                                     timeout=duration + 120)
        except Exception as e:
            self._log(f"  [{phase}] Error: {e}")

    def _run_parallel(self, cmds: list, duration: int, phase: str):
        """Run multiple benchmark commands in parallel."""
        threads = []
        for i, cmd in enumerate(cmds):
            # Use double quotes for bash -c to preserve single quotes in cmd
            # (e.g. SUDO_PASS='calvin' inside cmd)
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

        # Collect output
        for i in range(len(cmds)):
            try:
                out, _, _ = self.ssh.os_exec(
                    f"cat /tmp/bench_par_{i}.log 2>/dev/null", timeout=5)
                for line in out.strip().split("\n")[-10:]:
                    self._log(f"  [{phase}][job{i}] {line}")
            except:
                pass

    def _wait(self, seconds: int):
        """Wait with early exit on stop."""
        for _ in range(seconds):
            if self._stop_event.is_set():
                break
            time.sleep(1)

    def _log(self, msg: str):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        self.log_lines.append(line)
        if self.log_callback:
            self.log_callback(line)
