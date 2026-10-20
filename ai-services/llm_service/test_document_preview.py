import tempfile
import unittest
from pathlib import Path

from document_preview import resolve_guideline


class DocumentPreviewTests(unittest.TestCase):
    def test_only_registered_filename_or_stem_resolves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / 'Guideline [2026].pdf'
            pdf.touch()
            self.assertEqual(resolve_guideline(pdf.name, root), pdf)
            self.assertEqual(resolve_guideline(pdf.stem, root), pdf)
            for name in ('../Guideline [2026]', '..\\Guideline [2026]', 'C:/private.pdf', 'missing', ''):
                self.assertIsNone(resolve_guideline(name, root))


if __name__ == '__main__':
    unittest.main()
