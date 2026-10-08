import tempfile
import unittest
from pathlib import Path

from ulanzi_manager.metrics import SystemMetrics


class SystemMetricsTest(unittest.TestCase):
    def test_samples_cpu_memory_and_gpu_percentages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stat = root / "stat"
            meminfo = root / "meminfo"
            stat.write_text("cpu 100 0 0 100 0 0 0 0\n", encoding="ascii")
            meminfo.write_text(
                "MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 250 kB\n"
                "Buffers: 50 kB\nCached: 500 kB\nSReclaimable: 100 kB\nShmem: 50 kB\n",
                encoding="ascii",
            )
            metrics = SystemMetrics(
                proc_stat=stat,
                proc_meminfo=meminfo,
                gpu_reader=lambda: 37,
            )
            stat.write_text("cpu 130 0 0 170 0 0 0 0\n", encoding="ascii")

            sample = metrics.sample()

            self.assertEqual({"cpu": 30, "mem": 30, "gpu": 37}, sample)

    def test_clamps_sensor_values_to_protocol_range(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stat = root / "stat"
            meminfo = root / "meminfo"
            stat.write_text("cpu 1 0 0 1 0 0 0 0\n", encoding="ascii")
            meminfo.write_text(
                "MemTotal: 1000 kB\nMemFree: 1500 kB\nMemAvailable: 1500 kB\n",
                encoding="ascii",
            )
            metrics = SystemMetrics(
                proc_stat=stat,
                proc_meminfo=meminfo,
                gpu_reader=lambda: 140,
            )
            stat.write_text("cpu 3 0 0 1 0 0 0 0\n", encoding="ascii")

            sample = metrics.sample()
            self.assertEqual(100, sample["gpu"])
            self.assertEqual(100, sample["cpu"])
            self.assertEqual(0, sample["mem"])

    def test_guest_cpu_time_is_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stat = root / "stat"
            meminfo = root / "meminfo"
            stat.write_text("cpu 100 20 30 200 10 5 5 0 40 10\n", encoding="ascii")
            meminfo.write_text("MemTotal: 1000 kB\nMemFree: 500 kB\n", encoding="ascii")
            metrics = SystemMetrics(proc_stat=stat, proc_meminfo=meminfo, gpu_reader=lambda: 0)
            stat.write_text("cpu 140 30 40 230 20 10 10 5 60 15\n", encoding="ascii")
            # 75 busy ticks / 115 total ticks; guest is already included in user/nice.
            self.assertEqual(65, metrics.sample()["cpu"])


if __name__ == "__main__":
    unittest.main()
