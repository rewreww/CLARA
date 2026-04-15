using CLARA.Backend.Application.DTOs;

namespace CLARA.Backend.Application.Interfaces;

/// <summary>
/// Interface for Rule-Based Engine.
/// Implements clinical safety logic.
/// </summary>
public interface IRuleEngine
{
    /// <summary>
    /// Evaluates rules based on patient data.
    /// </summary>
    /// <param name="patientData">Patient input data.</param>
    /// <returns>Rule evaluation result.</returns>
    RuleEvaluationDto EvaluateRules(PatientInputDto patientData);
}