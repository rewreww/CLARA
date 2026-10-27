"""Stage and verify name-only redactions before replacing local patient PDFs.

Originals and the name dictionary are private local files under .clara/ (gitignored).
This is NOT complete de-identification: dates, identifiers and clinical content remain.
Only text PDFs with recognizable name labels are supported; unsupported files fail closed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil

import fitz

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".clara" / "name-redaction"
PATIENT_NAME = re.compile(
    r"\b(?:patient['’]?s\s+)?name\s*:\s*(.*?)"
    r"(?=\b(?:date\s+requested|date\s+rendered|age|gender|sex)\s*:)", re.I | re.S)
STAFF_NAME = re.compile(
    r"\b(?:physician|referral\s+doctor/s)\s*:\s*(.*?)"
    r"(?=\b(?:referral\s+doctor/s|date\s+(?:admitted|released)|clinical|hematology|condition)\b)", re.I | re.S)
SIGNATORY = re.compile(r"(?m)^\s*([A-Z][A-Z .,'-]+,\s*(?:RMT|MD\.?)(?:,\s*FPSP)?)\s*$")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names_in(text):
    found = set()
    patients = list(PATIENT_NAME.finditer(text))
    for match in patients + list(STAFF_NAME.finditer(text)) + list(SIGNATORY.finditer(text)):
        name = " ".join(match.group(1).split()).strip()
        if not name or name.upper() in {"DR.", "DR"}:
            continue
        # A malformed source sometimes contains ward information in a physician field.
        if re.search(r"\d|\b(?:WARD|ROOM)\b", name, re.I):
            continue
        if len(name) > 100:
            raise ValueError("Unrecognized name-field boundary; manual review required")
        found.add(name)
    return found, bool(patients)


def tokens(text):
    return Counter(re.findall(r"\w+|[^\w\s]", text, re.UNICODE))


def stage(source, work=WORK):
    source = source.resolve(strict=True)
    work = work.resolve()
    if work == source or source in work.parents or work in source.parents:
        raise ValueError("Staging directory must be outside the patient source tree")
    files = sorted(source.rglob("*.pdf"))
    if not files:
        raise ValueError("No PDFs found")
    if (work / "manifest.json").exists():
        raise ValueError("A staged run already exists; use a new --work directory")
    names = set()
    for path in files:
        with fitz.open(path) as doc:
            text = "\n".join(page.get_text() for page in doc)
            discovered, has_patient = names_in(text)
            if not has_patient:
                raise ValueError(f"No recognizable patient name field: {path.relative_to(source)}")
            names.update(discovered)
    # Longest phrases first avoids overlapping a shorter variant of the same name.
    names = sorted(names, key=lambda value: (-len(value), value))
    work.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in files:
        relative = path.relative_to(source)
        output = work / "staged" / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(path) as doc:
            original_pages = len(doc)
            expected = []
            for page in doc:
                before = page.get_text()
                selected = []
                expected_text = before
                for name in names:
                    pattern = r"\s+".join(re.escape(part) for part in name.split())
                    matches = list(re.finditer(pattern, expected_text, re.I))
                    if not matches:
                        continue
                    rectangles = page.search_for(name)
                    if not rectangles:
                        raise ValueError(f"Cannot locate name on page: {relative}")
                    for rect in rectangles:
                        # Shrink vertically to avoid adjacent lines' overlapping font boxes.
                        rect.y0 += rect.height * .15
                        rect.y1 -= rect.height * .15
                        if not any(existing.intersects(rect) for existing in selected):
                            selected.append(rect)
                    expected_text = re.sub(pattern, "", expected_text, flags=re.I)
                expected.append(tokens(expected_text))
                for rect in selected:
                    page.add_redact_annot(rect, fill=(.92, .92, .92))
                if selected:
                    page.apply_redactions(images=2, graphics=0)
            doc.set_metadata({})
            doc.del_xml_metadata()
            for name in list(doc.embfile_names()):
                doc.embfile_del(name)
            # Remove metadata-only name references without changing document destinations.
            toc = doc.get_toc()
            if toc:
                for item in toc:
                    for name in names:
                        item[1] = re.sub(re.escape(name), "[name removed]", item[1], flags=re.I)
                doc.set_toc(toc)
            doc.save(output, garbage=4, deflate=True)
        with fitz.open(output) as redacted:
            if len(redacted) != original_pages:
                raise ValueError("Page count changed")
            for index, page in enumerate(redacted):
                if tokens(page.get_text()) != expected[index]:
                    lost = expected[index] - tokens(page.get_text())
                    extra = tokens(page.get_text()) - expected[index]
                    raise ValueError(f"Non-name text changed in {relative}, page {index + 1}: lost={dict(lost)}, extra={dict(extra)}")
        entries.append({"path": relative.as_posix(), "before": digest(path), "after": digest(output), "pages": original_pages})
    # Private dictionary supports sanitizing pre-existing browser conversation history.
    name_tokens = sorted({word for name in names for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", name)
                          if word.upper() not in {"RMT", "FPSP"}})
    (work / "names.json").write_text(json.dumps({"names": names, "tokens": name_tokens}, indent=2), encoding="utf-8")
    manifest = {"source": str(source), "files": entries, "name_count": len(names)}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"files": len(entries), "pages": sum(e["pages"] for e in entries), "name_variants": len(names), "non_name_text_preserved": True}


def apply(work=WORK):
    work = work.resolve(strict=True)
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    source = Path(manifest["source"]).resolve(strict=True)
    checked = []
    for entry in manifest["files"]:
        target = (source / entry["path"]).resolve(strict=True)
        staged = (work / "staged" / entry["path"]).resolve(strict=True)
        backup = (work / "originals" / entry["path"]).resolve()
        if not target.is_relative_to(source) or not staged.is_relative_to(work / "staged") or not backup.is_relative_to(work / "originals"):
            raise ValueError("Manifest path escapes expected directory")
        if digest(target) not in {entry["before"], entry["after"]} or digest(staged) != entry["after"]:
            raise ValueError("Source or staged PDF changed since verification")
        checked.append((entry, target, staged, backup))
    for entry, target, staged, backup in checked:
        if digest(target) == entry["after"]:
            continue
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists() and digest(backup) != entry["before"]:
            raise ValueError("Existing backup does not match original")
        if not backup.exists():
            shutil.copy2(target, backup)
        shutil.copyfile(staged, target)
    return {"files_applied": len(checked), "originals_preserved": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["stage", "apply"])
    parser.add_argument("--source", type=Path, default=Path.home() / "Desktop" / "Patients")
    parser.add_argument("--work", type=Path, default=WORK)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.work) if args.command == "stage" else apply(args.work)))
