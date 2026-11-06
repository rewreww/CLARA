"""Read reconstructed MIMIC PDFs only. CSVs are never read by this importer.

The worker protocol is one JSON request/response per line. Tables are located
using PDF ruling lines, so a value cannot drift into the next column.
"""
import contextlib
import json
import re
import sys
from pathlib import Path

import fitz

VERSION = "mimic-grid-v1"
CATEGORIES = {
    "Chemistry": "chemistry", "Hematology": "hematology", "Blood_Gas": "blood_gas",
    "Diagnoses": "diagnoses", "Prescriptions": "prescriptions",
    "Medication_Administration": "medication_administration", "Microbiology": "microbiology",
    "Other_Measurements": "measurements", "ICU_Records": "icu_records",
    "Provider_Orders": "orders", "Care_Movements": "care_movements",
    "Procedures": "procedures", "Administrative": "administrative",
}


def key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def field(cells, *names):
    wanted = {key(name) for name in names}
    return next((v for k, v in cells.items() if key(k) in wanted), "")


def number(value):
    # Preserve unavailable text and comparators; never turn an ID into a value.
    text = str(value).strip()
    return float(text) if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text) else None


def timestamp(value):
    match = re.search(r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?\b", str(value))
    return re.sub(r"\s+", "T", match[0]) if match else None


def table_matrix(table):
    matrix = table.extract()
    if not matrix:
        return matrix
    headers = [str(x or '').strip() for x in matrix[0]]
    if all(headers) and len({key(h) for h in headers}) == len(headers):
        return matrix
    # Adjacent grids can move 6 pt at a page break. MuPDF then produces
    # interleaved nonexistent cells and narrow empty outer-margin rectangles.
    # Recover physical cells in each row, never drop a real blank data cell.
    recovered = []
    for values, row in zip(matrix, table.rows):
        cells = []
        for value, rect in zip(values, row.cells):
            if rect is None:
                if value:
                    return matrix
                continue
            if (rect[2] - rect[0] <= 6.1 and not value
                    and (abs(rect[0] - table.bbox[0]) < .1 or abs(rect[2] - table.bbox[2]) < .1)):
                continue
            cells.append(value)
        recovered.append(cells)
    if not recovered or not all(len(row) == len(recovered[0]) for row in recovered):
        return matrix
    return recovered


def extract(path, patient, relative):
    parts = Path(relative.replace("\\", "/")).parts
    admission = next((p[10:] for p in parts if re.fullmatch(r"Admission_\d+", p)), None)
    category = next((CATEGORIES[p] for p in parts if p in CATEGORIES), "overview")
    record_type = next((parts[i + 1] for i, p in enumerate(parts[:-1])
                        if p in CATEGORIES and p not in {"Chemistry", "Hematology", "Blood_Gas"}), "")
    fluid = next((parts[i + 1] for i, p in enumerate(parts[:-1])
                  if p in {"Chemistry", "Hematology", "Blood_Gas"}), None)
    if fluid:
        record_type = "labevents"
    result = {"version": "mimic-grid-v2" if category == "microbiology" else VERSION, "admission": admission, "category": category,
              "record_type": record_type or Path(relative).stem, "fluid": fluid,
              "metadata": {}, "rows": [], "text": "", "pages": 0}
    identified = False
    with fitz.open(path) as pdf:
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDF is unsupported")
        result["pages"] = len(pdf)
        for page_number, page in enumerate(pdf, 1):
            text = page.get_text()
            if "MIMIC-IV" not in text:
                raise ValueError("Not a supported reconstructed MIMIC PDF")
            result["text"] += f"[PDF PAGE {page_number}]\n{text}\n"
            recorded = re.search(r"Recorded:\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)", text)
            default_time = timestamp(recorded[1]) if recorded else None
            with contextlib.redirect_stdout(sys.stderr):
                tables = page.find_tables(strategy="lines").tables
            for table in tables:
                matrix = table_matrix(table)
                if len(matrix) < 2:
                    continue
                headers = [str(x or "").strip() for x in matrix[0]]
                # Reject ambiguous grids rather than quietly overwriting cells.
                if any(not h for h in headers) or len({key(h) for h in headers}) != len(headers):
                    raise ValueError(f"Ambiguous table headers on page {page_number}")
                for values in matrix[1:]:
                    cells = {h: str(v or "").strip() for h, v in zip(headers, values)}
                    if not any(cells.values()):
                        continue
                    if all(key(cells[h]) == key(h) for h in headers):
                        continue  # repeated table header
                    subject = field(cells, "Patient identifier")
                    if subject:
                        if subject != patient.removeprefix("Patient_"):
                            raise ValueError("PDF patient identifier does not match its folder")
                        found_admission = field(cells, "Hospital admission identifier")
                        if admission and found_admission != admission:
                            raise ValueError("PDF admission identifier does not match its folder")
                        identified = True
                        result["metadata"].update(cells)
                        continue
                    if any(key(h) == "admissiondateandtimetype" for h in headers):
                        result["metadata"].setdefault("Admission details", []).append(cells)
                        continue
                    if (record_type == "microbiologyevents" and page_number > 1
                            and table.bbox[1] < 100 and values is matrix[1]
                            and not field(cells, "Recorded date and time")
                            and not field(cells, "Microbiology specimen identifier")
                            and not field(cells, "Test name")
                            and result["rows"]):
                        previous = result["rows"][-1]
                        # Only the first fragment of the next page can extend
                        # the previous record. Keep both page numbers visible.
                        if previous["page"] == page_number - 1 and all(h in previous["cells"] for h in headers):
                            for h, fragment in cells.items():
                                if fragment:
                                    previous["cells"][h] += "\n" + fragment
                            previous["cells"]["PDF continuation pages"] = f"{previous['page']}, {page_number}"
                            continue
                        raise ValueError(f"Unmatched microbiology continuation on page {page_number}")
                    label = field(cells, "Test", "Test name", "Measurement", "Medication", "Recorded diagnosis or procedure description", "Observation", "Observation or item name", "Order detail name", "Description")
                    label = label or next(iter(cells.values()), "")
                    observed = next((timestamp(v) for k, v in cells.items()
                                     if key(k) in {"recordeddateandtime", "chartdateandtime", "startdateandtime", "dateandtime", "charttime", "recordedtime", "date", "recordeddate", "linkedorderdateandtime", "entrydateandtime", "orderdateandtime", "administrationdateandtime", "administrationeventdateandtime", "servicetransferdateandtime", "transferdateandtime"}
                                     and timestamp(v)), default_time)
                    value = field(cells, "Result", "Value", "Recorded value", "Recorded result")
                    unit = field(cells, "Unit", "Units", "Recorded unit")
                    refs = re.split(r"\s+to\s+", field(cells, "Reference range"))
                    low, high = (number(refs[0]), number(refs[1])) if len(refs) == 2 else (None, None)
                    numeric = number(value)
                    source_flag = field(cells, "Recorded flag")
                    flag = ("low" if numeric < low else None) if numeric is not None and low is not None else None
                    if numeric is not None and high is not None and numeric > high:
                        flag = "high"
                    result["rows"].append({"page": page_number, "row": len(result["rows"]) + 1,
                        "cells": cells, "label": label, "observed_at": observed,
                        "value": value, "numeric": numeric, "unit": unit,
                        "reference_low": low, "reference_high": high, "source_flag": source_flag,
                        "flag": flag})
    if not identified or not result["text"].strip():
        raise ValueError("No verifiable patient metadata found in PDF")
    return result


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            answer = extract(request["path"], request["patient"], request["relative"])
        except Exception as exc:
            answer = {"error": str(exc)}
        print(json.dumps(answer, ensure_ascii=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
