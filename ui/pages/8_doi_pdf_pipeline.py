# Version: 3.2.4
"""
Article Finder v3.2 - DOI/PDF Pipeline
Separated metadata extraction, open-access retrieval, deduplication, and ZIP fallback.
"""

from pathlib import Path
import queue
import sys
import tempfile
import threading
import time

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.loader import get
from core.database import Database
from ingest.doi_pdf_ingestion import DOIPDFIngestionPipeline, doi_to_filename_stem, parse_dois


st.set_page_config(page_title="DOI/PDF Pipeline - Article Finder", layout="wide")


@st.cache_resource
def get_database():
    db_path = get("paths.database", "data/article_finder.db")
    return Database(Path(db_path))


def make_pipeline(api_key: str, unpaywall_email: str, max_workers: int) -> DOIPDFIngestionPipeline:
    return DOIPDFIngestionPipeline(
        database=get_database(),
        semantic_scholar_api_key=api_key.strip() or None,
        unpaywall_email=unpaywall_email.strip() or get("apis.unpaywall.email"),
        pdf_dir=Path(get("paths.pdfs", "data/pdfs")),
        max_workers=max_workers,
    )


def render_status_table(rows):
    if not rows:
        st.info("Submit a DOI batch to start processing.")
        return
    df = pd.DataFrame(rows)
    status_order = {
        "Pending": 0,
        "Metadata Extracted": 1,
        "PDF Downloaded": 2,
        "PDF Failed": 3,
        "Manual ZIP Uploaded": 4,
    }
    df["_order"] = df["Status"].map(status_order).fillna(99)
    df = df.sort_values(["_order", "DOI"]).drop(columns=["_order"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def refresh_failed_records(db: Database):
    papers = db.search_papers(limit=10000)
    failed = [
        {
            "DOI": p.get("doi"),
            "Expected PDF Filename": f"{doi_to_filename_stem(p.get('doi'))}.pdf" if p.get("doi") else "",
            "Citation": (p.get("citation") or p.get("title") or "")[:160],
            "Provenance": p.get("pdf_source") or "Metadata Only",
        }
        for p in papers
        if p.get("doi") and not p.get("pdf_path")
    ]
    return failed


def main():
    st.title("DOI/PDF Ingestion Pipeline")
    st.caption("Metadata is captured independently from PDF retrieval, so paywalls do not break paper records.")

    db = get_database()

    if "doi_pdf_status_rows" not in st.session_state:
        st.session_state.doi_pdf_status_rows = []

    config_panel, dashboard = st.columns([1, 2])

    with config_panel:
        st.subheader("API Configuration")
        semantic_key = st.text_input(
            "Semantic Scholar API Key",
            type="password",
            value="",
            help="Sent as x-api-key to Semantic Scholar for higher rate limits.",
        )
        unpaywall_email = st.text_input(
            "Unpaywall Email",
            value=get("apis.unpaywall.email", "your-email@example.com"),
            help="Required by Unpaywall.",
        )
        max_workers = st.slider("Concurrent DOI Workers", min_value=1, max_value=8, value=4)

    with dashboard:
        st.subheader("Processing Dashboard")
        render_status_table(st.session_state.doi_pdf_status_rows)

    st.divider()

    tab_ingest, tab_fallback, tab_failed = st.tabs(["DOI Batch", "ZIP Fallback", "Failed PDFs"])

    with tab_ingest:
        st.subheader("Ingestion Input")
        doi_text = st.text_area(
            "Single DOI or comma-separated DOI list",
            height=140,
            placeholder="10.1038/s41586-020-2649-2, 10.1145/1234567.8901234",
        )
        dois = parse_dois(doi_text)
        st.write(f"Detected {len(dois)} valid DOI(s).")

        if dois:
            preview = pd.DataFrame(
                [{"DOI": doi, "Expected ZIP Fallback Filename": f"{doi_to_filename_stem(doi)}.pdf"} for doi in dois]
            )
            st.dataframe(preview, use_container_width=True, hide_index=True)

        if st.button("Run DOI/PDF Pipeline", type="primary", disabled=not dois):
            pipeline = make_pipeline(semantic_key, unpaywall_email, max_workers)
            status_slot = st.empty()
            status_map = {doi: "Pending" for doi in dois}
            event_queue = queue.Queue()
            result_holder = {"results": None, "error": None, "done": False}

            def update_status(event):
                event_queue.put(event)

            def run_worker():
                try:
                    result_holder["results"] = pipeline.ingest_batch(dois, status_callback=update_status)
                except Exception as exc:
                    result_holder["error"] = exc
                finally:
                    result_holder["done"] = True

            worker = threading.Thread(target=run_worker, daemon=True)
            worker.start()

            with st.spinner("Processing DOI batch..."):
                while not result_holder["done"] or not event_queue.empty():
                    while not event_queue.empty():
                        event = event_queue.get()
                        status_map[event["doi"]] = event["status"]
                    st.session_state.doi_pdf_status_rows = [
                        {"DOI": doi, "Status": status_map.get(doi, "Pending")} for doi in dois
                    ]
                    with status_slot.container():
                        render_status_table(st.session_state.doi_pdf_status_rows)
                    time.sleep(0.2)

            if result_holder["error"]:
                st.error(f"DOI batch failed: {result_holder['error']}")
                return

            for event in list(event_queue.queue):
                status_map[event["doi"]] = event["status"]
            results = result_holder["results"] or []

            rows = []
            for result in results:
                rows.append(
                    {
                        "DOI": result.doi,
                        "Status": result.status,
                        "Record": "Created" if result.created else "Updated",
                        "Citation": "yes" if result.metadata.citation else "no",
                        "Abstract": "yes" if result.metadata.abstract else "no",
                        "Article Type": result.metadata.article_type or "",
                        "Topic": result.metadata.topic or "",
                        "PDF": result.pdf.path or "",
                        "Provenance": result.pdf.provenance,
                        "Errors": "; ".join(result.metadata.errors + ([result.pdf.error] if result.pdf.error else [])),
                    }
                )
            st.success("DOI batch complete.")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_fallback:
        st.subheader("Manual ZIP Upload")
        st.caption("Rename each PDF to its DOI with slashes replaced by underscores, then upload the ZIP.")
        zip_file = st.file_uploader("ZIP file containing DOI-named PDFs", type=["zip"])

        if zip_file and st.button("Process ZIP Fallback", type="primary"):
            pipeline = make_pipeline(semantic_key, unpaywall_email, max_workers)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp.write(zip_file.getvalue())
                tmp_path = Path(tmp.name)

            with st.spinner("Matching PDFs to failed DOI records..."):
                stats = pipeline.process_manual_zip(tmp_path)

            try:
                tmp_path.unlink()
            except Exception:
                pass

            col1, col2, col3 = st.columns(3)
            col1.metric("PDFs in ZIP", stats.get("total_pdfs", 0))
            col2.metric("Records Updated", stats.get("updated", 0))
            col3.metric("Unmatched", len(stats.get("unmatched", [])))

            if stats.get("unmatched"):
                st.warning("Some PDF filenames did not match an existing DOI record.")
                st.dataframe(pd.DataFrame({"Unmatched File": stats["unmatched"]}), use_container_width=True, hide_index=True)
            if stats.get("errors"):
                st.error("ZIP fallback had errors.")
                for error in stats["errors"]:
                    st.write(error)

    with tab_failed:
        st.subheader("PDFs Needing Manual Retrieval")
        failed = refresh_failed_records(db)
        if failed:
            st.dataframe(pd.DataFrame(failed), use_container_width=True, hide_index=True)
        else:
            st.success("No DOI records are currently missing PDFs.")


if __name__ == "__main__":
    main()
