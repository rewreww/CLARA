namespace CLARA.Backend.Domain.Entities;

/// <summary>
/// Domain entity representing a patient.
/// </summary>
public class Patient
{
    public Guid Id { get; set; }
    public int Age { get; set; }
    public string Sex { get; set; } = string.Empty;
    public List<Symptom> Symptoms { get; set; } = new();
    public Vitals Vitals { get; set; } = new();
}

/// <summary>
/// Value object for patient vitals.
/// </summary>
public class Vitals
{
    public double BloodPressureSystolic { get; set; }
    public double BloodPressureDiastolic { get; set; }
    public double HeartRate { get; set; }
    public double Temperature { get; set; }
    public double OxygenSaturation { get; set; }
}