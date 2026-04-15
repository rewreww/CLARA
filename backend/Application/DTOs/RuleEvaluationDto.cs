namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for rule evaluation results.
/// </summary>
public class RuleEvaluationDto
{
    public List<string> Flags { get; set; } = new();
    public bool IsEmergency { get; set; }
}