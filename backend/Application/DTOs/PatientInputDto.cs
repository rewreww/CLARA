using FluentValidation;

namespace CLARA.Backend.Application.DTOs;

/// <summary>
/// Data Transfer Object for patient input data.
/// </summary>
public class PatientInputDto
{
    public int Age { get; set; }
    public string Sex { get; set; } = string.Empty;
    public List<string> Symptoms { get; set; } = new();
    public double BloodPressureSystolic { get; set; }
    public double BloodPressureDiastolic { get; set; }
    public double HeartRate { get; set; }
    public double Temperature { get; set; }
    public double OxygenSaturation { get; set; }
}

/// <summary>
/// Validator for PatientInputDto.
/// </summary>
public class PatientInputDtoValidator : AbstractValidator<PatientInputDto>
{
    public PatientInputDtoValidator()
    {
        RuleFor(x => x.Age).InclusiveBetween(0, 150);
        RuleFor(x => x.Sex).NotEmpty().Must(x => x == "M" || x == "F");
        RuleFor(x => x.BloodPressureSystolic).GreaterThan(0);
        RuleFor(x => x.BloodPressureDiastolic).GreaterThan(0);
        RuleFor(x => x.HeartRate).GreaterThan(0);
        RuleFor(x => x.Temperature).GreaterThan(0);
        RuleFor(x => x.OxygenSaturation).InclusiveBetween(0, 100);
    }
}