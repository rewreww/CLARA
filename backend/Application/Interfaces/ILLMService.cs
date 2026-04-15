using CLARA.Backend.Application.DTOs;

namespace CLARA.Backend.Application.Interfaces;

/// <summary>
/// Interface for LLM (Large Language Model) service.
/// This is a placeholder for future AI integration.
/// </summary>
public interface ILLMService
{
    /// <summary>
    /// Generates a response from the LLM based on user message and patient data.
    /// </summary>
    /// <param name="message">User's chat message.</param>
    /// <param name="patientData">Patient input data for context.</param>
    /// <returns>LLM response with reasoning.</returns>
    Task<LLMResponseDto> GenerateResponseAsync(string message, PatientInputDto patientData);
}