namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for chat responses.
/// </summary>
public class ChatResponseDto
{
    public string Response { get; set; } = string.Empty;
    public string Reasoning { get; set; } = string.Empty;
    public string SafetyNote { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; }
}