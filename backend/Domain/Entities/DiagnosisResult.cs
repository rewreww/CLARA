namespace CLARA.Backend.Domain.Entities;

/// <summary>
/// Domain entity representing a diagnosis result.
/// </summary>
public class DiagnosisResult
{
    public string Diagnosis { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public List<string> Recommendations { get; set; } = new();
    public DateTime Timestamp { get; set; }
}