"""Contain native PDF engine failures and preserve access to printable reports."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from flask import current_app, make_response, request
from werkzeug.utils import secure_filename


class PDFRenderError(RuntimeError):
    pass


def render_pdf(html, base_url):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.pdf_worker"],
            cwd=str(Path(__file__).resolve().parent.parent),
            input=json.dumps({"html": html, "base_url": base_url}).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PDFRenderError("PDF renderer could not finish.") from exc
    if result.returncode or not result.stdout.startswith(b"%PDF-"):
        raise PDFRenderError(f"PDF renderer exited without a PDF (code {result.returncode}).")
    return result.stdout


def pdf_response(html, filename):
    try:
        pdf = render_pdf(html, request.host_url)
    except PDFRenderError as exc:
        current_app.logger.error("%s", exc)
        banner = '<div class="pdf-print-notice" style="padding:16px;background:#fff3cd;color:#332701">PDF download is unavailable. Use your browser to print or save this report as PDF. <button type="button" onclick="window.print()">Print / Save as PDF</button></div><style>@media print{.pdf-print-notice{display:none!important}}</style>'
        printable, count = re.subn(r"(<body\b[^>]*>)", lambda match: match.group(1) + banner, html, count=1, flags=re.IGNORECASE)
        response = make_response(printable if count else banner + html)
        response.headers["X-PDF-Fallback"] = "printable-html"
        response.headers["Cache-Control"] = "no-store"
        return response
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{secure_filename(filename) or "report.pdf"}"'
    response.headers["Cache-Control"] = "no-store"
    return response
