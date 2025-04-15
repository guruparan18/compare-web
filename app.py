from flask import Flask, request, render_template, redirect, url_for
from urllib.parse import urlparse, urljoin
import requests
import re
from bs4 import BeautifulSoup
import difflib
from database import init_db, store_comparison, get_recent_comparisons, get_comparison

app = Flask(__name__)

# Initialize the database when the app starts
init_db()

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
    
@app.route("/crawl", methods=["GET", "POST"])
def crawl():
    results = None
    error = None
    if request.method == "POST":
        home_url = request.form.get("home_url")
        if home_url:
            try:
                crawler = WebCrawler(home_url)
                results = crawler.crawl(max_pages=10)  # Limit to 10 pages
            except Exception as e:
                error = f"Error during crawling: {e}"
        else:
            error = "Please provide a valid URL."
    return render_template("crawl.html", results=results, error=error)    


@app.template_filter('url_to_path')
def url_to_path(url):
    # Parse the URL to extract the path
    path = requests.compat.urlparse(url).path
    # Remove the ".html" extension if present
    if path.endswith('.html'):
        path = path[:-5]
    elif path.endswith('/'):
        path = path[:-1]
    return path

def fetch_images(soup, base_url):
    image_links = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            if not src.startswith("http"):
                src = requests.compat.urljoin(base_url, src)
            image_links.append(src)
    return image_links


def fetch_and_parse(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        return f"Error fetching the URL: {e}"


def fetch_css(soup, base_url):
    css_links = []
    broken_links = []
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            if not href.startswith("http"):
                href = requests.compat.urljoin(base_url, href)
            try:
                css_response = requests.get(href)
                css_response.raise_for_status()
                css_links.append(css_response.text)
            except requests.RequestException:
                broken_links.append(href)
    return css_links, broken_links


def list_items(soup):
    output = {"h1": [], "h2": [], "h3": [], "h4": []}
    for i in range(1, 5):
        for header in soup.find_all(f"h{i}"):
            output[f"h{i}"].append(header.get_text(strip=True))
    return output

def validate_links(links):
    validated_links = []
    for link in links:
        try:
            response = requests.head(link, allow_redirects=True)
            if response.status_code != 200:
                validated_links.append((link, f"ERROR ({response.status_code})"))
            else:
                validated_links.append((link, "OK"))
        except requests.RequestException as e:
            validated_links.append((link, f"ERROR ({str(e)})"))
    return validated_links

def fetch_links(soup, base_url):
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href.startswith("http"):
            href = requests.compat.urljoin(base_url, href)
        links.append(href)
    return validate_links(links)


def compare_links(links1, links2):
    def normalize_link(link):
        # Parse the URL to extract the path
        path = requests.compat.urlparse(link).path
        # Remove the ".html" extension if present
        if path.endswith('.html'):
            path = path[:-5]
        elif path.endswith('/'):
            path = path[:-1]
        return path

    # Normalize links
    normalized_links1 = {normalize_link(link) for link, status in links1}
    normalized_links2 = {normalize_link(link) for link, status in links2}

    # Create a dictionary to store comparison results
    comparison = {}

    # Compare links and store results
    for link in normalized_links1.union(normalized_links2):
        if link in normalized_links1 and link in normalized_links2:
            comparison[link] = 'both'
        else:
            comparison[link] = 'one'

    return comparison


def compare_items(items1, items2):
    comparison = {"h1": [], "h2": [], "h3": [], "h4": []}
    for key in comparison.keys():
        set1 = set(items1[key])
        set2 = set(items2[key])
        all_items = set1.union(set2)
        for item in all_items:
            if item in set1 and item in set2:
                # Check if the item is modified
                if items1[key].count(item) != items2[key].count(item):
                    comparison[key].append(
                        (item, item, "modified")
                    )  # Present in both but modified
                else:
                    comparison[key].append(
                        (item, item, "both")
                    )  # Present in both and identical
            elif item in set1:
                comparison[key].append((item, None, "one"))  # Present in one
            else:
                comparison[key].append((None, item, "one"))  # Present in one
    return comparison

def extract_text(soup):
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    # Get text and normalize whitespace
    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return lines

def compare_text(text1, text2):
    # Use difflib to compare text
    d = difflib.SequenceMatcher(None, text1, text2)
    comparison = []
    
    for tag, i1, i2, j1, j2 in d.get_opcodes():
        if tag == 'equal':
            # Text is the same in both versions
            for line in text1[i1:i2]:
                comparison.append(('both', line, None))
        elif tag == 'replace':
            # Text is modified - find character-level differences
            for line1, line2 in zip(text1[i1:i2], text2[j1:j2]):
                s = difflib.SequenceMatcher(None, line1, line2)
                left_changes = []
                right_changes = []
                last_left = 0
                last_right = 0
                
                for subtag, left_start, left_end, right_start, right_end in s.get_opcodes():
                    if subtag != 'equal':
                        left_changes.append((left_start, left_end))
                        right_changes.append((right_start, right_end))
                
                comparison.append(('modified', line1, line2, left_changes, right_changes))
        elif tag == 'delete':
            # Text only in first sequence
            for line in text1[i1:i2]:
                comparison.append(('left', line, None))
        elif tag == 'insert':
            # Text only in second sequence
            for line in text2[j1:j2]:
                comparison.append(('right', None, line))
    
    return comparison

@app.route("/", methods=["GET", "POST"])
def index():
    url1, url2, error1, error2, comparison = None, None, None, None, None
    content1, content2 = None, None
    css1, css2 = [], []
    broken_links1, broken_links2 = [], []
    images1, images2 = [], []
    results1, results2 = {}, {}
    links1, links2 = [], []
    links_comparison = []
    text_comparison = None
    recent_comparisons = get_recent_comparisons()  # Get recent comparisons for display

    if request.method == "POST":
        url1 = request.form.get("url1")
        url2 = request.form.get("url2")

        soup1 = fetch_and_parse(url1)
        if isinstance(soup1, BeautifulSoup):
            content1 = soup1.prettify()
            css1, broken_links1 = fetch_css(soup1, url1)
            images1 = fetch_images(soup1, url1)
            results1 = list_items(soup1)
            links1 = fetch_links(soup1, url1)
            text1 = extract_text(soup1)  # Extract text from first URL
        else:
            error1 = soup1

        soup2 = fetch_and_parse(url2)
        if isinstance(soup2, BeautifulSoup):
            content2 = soup2.prettify()
            css2, broken_links2 = fetch_css(soup2, url2)
            images2 = fetch_images(soup2, url2)
            results2 = list_items(soup2)
            links2 = fetch_links(soup2, url2)
            text2 = extract_text(soup2)  # Extract text from second URL
        else:
            error2 = soup2

        # Compare texts if both URLs were successfully fetched
        if isinstance(soup1, BeautifulSoup) and isinstance(soup2, BeautifulSoup):
            text_comparison = compare_text(text1, text2)

        if results1 and results2:
            comparison = compare_items(results1, results2)

        if links1 and links2:
            links_comparison = compare_links(links1, links2)

        # After all comparisons are done, store the results
        comparison_data = {
            'url1': url1,
            'url2': url2,
            'content1': content1,
            'content2': content2,
            'css1': css1,
            'css2': css2,
            'comparison': comparison,
            'error1': error1,
            'error2': error2,
            'broken_links1': broken_links1,
            'broken_links2': broken_links2,
            'images1': images1,
            'images2': images2,
            'results1': results1,
            'results2': results2,
            'links1': links1,
            'links2': links2,
            'links_comparison': links_comparison,
            'text_comparison': text_comparison
        }
        store_comparison(comparison_data)

    return render_template(
        "template.html",
        url1=url1,
        url2=url2,
        content1=content1,
        content2=content2,
        css1=css1,
        css2=css2,
        comparison=comparison,
        error1=error1,
        error2=error2,
        broken_links1=broken_links1,
        broken_links2=broken_links2,
        images1=images1,
        images2=images2,
        results1=results1,
        results2=results2,
        links1=links1,
        links2=links2,
        links_comparison=links_comparison,
        text_comparison=text_comparison,
        recent_comparisons=recent_comparisons  # Add recent comparisons to template
    )

# Add a new route to view historical comparisons
@app.route("/comparison/<int:comparison_id>")
def view_comparison(comparison_id):
    comparison_data = get_comparison(comparison_id)
    if comparison_data:
        return render_template(
            "template.html",
            **comparison_data,
            recent_comparisons=get_recent_comparisons()
        )
    return "Comparison not found", 404

if __name__ == "__main__":
    app.run(host="localhost", port=3000, debug=True)
