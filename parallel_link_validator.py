import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from typing import List, Tuple
import time


class ParallelLinkValidator:
    """Efficient parallel link validation using both threading and async approaches"""

    def __init__(self, max_workers: int = 20, timeout: int = 10):
        self.max_workers = max_workers
        self.timeout = timeout

    def validate_links_threaded(self, links: List[str]) -> List[Tuple[str, str]]:
        """
        Validate links using ThreadPoolExecutor for parallel HTTP requests.
        Best for moderate number of links (10-100).
        """

        def validate_single_link(link: str) -> Tuple[str, str]:
            try:
                response = requests.head(
                    link, allow_redirects=True, timeout=self.timeout
                )
                if 200 <= response.status_code < 400:
                    return (link, "OK")
                else:
                    return (link, f"ERROR ({response.status_code})")
            except requests.RequestException as e:
                return (link, f"ERROR ({str(e)})")

        validated_links = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_link = {
                executor.submit(validate_single_link, link): link for link in links
            }

            # Collect results as they complete
            for future in as_completed(future_to_link):
                try:
                    result = future.result()
                    validated_links.append(result)
                except Exception as e:
                    link = future_to_link[future]
                    validated_links.append((link, f"ERROR (Exception: {str(e)})"))

        return validated_links

    async def validate_links_async(self, links: List[str]) -> List[Tuple[str, str]]:
        """
        Validate links using aiohttp for async HTTP requests.
        Best for large number of links (100+).
        """

        async def validate_single_link_async(
            session: aiohttp.ClientSession, link: str
        ) -> Tuple[str, str]:
            try:
                async with session.head(
                    link,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if 200 <= response.status < 400:
                        return (link, "OK")
                    else:
                        return (link, f"ERROR ({response.status})")
            except asyncio.TimeoutError:
                return (link, "ERROR (Timeout)")
            except Exception as e:
                return (link, f"ERROR ({str(e)})")

        connector = aiohttp.TCPConnector(limit=self.max_workers, limit_per_host=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [validate_single_link_async(session, link) for link in links]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions that occurred
            validated_links = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    validated_links.append(
                        (links[i], f"ERROR (Exception: {str(result)})")
                    )
                else:
                    validated_links.append(result)

            return validated_links

    def validate_links_smart(self, links: List[str]) -> List[Tuple[str, str]]:
        """
        Smart validation that chooses the best method based on number of links.
        """
        if len(links) <= 50:
            # Use threading for smaller sets
            return self.validate_links_threaded(links)
        else:
            # Use async for larger sets
            return asyncio.run(self.validate_links_async(links))


# Updated function for app.py integration
def validate_links_parallel(
    links: List[str], max_workers: int = 20
) -> List[Tuple[str, str]]:
    """
    Drop-in replacement for the original validate_links function.
    Automatically chooses optimal parallel validation method.
    """
    validator = ParallelLinkValidator(max_workers=max_workers)
    return validator.validate_links_smart(links)


# Performance comparison function
def compare_validation_performance():
    """Compare sequential vs parallel validation performance"""
    test_links = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",
        "https://example.com",
        "https://google.com",
    ] * 10  # 50 links total

    validator = ParallelLinkValidator()

    # Sequential (original method)
    start = time.time()
    sequential_results = []
    for link in test_links:
        try:
            response = requests.head(link, allow_redirects=True, timeout=10)
            if response.status_code != 200:
                sequential_results.append((link, f"ERROR ({response.status_code})"))
            else:
                sequential_results.append((link, "OK"))
        except requests.RequestException as e:
            sequential_results.append((link, f"ERROR ({str(e)})"))
    sequential_time = time.time() - start

    # Parallel (threaded)
    start = time.time()
    parallel_results = validator.validate_links_threaded(test_links)
    parallel_time = time.time() - start

    print(f"Sequential validation: {sequential_time:.2f} seconds")
    print(f"Parallel validation: {parallel_time:.2f} seconds")
    print(f"Speedup: {sequential_time / parallel_time:.2f}x")

    return sequential_results, parallel_results


if __name__ == "__main__":
    compare_validation_performance()
