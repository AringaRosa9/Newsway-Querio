"""Load testing script using concurrent async requests.

Usage:
    python scripts/load_test.py --base-url http://localhost:8000 --qps 50 --duration 60

Requires: httpx (already in backend requirements)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field

import httpx

SAMPLE_QUERIES = [
    "AI latest news",
    "人工智能最新进展",
    "OpenAI GPT-5",
    "Tesla stock price",
    "中国经济形势",
    "climate change report",
    "semiconductor chip shortage",
    "芯片半导体",
    "大模型训练",
    "quantum computing breakthrough",
    "Apple WWDC 2025",
    "机器人技术发展",
    "金融市场分析",
    "blockchain regulation",
    "space exploration news",
    "自动驾驶技术",
    "cybersecurity threats",
    "renewable energy policy",
    "社交媒体监管",
    "healthcare AI applications",
]


@dataclass
class LoadTestResult:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)
    errors: dict[int, int] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def actual_qps(self) -> float:
        return self.total_requests / self.duration if self.duration > 0 else 0

    @property
    def success_rate(self) -> float:
        return self.successful / self.total_requests * 100 if self.total_requests > 0 else 0

    def report(self) -> str:
        lines = [
            "=" * 60,
            "LOAD TEST REPORT",
            "=" * 60,
            f"Duration:          {self.duration:.1f}s",
            f"Total requests:    {self.total_requests}",
            f"Successful:        {self.successful}",
            f"Failed:            {self.failed}",
            f"Success rate:      {self.success_rate:.1f}%",
            f"Actual QPS:        {self.actual_qps:.1f}",
            "",
        ]

        if self.latencies:
            sorted_lat = sorted(self.latencies)
            lines.extend([
                "Latency (ms):",
                f"  Min:    {min(sorted_lat):.0f}",
                f"  Mean:   {statistics.mean(sorted_lat):.0f}",
                f"  Median: {statistics.median(sorted_lat):.0f}",
                f"  P95:    {sorted_lat[int(len(sorted_lat) * 0.95)]:.0f}",
                f"  P99:    {sorted_lat[int(len(sorted_lat) * 0.99)]:.0f}",
                f"  Max:    {max(sorted_lat):.0f}",
            ])

        if self.errors:
            lines.append("\nErrors by status code:")
            for code, count in sorted(self.errors.items()):
                lines.append(f"  {code}: {count}")

        lines.append("=" * 60)
        return "\n".join(lines)


async def send_request(
    client: httpx.AsyncClient,
    base_url: str,
    result: LoadTestResult,
    semaphore: asyncio.Semaphore,
) -> None:
    query = random.choice(SAMPLE_QUERIES)
    url = f"{base_url}/api/search"
    params = {"q": query, "page_size": 5}

    async with semaphore:
        t0 = time.perf_counter()
        try:
            resp = await client.get(url, params=params, timeout=30.0)
            latency_ms = (time.perf_counter() - t0) * 1000
            result.total_requests += 1
            result.latencies.append(latency_ms)

            if resp.status_code == 200:
                result.successful += 1
            else:
                result.failed += 1
                result.errors[resp.status_code] = result.errors.get(resp.status_code, 0) + 1
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            result.total_requests += 1
            result.failed += 1
            result.latencies.append(elapsed_ms)
            result.errors[0] = result.errors.get(0, 0) + 1


async def run_load_test(base_url: str, qps: int, duration: int) -> LoadTestResult:
    result = LoadTestResult()
    semaphore = asyncio.Semaphore(qps * 2)
    interval = 1.0 / qps

    async with httpx.AsyncClient() as client:
        print(f"Starting load test: {qps} QPS for {duration}s against {base_url}")
        result.start_time = time.perf_counter()
        end_at = result.start_time + duration

        tasks: list[asyncio.Task] = []
        while time.perf_counter() < end_at:
            task = asyncio.create_task(send_request(client, base_url, result, semaphore))
            tasks.append(task)
            await asyncio.sleep(interval)

        await asyncio.gather(*tasks, return_exceptions=True)
        result.end_time = time.perf_counter()

    return result


async def run_health_test(base_url: str, qps: int, duration: int) -> LoadTestResult:
    result = LoadTestResult()
    semaphore = asyncio.Semaphore(qps * 2)
    interval = 1.0 / qps

    async with httpx.AsyncClient() as client:
        print(f"Health endpoint test: {qps} QPS for {duration}s")
        result.start_time = time.perf_counter()
        end_at = result.start_time + duration

        tasks: list[asyncio.Task] = []

        async def _health_req() -> None:
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    resp = await client.get(f"{base_url}/health", timeout=5.0)
                    latency_ms = (time.perf_counter() - t0) * 1000
                    result.total_requests += 1
                    result.latencies.append(latency_ms)
                    if resp.status_code == 200:
                        result.successful += 1
                    else:
                        result.failed += 1
                except Exception:
                    result.total_requests += 1
                    result.failed += 1

        while time.perf_counter() < end_at:
            tasks.append(asyncio.create_task(_health_req()))
            await asyncio.sleep(interval)

        await asyncio.gather(*tasks, return_exceptions=True)
        result.end_time = time.perf_counter()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="AI News Search Load Test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--qps", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--health-only", action="store_true", help="Only test /health endpoint")
    args = parser.parse_args()

    if args.health_only:
        result = asyncio.run(run_health_test(args.base_url, args.qps, args.duration))
    else:
        result = asyncio.run(run_load_test(args.base_url, args.qps, args.duration))

    print(result.report())


if __name__ == "__main__":
    main()
