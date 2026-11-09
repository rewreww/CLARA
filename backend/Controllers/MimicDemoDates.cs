using System.Globalization;
using System.Text.RegularExpressions;

namespace CLARA.Backend.Controllers;

// Presentation-only date conversion. Original PDFs, database values and source CSVs remain intact.
internal static class MimicDemoDates
{
    private static readonly Regex DatePattern = new(
        @"(?<!\d)(?<year>21\d{2}|2200)-(?<month>0[1-9]|1[0-2])-(?<day>0[1-9]|[12]\d|3[01])(?!\d)",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    internal static string Convert(string text, MimicDemographicsCsv.Timeline? timeline)
    {
        if (timeline is null || string.IsNullOrEmpty(text)) return text;
        return DatePattern.Replace(text, match =>
        {
            if (!DateOnly.TryParseExact(match.Value, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                DateTimeStyles.None, out var date)) return match.Value;
            try { return date.AddDays(timeline.OffsetDays).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture); }
            catch (ArgumentOutOfRangeException) { return match.Value; }
        });
    }
}
