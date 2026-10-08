"""Host CPU, memory, and GPU utilization for the D200 status display."""

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple


class SystemMetrics:
    """Collect utilization percentages without optional Python dependencies."""

    def __init__(
        self,
        proc_stat: Path = Path("/proc/stat"),
        proc_meminfo: Path = Path("/proc/meminfo"),
        gpu_reader: Optional[Callable[[], int]] = None,
    ):
        self.proc_stat = proc_stat
        self.proc_meminfo = proc_meminfo
        self._gpu_busy_path = next(
            Path("/sys/class/drm").glob("card*/device/gpu_busy_percent"),
            None,
        )
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._gpu_reader = gpu_reader or self._read_gpu_percent
        self._previous_cpu = self._read_cpu_times()

    @staticmethod
    def _percent(value: float) -> int:
        return max(0, min(100, round(value)))

    def _read_cpu_times(self) -> Tuple[int, int]:
        fields = self.proc_stat.read_text(encoding="ascii").splitlines()[0].split()
        if not fields or fields[0] != "cpu":
            raise ValueError("/proc/stat does not contain aggregate CPU times")
        values = [int(value) for value in fields[1:]]
        # Guest/guest_nice are already included in user/nice by the kernel.
        total = sum(values[:8])
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle

    def _read_memory_percent(self) -> int:
        values = {}
        for line in self.proc_meminfo.read_text(encoding="ascii").splitlines():
            key, separator, remainder = line.partition(":")
            if separator:
                values[key] = int(remainder.strip().split()[0])
        total = values.get("MemTotal", 0)
        free = values.get("MemFree", 0)
        if total <= 0:
            return 0
        # Match htop's numeric RAM meter: include shared memory, exclude reclaimable caches.
        reclaimable = (
            free + values.get("Buffers", 0) + values.get("Cached", 0)
            + values.get("SReclaimable", 0)
        )
        used = total - reclaimable if total >= reclaimable else total - free
        return self._percent((used + values.get("Shmem", 0)) * 100 / total)

    def _read_gpu_percent(self) -> int:
        if self._gpu_busy_path is not None:
            try:
                return self._percent(
                    float(self._gpu_busy_path.read_text(encoding="ascii").strip())
                )
            except (OSError, ValueError):
                pass

        if self._nvidia_smi is None:
            return 0
        try:
            result = subprocess.run(
                [
                    self._nvidia_smi,
                    "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=0.8,
            )
            values = [
                float(line.strip())
                for line in result.stdout.splitlines()
                if line.strip()
            ]
            return self._percent(max(values)) if values else 0
        except (OSError, ValueError, subprocess.SubprocessError):
            return 0

    def sample(self) -> Dict[str, int]:
        """Return CPU, RAM, and GPU utilization percentages."""
        current_total, current_idle = self._read_cpu_times()
        previous_total, previous_idle = self._previous_cpu
        self._previous_cpu = (current_total, current_idle)
        total_delta = current_total - previous_total
        idle_delta = current_idle - previous_idle
        cpu = 0 if total_delta <= 0 else self._percent(
            (total_delta - idle_delta) * 100 / total_delta
        )
        return {
            "cpu": cpu,
            "mem": self._read_memory_percent(),
            "gpu": self._percent(self._gpu_reader()),
        }
