from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
import difflib
from concurrent.futures import ThreadPoolExecutor
from database import init_db, store_comparison, get_recent_comparisons, get_comparison
from crawler import WebCrawler
from urllib.parse import urlparse, urljoin # Make sure urlparse is imported


app = Flask(__name__)

# Initialize the database when the app starts
init_db()


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


@app.template_filter('url_path')
def extract_url_path(url):
    """Jinja filter to extract the path, query, and fragment from a URL."""
    if not url:
        return ''
    try:
        parsed = urlparse(str(url))
        # Start with path, default to '/' if empty
        path = parsed.path if parsed.path else '/'
        # Add query string if present
        if parsed.query:
            path += '?' + parsed.query
        # Add fragment if present
        if parsed.fragment:
            path += '#' + parsed.fragment
        return path
    except Exception:
        # Fallback to the original URL string in case of parsing errors
        return str(url)


@app.route("/crawl", methods=["GET", "POST"])
def crawl():
    results = None
    error = None
    if request.method == "POST":
        home_url = request.form.get("home_url")
        if home_url:
            crawler = None
            try:
                crawler = WebCrawler(home_url)
                results = crawler.crawl(max_pages=5000)
            except ValueError as ve:
                print(f"Initialization Error: {ve}")
            except Exception as e:
                print(f"An error occurred during crawling: {e}")
            finally:
                if crawler:
                    crawler.close_session() # Ensure session is closed
        else:
            error = "Please provide a valid URL."
    return render_template("crawl.html", results=results, error=error)    


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
    def check_link(link):
        try:
            response = requests.head(link, allow_redirects=True)
            if response.status_code != 200:
                return (link, f"ERROR ({response.status_code})")
            return (link, "OK")
        except requests.RequestException as e:
            return (link, f"ERROR ({str(e)})")

    with ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(check_link, links))

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

        def process(url):
            soup = fetch_and_parse(url)
            if isinstance(soup, BeautifulSoup):
                return {
                    'content': soup.prettify(),
                    'css': fetch_css(soup, url),
                    'images': fetch_images(soup, url),
                    'results': list_items(soup),
                    'links': fetch_links(soup, url),
                    'text': extract_text(soup),
                    'error': None,
                }
            return {'error': soup}

        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(process, url1)
            future2 = executor.submit(process, url2)
            data1 = future1.result()
            data2 = future2.result()

        if not data1['error']:
            content1 = data1['content']
            css1, broken_links1 = data1['css']
            images1 = data1['images']
            results1 = data1['results']
            links1 = data1['links']
            text1 = data1['text']
        else:
            error1 = data1['error']

        if not data2['error']:
            content2 = data2['content']
            css2, broken_links2 = data2['css']
            images2 = data2['images']
            results2 = data2['results']
            links2 = data2['links']
            text2 = data2['text']
        else:
            error2 = data2['error']

        # Compare texts if both URLs were successfully fetched
        if not data1['error'] and not data2['error']:
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
