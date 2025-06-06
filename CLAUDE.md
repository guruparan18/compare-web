# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Compare Web is a Flask-based web application that allows users to compare two websites side-by-side. The application provides three main comparison modes: visual rendering, header comparison (H1-H4), and link comparison with status validation.

## Core Architecture

The application consists of four main Python modules:

- **app.py**: Main Flask application with routes for comparison (`/`) and crawling (`/crawl`), plus template filters for URL processing
- **crawler.py**: WebCrawler class that performs breadth-first crawling of websites, extracting links with detailed metadata and accessibility checking
- **database.py**: SQLite database operations for storing and retrieving comparison history
- **templates/**: HTML templates with tabbed interface for displaying comparisons

Key architectural patterns:
- Uses requests.Session for connection pooling in the crawler
- Stores comparison results as JSON in SQLite for historical viewing
- Implements URL normalization for link comparison (removes .html extensions and trailing slashes)
- Uses BeautifulSoup for HTML parsing throughout

## Development Commands

Install dependencies:
```bash
uv sync
```

Run the application:
```bash
uv run python app.py
```

The application runs on localhost:3000 by default.

## Database Schema

The application uses SQLite with a single `comparisons` table that stores all comparison data including URLs, content, CSS, links, and comparison results. The database file is `comparisons.db` and is automatically created on first run.

## Key Features

- **Visual Comparison**: Side-by-side iframe rendering of websites
- **Header Comparison**: Extracts and compares H1-H4 headers between sites
- **Link Comparison**: Validates all links and compares accessibility status
- **Web Crawling**: Can crawl up to 5000 pages from a home URL with detailed link analysis
- **Comparison History**: Stores all comparisons in SQLite for later viewing

## Template Filters

Two custom Jinja filters are available:
- `url_to_path`: Removes .html extensions and trailing slashes
- `url_path`: Extracts path, query, and fragment from URLs