using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;

namespace CLARA.Backend.Infrastructure.Services;

/// <summary>
/// Placeholder implementation of LLM service.
/// TODO: Integrate with actual LLM API (e.g., OpenAI, Azure OpenAI).
/// </summary>
public class LLMService : ILLMService
{
    public async Task<LLMResponseDto> GenerateResponseAsync(string message, PatientInputDto patientData)
    {
        // TODO: Implement actual LLM call
        // For now, return mock response based on patient data

        await Task.Delay(100); // Simulate API call

        var response = $"Based on patient data (Age: {patientData.Age}, Symptoms: {string.Join(", ", patientData.Symptoms)}), " +
                      $"the AI suggests monitoring vital signs closely. " +
                      $"Blood Pressure: {patientData.BloodPressureSystolic}/{patientData.BloodPressureDiastolic}, " +
                      $"Heart Rate: {patientData.HeartRate} bpm.";

        var reasoning = "LLM analyzed patient symptoms and vitals against medical knowledge base. " +
                       "Applied pattern recognition for potential cardiovascular concerns.";

        return new LLMResponseDto
        {
            Response = response,
            Reasoning = reasoning
        };
    }
}