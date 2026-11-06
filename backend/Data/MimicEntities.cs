namespace CLARA.Backend.Data;

// Cells preserve exactly what is in the PDF, including missing values and units.
public sealed class MimicDocumentInfo
{
    public Guid DocumentId { get; set; }
    public PatientDocument Document { get; set; } = null!;
    public string? AdmissionId { get; set; }
    public string Category { get; set; } = "overview";
    public string RecordType { get; set; } = "";
    public string? Fluid { get; set; }
    public string ParserVersion { get; set; } = "";
    public string MetadataJson { get; set; } = "{}";
    public int Pages { get; set; }
}

public sealed class MimicPdfRow
{
    public long Id { get; set; }
    public Guid DocumentId { get; set; }
    public PatientDocument Document { get; set; } = null!;
    public string PatientId { get; set; } = "";
    public string? AdmissionId { get; set; }
    public string Category { get; set; } = "";
    public string RecordType { get; set; } = "";
    public int Page { get; set; }
    public int RowNumber { get; set; }
    public string Label { get; set; } = "";
    // MIMIC dates are shifted local timestamps. No timezone is inferred.
    public DateTime? ObservedAt { get; set; }
    public string RawValue { get; set; } = "";
    public decimal? NumericValue { get; set; }
    public string Unit { get; set; } = "";
    public decimal? ReferenceLow { get; set; }
    public decimal? ReferenceHigh { get; set; }
    public string SourceFlag { get; set; } = "";
    public string? Flag { get; set; }
    public string CellsJson { get; set; } = "{}";
    public string SearchText { get; set; } = "";
}
