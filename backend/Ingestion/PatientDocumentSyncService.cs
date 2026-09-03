using System.Security.Cryptography;
using System.Text.Json;
using CLARA.Backend.Data;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Ingestion;

public sealed class PatientDocumentSyncService
{
    private static readonly SemaphoreSlim SyncLock = new(1, 1);
    private readonly ClaraDbContext _db;
    private readonly PdfParser _pdfParser;
    private readonly ClinicalTextExtractor _clinicalTextExtractor;
    private readonly PatientDocumentSyncProgress _progress;
    private readonly string _patientsFolderPath;
    private readonly ILogger<PatientDocumentSyncService> _logger;

    public PatientDocumentSyncService(
        ClaraDbContext db,
        PdfParser pdfParser,
        ClinicalTextExtractor clinicalTextExtractor,
        PatientDocumentSyncProgress progress,
        ILogger<PatientDocumentSyncService> logger)
    {
        _db = db;
        _pdfParser = pdfParser;
        _clinicalTextExtractor = clinicalTextExtractor;
        _progress = progress;
        _logger = logger;
        _patientsFolderPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            "Patients");
    }

    public async Task<PatientDocumentSyncResult> SyncAsync(
        string? requestedPatientId = null,
        CancellationToken cancellationToken = default)
    {
        var patientId = NormalizePatientId(requestedPatientId);
        await SyncLock.WaitAsync(cancellationToken);

        try
        {
            _progress.Info("Scanning patient folders");
            if (!Directory.Exists(_patientsFolderPath))
            {
                _progress.Error($"Patients folder was not found: {_patientsFolderPath}");
                return new PatientDocumentSyncResult(0, 0, 0, 0, 0, 0, 0,
                    [$"Patients folder was not found: {_patientsFolderPath}"]);
            }

            var patientDirectories = patientId is null
                ? Directory.GetDirectories(_patientsFolderPath)
                : [Path.Combine(_patientsFolderPath, patientId)];

            var result = new MutableSyncResult();
            foreach (var patientDirectory in patientDirectories)
            {
                cancellationToken.ThrowIfCancellationRequested();

                if (!Directory.Exists(patientDirectory))
                {
                    result.Failures.Add($"Patient folder was not found: {Path.GetFileName(patientDirectory)}");
                    continue;
                }

                await SyncPatientDirectoryAsync(patientDirectory, result, cancellationToken);
            }

            _progress.Working("Saving synchronized patient data");
            await _db.SaveChangesAsync(cancellationToken);
            _progress.Success(
                $"Patient data sync complete: {result.FilesExtracted} parsed, {result.StructuredItemsSaved} structured records saved, {result.FilesUnchanged} unchanged");
            return result.ToResult();
        }
        finally
        {
            SyncLock.Release();
        }
    }

    private async Task SyncPatientDirectoryAsync(
        string patientDirectory,
        MutableSyncResult result,
        CancellationToken cancellationToken)
    {
        var patientId = Path.GetFileName(patientDirectory);
        if (string.IsNullOrWhiteSpace(patientId))
        {
            result.Failures.Add($"Could not determine a patient id for '{patientDirectory}'.");
            return;
        }

        var now = DateTimeOffset.UtcNow;
        _progress.Working("Scanning patient record", patientId);
        var patient = await _db.Patients.FindAsync([patientId], cancellationToken);
        if (patient is null)
        {
            patient = new PatientRecord
            {
                Id = patientId,
                CreatedAtUtc = now,
                UpdatedAtUtc = now
            };
            _db.Patients.Add(patient);
            result.PatientsCreated++;
        }
        foreach (var filePath in Directory.EnumerateFiles(patientDirectory, "*.pdf", SearchOption.AllDirectories))
        {
            cancellationToken.ThrowIfCancellationRequested();
            result.FilesSeen++;
            var relativePath = Path.GetRelativePath(patientDirectory, filePath).Replace('\\', '/');
            PatientDocument? document = null;

            try
            {
                var fileInfo = new FileInfo(filePath);
                var contentHash = await ComputeSha256Async(filePath, cancellationToken);
                var recordDate = _clinicalTextExtractor.ExtractDateFromPath(relativePath);
                document = await _db.PatientDocuments.SingleOrDefaultAsync(
                    item => item.PatientId == patientId && item.RelativePath == relativePath,
                    cancellationToken);

                var hasCompletedText = document?.ExtractionStatus == "completed"
                    && !string.IsNullOrWhiteSpace(document.ExtractedText);
                var contentUnchanged = document is not null
                    && document.ContentHash == contentHash
                    && hasCompletedText;

                if (contentUnchanged && await HasDerivedRecordsAsync(document!.Id, cancellationToken))
                {
                    document.RecordDate ??= recordDate;
                    result.FilesUnchanged++;
                    continue;
                }

                if (document is not null
                    && document.ContentHash == contentHash
                    && document.ExtractionStatus == "completed")
                {
                    document.RecordDate ??= recordDate;
                    result.FilesUnchanged++;
                    _progress.Working("Preparing stored PDF data for database indexing", patientId, fileInfo.Name);
                    await ReplaceDerivedRecordsAsync(patient, document, document.ExtractedText ?? "", result, cancellationToken);
                    continue;
                }

                document ??= new PatientDocument
                {
                    Id = Guid.NewGuid(),
                    PatientId = patientId,
                    RelativePath = relativePath,
                    CreatedAtUtc = now
                };

                if (_db.Entry(document).State == EntityState.Detached)
                {
                    _db.PatientDocuments.Add(document);
                    result.DocumentsCreated++;
                }

                document.FileName = fileInfo.Name;
                document.DocumentType = InferDocumentType(relativePath);
                document.RecordDate = recordDate;
                document.ContentHash = contentHash;
                document.FileSizeBytes = fileInfo.Length;
                document.SourceModifiedAtUtc = fileInfo.LastWriteTimeUtc;
                document.UpdatedAtUtc = now;
                _progress.Working("Parsing PDF", patientId, fileInfo.Name);
                patient.UpdatedAtUtc = now;
                document.ExtractedText = _pdfParser.ExtractText(filePath);
                document.ExtractionStatus = "completed";
                document.ExtractedAtUtc = now;
                result.FilesExtracted++;
                await ReplaceDerivedRecordsAsync(patient, document, document.ExtractedText, result, cancellationToken);
                _progress.Success("New data successfully saved", patientId, fileInfo.Name);
            }
            catch (Exception ex)
            {
                if (document is not null)
                {
                    // A changed source must never keep serving text from its older version.
                    document.ExtractedText = null;
                    document.ExtractionStatus = "failed";
                    document.ExtractedAtUtc = now;
                    document.UpdatedAtUtc = now;
                    patient.UpdatedAtUtc = now;
                }

                result.Failures.Add($"{patientId}/{relativePath}: {ex.Message}");
                _progress.Error($"Could not parse PDF: {ex.Message}", patientId, Path.GetFileName(relativePath));
                _logger.LogWarning(ex, "Could not synchronize PDF for patient {PatientId}: {RelativePath}", patientId, relativePath);
            }
        }
    }

    private async Task<bool> HasDerivedRecordsAsync(Guid documentId, CancellationToken cancellationToken)
    {
        return await _db.LabResults.AnyAsync(item => item.SourceDocumentId == documentId, cancellationToken)
            || await _db.Diagnoses.AnyAsync(item => item.SourceDocumentId == documentId, cancellationToken)
            || await _db.Medications.AnyAsync(item => item.SourceDocumentId == documentId, cancellationToken)
            || await _db.DischargeSummaries.AnyAsync(item => item.SourceDocumentId == documentId, cancellationToken);
    }

    private async Task ReplaceDerivedRecordsAsync(
        PatientRecord patient,
        PatientDocument document,
        string extractedText,
        MutableSyncResult result,
        CancellationToken cancellationToken)
    {
        await RemoveDerivedRecordsAsync(document.Id, cancellationToken);
        var saved = 0;

        var metadata = _clinicalTextExtractor.ExtractPatientMetadata(extractedText);
        if (!string.IsNullOrWhiteSpace(metadata.Name))
        {
            patient.DisplayName = metadata.Name;
        }
        patient.AgeYears ??= metadata.AgeYears;
        patient.Sex ??= metadata.Sex;

        if (document.DocumentType == "laboratory")
        {
            _progress.Working("Extracting lab values", patient.Id, document.FileName);
            var labType = _clinicalTextExtractor.InferLabType(document.RelativePath, extractedText);
            foreach (var lab in _clinicalTextExtractor.ExtractLabResults(extractedText, labType))
            {
                _db.LabResults.Add(new LabResultRecord
                {
                    Id = Guid.NewGuid(),
                    PatientId = patient.Id,
                    SourceDocumentId = document.Id,
                    TestName = lab.TestName,
                    RawValue = lab.RawValue,
                    NumericValue = lab.NumericValue,
                    Unit = lab.Unit,
                    ReferenceLow = lab.ReferenceLow,
                    ReferenceHigh = lab.ReferenceHigh,
                    Flag = lab.Flag,
                    ObservedOn = document.RecordDate,
                    ExtractionConfidence = 0.85m,
                    CreatedAtUtc = DateTimeOffset.UtcNow
                });
                saved++;
            }
        }

        if (document.DocumentType == "discharge_summary")
        {
            _progress.Working("Extracting discharge summary data", patient.Id, document.FileName);
            var discharge = _clinicalTextExtractor.ParseDischarge(extractedText);
            ApplyDischargeMetadata(patient, discharge);

            _db.DischargeSummaries.Add(new DischargeSummaryRecord
            {
                Id = Guid.NewGuid(),
                PatientId = patient.Id,
                SourceDocumentId = document.Id,
                ChiefComplaint = discharge.ChiefComplaint,
                AdmittingDiagnosis = discharge.AdmittingDiagnosis,
                FinalDiagnosis = discharge.FinalDiagnosis,
                HistoryOfPresentIllness = discharge.HistoryOfPresentIllness,
                PastMedicalHistory = discharge.PastMedicalHistory,
                Allergies = discharge.Allergies,
                ConditionOnDischarge = discharge.ConditionOnDischarge,
                FollowUp = discharge.FollowUp,
                PhysicalExam = JsonSerializer.Serialize(discharge.PhysicalExam),
                HospitalCourse = JsonSerializer.Serialize(discharge.HospitalCourse),
                Instructions = JsonSerializer.Serialize(discharge.Instructions),
                DischargeDate = document.RecordDate,
                ExtractionConfidence = 0.85m,
                CreatedAtUtc = DateTimeOffset.UtcNow,
                UpdatedAtUtc = DateTimeOffset.UtcNow
            });
            saved++;

            foreach (var diagnosis in new[]
            {
                ("admitting", discharge.AdmittingDiagnosis),
                ("final", discharge.FinalDiagnosis)
            })
            {
                if (string.IsNullOrWhiteSpace(diagnosis.Item2))
                {
                    continue;
                }

                _db.Diagnoses.Add(new DiagnosisRecord
                {
                    Id = Guid.NewGuid(),
                    PatientId = patient.Id,
                    SourceDocumentId = document.Id,
                    DiagnosisType = diagnosis.Item1,
                    DiagnosisText = diagnosis.Item2,
                    NormalizedName = diagnosis.Item2.Length > 500 ? diagnosis.Item2[..500] : diagnosis.Item2,
                    RecordedOn = document.RecordDate,
                    ExtractionConfidence = 0.85m,
                    CreatedAtUtc = DateTimeOffset.UtcNow
                });
                saved++;
            }

            foreach (var medication in discharge.Medications)
            {
                _db.Medications.Add(new MedicationRecord
                {
                    Id = Guid.NewGuid(),
                    PatientId = patient.Id,
                    SourceDocumentId = document.Id,
                    MedicationName = medication.Length > 500 ? medication[..500] : medication,
                    MedicationStatus = "documented",
                    SourceText = medication,
                    RecordedOn = document.RecordDate,
                    ExtractionConfidence = 0.8m,
                    CreatedAtUtc = DateTimeOffset.UtcNow
                });
                saved++;
            }

            foreach (var lab in discharge.Labs)
            {
                if (string.IsNullOrWhiteSpace(lab.Test) || string.IsNullOrWhiteSpace(lab.Value))
                {
                    continue;
                }

                _db.LabResults.Add(new LabResultRecord
                {
                    Id = Guid.NewGuid(),
                    PatientId = patient.Id,
                    SourceDocumentId = document.Id,
                    TestName = lab.Test,
                    RawValue = lab.Value,
                    NumericValue = TryDecimal(lab.Value),
                    Unit = lab.Unit,
                    Flag = lab.Flag,
                    ObservedOn = document.RecordDate,
                    ExtractionConfidence = 0.7m,
                    CreatedAtUtc = DateTimeOffset.UtcNow
                });
                saved++;
            }
        }

        result.StructuredItemsSaved += saved;
        if (saved > 0)
        {
            _progress.Working($"Storing {saved} structured records in database", patient.Id, document.FileName);
        }
    }

    private async Task RemoveDerivedRecordsAsync(Guid documentId, CancellationToken cancellationToken)
    {
        var labs = await _db.LabResults.Where(item => item.SourceDocumentId == documentId).ToListAsync(cancellationToken);
        var diagnoses = await _db.Diagnoses.Where(item => item.SourceDocumentId == documentId).ToListAsync(cancellationToken);
        var medications = await _db.Medications.Where(item => item.SourceDocumentId == documentId).ToListAsync(cancellationToken);
        var summaries = await _db.DischargeSummaries.Where(item => item.SourceDocumentId == documentId).ToListAsync(cancellationToken);

        _db.LabResults.RemoveRange(labs);
        _db.Diagnoses.RemoveRange(diagnoses);
        _db.Medications.RemoveRange(medications);
        _db.DischargeSummaries.RemoveRange(summaries);
    }

    private static void ApplyDischargeMetadata(PatientRecord patient, DischargeExtraction discharge)
    {
        if (!string.IsNullOrWhiteSpace(discharge.Header.PatientName))
        {
            patient.DisplayName = discharge.Header.PatientName;
        }

        patient.AgeYears ??= TryInt(discharge.Header.Age);
        if (string.IsNullOrWhiteSpace(patient.Sex) && !string.IsNullOrWhiteSpace(discharge.Header.Sex))
        {
            patient.Sex = discharge.Header.Sex.StartsWith("M", StringComparison.OrdinalIgnoreCase) ? "M"
                : discharge.Header.Sex.StartsWith("F", StringComparison.OrdinalIgnoreCase) ? "F"
                : discharge.Header.Sex[..1].ToUpperInvariant();
        }
    }

    private static int? TryInt(string? value)
    {
        var match = System.Text.RegularExpressions.Regex.Match(value ?? "", @"\d+");
        return match.Success && int.TryParse(match.Value, out var parsed) ? parsed : null;
    }

    private static decimal? TryDecimal(string? value)
    {
        var match = System.Text.RegularExpressions.Regex.Match(value ?? "", @"[-+]?\d+(?:\.\d+)?");
        return match.Success && decimal.TryParse(match.Value, out var parsed) ? parsed : null;
    }

    private static string? NormalizePatientId(string? patientId)
    {
        if (string.IsNullOrWhiteSpace(patientId))
        {
            return null;
        }

        var normalized = patientId.Trim();
        if (normalized != Path.GetFileName(normalized) || normalized is "." or "..")
        {
            throw new ArgumentException("Invalid patient id.", nameof(patientId));
        }

        return normalized;
    }

    private static async Task<string> ComputeSha256Async(string filePath, CancellationToken cancellationToken)
    {
        await using var stream = new FileStream(
            filePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 81920,
            useAsync: true);
        var hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash);
    }

    private static string InferDocumentType(string relativePath)
    {
        var name = relativePath.ToLowerInvariant();
        if (name.Contains("discharge")) return "discharge_summary";
        if (name.Contains("prescription") || name.Contains("medication") || name.Contains("medicine")) return "prescription";
        if (name.Contains("laboratory") || name.Contains("lab ") || name.Contains("lab_") || name.Contains("chemistry") || name.Contains("hematology")) return "laboratory";
        if (name.Contains("ecg") || name.Contains("electrocard")) return "ecg";
        if (name.Contains("echo") || name.Contains("echocardi")) return "echocardiogram";
        if (name.Contains("radiology") || name.Contains("xray") || name.Contains("x-ray") || name.Contains("ct ")) return "imaging";
        return "other";
    }

    private sealed class MutableSyncResult
    {
        public int PatientsCreated { get; set; }
        public int FilesSeen { get; set; }
        public int DocumentsCreated { get; set; }
        public int FilesExtracted { get; set; }
        public int FilesUnchanged { get; set; }
        public int StructuredItemsSaved { get; set; }
        public List<string> Failures { get; } = [];

        public PatientDocumentSyncResult ToResult() => new(
            PatientsCreated,
            FilesSeen,
            DocumentsCreated,
            FilesExtracted,
            FilesUnchanged,
            StructuredItemsSaved,
            Failures.Count,
            Failures);
    }
}

public sealed record PatientDocumentSyncResult(
    int PatientsCreated,
    int FilesSeen,
    int DocumentsCreated,
    int FilesExtracted,
    int FilesUnchanged,
    int StructuredItemsSaved,
    int FailedFiles,
    IReadOnlyList<string> Failures);
