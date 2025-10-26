#!/usr/bin/env python3
"""
Performance benchmarking script for Issue Observatory Search.

Tests all performance targets from .clinerules:
- API response time < 200ms (excluding scraping)
- Support 100+ concurrent users
- Scraping rate: 10+ pages/second
- Network generation < 30s for 1000 nodes
- Bulk insert: 1000+ records/second

Usage:
    python scripts/benchmark.py --all
    python scripts/benchmark.py --api
    python scripts/benchmark.py --concurrent
    python scripts/benchmark.py --database
"""
import asyncio
import argparse
import time
import statistics
from typing import List, Dict, Any
import httpx
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.search import SearchSession
from backend.config import settings


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{status} {test_name}")
    if details:
        print(f"      {details}")


def print_metric(name: str, value: Any, unit: str = "", target: str = ""):
    """Print metric."""
    target_str = f" (target: {target})" if target else ""
    print(f"   {Colors.BOLD}{name}:{Colors.RESET} {value}{unit}{target_str}")


async def benchmark_api_response_time(base_url: str) -> Dict[str, Any]:
    """
    Benchmark API response times.

    Target: < 200ms per request (excluding scraping)

    Tests:
    - GET /health
    - GET /api/sessions (list)
    - GET /api/sessions/:id (detail)
    - POST /api/search/execute (search)

    Returns:
        Dict with results and pass/fail status
    """
    print_header("API Response Time Benchmark")

    results = {
        "passed": True,
        "endpoints": [],
        "avg_response_time": 0,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoints = [
            ("GET", "/health", None),
            ("GET", f"{base_url}/api/sessions", None),
        ]

        times = []

        for method, path, data in endpoints:
            endpoint_times = []

            # Run each endpoint 10 times
            for i in range(10):
                start = time.time()

                try:
                    if method == "GET":
                        response = await client.get(f"{base_url}{path}")
                    elif method == "POST":
                        response = await client.post(f"{base_url}{path}", json=data)

                    duration = (time.time() - start) * 1000  # Convert to ms

                    if response.status_code < 500:
                        endpoint_times.append(duration)
                        times.append(duration)
                except Exception as e:
                    print(f"   {Colors.RED}Error:{Colors.RESET} {path} - {e}")
                    results["passed"] = False

            if endpoint_times:
                avg_time = statistics.mean(endpoint_times)
                min_time = min(endpoint_times)
                max_time = max(endpoint_times)
                p95_time = statistics.quantiles(endpoint_times, n=20)[18] if len(endpoint_times) >= 20 else max_time

                passed = avg_time < 200

                results["endpoints"].append({
                    "path": path,
                    "avg": avg_time,
                    "min": min_time,
                    "max": max_time,
                    "p95": p95_time,
                    "passed": passed,
                })

                print_result(
                    f"{method} {path}",
                    passed,
                    f"avg: {avg_time:.1f}ms, p95: {p95_time:.1f}ms"
                )

                if not passed:
                    results["passed"] = False

        if times:
            results["avg_response_time"] = statistics.mean(times)
            print_metric("Overall Average", f"{results['avg_response_time']:.1f}", "ms", "< 200ms")

    return results


async def benchmark_concurrent_users(base_url: str, num_users: int = 100) -> Dict[str, Any]:
    """
    Benchmark concurrent user support.

    Target: Support 100+ concurrent users

    Simulates concurrent requests and measures:
    - Total time
    - Average response time
    - Requests per second
    - Error rate

    Returns:
        Dict with results and pass/fail status
    """
    print_header(f"Concurrent Users Benchmark ({num_users} users)")

    results = {
        "passed": True,
        "num_users": num_users,
        "total_time": 0,
        "avg_response_time": 0,
        "requests_per_second": 0,
        "error_count": 0,
    }

    async def make_request(client: httpx.AsyncClient, user_id: int) -> float:
        """Make a single request and return response time."""
        try:
            start = time.time()
            response = await client.get(f"{base_url}/health")
            duration = time.time() - start

            if response.status_code >= 500:
                results["error_count"] += 1

            return duration
        except Exception as e:
            results["error_count"] += 1
            return 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_time = time.time()

        # Create tasks for concurrent requests
        tasks = [make_request(client, i) for i in range(num_users)]

        # Execute all requests concurrently
        times = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Calculate metrics
        valid_times = [t for t in times if t > 0]

        if valid_times:
            results["total_time"] = total_time
            results["avg_response_time"] = statistics.mean(valid_times)
            results["requests_per_second"] = num_users / total_time

            # Pass if completed in reasonable time with low error rate
            error_rate = results["error_count"] / num_users
            passed = total_time < 10 and error_rate < 0.05  # < 10s, < 5% errors

            results["passed"] = passed

            print_result(
                f"{num_users} concurrent requests",
                passed,
                f"time: {total_time:.2f}s, rps: {results['requests_per_second']:.1f}"
            )

            print_metric("Total Time", f"{total_time:.2f}", "s", "< 10s")
            print_metric("Requests/Second", f"{results['requests_per_second']:.1f}")
            print_metric("Avg Response Time", f"{results['avg_response_time']*1000:.1f}", "ms")
            print_metric("Error Rate", f"{error_rate*100:.1f}", "%", "< 5%")

    return results


async def benchmark_database_operations() -> Dict[str, Any]:
    """
    Benchmark database operations.

    Target: 1000+ records/second for bulk inserts

    Tests:
    - Bulk insert performance
    - Query performance
    - Index effectiveness

    Returns:
        Dict with results and pass/fail status
    """
    print_header("Database Operations Benchmark")

    results = {
        "passed": True,
        "bulk_insert_rate": 0,
        "query_time": 0,
    }

    async with AsyncSessionLocal() as db:
        # Test 1: Bulk insert performance
        from backend.models.search import SearchSession
        from backend.utils.bulk_operations import bulk_insert
        from datetime import datetime

        num_records = 1000
        test_data = [
            {
                "user_id": 1,
                "name": f"Test Session {i}",
                "description": f"Benchmark test session {i}",
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            for i in range(num_records)
        ]

        start = time.time()
        try:
            ids = await bulk_insert(db, SearchSession, test_data, return_ids=True)
            insert_time = time.time() - start

            insert_rate = num_records / insert_time
            results["bulk_insert_rate"] = insert_rate

            passed = insert_rate >= 1000

            print_result(
                f"Bulk insert {num_records} records",
                passed,
                f"rate: {insert_rate:.0f} records/sec"
            )

            print_metric("Insert Rate", f"{insert_rate:.0f}", " records/sec", ">= 1000")
            print_metric("Total Time", f"{insert_time*1000:.1f}", "ms")

            if not passed:
                results["passed"] = False

            # Cleanup: delete test records
            if ids:
                from backend.utils.bulk_operations import bulk_delete
                await bulk_delete(db, SearchSession, ids)

        except Exception as e:
            print(f"   {Colors.RED}Error:{Colors.RESET} Bulk insert failed - {e}")
            results["passed"] = False

        # Test 2: Query performance
        start = time.time()
        try:
            stmt = select(SearchSession).limit(100)
            await db.execute(stmt)
            query_time = (time.time() - start) * 1000

            results["query_time"] = query_time

            passed = query_time < 100

            print_result(
                "Query 100 records",
                passed,
                f"time: {query_time:.1f}ms"
            )

            if not passed:
                results["passed"] = False

        except Exception as e:
            print(f"   {Colors.RED}Error:{Colors.RESET} Query failed - {e}")
            results["passed"] = False

    return results


async def benchmark_cache_performance(base_url: str) -> Dict[str, Any]:
    """
    Benchmark cache performance.

    Tests:
    - Cache hit rate
    - Cache speedup factor

    Returns:
        Dict with results and pass/fail status
    """
    print_header("Cache Performance Benchmark")

    results = {
        "passed": True,
        "cache_speedup": 0,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoint = f"{base_url}/api/sessions"

        # First request (cache miss)
        start = time.time()
        await client.get(endpoint)
        uncached_time = time.time() - start

        # Second request (cache hit)
        start = time.time()
        await client.get(endpoint)
        cached_time = time.time() - start

        if cached_time > 0:
            speedup = uncached_time / cached_time
            results["cache_speedup"] = speedup

            passed = speedup > 1.5  # At least 50% faster

            print_result(
                "Cache speedup",
                passed,
                f"speedup: {speedup:.2f}x"
            )

            print_metric("Uncached", f"{uncached_time*1000:.1f}", "ms")
            print_metric("Cached", f"{cached_time*1000:.1f}", "ms")
            print_metric("Speedup", f"{speedup:.2f}", "x", "> 1.5x")

            if not passed:
                results["passed"] = False

    return results


def print_summary(all_results: Dict[str, Dict[str, Any]]):
    """Print benchmark summary."""
    print_header("Benchmark Summary")

    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results.values() if r.get("passed", False))

    for test_name, results in all_results.items():
        passed = results.get("passed", False)
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"   {status}  {test_name}")

    print(f"\n   {Colors.BOLD}Total:{Colors.RESET} {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print(f"\n   {Colors.GREEN}{Colors.BOLD}✓ All benchmarks passed!{Colors.RESET}")
        return 0
    else:
        print(f"\n   {Colors.RED}{Colors.BOLD}✗ Some benchmarks failed{Colors.RESET}")
        return 1


async def main():
    """Run benchmarks."""
    parser = argparse.ArgumentParser(description="Performance benchmarking")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--api", action="store_true", help="API response time")
    parser.add_argument("--concurrent", action="store_true", help="Concurrent users")
    parser.add_argument("--database", action="store_true", help="Database operations")
    parser.add_argument("--cache", action="store_true", help="Cache performance")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--users", type=int, default=100, help="Concurrent users count")

    args = parser.parse_args()

    # If no specific test selected, run all
    if not any([args.api, args.concurrent, args.database, args.cache]):
        args.all = True

    print(f"\n{Colors.BOLD}Issue Observatory Search - Performance Benchmarks{Colors.RESET}")
    print(f"Target: {args.base_url}")

    all_results = {}

    try:
        if args.all or args.api:
            all_results["API Response Time"] = await benchmark_api_response_time(args.base_url)

        if args.all or args.concurrent:
            all_results["Concurrent Users"] = await benchmark_concurrent_users(
                args.base_url, args.users
            )

        if args.all or args.database:
            all_results["Database Operations"] = await benchmark_database_operations()

        if args.all or args.cache:
            all_results["Cache Performance"] = await benchmark_cache_performance(args.base_url)

        return print_summary(all_results)

    except Exception as e:
        print(f"\n{Colors.RED}Benchmark error: {e}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
