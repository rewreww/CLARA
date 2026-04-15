namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for LLM responses.
/// </summary>
public class LLMResponseDto
{
    public string Response { get; set; } = string.Empty;
    public string Reasoning { get; set; } = string.Empty;
}