import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time
from collections import deque # Use deque for efficient queue operations

# Optional: For robots.txt parsing
# from urllib.robotparser import RobotFileParser

class WebCrawler:
    def __init__(self, home_url):
        # Validate and store home URL
        parsed_home = urlparse(home_url)
        if not parsed_home.scheme or not parsed_home.netloc:
            raise ValueError("Invalid home URL provided.")
        self.home_url = home_url
        self.home_domain = parsed_home.netloc

        # Use sets for efficient membership testing and deduplication
        self.internal_links = set()
        self.external_links = set()
        self.visited_links = set()
        self.link_attributes = {} # Store attributes per link

        # Queue for URLs to crawl (using deque for efficiency)
        self.crawl_queue = deque([self.home_url])
        self.visited_links.add(self.home_url) # Add home URL as visited initially

        # Use a requests.Session for connection pooling and headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MyCoolWebCrawler/1.0 (Python Requests; +http://mycrawler.example.com)' # Be a polite crawler
        })

        # Optional: Robots.txt handling
        # self.rp = RobotFileParser()
        # self.rp.set_url(urljoin(home_url, '/robots.txt'))
        # try:
        #     self.rp.read()
        # except Exception as e:
        #     print(f"Could not read robots.txt for {home_url}: {e}")
        #     self.rp = None # Disable robots checking if reading fails

    def _is_valid_url(self, url):
        """Checks if a URL has a valid scheme and network location."""
        try:
            parsed = urlparse(url)
            # Added check for common schemes, excluding 'javascript:' etc.
            return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
        except ValueError:
            return False # Handle potential parsing errors

    def _is_internal_link(self, url):
        """Checks if a URL belongs to the same domain as the home URL."""
        try:
            return urlparse(url).netloc == self.home_domain
        except ValueError:
            return False

    def _get_link_attributes(self, a_tag):
        """Extracts attributes from an anchor tag, excluding 'href'."""
        # Using dict comprehension for conciseness
        return {attr: value for attr, value in a_tag.attrs.items() if attr != 'href'}

    def _check_accessibility(self, url):
        """
        Checks if a URL is accessible using a HEAD request.
        Returns True if accessible (status 2xx), False otherwise.
        Handles common request exceptions.
        """
        # Skip check if already visited/crawled
        if url in self.visited_links and url in self.link_attributes:
             return self.link_attributes[url].get('accessible', False)

        try:
            # Use the session for the HEAD request too
            head_response = self.session.head(url, timeout=5, allow_redirects=True)
            # Consider any 2xx status code as accessible
            return head_response.status_code >= 200 and head_response.status_code < 300
        # Catch more specific exceptions
        except requests.exceptions.Timeout:
            print(f"Accessibility check timed out for {url}")
            return False
        except requests.exceptions.ConnectionError:
            print(f"Accessibility check connection error for {url}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Accessibility check error for {url}: {e}")
            return False
        except Exception as e: # Catch unexpected errors during HEAD request
             print(f"Unexpected error during accessibility check for {url}: {e}")
             return False

    def _crawl_page(self, url):
        """Crawls a single page, extracts links, and adds them to sets/queue."""
        print(f"Crawling: {url}") # Log which page is being crawled

        # --- Optional: robots.txt check ---
        # if self.rp and not self.rp.can_fetch(self.session.headers['User-Agent'], url):
        #     print(f"Skipping disallowed (robots.txt): {url}")
        #     return
        # --- End optional ---

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Check content type - only parse HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type:
                print(f"Skipping non-HTML content at {url}")
                return

            soup = BeautifulSoup(response.text, 'html.parser') # Consider 'lxml' for speed if installed

            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '').strip()
                if not href: # Skip empty hrefs
                    continue

                # Resolve relative URLs
                absolute_url = urljoin(response.url, href) # Use response.url for accuracy after redirects

                if not self._is_valid_url(absolute_url):
                    # print(f"Skipping invalid URL: {absolute_url}")
                    continue

                # --- Optimization: Delay Accessibility Check ---
                # Check accessibility only when needed, or perhaps asynchronously later.
                # For this version, we'll check it but be aware it's a bottleneck.
                # A potential optimization is to only check *external* links this way.
                is_accessible = self._check_accessibility(absolute_url)

                attributes = self._get_link_attributes(a_tag)
                self.link_attributes[absolute_url] = {
                    'attributes': attributes,
                    'accessible': is_accessible,
                    'source_page': url # Track where the link was found
                }

                if self._is_internal_link(absolute_url):
                    self.internal_links.add(absolute_url)
                    # Add to queue only if it hasn't been visited/queued
                    if absolute_url not in self.visited_links:
                        self.visited_links.add(absolute_url) # Mark as visited *when queued*
                        self.crawl_queue.append(absolute_url)
                else:
                    self.external_links.add(absolute_url)

        except requests.exceptions.Timeout:
            print(f"Request timed out for {url}")
        except requests.exceptions.ConnectionError:
             print(f"Connection error for {url}")
        except requests.exceptions.HTTPError as e:
             print(f"HTTP error {e.response.status_code} for {url}")
        except requests.exceptions.RequestException as e:
            print(f"Error crawling {url}: {e}")
        except Exception as e: # Catch other potential errors (e.g., BS4 parsing)
            print(f"Unexpected error processing page {url}: {e}")


    def crawl(self, max_pages=10):
        """
        Performs the crawl up to max_pages.
        Uses a queue for breadth-first crawling.
        """
        pages_crawled = 0
        while self.crawl_queue and pages_crawled < max_pages:
            url_to_crawl = self.crawl_queue.popleft()
            self._crawl_page(url_to_crawl)
            pages_crawled += 1
            # Optional: Add a small delay between requests to be polite
            # time.sleep(0.1)

        print(f"Crawl finished. Crawled {pages_crawled} pages.")
        return {
            'internal_links': sorted(list(self.internal_links)), # Sort for consistent output
            'external_links': sorted(list(self.external_links)),
            'link_attributes': self.link_attributes
        }

    def close_session(self):
        """Closes the requests session."""
        self.session.close()
        print("Requests session closed.")
