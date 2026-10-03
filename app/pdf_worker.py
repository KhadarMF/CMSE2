"""Render one PDF in an isolated process without creating an ERP application."""
import json
import os
import sys


def main():
    if os.name == "nt":
        import ctypes
        # A broken native DLL must exit rather than open a Windows crash dialog.
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
    from weasyprint import HTML
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    pdf = HTML(string=payload["html"], base_url=payload["base_url"]).write_pdf()
    sys.stdout.buffer.write(pdf)


if __name__ == "__main__":
    main()
