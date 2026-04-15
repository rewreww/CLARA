using CLARA.Backend.Application.DTOs;

namespace CLARA.Backend.Application.Interfaces;

/// <summary>
/// Interface for Machine Learning service.
/// Communicates with Python ML service.
/// </summary>
public interface IMLService
{
    /// <summary>
    /// Predicts diagnosis based on patient data.
    /// </summary>
    /// <param name="patientData">Patient input data.</param>
    /// <returns>Prediction result.</returns>
    Task<PredictionResultDto> PredictAsync(PatientInputDto patientData);
}