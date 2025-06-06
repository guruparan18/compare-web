import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag # Import Tag
from collections import deque # Use deque for efficient queue operations
import csv
import os
from datetime import datetime

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
        # Store detailed info including text and attributes for each unique link URL
        self.link_details = {}

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

    def _get_all_attributes(self, tag: Tag):
        """Extracts ALL attributes from a tag."""
        # Convert multi-value attributes (like class) to space-separated strings
        attrs = {}
        for attr, value in tag.attrs.items():
            if isinstance(value, list):
                attrs[attr] = ' '.join(value)
            else:
                attrs[attr] = value
        return attrs

    def _check_accessibility(self, url):
        """
        Checks if a URL is accessible using a HEAD request.
        Returns True if accessible (status 2xx), False otherwise.
        Handles common request exceptions.
        Updates accessibility in self.link_details if entry exists.
        """
        # Check if accessibility info already exists for this URL
        # Use .get() with a default to avoid KeyError if 'accessible' is missing
        if url in self.link_details and self.link_details[url].get('accessible') is not None:
             return self.link_details[url]['accessible']

        accessible = False # Default assumption
        try:
            # Use the session for the HEAD request too
            head_response = self.session.head(url, timeout=5, allow_redirects=True)
            # Consider any 2xx status code as accessible
            accessible = head_response.status_code >= 200 and head_response.status_code < 300
        # Catch more specific exceptions
        except requests.exceptions.Timeout:
            print(f"Accessibility check timed out for {url}")
        except requests.exceptions.ConnectionError:
            print(f"Accessibility check connection error for {url}")
        except requests.exceptions.RequestException as e:
            print(f"Accessibility check error for {url}: {e}")
        except Exception as e: # Catch unexpected errors during HEAD request
             print(f"Unexpected error during accessibility check for {url}: {e}")

        # --- MODIFICATION ---
        # Update the accessibility status *only if* the link detail entry already exists.
        # Let _crawl_page be responsible for creating the initial entry.
        if url in self.link_details:
            self.link_details[url]['accessible'] = accessible
        # --- END MODIFICATION ---

        # Return the determined status, whether updated or not.
        # _crawl_page will use this return value when creating the entry if needed.
        return accessible

    def _crawl_page(self, url):
        """Crawls a single page, extracts links and their details, and adds them to sets/queue."""
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
                    continue

                # Get all attributes including href
                attributes = self._get_all_attributes(a_tag)
                link_text = a_tag.get_text(strip=True)

                # --- Accessibility Check ---
                # Decide if/when to check. Checking here is simpler but slower.
                # Consider checking only external links or doing it post-crawl.
                is_accessible = self._check_accessibility(absolute_url) # Check accessibility

                # Store details aggregated by absolute_url
                if absolute_url not in self.link_details:
                    self.link_details[absolute_url] = {
                        'url': absolute_url, # Store the URL itself for easy access
                        'is_internal': self._is_internal_link(absolute_url),
                        'accessible': is_accessible, # Store accessibility status
                        'sources': [] # List of (source_page, link_text, attributes) tuples
                    }
                # Add occurrence details (page found on, text, specific attributes)
                self.link_details[absolute_url]['sources'].append({
                     'page': url,
                     'text': link_text,
                     'attributes': attributes
                })

                # Classify link and add to queue if internal and new
                if self.link_details[absolute_url]['is_internal']:
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
        Returns detailed link information.
        """
        pages_crawled = 0
        while self.crawl_queue and pages_crawled < max_pages:
            url_to_crawl = self.crawl_queue.popleft()
            self._crawl_page(url_to_crawl)
            pages_crawled += 1
            # Optional: Add a small delay between requests to be polite
            # time.sleep(0.1)

        print(f"Crawl finished. Crawled {pages_crawled} pages.")

        # Prepare results: Separate internal/external link details
        results = {'internal': [], 'external': []}
        all_links = self.internal_links.union(self.external_links)

        for link_url in sorted(list(all_links)):
             if link_url in self.link_details:
                 detail = self.link_details[link_url]
                 if detail['is_internal']:
                     results['internal'].append(detail)
                 else:
                     results['external'].append(detail)

        # Store results in CSV file before returning
        self._save_to_csv(results)

        return results # Return the structured details

    def _save_to_csv(self, results):
        """Save crawl results to a CSV file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain_name = self.home_domain.replace('.', '_')
        filename = f"crawl_results_{domain_name}_{timestamp}.csv"
        
        # Create directory if it doesn't exist
        os.makedirs('crawl_results', exist_ok=True)
        filepath = os.path.join('crawl_results', filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['url', 'type', 'accessible', 'source_page', 'link_text', 'attributes']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            # Write internal links
            for link_detail in results['internal']:
                for source in link_detail['sources']:
                    writer.writerow({
                        'url': link_detail['url'],
                        'type': 'internal',
                        'accessible': link_detail['accessible'],
                        'source_page': source['page'],
                        'link_text': source['text'],
                        'attributes': str(source['attributes'])
                    })
            
            # Write external links
            for link_detail in results['external']:
                for source in link_detail['sources']:
                    writer.writerow({
                        'url': link_detail['url'],
                        'type': 'external',
                        'accessible': link_detail['accessible'],
                        'source_page': source['page'],
                        'link_text': source['text'],
                        'attributes': str(source['attributes'])
                    })
        
        print(f"Crawl results saved to: {filepath}")

    def close_session(self):
        """Closes the requests session."""
        self.session.close()
        print("Requests session closed.")
