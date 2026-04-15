namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for prediction results.
/// </summary>
public class PredictionResultDto
{
    public string Diagnosis { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public List<string> Recommendations { get; set; } = new();
}