import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

import fitz
from mimic_pdf import extract, timestamp, number, table_matrix


class MimicParserTests(unittest.TestCase):
    def test_shifted_grid_preserves_blank_real_cells(self):
        matrix = [['', 'Test', None, 'Result', None],
                  [None, 'Culture', None, '', None],
                  ['Test', None, 'Result', None, ''],
                  ['Repeat', None, 'negative', None, None]]
        rectangles = [
            [(0,0,6,40), (6,0,56,10), None, (56,0,106,10), None],
            [None, (6,10,56,20), None, (56,10,106,20), None],
            [(0,20,50,30), None, (50,20,100,30), None, (100,20,106,40)],
            [(0,30,50,40), None, (50,30,100,40), None, None]]
        table = SimpleNamespace(extract=lambda: matrix, bbox=(0,0,106,40),
                                rows=[SimpleNamespace(cells=row) for row in rectangles])
        self.assertEqual(table_matrix(table), [['Test','Result'], ['Culture',''], ['Test','Result'], ['Repeat','negative']])
        matrix[0][0] = 'unexpected text'
        self.assertEqual(table_matrix(table), matrix)

    def make_pdf(self, path):
        with fitz.open() as pdf:
            page = pdf.new_page(width=900, height=600)
            page.insert_text((30, 25), 'MIMIC-IV Demo')
            page.insert_text((30, 45), 'Recorded: 2125-02-27 13:24:00')

            def table(y, data, widths):
                height = 32
                xs = [30]
                for width in widths:
                    xs.append(xs[-1] + width)
                for x in xs:
                    page.draw_line((x, y), (x, y + len(data) * height))
                for i in range(len(data) + 1):
                    page.draw_line((30, y + i * height), (xs[-1], y + i * height))
                for row, values in enumerate(data):
                    for col, value in enumerate(values):
                        page.insert_text((xs[col] + 4, y + row * height + 18), value, fontsize=9)

            table(70, [['Patient identifier', 'Hospital admission identifier'],
                       ['12345678', '87654321']], [180, 220])
            table(170, [['Test', 'Result', 'Unit', 'Reference range', 'Recorded flag'],
                        ['Base Excess', '-5', 'mEq/L', '-2 to 2', 'abnormal'],
                        ['Hemoglobin', '8.6', 'g/dL', '12 to 16', 'abnormal'],
                        ['Unknown', '<0.5', 'mg/dL', 'Not provided', 'Not provided']],
                  [140, 100, 100, 160, 140])
            pdf.save(path)

    def test_pdf_values_units_scope_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.pdf'
            self.make_pdf(path)
            result = extract(path, 'Patient_12345678', 'Admission_87654321/Blood_Gas/Blood/2125-02-27/sample.pdf')
            self.assertEqual(result['admission'], '87654321')
            self.assertEqual(len(result['rows']), 3)
            base, hemoglobin, unknown = result['rows']
            self.assertEqual((base['numeric'], base['flag'], base['page']), (-5, 'low', 1))
            self.assertEqual((hemoglobin['numeric'], hemoglobin['unit']), (8.6, 'g/dL'))
            self.assertEqual(hemoglobin['observed_at'], '2125-02-27T13:24:00')
            self.assertEqual(unknown['value'], '<0.5')
            self.assertIsNone(unknown['numeric'])
            with self.assertRaisesRegex(ValueError, 'patient identifier'):
                extract(path, 'Patient_11111111', 'Admission_87654321/sample.pdf')
            with self.assertRaisesRegex(ValueError, 'admission identifier'):
                extract(path, 'Patient_12345678', 'Admission_11111111/sample.pdf')

    def test_wrapped_dates_and_missing_numbers(self):
        self.assertEqual(timestamp('2125-03-19\n19:00:00'), '2125-03-19T19:00:00')
        self.assertIsNone(number('Not provid\ned'))
        self.assertIsNone(number('>100'))


if __name__ == '__main__':
    unittest.main()
