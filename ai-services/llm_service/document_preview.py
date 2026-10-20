from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
GUIDELINES_DIR = Path(__file__).resolve().parent.parent / "guidelines"


def resolve_guideline(source: str, root: Path = GUIDELINES_DIR) -> Path | None:
    # Ingestion records the exact filename stem. Never resolve a user-supplied path.
    if not source or any(char in source for char in ("/", "\\", "\x00")):
        return None
    for path in root.glob("*.pdf"):
        if source in (path.name, path.stem) and not path.is_symlink() and path.resolve().parent == root.resolve():
            return path
    return None


@router.get("/documents/guideline")
def guideline_pdf(source: str):
    path = resolve_guideline(source)
    if path is None:
        raise HTTPException(status_code=404, detail="Source PDF is unavailable")
    return FileResponse(path, media_type="application/pdf", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
