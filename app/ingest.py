"""Ingest module: read source files and yield (location, text) units."""
import csv
import os
import re


def read_source(path: str):
    """Yield (location, text, metadata) tuples from a file.

    location format:
      - xlsx: "SheetName/R{row}/C{col}"
      - csv:  "R{row}/C{col}"
      - txt (WhatsApp): "line {n}"

    metadata is a dict with optional keys: header, sender, row, col.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        yield from _read_xlsx(path)
    elif ext == ".csv":
        yield from _read_csv(path)
    elif ext == ".txt":
        yield from _read_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _read_xlsx(path: str):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        headers = []
        for row_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
            if row_idx == 1:
                headers = [cell.value or "" for cell in row]
                continue
            for col_idx, cell in enumerate(row, start=1):
                val = cell.value
                if val is None:
                    continue
                text = str(val).strip()
                if not text:
                    continue
                header = headers[col_idx - 1] if col_idx - 1 < len(headers) else ""
                location = f"{ws.title}/R{row_idx}/C{col_idx}"
                yield location, text, {"header": str(header), "row": row_idx, "col": col_idx}
    wb.close()


def _read_csv(path: str):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = []
        for row_idx, row in enumerate(reader, start=1):
            if row_idx == 1:
                headers = row
                continue
            for col_idx, val in enumerate(row, start=1):
                text = val.strip()
                if not text:
                    continue
                header = headers[col_idx - 1] if col_idx - 1 < len(headers) else ""
                location = f"R{row_idx}/C{col_idx}"
                yield location, text, {"header": str(header), "row": row_idx, "col": col_idx}


# WhatsApp Android export format: "dd/mm/yy, h:mm am - Sender: message"
_WA_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(.+?):\s*(.+)$",
    re.IGNORECASE,
)


def _read_txt(path: str):
    with open(path, encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n\r")
            if not line:
                continue
            m = _WA_RE.match(line)
            if m:
                sender = m.group(2).strip()
                message = m.group(3).strip()
                location = f"line {line_num}"
                yield location, line, {"sender": sender, "message": message}
            else:
                # System message or continuation
                location = f"line {line_num}"
                yield location, line, {}
