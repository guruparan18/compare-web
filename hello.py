from bs4 import BeautifulSoup
import requests


def fetch_and_parse(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return None


def check_link(url):
    try:
        response = requests.get(url)
        if response.status_code == 404:
            return "ERROR"
        return "OK"
    except requests.RequestException:
        return "ERROR"


def list_items(soup):
    # Extract and print all H1, H2, H3, H4 text
    for i in range(1, 5):
        for header in soup.find_all(f"h{i}"):
            print(f"H{i}: {header.get_text(strip=True)}")

    # Extract and print all anchor links text and URLs
    for a in soup.find_all("a", href=True):
        link_status = check_link(a["href"])
        print(f"Link text: {a.get_text(strip=True)}, URL: {a['href']} ({link_status})")

    # # Extract and print all paragraphs
    # for p in soup.find_all('p'):
    #     print(f"Paragraph: {p.get_text(strip=True)}")

    # # Extract and print all lists
    # for ul in soup.find_all('ul'):
    #     for li in ul.find_all('li'):
    #         print(f"List item: {li.get_text(strip=True)}")


def main(url):
    # url = input("Enter the website URL: ")
    soup = fetch_and_parse(url)
    if soup:
        list_items(soup)


if __name__ == "__main__":
    main("https://sappachi-sandbox-web.ustaxcourt.gov/petitioners_start")
