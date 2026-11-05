"""Read the PDF with Docling and keep what it saw, untouched, as raw JSON.

Separating this step lets the cleaning run and be tested without Docling, which weighs
several GB.
"""

import json
from pathlib import Path

from docling.document_converter import DocumentConverter


def extract_raw(pdf_path: Path, raw_path: Path) -> None:
    document = DocumentConverter().convert(pdf_path).document

    tables = []
    for index, table in enumerate(document.tables):
        frame = table.export_to_dataframe(doc=document)
        tables.append({
            "index": index,
            "page": table.prov[0].page_no,
            "rows": [[str(cell) for cell in row] for row in frame.values.tolist()],
        })

    page_texts: dict[int, list[str]] = {}
    for item in document.texts:
        if item.prov:
            page_texts.setdefault(item.prov[0].page_no, []).append(item.text)

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps({"tables": tables, "page_texts": page_texts}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
