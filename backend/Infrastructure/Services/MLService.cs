using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using System.Net.Http.Json;

namespace CLARA.Backend.Infrastructure.Services;

/// <summary>
/// Service for communicating with Python ML service.
/// </summary>
public class MLService : IMLService
{
    private readonly HttpClient _httpClient;
    private readonly string _mlServiceUrl;

    public MLService(IConfiguration configuration)
    {
        _httpClient = new HttpClient();
        _mlServiceUrl = configuration["AIServices:MLServiceUrl"] ?? "http://localhost:8000";
    }

    public async Task<PredictionResultDto> PredictAsync(PatientInputDto patientData)
    {
        // TODO: Call actual Python ML service
        // For now, return mock prediction

        // Simulate API call
        // var response = await _httpClient.PostAsJsonAsync($"{_mlServiceUrl}/predict", patientData);
        // return await response.Content.ReadFromJsonAsync<PredictionResultDto>();

        await Task.Delay(200); // Simulate delay

        // Mock prediction logic
        var diagnosis = "Possible Hypertension";
        if (patientData.Symptoms.Contains("chest pain"))
        {
            diagnosis = "Potential Cardiac Issue";
        }

        var confidence = 0.85;
        var recommendations = new List<string>
        {
            "Monitor blood pressure regularly",
            "Consult with cardiologist if symptoms persist",
            "Lifestyle modifications recommended"
        };

        return new PredictionResultDto
        {
            Diagnosis = diagnosis,
            Confidence = confidence,
            Recommendations = recommendations
        };
    }
}