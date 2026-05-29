"""
HTML and PDF -> Markdown preprocessing for RAG / knowledge bases.

Two utilities:
- html_to_markdown(url, output_dir): scrape a web page with trafilatura
- pdf_to_markdown(path, output_dir): convert a local PDF with docling

Output is clean markdown that is machine readable. 
No metadata schema or storage backend is assumed; this is just meant to be part 1 of an AI-ready data pipeline. 


Install: pip install trafilatura docling
Usage:
    python preprocess.py --urls-file urls.txt --output-dir output/
    python preprocess.py --pdf-dir input_pdfs/  --output-dir output/
"""

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

from trafilatura import fetch_url, extract

# docling is imported lazily inside _build_converter() so users who only need
# HTML -> Markdown don't have to install it (it pulls in PyTorch, ~2GB).


def slugify(text, max_length=80):
    """Convert a string to a safe, lowercase filename.

    Strips special characters, replaces spaces/hyphens with underscores,
    and lowercases everything. Used for both HTML-derived titles and
    PDF filenames to ensure consistent naming.

    Example document title: "Living wages, Flagstaff AZ" -> "living_wages_flagstaff_az"
    """
    text = str(text).lower().strip()
    text = text.replace('-', '_').replace(' ', '_')
    text = re.sub(r'[^a-z0-9_]+', '', text)
    text = re.sub(r'_+', '_', text).strip('_')
    if len(text) > max_length:
        text = text[:max_length].rsplit('_', 1)[0]

    return text


# ---------------------------------------------------------------------------
# HTML -> Markdown (trafilatura)
# ---------------------------------------------------------------------------

def scrape_url(url):
    """
    Fetch URL and extract content as markdown.

    The extract flags are tuned for policy/research content:
    - favor_precision=True   prefer fewer false-positive paragraphs (nav, footers)
    - include_tables=True    preserve tabular data, important for stats-heavy docs
    - include_formatting=True keep headings/lists for downstream chunkers
    - with_metadata=True     emit a YAML frontmatter block (title, author, date)

    Args:
        url: Web page URL to scrape

    Returns:
        Extracted markdown content or None on failure
    """
    print(f"  Fetching: {url}")
    downloaded = fetch_url(url)

    if not downloaded:
        print(f"  Failed to download: {url}")
        return None

    result = extract(
        downloaded,
        output_format="markdown",
        with_metadata=True,
        include_tables=True,
        include_formatting=True,
        favor_precision=True,
    )

    if not result:
        print(f"  No content extracted from: {url}")
        return None

    return result


def extract_title(content):
    """Extract the title from trafilatura's YAML frontmatter.

    Args:
        content: Markdown string with YAML frontmatter delimited by '---'

    Returns:
        Title string, or None if not found
    """
    # Require a complete frontmatter block (open + close '---').
    # Trafilatura may emit content without frontmatter when metadata extraction fails.
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]
    match = re.search('title: ', frontmatter)
    if not match:
        return None
    start_pos = match.end()
    end_pos = start_pos + frontmatter[start_pos:].find('\n')
    return frontmatter[start_pos:end_pos]


def derive_filename(content, url):
    """Derive a .md filename from scraped content, falling back to URL path.

    Args:
        content: Scraped markdown content (with YAML frontmatter)
        url: Original URL (used as fallback)

    Returns:
        Filename string ending in .md
    """
    title = extract_title(content)
    if title:
        return f"{slugify(title)}.md"

    # Fallback: use the last segment of the URL path
    path = urlparse(url).path.strip('/').split('/')[-1]
    return f"{slugify(path)}.md"


def save_markdown(content, filename, output_dir):
    """Save content to markdown file in output_dir, creating the dir if needed."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    if filepath.exists():
        print(f"  Warning: overwriting existing {filepath}")
    filepath.write_text(content, encoding="utf-8")
    print(f"  Saved: {filepath}")
    return filepath


def html_to_markdown(url, output_dir):
    """End-to-end: scrape a URL, derive a filename, save markdown.

    Returns:
        Path to the saved .md file, or None on scrape failure.
    """
    content = scrape_url(url)
    if not content:
        return None
    filename = derive_filename(content, url)
    return save_markdown(content, filename, output_dir)


# ---------------------------------------------------------------------------
# PDF -> Markdown (docling)
# ---------------------------------------------------------------------------

def _build_converter():
    """Lazy-import docling and return a fresh DocumentConverter.

    Kept lazy so HTML-only usage doesn't require docling (and its ~2GB
    PyTorch transitive dependency) to be installed.
    """
    from docling.document_converter import DocumentConverter
    return DocumentConverter()


def convert_pdf_to_md(pdf_path, output_path, converter=None):
    """Convert a single PDF file to Markdown format using docling.

    docling handles layout, tables, and figure captions better than text-only
    PDF extractors. For scanned PDFs, enable OCR in docling's pipeline options.

    Args:
        pdf_path: Full path to the source PDF file
        output_path: Full path for the output .md file
        converter: Optional pre-built DocumentConverter. Pass one in for batch
            conversions so docling's models are loaded only once. If omitted,
            a fresh converter is created (fine for one-off use).

    Returns:
        The output path on success, or None on failure
    """
    try:
        converter = converter or _build_converter()
        result = converter.convert(str(pdf_path))
        markdown_text = result.document.export_to_markdown()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            print(f"  Warning: overwriting existing {output_path}")
        output_path.write_text(markdown_text, encoding="utf-8")
        print(f"  Saved: {output_path}")
        return output_path
    except Exception as e:
        print(f"  Failed to convert {pdf_path.name}: {e}")
        return None


def pdf_to_markdown(pdf_path, output_dir, converter=None):
    """End-to-end: convert a PDF and save as markdown in output_dir.

    Pass a pre-built `converter` for batch jobs to avoid reloading docling
    models per file.
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_dir) / f"{slugify(pdf_path.stem)}.md"
    print(f"  Converting: {pdf_path.name} -> {output_path}")
    return convert_pdf_to_md(pdf_path, output_path, converter=converter)


# ---------------------------------------------------------------------------
# Batch entry points
# ---------------------------------------------------------------------------

def process_urls_file(urls_file, output_dir):
    """Read one URL per line from urls_file (# comments ignored) and scrape each."""
    lines = Path(urls_file).read_text().splitlines()
    urls = [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    print(f"Processing {len(urls)} URLs from {urls_file}\n")
    for url in urls:
        print(f"[{url}]")
        html_to_markdown(url, output_dir)
        print()


def process_pdf_dir(pdf_dir, output_dir):
    """Recursively find every PDF under pdf_dir and convert to markdown."""
    pdf_dir = Path(pdf_dir)
    # Case-insensitive match: handles .pdf / .PDF / .Pdf
    pdfs = list(pdf_dir.rglob("*.[pP][dD][fF]"))
    print(f"Found {len(pdfs)} PDFs in {pdf_dir}\n")
    converter = _build_converter() if pdfs else None
    for pdf in pdfs:
        pdf_to_markdown(pdf, output_dir, converter=converter)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--urls-file", help="Text file with one URL per line")
    parser.add_argument("--pdf-dir", help="Directory of PDFs to convert (recursive)")
    parser.add_argument("--output-dir", default="output",
                        help="Where to write .md files (default: ./output)")
    args = parser.parse_args()

    if not args.urls_file and not args.pdf_dir:
        parser.error("Pass --urls-file and/or --pdf-dir")

    if args.urls_file:
        process_urls_file(args.urls_file, args.output_dir)
    if args.pdf_dir:
        process_pdf_dir(args.pdf_dir, args.output_dir)


if __name__ == "__main__":
    main()
