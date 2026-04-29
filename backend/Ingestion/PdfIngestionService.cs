using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace CLARA.Backend.Ingestion
{
    public class PdfIngestionService
    {
        private readonly PdfParser _pdfParser;
        private readonly string _patientsFolderPath;

        public PdfIngestionService()
        {
            _pdfParser = new PdfParser();
            _patientsFolderPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Desktop), "Patients");
        }

        public IReadOnlyList<ExtractedPdf> ExtractTextFromFolder(string folderName)
        {
            if (string.IsNullOrWhiteSpace(folderName))
                throw new ArgumentException("Folder name cannot be empty.", nameof(folderName));

            var safeFolderName = Path.GetFileName(folderName);
            if (string.IsNullOrEmpty(safeFolderName) || safeFolderName != folderName)
                throw new ArgumentException("Invalid folder name.", nameof(folderName));

            var targetFolder = Path.Combine(_patientsFolderPath, safeFolderName);

            if (!Directory.Exists(targetFolder))
                throw new DirectoryNotFoundException($"Folder not found in Patients folder: {safeFolderName}");

            var pdfFiles = Directory.GetFiles(targetFolder, "*.pdf", SearchOption.AllDirectories);

            return pdfFiles
                .Select(filePath => new ExtractedPdf(filePath, _pdfParser.ExtractText(filePath)))
                .ToList();
        }
    }

    public sealed record ExtractedPdf(string FilePath, string Text);
}
