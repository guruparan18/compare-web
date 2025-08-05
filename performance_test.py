#!/usr/bin/env python3
"""
Performance testing script for Compare Web optimizations.
Run this to measure the performance improvements.
"""

import time
import requests
import sys
import os

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_link_validation_performance():
    """Test the link validation performance improvements."""
    print("=== Link Validation Performance Test ===")

    # Test URLs (mix of fast and slow responses)
    test_links = [
        "https://httpbin.org/delay/0.5",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",
        "https://example.com",
        "https://google.com",
        "https://github.com",
        "https://stackoverflow.com",
        "https://python.org",
        "https://flask.palletsprojects.com",
        "https://requests.readthedocs.io",
    ]

    print(f"Testing with {len(test_links)} URLs...")

    # Test original sequential method
    print("\n1. Sequential Link Validation (Original):")
    start_time = time.time()
    sequential_results = []
    for link in test_links:
        try:
            response = requests.head(link, allow_redirects=True, timeout=5)
            if response.status_code == 200:
                sequential_results.append((link, "OK"))
            else:
                sequential_results.append((link, f"ERROR ({response.status_code})"))
        except requests.RequestException as e:
            sequential_results.append((link, f"ERROR ({str(e)})"))

    sequential_time = time.time() - start_time
    print(f"Time taken: {sequential_time:.2f} seconds")
    print(
        f"Results: {len([r for r in sequential_results if r[1] == 'OK'])} OK, {len([r for r in sequential_results if r[1] != 'OK'])} errors"
    )

    # Test optimized parallel method
    print("\n2. Parallel Link Validation (Optimized):")
    try:
        from parallel_link_validator import validate_links_parallel

        start_time = time.time()
        parallel_results = validate_links_parallel(test_links, max_workers=10)
        parallel_time = time.time() - start_time

        print(f"Time taken: {parallel_time:.2f} seconds")
        print(
            f"Results: {len([r for r in parallel_results if r[1] == 'OK'])} OK, {len([r for r in parallel_results if r[1] != 'OK'])} errors"
        )

        if sequential_time > 0:
            speedup = sequential_time / parallel_time
            print(f"Speedup: {speedup:.2f}x faster")
            print(
                f"Time saved: {sequential_time - parallel_time:.2f} seconds ({((sequential_time - parallel_time) / sequential_time * 100):.1f}%)"
            )

    except ImportError:
        print("Parallel link validator not available")


def test_session_reuse_performance():
    """Test the session reuse performance improvements."""
    print("\n=== Session Reuse Performance Test ===")

    # Test URLs from the same domain for maximum session reuse benefit
    test_urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/headers",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/ip",
        "https://httpbin.org/status/200",
    ] * 3  # 15 requests total to same domain

    print(f"Testing with {len(test_urls)} requests to same domain...")

    # Test without session reuse (original method)
    print("\n1. Without Session Reuse (Original):")
    start_time = time.time()
    for url in test_urls:
        try:
            requests.get(url, timeout=5)
            # Don't print status to avoid spam
        except Exception:
            pass
    no_session_time = time.time() - start_time
    print(f"Time taken: {no_session_time:.2f} seconds")

    # Test with session reuse
    print("\n2. With Session Reuse (Optimized):")
    try:
        from http_session_manager import fetch_with_session, close_all_sessions

        start_time = time.time()
        for url in test_urls:
            try:
                fetch_with_session(url, timeout=5)
                # Don't print status to avoid spam
            except Exception:
                pass
        session_time = time.time() - start_time

        close_all_sessions()

        print(f"Time taken: {session_time:.2f} seconds")

        if no_session_time > 0:
            speedup = no_session_time / session_time
            print(f"Speedup: {speedup:.2f}x faster")
            print(
                f"Time saved: {no_session_time - session_time:.2f} seconds ({((no_session_time - session_time) / no_session_time * 100):.1f}%)"
            )

    except ImportError:
        print("HTTP session manager not available")


def test_database_performance():
    """Test the database performance improvements."""
    print("\n=== Database Performance Test ===")

    try:
        from database_optimized import (
            init_db_optimized,
            store_comparison_optimized,
            get_recent_comparisons_optimized,
            get_database_stats,
        )

        # Initialize optimized database
        print("Initializing optimized database...")
        init_db_optimized()

        # Test data
        test_data = {
            "url1": "https://example.com",
            "url2": "https://test.com",
            "content1": "<html><body>Test content 1</body></html>"
            * 100,  # Make it larger
            "content2": "<html><body>Test content 2</body></html>" * 100,
            "css1": ["body { color: red; }"] * 10,
            "css2": ["body { color: blue; }"] * 10,
            "comparison": {"h1": [("Title", "Title", "both")]},
            "error1": None,
            "error2": None,
            "broken_links1": [],
            "broken_links2": [],
            "images1": ["image1.jpg"] * 5,
            "images2": ["image2.jpg"] * 5,
            "results1": {"h1": ["Title"]},
            "results2": {"h1": ["Title"]},
            "links1": [("https://example.com/page1", "OK")] * 20,
            "links2": [("https://test.com/page1", "OK")] * 20,
            "links_comparison": {"page1": "both"},
            "text_comparison": [("both", "Test content", None)] * 50,
        }

        # Test storage performance
        print("\n1. Testing Storage Performance:")
        storage_times = []
        for i in range(5):
            test_data["url1"] = f"https://example.com/test{i}"
            test_data["url2"] = f"https://test.com/test{i}"

            start_time = time.time()
            store_comparison_optimized(test_data, async_mode=False)
            storage_time = time.time() - start_time
            storage_times.append(storage_time)

        avg_storage_time = sum(storage_times) / len(storage_times)
        print(f"Average storage time: {avg_storage_time:.3f} seconds")

        # Test retrieval performance
        print("\n2. Testing Retrieval Performance:")
        retrieval_times = []
        for i in range(10):
            start_time = time.time()
            recent = get_recent_comparisons_optimized(10)
            retrieval_time = time.time() - start_time
            retrieval_times.append(retrieval_time)

        avg_retrieval_time = sum(retrieval_times) / len(retrieval_times)
        print(f"Average retrieval time: {avg_retrieval_time:.3f} seconds")
        print(f"Retrieved {len(recent)} comparisons")

        # Show database statistics
        print("\n3. Database Statistics:")
        stats = get_database_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except ImportError:
        print("Database optimizations not available")
    except Exception as e:
        print(f"Database test failed: {e}")


def main():
    """Run all performance tests."""
    print("Compare Web Performance Test Suite")
    print("=" * 50)

    test_link_validation_performance()
    test_session_reuse_performance()
    test_database_performance()

    print("\n" + "=" * 50)
    print("Performance testing complete!")
    print("\nNOTE: These tests require internet connectivity and may be affected by")
    print("network conditions. Run multiple times for consistent measurements.")


if __name__ == "__main__":
    main()
