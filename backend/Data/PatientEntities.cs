namespace CLARA.Backend.Data;

public sealed class PatientRecord
{
    public string Id { get; set; } = string.Empty;
    public string? DisplayName { get; set; }
    public int? AgeYears { get; set; }
    public string? Sex { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset UpdatedAtUtc { get; set; }

    public ICollection<PatientDocument> Documents { get; set; } = new List<PatientDocument>();
    public ICollection<DiagnosisRecord> Diagnoses { get; set; } = new List<DiagnosisRecord>();
    public ICollection<MedicationRecord> Medications { get; set; } = new List<MedicationRecord>();
    public ICollection<LabResultRecord> LabResults { get; set; } = new List<LabResultRecord>();
    public ICollection<DischargeSummaryRecord> DischargeSummaries { get; set; } = new List<DischargeSummaryRecord>();
}

public sealed class PatientDocument
{
    public Guid Id { get; set; }
    public string PatientId { get; set; } = string.Empty;
    public PatientRecord Patient { get; set; } = null!;
    public string RelativePath { get; set; } = string.Empty;
    public string FileName { get; set; } = string.Empty;
    public string DocumentType { get; set; } = "other";
    public DateOnly? RecordDate { get; set; }
    public string ContentHash { get; set; } = string.Empty;
    public long? FileSizeBytes { get; set; }
    public DateTimeOffset? SourceModifiedAtUtc { get; set; }
    public string ExtractionStatus { get; set; } = "pending";
    public string? ExtractedText { get; set; }
    public DateTimeOffset? ExtractedAtUtc { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset UpdatedAtUtc { get; set; }

    public ICollection<LabResultRecord> LabResults { get; set; } = new List<LabResultRecord>();
}

public sealed class DiagnosisRecord
{
    public Guid Id { get; set; }
    public string PatientId { get; set; } = string.Empty;
    public PatientRecord Patient { get; set; } = null!;
    public Guid? SourceDocumentId { get; set; }
    public PatientDocument? SourceDocument { get; set; }
    public string DiagnosisType { get; set; } = "documented";
    public string DiagnosisText { get; set; } = string.Empty;
    public string? NormalizedName { get; set; }
    public DateOnly? RecordedOn { get; set; }
    public decimal? ExtractionConfidence { get; set; }
    public bool IsClinicianReviewed { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
}

public sealed class MedicationRecord
{
    public Guid Id { get; set; }
    public string PatientId { get; set; } = string.Empty;
    public PatientRecord Patient { get; set; } = null!;
    public Guid? SourceDocumentId { get; set; }
    public PatientDocument? SourceDocument { get; set; }
    public string MedicationName { get; set; } = string.Empty;
    public string? Dose { get; set; }
    public string? Route { get; set; }
    public string? Frequency { get; set; }
    public string? MedicationStatus { get; set; }
    public string SourceText { get; set; } = string.Empty;
    public DateOnly? RecordedOn { get; set; }
    public decimal? ExtractionConfidence { get; set; }
    public bool IsClinicianReviewed { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
}

public sealed class LabResultRecord
{
    public Guid Id { get; set; }
    public string PatientId { get; set; } = string.Empty;
    public PatientRecord Patient { get; set; } = null!;
    public Guid? SourceDocumentId { get; set; }
    public PatientDocument? SourceDocument { get; set; }
    public string TestName { get; set; } = string.Empty;
    public string RawValue { get; set; } = string.Empty;
    public decimal? NumericValue { get; set; }
    public string? Unit { get; set; }
    public decimal? ReferenceLow { get; set; }
    public decimal? ReferenceHigh { get; set; }
    public string? Flag { get; set; }
    public DateOnly? ObservedOn { get; set; }
    public decimal? ExtractionConfidence { get; set; }
    public bool IsClinicianReviewed { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
}

public sealed class DischargeSummaryRecord
{
    public Guid Id { get; set; }
    public string PatientId { get; set; } = string.Empty;
    public PatientRecord Patient { get; set; } = null!;
    public Guid SourceDocumentId { get; set; }
    public PatientDocument SourceDocument { get; set; } = null!;
    public string? ChiefComplaint { get; set; }
    public string? AdmittingDiagnosis { get; set; }
    public string? FinalDiagnosis { get; set; }
    public string? HistoryOfPresentIllness { get; set; }
    public string? PastMedicalHistory { get; set; }
    public string? Allergies { get; set; }
    public string? ConditionOnDischarge { get; set; }
    public string? FollowUp { get; set; }
    public string? PhysicalExam { get; set; }
    public string? HospitalCourse { get; set; }
    public string? Instructions { get; set; }
    public DateOnly? DischargeDate { get; set; }
    public decimal? ExtractionConfidence { get; set; }
    public bool IsClinicianReviewed { get; set; }
    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset UpdatedAtUtc { get; set; }
}
