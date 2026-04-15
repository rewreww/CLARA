using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;

namespace CLARA.Backend.Infrastructure.Services;

/// <summary>
/// Rule-based engine for clinical safety logic.
/// </summary>
public class RuleEngineService : IRuleEngine
{
    public RuleEvaluationDto EvaluateRules(PatientInputDto patientData)
    {
        var flags = new List<string>();
        var isEmergency = false;

        // Rule 1: Chest pain + shortness of breath → Emergency
        if (patientData.Symptoms.Contains("chest pain") && patientData.Symptoms.Contains("shortness of breath"))
        {
            flags.Add("Emergency: Possible myocardial infarction");
            isEmergency = true;
        }

        // Rule 2: High blood pressure
        if (patientData.BloodPressureSystolic > 180 || patientData.BloodPressureDiastolic > 120)
        {
            flags.Add("Hypertensive crisis");
        }

        // Rule 3: Low oxygen saturation
        if (patientData.OxygenSaturation < 95)
        {
            flags.Add("Hypoxemia detected");
        }

        // Rule 4: Fever + symptoms
        if (patientData.Temperature > 100.4 && patientData.Symptoms.Any())
        {
            flags.Add("Possible infection");
        }

        return new RuleEvaluationDto
        {
            Flags = flags,
            IsEmergency = isEmergency
        };
    }
}