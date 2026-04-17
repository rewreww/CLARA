using CLARA.Backend.Models;

namespace CLARA.Backend.Ingestion
{
    public class PatientDataExtractor
    {
        public PatientDto Extract(string rawText)
        {
            var patient = new PatientDto();

            // Simple parsing assuming text has "Name: value", "Age: value", etc.
            var lines = rawText.Split('\n');
            foreach (var line in lines)
            {
                if (line.Contains("Name:"))
                {
                    patient.Name = line.Split("Name:")[1].Trim();
                }
                else if (line.Contains("Age:"))
                {
                    if (int.TryParse(line.Split("Age:")[1].Trim(), out int age))
                    {
                        patient.Age = age;
                    }
                }
                else if (line.Contains("Gender:"))
                {
                    patient.Gender = line.Split("Gender:")[1].Trim();
                }
                else if (line.Contains("Birthday:"))
                {
                    if (DateTime.TryParse(line.Split("Birthday:")[1].Trim(), out DateTime birthday))
                    {
                        patient.Birthday = birthday;
                    }
                }
            }

            return patient;
        }
    }
}