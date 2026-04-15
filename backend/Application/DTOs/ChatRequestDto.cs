namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for chat requests.
/// </summary>
public class ChatRequestDto
{
    public string Message { get; set; } = string.Empty;
    public PatientInputDto PatientData { get; set; } = new();
}