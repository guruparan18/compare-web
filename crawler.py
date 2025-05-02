from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

class WebCrawler:
    def __init__(self, home_url):
        self.home_url = home_url
        self.home_domain = urlparse(home_url).netloc
        self.internal_links = set()
        self.external_links = set()
        self.visited_links = set()
        self.link_attributes = {}

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme) and not url.startswith('javascript:')

    def is_internal_link(self, url):
        return urlparse(url).netloc == self.home_domain

    def get_link_attributes(self, a_tag):
        attributes = {}
        for attr in a_tag.attrs:
            if attr != 'href':
                attributes[attr] = a_tag[attr]
        return attributes

    def crawl_page(self, url):
        if url in self.visited_links:
            return
        self.visited_links.add(url)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                absolute_url = urljoin(url, href)
                if not self.is_valid_url(absolute_url):
                    continue
                try:
                    head_response = requests.head(absolute_url, timeout=5)
                    is_accessible = head_response.status_code == 200
                except:
                    is_accessible = False
                attributes = self.get_link_attributes(a_tag)
                self.link_attributes[absolute_url] = {
                    'attributes': attributes,
                    'accessible': is_accessible
                }
                if self.is_internal_link(absolute_url):
                    self.internal_links.add(absolute_url)
                else:
                    self.external_links.add(absolute_url)
        except Exception as e:
            print(f"Error crawling {url}: {e}")

    def crawl(self, max_pages=None):
        self.crawl_page(self.home_url)
        links_to_crawl = list(self.internal_links - self.visited_links)
        if max_pages and max_pages > 0:
            links_to_crawl = links_to_crawl[:max_pages]
        for link in links_to_crawl:
            self.crawl_page(link)
        return {
            'internal_links': list(self.internal_links),
            'external_links': list(self.external_links),
            'link_attributes': self.link_attributes
        }
