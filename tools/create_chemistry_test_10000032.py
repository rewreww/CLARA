"""Create and verify a clearly synthetic chemistry PDF for EXISTING MIMIC-IV patient 10000032.

Requires PyMuPDF (fitz) from CLARA's .venv.
Run from the project root:
    .\\.venv\\Scripts\\python.exe tools\\create_chemistry_test_10000032.py

Only use in a disposable/demo database. Never treat the invented values as real observations.
"""
import argparse
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import fitz

PATIENT = "Patient_10000032"
BASE = Path(__file__).resolve().parents[1]


def find_admission(patient_dir, requested):
    choices = sorted(d for d in patient_dir.iterdir()
                     if d.is_dir() and re.fullmatch(r"Admission_\d{8}", d.name))
    if requested:
        target = patient_dir / f"Admission_{requested}"
        if target not in choices:
            raise SystemExit(f"Admission_{requested} not found under {patient_dir}")
        return target
    if not choices:
        raise SystemExit("No admission folders found for existing patient 10000032.")
    if len(choices) == 1:
        print(f"Using existing {choices[0].name}")
        return choices[0]
    print("Choose an EXISTING admission for patient 10000032:")
    for i, folder in enumerate(choices, 1):
        print(f"{i}. {folder.name}")
    selected = input(f"Admission number 1-{len(choices)} (blank to cancel): ").strip()
    if not selected.isdigit() or not 1 <= int(selected) <= len(choices):
        raise SystemExit("Cancelled; nothing was created.")
    return choices[int(selected) - 1]


def draw_table(page, top, widths, rows, row_height):
    x0 = 39
    for r, cells in enumerate(rows):
        x = x0
        for width, text in zip(widths, cells):
            box = fitz.Rect(x, top + r * row_height, x + width, top + (r + 1) * row_height)
            page.draw_rect(box, color=(.24, .42, .57),
                           fill=(.87, .94, .98) if r == 0 else (1, 1, 1), width=.8)
            page.insert_textbox(fitz.Rect(x + 3, box.y0 + 5, x + width - 3, box.y1 - 2),
                                str(text), fontsize=8.1 if r == 0 else 8.7,
                                fontname="hebo" if r == 0 else "helv", color=(.07, .18, .30))
            x += width


def make_pdf(path, admission, recorded):
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(34, 32, 561, 87), color=(.06, .16, .30), fill=(.06, .16, .30))
    page.insert_text((46, 55), "MIMIC-IV | SYNTHETIC CHEMISTRY IMPORT TEST",
                     fontsize=13.0, fontname="hebo", color=(1, 1, 1))
    page.insert_text((46, 73), "DEMO ONLY - INVENTED RESULTS - NOT AN ORIGINAL MIMIC-IV RECORD",
                     fontsize=8, color=(1, .87, .45))
    page.insert_text((40, 108), f"Recorded: {recorded}", fontsize=10)
    draw_table(page, 131, [248, 270], [
        ["Patient identifier", "Hospital admission identifier"],
        ["10000032", admission]], 30)
    page.insert_text((40, 216), "Chemistry - Blood | SYNTHETIC TEST DATA", fontsize=10.4, fontname="hebo")
    draw_table(page, 228, [140, 80, 55, 105, 138], [
        ["Test", "Result", "Unit", "Reference range", "Recorded date and time"],
        ["Glucose", "158", "mg/dL", "70 to 99", recorded],
        ["Sodium", "141", "mmol/L", "135 to 145", recorded],
        ["Potassium", "3.1", "mmol/L", "3.5 to 5.1", recorded],
        ["Creatinine", "0.9", "mg/dL", "0.6 to 1.3", recorded]], 34)
    page.insert_textbox(fitz.Rect(40, 450, 556, 520),
        "RESEARCH DEMONSTRATION ONLY. Values are synthetic. Do not use for care, "
        "patient assessment, clinical conclusions or final thesis results. "
        "Delete this PDF after testing and allow CLARA to resynchronize.",
        fontsize=9, color=(.46, .16, .12))
    pdf.set_metadata({"title": "Synthetic chemistry ingestion test for Patient_10000032"})
    pdf.save(str(path), garbage=4, deflate=True)
    pdf.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.home() / "Desktop" / "MIMIC_100_Patients")
    ap.add_argument("--admission", help="Existing 8-digit admission ID, optional")
    ap.add_argument("--recorded", help="Synthetic timestamp YYYY-MM-DD HH:MM:SS")
    args = ap.parse_args()
    root = args.root.expanduser().resolve()
    patient_dir = root / PATIENT
    if not patient_dir.is_dir():
        raise SystemExit(f"Existing patient folder not found: {patient_dir}")
    admission_dir = find_admission(patient_dir, args.admission)
    if not any(admission_dir.rglob("*.pdf")):
        raise SystemExit("No original PDFs found in this admission. Refusing to create test data.")
    adm = admission_dir.name.removeprefix("Admission_")
    if args.recorded:
        recorded = args.recorded
        datetime.strptime(recorded, "%Y-%m-%d %H:%M:%S")
    else:
        recorded = None
        # Derive a plausible demo timestamp from an EXISTING PDF without changing originals.
        for source in admission_dir.rglob("*.pdf"):
            try:
                with fitz.open(str(source)) as existing:
                    for p in existing:
                        hit = re.search(r"Recorded:\s*(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?)", p.get_text())
                        if hit:
                            recorded = hit.group(1)
                            if len(recorded) == 10:
                                recorded += " 09:00:00"
                            break
                if recorded:
                    break
            except (OSError, ValueError, RuntimeError):
                continue
        if not recorded:
            raise SystemExit("No existing PDF Recorded date found. Use --recorded 'YYYY-MM-DD HH:MM:SS'.")
    target_dir = admission_dir / "Chemistry" / "Blood"
    relative = str((target_dir / "CLARA_SYNTHETIC_CHEMISTRY_TEST.pdf").relative_to(patient_dir)).replace("\\", "/")
    parser_file = BASE / "ai-services" / "mimic_pdf.py"
    spec = importlib.util.spec_from_file_location("clara_mimic_pdf", parser_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory() as tempdir:
        temp = Path(tempdir) / "chemistry-validation.pdf"
        make_pdf(temp, adm, recorded)
        # Exact parser CLARA uses in production. Check identifiers, classification and lab rows.
        parsed = module.extract(str(temp), PATIENT, relative)
        if parsed["admission"] != adm or parsed["category"] != "chemistry":
            raise SystemExit("Parser verification failed: patient admission/category mismatch.")
        tests = {r["label"]: r for r in parsed["rows"]}
        if set(tests) != {"Glucose", "Sodium", "Potassium", "Creatinine"}:
            raise SystemExit(f"Parser verification failed: unexpected rows {list(tests)}")
        if tests["Glucose"]["flag"] != "high" or tests["Potassium"]["flag"] != "low":
            raise SystemExit("Parser verification failed: high/low flags were not recognized.")
        target_dir.mkdir(parents=True, exist_ok=True)
        final = target_dir / f"CLARA_SYNTHETIC_CHEMISTRY_TEST_{datetime.now():%Y%m%d_%H%M%S_%f}.pdf"
        if final.exists():
            raise SystemExit("Refusing to overwrite existing document.")
        # Copy only after parser validation; atomic rename triggers the watcher.
        staging = target_dir / (final.name + ".tmp")
        try:
            staging.write_bytes(temp.read_bytes())
            os.replace(staging, final)
        finally:
            staging.unlink(missing_ok=True)
    print(f"VALIDATED {len(parsed['rows'])} chemistry rows for {PATIENT} / {adm}.")
    print(f"Added SYNTHETIC test PDF: {final}")
    print("Check the CLARA sync logs for successful ingestion and a new-lab notification.")
    print("IMPORTANT: Remove this demo PDF and re-sync before using patient data for research.")


if __name__ == "__main__":
    main()
