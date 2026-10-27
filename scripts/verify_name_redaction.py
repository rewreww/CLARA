"""Check the running local CLARA APIs and PDF downloads without printing records."""
import json
from pathlib import Path
import re
import hashlib
import requests

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".clara/name-redaction"


def verify():
    dictionary = json.loads((WORK / "names.json").read_text(encoding="utf-8"))
    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, dictionary["tokens"])) + r")\b", re.I)
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    session = requests.Session()
    session.trust_env = False
    base = "http://127.0.0.1:5000/api"
    checks = 0

    def data(method, path, **kwargs):
        nonlocal checks
        response = session.request(method, base + path, timeout=30, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if pattern.search(json.dumps(payload)):
            raise AssertionError("Known name remains in " + path)
        checks += 1
        return payload

    patients = data("GET", "/patientdata/patients")["patients"]
    expected_ids = {entry["path"].split("/")[0] for entry in manifest["files"]}
    assert {patient["id"] for patient in patients} == expected_ids
    for patient in patients:
        pid = patient["id"]
        assert patient["name"] == f"Patient {pid}"
        for kind in ("chemistry", "hematology", "microscopy"):
            data("POST", f"/patientdata/{kind}-results", json={"patient": pid, "labs": kind})
        for endpoint in ("discharge-list", "discharge-parsed", "vitals", "vitals-timeline"):
            data("POST", f"/patientdata/{endpoint}", json={"patient": pid})
        data("GET", f"/patientdata/{pid}/rag-context")
        context = data("GET", f"/patientdata/{pid}/document-context", params={"query": "discharge"})
        assert context["sources"], "Patient document retrieval returned no sources"
        data("POST", "/pdfingestion/extract", json={"folderName": pid})

    for entry in manifest["files"]:
        pid, source = entry["path"].split("/", 1)
        response = session.get(base + f"/patientdata/{pid}/document", params={"source": source}, timeout=30)
        response.raise_for_status()
        assert response.headers["Content-Type"].startswith("application/pdf")
        assert hashlib.sha256(response.content).hexdigest() == entry["after"], "Preview does not serve verified redacted PDF"
    history = {"conversations": [{"id": "privacy-smoke", "patientId": "00001", "title": dictionary["names"][0],
                                  "messages": [{"role": "doctor", "text": dictionary["names"][0] + " creatinine 1.16 mg/dL"}]}]}
    response = session.post("http://127.0.0.1:8001/privacy/sanitize-history", json=history, timeout=30)
    response.raise_for_status()
    assert not pattern.search(response.text)
    result = response.json()["conversations"][0]
    assert result["id"] == "privacy-smoke" and "creatinine 1.16 mg/dL" in result["messages"][0]["text"]
    return {"patients": len(patients), "json_api_checks": checks, "verified_pdf_downloads": len(manifest["files"]),
            "known_names_remaining": 0, "saved_history_cleanup": "passed"}


if __name__ == "__main__":
    print(json.dumps(verify()))
