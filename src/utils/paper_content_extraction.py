"""Port of AIScientist's `analysis/contribution_dimension/prepare_paper_content.py`.

Takes a paper PDF, runs it through GROBID (must be running -- see
`GROBID_config.json`, default `http://localhost:8070`), and extracts every
section except Results/Discussion/Conclusion/Findings (matched by heading
keyword, case-insensitive substring) -- keeping title, abstract, and
everything else (introduction, method, related work, appendix, etc.) as-is.
Falls back to plain PyPDF2 text extraction if GROBID processing fails.

Logic (`extract_sections_from_grobid_xml`, `extract_text_from_pdf`) is kept
line-for-line identical to the source script; only the batch/CLI/threading
scaffolding around it is dropped, since we're processing 4 known PDFs, not a
directory of arbitrary ones.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import PyPDF2
from grobid_client.grobid_client import GrobidClient


def extract_text_from_pdf(pdf_path: str) -> str | None:
    """Extract text from a PDF file using PyPDF2."""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return None


def extract_sections_from_grobid_xml(xml_content: str) -> str | None:
    """
    Extract all sections from GROBID XML except results and conclusion sections.
    Returns the extracted text or None if extraction fails.
    """
    try:
        root = ET.fromstring(xml_content)
        namespaces = {"tei": "http://www.tei-c.org/ns/1.0"}
        sections = []

        title_elem = root.find('.//tei:titleStmt/tei:title[@type="main"]', namespaces)
        if title_elem is not None and title_elem.text:
            sections.append(f"Title: {title_elem.text.strip()}")

        abstract_elem = root.find(".//tei:abstract", namespaces)
        if abstract_elem is not None:
            abstract_text = "".join(abstract_elem.itertext()).strip()
            if abstract_text:
                sections.append(f"Abstract: {abstract_text}")

        body_elem = root.find(".//tei:body", namespaces)
        if body_elem is not None:
            divs = body_elem.findall(".//tei:div", namespaces)
            for div in divs:
                head_elem = div.find("./tei:head", namespaces)
                if head_elem is not None:
                    section_title = head_elem.text.strip() if head_elem.text else ""
                    section_title_lower = section_title.lower()
                    if any(
                        keyword in section_title_lower
                        for keyword in ["result", "conclusion", "discussion", "findings"]
                    ):
                        continue

                    section_content = []
                    for elem in div:
                        if elem.tag.endswith("p"):
                            paragraph_text = "".join(elem.itertext()).strip()
                            if paragraph_text:
                                section_content.append(paragraph_text)

                    if section_content:
                        section_text = f"\n{section_title}:\n" + "\n\n".join(section_content)
                        sections.append(section_text)

        return "\n\n".join(sections) if sections else None

    except Exception as e:
        print(f"Error parsing GROBID XML: {e}")
        return None


def process_pdf_with_grobid(pdf_path: str, client: GrobidClient, output_dir: str) -> dict:
    """Process a single PDF with GROBID, extract sections excluding results/conclusion,
    write the result to `output_dir`, return a status dict."""
    pdf_filename = os.path.basename(pdf_path)
    pdf_name = os.path.splitext(pdf_filename)[0]
    xml_output_path = os.path.join(output_dir, f"{pdf_name}.grobid.tei.xml")
    txt_output_path = os.path.join(output_dir, f"{pdf_name}.txt")

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(xml_output_path):
        temp_dir = os.path.join(output_dir, f"temp_grobid_{pdf_name}")
        os.makedirs(temp_dir, exist_ok=True)
        temp_pdf_path = os.path.join(temp_dir, pdf_filename)
        import shutil

        shutil.copy2(pdf_path, temp_pdf_path)

        client.process("processFulltextDocument", temp_dir, n=1)

        import glob

        temp_xml_files = glob.glob(os.path.join(temp_dir, "*.grobid.tei.xml"))
        if temp_xml_files:
            shutil.move(temp_xml_files[0], xml_output_path)
            os.remove(temp_pdf_path)
        else:
            print(f"GROBID failed for {pdf_filename}, falling back to PyPDF2")
            fallback_text = extract_text_from_pdf(pdf_path)
            if fallback_text:
                with open(txt_output_path, "w", encoding="utf-8") as f:
                    f.write(fallback_text)
                return {"pdf_file": pdf_filename, "txt_file": f"{pdf_name}.txt", "method": "pypdf2_fallback", "success": True}
            return {"pdf_file": pdf_filename, "success": False, "error": "Both GROBID and PyPDF2 extraction failed"}

    with open(xml_output_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    extracted_text = extract_sections_from_grobid_xml(xml_content)
    if extracted_text:
        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        return {"pdf_file": pdf_filename, "txt_file": f"{pdf_name}.txt", "method": "grobid", "success": True}

    print(f"XML parsing failed for {pdf_filename}, falling back to PyPDF2")
    fallback_text = extract_text_from_pdf(pdf_path)
    if fallback_text:
        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(fallback_text)
        return {"pdf_file": pdf_filename, "txt_file": f"{pdf_name}.txt", "method": "pypdf2_fallback", "success": True}
    return {"pdf_file": pdf_filename, "success": False, "error": "Both GROBID XML parsing and PyPDF2 extraction failed"}


if __name__ == "__main__":
    import sys

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(pdf_path)
    grobid_config = sys.argv[3] if len(sys.argv) > 3 else "GROBID_config.json"

    client = GrobidClient(config_path=grobid_config)
    result = process_pdf_with_grobid(pdf_path, client, output_dir)
    print(result)
