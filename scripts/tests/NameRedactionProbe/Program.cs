using CLARA.Backend.Ingestion;
using System.Text.Json;

if (args.Length != 2) throw new ArgumentException("Supply original and redacted patient directories.");
var original = Path.GetFullPath(args[0]);
var redacted = Path.GetFullPath(args[1]);
var parser = new PdfParser();
var extractor = new ClinicalTextExtractor();
var checkedFiles = 0;
var failures = new List<string>();
foreach (var file in Directory.GetFiles(original, "*.pdf", SearchOption.AllDirectories))
{
    var relative = Path.GetRelativePath(original, file);
    var beforeText = parser.ExtractText(file);
    var afterText = parser.ExtractText(Path.Combine(redacted, relative));
    var beforeMetadata = extractor.ExtractPatientMetadata(beforeText);
    var afterMetadata = extractor.ExtractPatientMetadata(afterText);
    if (beforeMetadata.AgeYears != afterMetadata.AgeYears || beforeMetadata.Sex != afterMetadata.Sex)
        failures.Add(relative + ": demographics changed");
    if (relative.Contains("discharge", StringComparison.OrdinalIgnoreCase))
    {
        object Clinical(string text)
        {
            var d = extractor.ParseDischarge(text);
            return d with { Header = d.Header with { PatientName = null, AttendingPhysician = null, ReferralDoctors = null } };
        }
        if (JsonSerializer.Serialize(Clinical(beforeText)) != JsonSerializer.Serialize(Clinical(afterText)))
            failures.Add(relative + ": discharge extraction changed");
    }
    else
    {
        var kind = extractor.InferLabType(relative, beforeText);
        if (JsonSerializer.Serialize(extractor.ExtractLabResults(beforeText, kind)) !=
            JsonSerializer.Serialize(extractor.ExtractLabResults(afterText, kind)))
            failures.Add(relative + ": laboratory extraction changed");
    }
    checkedFiles++;
}
Console.WriteLine(JsonSerializer.Serialize(new { checkedFiles, failures }));
if (failures.Count > 0) Environment.Exit(1);
