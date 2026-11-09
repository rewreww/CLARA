using Microsoft.VisualBasic.FileIO;
using System.Globalization;
using System.Text.RegularExpressions;

namespace CLARA.Backend.Controllers;

// Read only the two patient-local CSV exports. Never enumerate other patient folders
// or use the global MIMIC files. Subject and admission IDs must match exactly.
internal static class MimicDemographicsCsv
{
    private static readonly string[] PatientHeaders = ["subject_id", "gender", "anchor_age"];
    private static readonly string[] AdmissionHeaders = ["subject_id", "hadm_id", "race", "insurance", "marital_status", "language"];

    private static Dictionary<string, string>? ReadMatchingRow(string filename, string[] headers,
        Func<Dictionary<string, string>, bool> matches)
    {
        if (!File.Exists(filename)) return null;
        // Patient exports are small, but cap file size to avoid unexpected large inputs.
        if (new FileInfo(filename).Length > 4_000_000) throw new InvalidDataException("CSV export exceeds safe size limit.");
        using var parser = new TextFieldParser(filename);
        parser.TextFieldType = FieldType.Delimited;
        parser.SetDelimiters(",");
        parser.HasFieldsEnclosedInQuotes = true;
        var names = parser.ReadFields()?.Select(h => h.Trim().TrimStart('\uFEFF')).ToArray()
            ?? throw new InvalidDataException("CSV header missing.");
        if (names.Distinct(StringComparer.OrdinalIgnoreCase).Count() != names.Length ||
            headers.Any(h => !names.Contains(h, StringComparer.OrdinalIgnoreCase)))
            throw new InvalidDataException("CSV does not have the expected columns.");
        Dictionary<string, string>? matched = null;
        while (!parser.EndOfData)
        {
            var cells = parser.ReadFields() ?? [];
            if (cells.Length != names.Length) throw new InvalidDataException("Invalid CSV row.");
            var row = names.Zip(cells).ToDictionary(pair => pair.First, pair => pair.Second.Trim(), StringComparer.OrdinalIgnoreCase);
            if (!matches(row)) continue;
            if (matched is not null) throw new InvalidDataException("Duplicate subject or admission in CSV.");
            matched = row;
        }
        return matched;
    }

    // A single day offset per patient is deliberately used instead of rewriting year digits:
    // it preserves exact intervals between chart events, including leap-day boundaries.
    internal sealed record Timeline(int OffsetDays, string YearGroup);

    internal static Timeline? ReadTimeline(IConfiguration configuration, string patientId)
    {
        if (!Regex.IsMatch(patientId, @"^Patient_\d{8}$")) return null;
        var root = CLARA.Backend.Ingestion.PatientDocumentSyncService.ResolvePatientsFolderPath(configuration);
        var patientDir = Path.Combine(root, patientId);
        var csvDir = Path.Combine(patientDir, "Source_CSV");
        foreach (var dir in new[] { root, patientDir, csvDir })
        {
            if (!Directory.Exists(dir)) return null;
            if ((File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0) return null;
        }
        var path = Path.Combine(csvDir, "hosp_patients.csv");
        if (!File.Exists(path) || (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) return null;
        var id = patientId["Patient_".Length..];
        var row = ReadMatchingRow(path, ["subject_id", "anchor_year", "anchor_year_group"], r => r["subject_id"] == id);
        if (row is null || !int.TryParse(row["anchor_year"], NumberStyles.None, CultureInfo.InvariantCulture, out var anchor)
            || anchor is < 2100 or > 2200) return null;
        var group = Regex.Match(row["anchor_year_group"], @"^(\d{4})\s*-\s*(\d{4})$");
        if (!group.Success || !int.TryParse(group.Groups[1].Value, out var first)
            || !int.TryParse(group.Groups[2].Value, out var last)
            || first < 1900 || last > 2100 || last < first || last - first > 9) return null;
        var midpoint = first + (last - first) / 2;
        var offsetDays = new DateOnly(midpoint, 1, 1).DayNumber - new DateOnly(anchor, 1, 1).DayNumber;
        return new Timeline(offsetDays, $"{first}-{last}");
    }

    public static object Read(IConfiguration configuration, string patientId, string admissionId)
    {
        var root = CLARA.Backend.Ingestion.PatientDocumentSyncService.ResolvePatientsFolderPath(configuration);
        var patientDir = Path.Combine(root, patientId);
        var csvDir = Path.Combine(patientDir, "Source_CSV");
        // Do not follow Windows junctions/symlinks that could redirect outside the configured source.
        foreach (var dir in new[] { root, patientDir, csvDir })
        {
            if (!Directory.Exists(dir)) throw new FileNotFoundException("Patient CSV directory unavailable.");
            if ((File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Linked CSV directories are not supported.");
        }
        var patientCsv = Path.Combine(csvDir, "hosp_patients.csv");
        var admissionsCsv = Path.Combine(csvDir, "hosp_admissions.csv");
        foreach (var file in new[] { patientCsv, admissionsCsv })
        {
            if (File.Exists(file) && (File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Linked CSV files are not supported.");
        }
        var id = patientId["Patient_".Length..];
        var p = ReadMatchingRow(patientCsv, PatientHeaders, row => row["subject_id"] == id);
        var a = ReadMatchingRow(admissionsCsv, AdmissionHeaders, row =>
            row["subject_id"] == id && row["hadm_id"] == admissionId);
        if (p is null || a is null) throw new FileNotFoundException("Matching patient and admission CSV rows were not found.");
        static string? Value(Dictionary<string, string> row, string field) =>
            row.TryGetValue(field, out var value) && !string.IsNullOrWhiteSpace(value) ? value : null;
        return new {
            patient = patientId,
            admission = admissionId,
            fields = new[] {
                new { label = "Age (reference year)", value = Value(p, "anchor_age") },
                new { label = "Sex", value = Value(p, "gender") },
                new { label = "Race / ethnicity", value = Value(a, "race") },
                new { label = "Insurance", value = Value(a, "insurance") },
                new { label = "Marital status", value = Value(a, "marital_status") },
                new { label = "Language", value = Value(a, "language") },
            },
            source = "Local patient-specific MIMIC-IV CSV exports"
        };
    }
}
