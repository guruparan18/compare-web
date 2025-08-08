import requests
from urllib.parse import urlparse
from typing import Dict
import threading
from contextlib import contextmanager


class HTTPSessionManager:
    """
    Thread-safe HTTP session manager with connection pooling and reuse.
    Maintains separate sessions per domain for optimal connection reuse.
    """

    def __init__(self):
        self._sessions: Dict[str, requests.Session] = {}
        self._lock = threading.Lock()

    def get_session(self, url: str) -> requests.Session:
        """
        Get or create a session for the given URL's domain.
        Thread-safe and reuses connections for the same domain.
        """
        parsed = urlparse(url)
        domain_key = f"{parsed.scheme}://{parsed.netloc}"

        with self._lock:
            if domain_key not in self._sessions:
                session = requests.Session()

                # Configure session for optimal performance
                session.headers.update(
                    {
                        "User-Agent": "Compare-Web/1.0 (Python-requests)",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                    }
                )

                # Configure connection pooling
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,  # Number of connection pools
                    pool_maxsize=20,  # Max connections per pool
                    max_retries=3,  # Retry failed requests
                    pool_block=False,  # Don't block when pool is full
                )
                session.mount("http://", adapter)
                session.mount("https://", adapter)

                self._sessions[domain_key] = session

            return self._sessions[domain_key]

    def close_all_sessions(self):
        """Close all active sessions and clear the cache"""
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()

    @contextmanager
    def session_for_url(self, url: str):
        """Context manager for getting a session for a specific URL"""
        session = self.get_session(url)
        try:
            yield session
        finally:
            # Don't close the session - keep it for reuse
            pass


# Global session manager instance
_session_manager = HTTPSessionManager()


def get_session_for_url(url: str) -> requests.Session:
    """
    Get a reusable session for the given URL.
    This is the main function to use throughout the application.
    """
    return _session_manager.get_session(url)


def close_all_sessions():
    """Close all sessions - call this when shutting down the application"""
    _session_manager.close_all_sessions()


def fetch_with_session(url: str, method: str = "GET", **kwargs) -> requests.Response:
    """
    Fetch a URL using session reuse with automatic retry and error handling.
    Args:
        url: The URL to fetch
        method: HTTP method ('GET', 'HEAD', etc.)
        **kwargs: Additional arguments to pass to the request
    """
    session = get_session_for_url(url)

    # Set default timeout if not provided
    if "timeout" not in kwargs:
        kwargs["timeout"] = 10

    # Set default allow_redirects if not provided for HEAD requests
    if method.upper() == "HEAD" and "allow_redirects" not in kwargs:
        kwargs["allow_redirects"] = True

    try:
        response = session.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        # Re-raise with more context
        raise requests.exceptions.RequestException(
            f"Failed to fetch {url}: {str(e)}"
        ) from e


# Performance monitoring decorator
def monitor_session_performance(func):
    """Decorator to monitor session reuse performance"""
    import time
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        print(f"Session operation {func.__name__} took {end_time - start_time:.3f}s")
        return result

    return wrapper


# Session statistics
class SessionStats:
    """Track session usage statistics"""

    def __init__(self):
        self.request_count = 0
        self.session_reuse_count = 0
        self.total_time = 0

    def record_request(self, reused_session: bool, duration: float):
        self.request_count += 1
        if reused_session:
            self.session_reuse_count += 1
        self.total_time += duration

    def get_stats(self) -> dict:
        if self.request_count == 0:
            return {"requests": 0, "reuse_rate": 0, "avg_time": 0}

        return {
            "requests": self.request_count,
            "reuse_rate": self.session_reuse_count / self.request_count,
            "avg_time": self.total_time / self.request_count,
        }


# Global stats instance
session_stats = SessionStats()

if __name__ == "__main__":
    # Example usage and performance test
    import time

    test_urls = [
        "https://example.com",
        "https://example.com/page1",
        "https://example.com/page2",
        "https://httpbin.org/get",
        "https://httpbin.org/status/200",
    ]

    # Test without session reuse (old way)
    print("Testing without session reuse...")
    start = time.time()
    for url in test_urls:
        try:
            response = requests.get(url, timeout=5)
            print(f"  {url}: {response.status_code}")
        except Exception as e:
            print(f"  {url}: ERROR - {e}")
    no_session_time = time.time() - start

    # Test with session reuse (new way)
    print("\nTesting with session reuse...")
    start = time.time()
    for url in test_urls:
        try:
            response = fetch_with_session(url, timeout=5)
            print(f"  {url}: {response.status_code}")
        except Exception as e:
            print(f"  {url}: ERROR - {e}")
    session_time = time.time() - start

    close_all_sessions()

    print("\nPerformance comparison:")
    print(f"Without session reuse: {no_session_time:.2f}s")
    print(f"With session reuse: {session_time:.2f}s")
    if no_session_time > 0:
        print(
            f"Improvement: {((no_session_time - session_time) / no_session_time * 100):.1f}%"
        )
