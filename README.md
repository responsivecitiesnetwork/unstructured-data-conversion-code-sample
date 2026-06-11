# unstructured-data-conversion-code-sample

**Author:** Judah Axelrod | Urban Institute | jaxelrod@urban.org

---

Convert HTML pages and PDFs to clean Markdown for RAG / knowledge-base ingestion.

- HTML → Markdown via [trafilatura](https://trafilatura.readthedocs.io/)
- PDF  → Markdown via [docling](https://github.com/DS4SD/docling)

## Requirements

- Python 3.9+
- Install dependencies:

```bash
pip install -r requirements.txt
```

### HTML-only install

If you only need HTML -> Markdown (no PDFs), you can skip docling entirely:

```bash
pip install "trafilatura>=2.0,<3"
```

### A note on docling's footprint

docling pulls in PyTorch as a dependency, which adds roughly **2 GB**
to your environment. On first PDF conversion it will also download layout/OCR
model weights (cached under `~/.cache/docling/`), which can take a few minutes
on a fresh machine.

## Usage

```bash
python preprocess.py \
  --urls-file examples/urls.example.txt \
  --pdf-dir   examples/ \
  --output-dir examples/output/
```

Either `--urls-file` or `--pdf-dir` (or both) is required. `--output-dir` defaults to `./output`.

- `--urls-file` is a plain text file with one URL per line (`#` for comments).
- `--pdf-dir` is searched recursively for `*.pdf` (case-insensitive).

## Examples

`examples/` contains a sample URL you can convert with `trafilatura` and a sample one-page PDF you can convert with `docling` by running the `preprocess.py` script.
