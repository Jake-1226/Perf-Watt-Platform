"""
SSH connection manager for OS and iDRAC connections.
Handles persistent connections, command execution, and file transfers.
"""

import io
import re
import time
import threading
from typing import Optional, Tuple

import paramiko


class SSHManager:
    """Manages SSH connections to both the server OS and iDRAC."""

    def __init__(self):
        self.os_client: Optional[paramiko.SSHClient] = None
        self.idrac_client: Optional[paramiko.SSHClient] = None
        self.idrac_channel = None  # interactive shell for racadm→rootshell
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # OS Connection
    # ------------------------------------------------------------------
    def connect_os(self, ip: str, user: str, password: str, timeout: int = 15) -> dict:
        """Connect to the server OS via SSH. Returns system info dict."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=user, password=password,
                           timeout=timeout, allow_agent=False, look_for_keys=False)
            self.os_client = client
            return {"status": "connected", "ip": ip, "user": user}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def disconnect_os(self):
        if self.os_client:
            try:
                self.os_client.close()
            except:
                pass
            self.os_client = None

    def os_exec(self, cmd: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute a command on the OS. Returns (stdout, stderr, exit_code)."""
        if not self.os_client:
            raise RuntimeError("OS not connected")
        stdin, stdout, stderr = self.os_client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode("utf-8", errors="replace"), \
               stderr.read().decode("utf-8", errors="replace"), exit_code

    def os_exec_stream(self, cmd: str, callback=None, timeout: int = 3600):
        """Execute a command and stream stdout line-by-line via callback."""
        if not self.os_client:
            raise RuntimeError("OS not connected")
        transport = self.os_client.get_transport()
        channel = transport.open_session()
        channel.settimeout(timeout)
        channel.get_pty(width=200)
        channel.exec_command(cmd)
        buf = ""
        while True:
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if callback:
                        callback(line)
            elif channel.exit_status_ready():
                # drain remaining
                while channel.recv_ready():
                    data = channel.recv(4096).decode("utf-8", errors="replace")
                    buf += data
                if buf.strip() and callback:
                    callback(buf.strip())
                break
            else:
                time.sleep(0.05)
        return channel.recv_exit_status()

    def sftp_put(self, local_path: str, remote_path: str):
        """Upload a file to the server."""
        if not self.os_client:
            raise RuntimeError("OS not connected")
        sftp = self.os_client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()

    def sftp_get(self, remote_path: str, local_path: str):
        """Download a file from the server."""
        if not self.os_client:
            raise RuntimeError("OS not connected")
        sftp = self.os_client.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()

    def sftp_get_bytes(self, remote_path: str) -> bytes:
        """Download a file as bytes."""
        if not self.os_client:
            raise RuntimeError("OS not connected")
        sftp = self.os_client.open_sftp()
        with sftp.open(remote_path, "rb") as f:
            data = f.read()
        sftp.close()
        return data

    # ------------------------------------------------------------------
    # iDRAC Connection (SSH → racadm → rootshell)
    # ------------------------------------------------------------------
    def connect_idrac(self, ip: str, user: str, password: str, timeout: int = 20) -> dict:
        """Connect to iDRAC via SSH, navigate to racadm→rootshell."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=user, password=password,
                           timeout=timeout, allow_agent=False, look_for_keys=False)
            self.idrac_client = client

            # Open interactive shell
            channel = client.invoke_shell(width=200, height=50)
            channel.settimeout(10)
            time.sleep(1)

            # Wait for racadm>> prompt
            output = self._read_until(channel, "racadm>>", timeout=15)
            if "racadm>>" not in output:
                return {"status": "error", "error": f"No racadm prompt. Got: {output[:200]}"}

            # Enter rootshell
            channel.send("rootshell\n")
            time.sleep(1)
            output = self._read_until(channel, ["#", "$"], timeout=10)
            if "#" not in output and "$" not in output:
                return {"status": "error", "error": f"No rootshell prompt. Got: {output[:200]}"}

            self.idrac_channel = channel
            return {"status": "connected", "ip": ip}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def disconnect_idrac(self):
        if self.idrac_channel:
            try:
                self.idrac_channel.send("exit\n")
                time.sleep(0.5)
                self.idrac_channel.send("exit\n")
                time.sleep(0.5)
                self.idrac_channel.close()
            except:
                pass
            self.idrac_channel = None
        if self.idrac_client:
            try:
                self.idrac_client.close()
            except:
                pass
            self.idrac_client = None

    def idrac_exec(self, cmd: str, timeout: int = 15) -> str:
        """Execute a command on the iDRAC rootshell."""
        if not self.idrac_channel:
            raise RuntimeError("iDRAC not connected")
        # Clear buffer
        while self.idrac_channel.recv_ready():
            self.idrac_channel.recv(65536)
        self.idrac_channel.send(cmd + "\n")
        output = self._read_until_prompt(self.idrac_channel, timeout=timeout)
        return output

    def get_thmtest(self) -> str:
        """Run thmtest -g s on iDRAC rootshell and return raw output."""
        return self.idrac_exec("thmtest -g s", timeout=30)

    def parse_thmtest(self, raw: str) -> dict:
        """Parse thmtest -g s output into a dict of sensor→value.
        Handles both tabular format (space-delimited columns) and pipe-delimited format.
        """
        sensors = {}
        text = raw.replace("\r", "")

        # Check if pipe-delimited (older iDRAC firmware)
        if "|" in text and text.count("|") > 5:
            blocks = text.split("|")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                parts = block.split()
                if len(parts) >= 2:
                    try:
                        sensors[parts[0]] = float(parts[1])
                    except ValueError:
                        sensors[parts[0]] = parts[1]
        else:
            # Tabular format: SENSOR_NAME  RDG  DISP  RAW  ...
            for line in text.split("\n"):
                line = line.strip()
                if not line or line.startswith("---") or line.startswith("SENSOR"):
                    continue
                if line.startswith("thmtest"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    # Skip header-like lines
                    if name in ("SENSOR_NAME", "RDG", "DISP"):
                        continue
                    try:
                        val = float(parts[1])
                        sensors[name] = val
                    except ValueError:
                        pass
        return sensors

    def _read_until(self, channel, patterns, timeout=10) -> str:
        """Read from channel until one of the patterns appears or timeout."""
        if isinstance(patterns, str):
            patterns = [patterns]
        output = ""
        start = time.time()
        while time.time() - start < timeout:
            if channel.recv_ready():
                data = channel.recv(65536).decode("utf-8", errors="replace")
                output += data
                for p in patterns:
                    if p in output:
                        return output
            else:
                time.sleep(0.1)
        return output

    def _read_until_prompt(self, channel, timeout=30) -> str:
        """Read from channel until we see a shell prompt on its own line.
        The prompt is typically '/ #' or '/home/root #' or '$ ' at end of line.
        This avoids stopping at '#' characters inside data.
        """
        import re
        output = ""
        start = time.time()
        idle_count = 0
        while time.time() - start < timeout:
            if channel.recv_ready():
                data = channel.recv(65536).decode("utf-8", errors="replace")
                output += data
                idle_count = 0
                # Check for shell prompt at end of output
                # Typical: '/ # ' or '/home/root # ' at end
                stripped = output.rstrip()
                if re.search(r'[/#\$]\s*$', stripped) and len(output) > 100:
                    # Make sure we've received substantial data and see a prompt
                    # Wait a tiny bit more to see if more data is coming
                    time.sleep(0.3)
                    if not channel.recv_ready():
                        return output
            else:
                idle_count += 1
                if idle_count > 5 and len(output) > 100:
                    # No more data coming and we have content
                    return output
                time.sleep(0.2)
        return output

    # ------------------------------------------------------------------
    # System Info Collection
    # ------------------------------------------------------------------
    def get_os_sysinfo(self) -> dict:
        """Collect comprehensive system info from the OS."""
        info = {}
        commands = {
            "hostname": "hostname",
            "os_release": "cat /etc/os-release 2>/dev/null | head -5",
            "kernel": "uname -r",
            "arch": "uname -m",
            "cpu_model": "lscpu | grep 'Model name' | head -1 | sed 's/Model name:\\s*//'",
            "cpu_cores": "nproc",
            "cpu_sockets": "lscpu | grep 'Socket(s)' | awk '{print $NF}'",
            "cpu_threads_per_core": "lscpu | grep 'Thread(s) per core' | awk '{print $NF}'",
            "memory_total_gb": "free -g | awk '/^Mem:/{print $2}'",
            "memory_total_mb": "free -m | awk '/^Mem:/{print $2}'",
            "swap_total_gb": "free -g | awk '/^Swap:/{print $2}'",
            "disk_info": "lsblk -ndo NAME,SIZE,TYPE,MODEL | head -20",
            "nvme_drives": "lsblk -ndo NAME,SIZE,TYPE | awk '$3==\"disk\" && $1~/^nvme/ {print $1, $2}'",
            "ip_addresses": "ip -4 addr show | grep inet | awk '{print $2}' | head -10",
            "uptime": "uptime -p 2>/dev/null || uptime",
            "bios_version": "sudo dmidecode -s bios-version 2>/dev/null || echo 'N/A'",
            "system_product": "sudo dmidecode -s system-product-name 2>/dev/null || echo 'N/A'",
            "system_serial": "sudo dmidecode -s system-serial-number 2>/dev/null || echo 'N/A'",
            "system_manufacturer": "sudo dmidecode -s system-manufacturer 2>/dev/null || echo 'N/A'",
        }
        for key, cmd in commands.items():
            try:
                stdout, _, _ = self.os_exec(cmd, timeout=10)
                info[key] = stdout.strip()
            except Exception as e:
                info[key] = f"Error: {e}"
        return info

    def get_idrac_sysinfo(self) -> dict:
        """Collect system info from iDRAC rootshell."""
        info = {}
        commands = {
            "idrac_version": "racadm getversion 2>/dev/null || echo 'N/A'",
            "service_tag": "cat /sys/devices/virtual/dmi/id/product_serial 2>/dev/null || echo 'N/A'",
            "bios_version": "cat /sys/devices/virtual/dmi/id/bios_version 2>/dev/null || echo 'N/A'",
        }
        for key, cmd in commands.items():
            try:
                output = self.idrac_exec(cmd, timeout=10)
                # Strip command echo and prompt
                lines = output.strip().split("\n")
                if len(lines) > 1:
                    info[key] = "\n".join(lines[1:-1]).strip()
                else:
                    info[key] = output.strip()
            except Exception as e:
                info[key] = f"Error: {e}"
        return info
