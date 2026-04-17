using System;
using CLARA.Backend.Models;

namespace CLARA.Backend.Ingestion
{
    public class PdfIngestionService
    {
        private readonly PdfParser _pdfParser;
        private readonly PatientDataExtractor _extractor;

        public PdfIngestionService()
        {
            _pdfParser = new PdfParser();
            _extractor = new PatientDataExtractor();
        }

        public PatientDto Process(string filePath)
        {
            if (string.IsNullOrEmpty(filePath))
                throw new ArgumentException("File path cannot be empty.");

            // 🟦 Step 1: Extract raw text from PDF
            string rawText = _pdfParser.ExtractText(filePath);

            if (string.IsNullOrWhiteSpace(rawText))
                throw new Exception("Failed to extract text from PDF.");

            // 🟨 Step 2: Convert raw text into structured patient data
            PatientDto patient = _extractor.Extract(rawText);

            if (patient == null)
                throw new Exception("Failed to extract patient data.");

            // 🟩 Step 3: Return structured result
            return patient;
        }
    }
}