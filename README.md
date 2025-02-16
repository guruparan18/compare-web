# Compare Web

A simple tool that runs in local and compares any two given website URLs that you have access to.

## Setup

You will need `uv` to run. Checkout the code and do `uv sync` to install all dependencies.

## Run

To run the application:

```sh
uv run python app.py
```

## Comparison

All comparisons are returned in two columns. There are three main comparisons listed in tabs. 

### Visual Comparison

Visaully renders both websites next to next. This aids manual comparison of both websites for visual elements. The rendering is scrollable.

### Header Comparison

Lists H1, H2, H3, and H4 headers from both websites. No styling is applied.

### Link Comparison

Lists all the URLs each websites link to. If the linked URL returns anything other than 200, it lists the status as "ERROR (HTTP.status)" in red.
