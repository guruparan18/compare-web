from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
import difflib

app = Flask(__name__)

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
                comparison.append(('both', line))
        elif tag == 'delete':
            # Text only in first sequence
            for line in text1[i1:i2]:
                comparison.append(('left', line))
        elif tag == 'insert':
            # Text only in second sequence
            for line in text2[j1:j2]:
                comparison.append(('right', line))
        elif tag == 'replace':
            # Text is modified
            for line in text1[i1:i2]:
                comparison.append(('left', line))
            for line in text2[j1:j2]:
                comparison.append(('right', line))
    
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
    text_comparison = None  # New variable for text comparison

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
        text_comparison=text_comparison,  # Add text comparison to template context
    )


if __name__ == "__main__":
    app.run(host="localhost", port=3000, debug=True)
