namespace CLARA.Backend.Domain.Entities;

/// <summary>
/// Domain entity representing a symptom.
/// </summary>
public class Symptom
{
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public int Severity { get; set; } // 1-10 scale
}