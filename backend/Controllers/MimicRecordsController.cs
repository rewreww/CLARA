using System.Text.Json;
using System.Text.RegularExpressions;
using CLARA.Backend.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/patientdata/{patientId}/mimic")]
public sealed class MimicRecordsController(ClaraDbContext db, IConfiguration configuration) : ControllerBase
{
    private static bool ValidPatient(string patientId) => Regex.IsMatch(patientId, @"^Patient_\d{8}$");
    private static bool ValidAdmission(string? admission) => admission == "unlinked" || Regex.IsMatch(admission ?? "", @"^\d{8}$");
    private IQueryable<MimicPdfRow> Rows(string patientId, string admission) => db.MimicRows.AsNoTracking()
        .Where(x => x.PatientId == patientId && x.AdmissionId == (admission == "unlinked" ? null : admission)
            && x.Document.ExtractionStatus == "completed");
    private IQueryable<MimicDocumentInfo> Documents(string patientId, string admission) => db.MimicDocuments.AsNoTracking()
        .Where(x => x.Document.PatientId == patientId && x.AdmissionId == (admission == "unlinked" ? null : admission)
            && x.Document.ExtractionStatus == "completed");

    [HttpGet("summary")]
    public async Task<IActionResult> Summary(string patientId, CancellationToken token)
    {
        if (!ValidPatient(patientId) || !await db.Patients.AnyAsync(x => x.Id == patientId, token)) return NotFound();
        var docs = db.MimicDocuments.AsNoTracking().Where(x => x.Document.PatientId == patientId && x.Document.ExtractionStatus == "completed");
        var admissions = await docs.GroupBy(x => x.AdmissionId).Select(g => new { id = g.Key ?? "unlinked", documents = g.Count() }).OrderBy(x => x.id).ToListAsync(token);
        var overview = await docs.Where(x => x.Category == "overview").OrderBy(x => x.AdmissionId)
            .Select(x => new { admission = x.AdmissionId, source = x.Document.RelativePath, metadata = x.MetadataJson }).ToListAsync(token);
        MimicDemographicsCsv.Timeline? timeline = null;
        try { timeline = MimicDemographicsCsv.ReadTimeline(configuration, patientId); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException) { }
        return Ok(new { patient = patientId, admissions, overview,
            demo_date_offset_days = timeline?.OffsetDays,
            demo_year_group = timeline?.YearGroup,
            rows = await db.MimicRows.CountAsync(x => x.PatientId == patientId && x.Document.ExtractionStatus == "completed", token),
            failed_documents = await db.PatientDocuments.CountAsync(x => x.PatientId == patientId && x.ExtractionStatus == "failed", token),
            notice = "Historical MIMIC-IV Demo 2.2. Dates are shifted. No physician-written discharge summaries. Clinical alerts and ML predictions have not been validated for this dataset." });
    }

    [HttpGet("demographics")]
    public async Task<IActionResult> Demographics(string patientId, string admission, CancellationToken token)
    {
        if (!ValidPatient(patientId) || !Regex.IsMatch(admission ?? "", @"^\d{8}$"))
            return BadRequest(new { error = "Select a valid MIMIC admission." });
        // A CSV entry alone cannot authorize access to an unimported patient/admission.
        if (!await db.MimicDocuments.AsNoTracking().AnyAsync(x =>
                x.Document.PatientId == patientId && x.AdmissionId == admission
                && x.Document.ExtractionStatus == "completed", token))
            return NotFound(new { error = "This patient/admission has no imported records." });
        try
        {
            return Ok(MimicDemographicsCsv.Read(configuration, patientId, admission));
        }
        catch (FileNotFoundException)
        {
            return NotFound(new { error = "Matching local CSV demographics are unavailable." });
        }
        catch (InvalidDataException)
        {
            return StatusCode(422, new { error = "The local CSV demographics failed validation." });
        }
        catch (IOException)
        {
            return StatusCode(422, new { error = "The local CSV demographics could not be verified." });
        }
        catch (UnauthorizedAccessException)
        {
            return StatusCode(422, new { error = "The CSV demographics are inaccessible." });
        }
    }

    [HttpGet("vitals")]
    public async Task<IActionResult> Vitals(string patientId, string admission, CancellationToken token)
    {
        if (!ValidPatient(patientId) || !ValidAdmission(admission)) return BadRequest();
        string[] labels = ["noninvasivebloodpressuresystolic", "noninvasivebloodpressurediastolic",
            "arterialbloodpressuresystolic", "arterialbloodpressurediastolic", "heartrate",
            "respiratoryrate", "o2saturationpulseoxymetry", "temperaturecelsius", "temperaturefahrenheit"];
        var values = await Rows(patientId, admission)
            .Where(x => x.RecordType == "chartevents" && x.NumericValue != null && x.ObservedAt != null
                && labels.Contains(x.Label.ToLower().Replace(" ", "").Replace("\n", "").Replace("\r", "")))
            .OrderBy(x => x.ObservedAt).ThenBy(x => x.Id)
            .Select(x => new { label = x.Label, value = x.NumericValue, unit = x.Unit,
                at = x.ObservedAt, source = x.Document.RelativePath, page = x.Page }).ToListAsync(token);
        return Ok(new { patient = patientId, admission, values });
    }

    [HttpGet("records")]
    public async Task<IActionResult> Records(string patientId, string admission, string? category, string? search, int page = 1, CancellationToken token = default)
    {
        if (!ValidPatient(patientId) || !ValidAdmission(admission)) return BadRequest(new { error = "Select an admission or unlinked records." });
        var baseRows = Rows(patientId, admission);
        var categories = await baseRows.GroupBy(x => x.Category).Select(g => new { category = g.Key, count = g.Count() }).OrderBy(x => x.category).ToListAsync(token);
        var query = baseRows;
        if (!string.IsNullOrWhiteSpace(category)) query = query.Where(x => x.Category == category);
        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim();
            if (term.Length > 120) return BadRequest();
            query = query.Where(x => x.SearchText.ToLower().Contains(term.ToLower()));
        }
        var total = await query.CountAsync(token);
        page = Math.Clamp(page, 1, Math.Max(1, (total + 49) / 50));
        var rows = await query.OrderByDescending(x => x.ObservedAt).ThenBy(x => x.Document.RelativePath).ThenBy(x => x.RowNumber)
            .Skip((page - 1) * 50).Take(50).Select(x => new {
                x.Id, x.Category, record_type = x.RecordType, label = x.Label, observed_at = x.ObservedAt,
                cells = x.CellsJson, value = x.RawValue, numeric = x.NumericValue, unit = x.Unit,
                reference_low = x.ReferenceLow, reference_high = x.ReferenceHigh, source_flag = x.SourceFlag, flag = x.Flag,
                source = x.Document.RelativePath, page = x.Page
            }).ToListAsync(token);
        return Ok(new { rows, categories, total, page, page_size = 50 });
    }

    [HttpGet("documents")]
    public async Task<IActionResult> DocumentList(string patientId, string admission, string? category, int page = 1, CancellationToken token = default)
    {
        if (!ValidPatient(patientId) || !ValidAdmission(admission)) return BadRequest();
        var query = Documents(patientId, admission);
        if (!string.IsNullOrEmpty(category)) query = query.Where(x => x.Category == category);
        var total = await query.CountAsync(token);
        page = Math.Clamp(page, 1, Math.Max(1, (total + 49) / 50));
        return Ok(new { total, page, documents = await query.OrderBy(x => x.Document.RelativePath).Skip((page - 1) * 50).Take(50)
            .Select(x => new { source = x.Document.RelativePath, category = x.Category, pages = x.Pages, metadata = x.MetadataJson }).ToListAsync(token) });
    }

    [HttpGet("context")]
    public async Task<IActionResult> Context(string patientId, string admission, string? query, string? category, CancellationToken token)
    {
        if (!ValidPatient(patientId) || !ValidAdmission(admission)) return BadRequest(new { error = "An explicit admission selection is required." });
        var rows = Rows(patientId, admission);
        if (!string.IsNullOrEmpty(category) && category != "overview" && category != "documents") rows = rows.Where(x => x.Category == category);
        var total = await rows.CountAsync(token);
        var terms = Regex.Matches(query ?? "", @"[\p{L}\d]{3,}").Select(m => m.Value.ToLowerInvariant())
            .Where(x => !new[] { "the", "and", "for", "this", "patient", "what", "are", "was", "show", "summarize", "summary", "please", "latest", "recent", "results", "records", "review", "admission", "can", "you", "all", "labs", "lab", "values" }.Contains(x)).Distinct().Take(8).ToArray();
        var relevant = terms.Length == 0 ? rows : rows.Where(x => terms.Any(term => x.SearchText.ToLower().Contains(term)));
        var matched = await relevant.CountAsync(token);
        var selected = await relevant.OrderByDescending(x => x.ObservedAt).ThenBy(x => x.Document.RelativePath).ThenBy(x => x.RowNumber)
            .Take(40).Select(x => new { x.Category, x.RecordType, x.ObservedAt, x.CellsJson, source = x.Document.RelativePath, page = x.Page }).ToListAsync(token);
        var included = selected.Take(0).ToList();
        var lines = new List<string> { $"Patient: {patientId}; admission: {admission}.",
            $"Matched {matched} of {total} scoped PDF rows; showing at most 40. This is a subset, not the full record.",
            "Dates are shifted. Orders are not proof of administration. Missing values are unknown, not normal.",
            "No physician-written discharge summaries exist. No validated automated clinical alerts or ML assessment is available." };
        // Supplement the admission-scoped PDF subset with verified LOCAL CSV demographics.
        // Missing or invalid CSV exports must never be interpreted as negative findings.
        var demographicsAvailable = false;
        if (admission != "unlinked")
        {
            try
            {
                var demographicsJson = JsonSerializer.Serialize(MimicDemographicsCsv.Read(configuration, patientId, admission));
                using var demographics = JsonDocument.Parse(demographicsJson);
                lines.Add("[VERIFIED MIMIC-IV CSV DEMOGRAPHICS — SELECTED PATIENT AND ADMISSION]");
                lines.Add("Source: local patient-specific Source_CSV/hosp_patients.csv and Source_CSV/hosp_admissions.csv; verified subject_id and hadm_id.");
                lines.Add("Age is anchor_age in the dataset reference year, NOT age today or necessarily age at this admission.");
                foreach (var field in demographics.RootElement.GetProperty("fields").EnumerateArray())
                {
                    var label = field.GetProperty("label").GetString();
                    var value = field.GetProperty("value");
                    var text = value.ValueKind == JsonValueKind.String ? value.GetString() : null;
                    lines.Add($"{label}: {(string.IsNullOrWhiteSpace(text) ? "Not recorded" : text)}");
                }
                demographicsAvailable = true;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException)
            {
                lines.Add("CSV demographics are unavailable or could not be verified for this admission. Do not infer missing demographic fields.");
            }
        }
        else
        {
            lines.Add("No admission-linked CSV demographics for unlinked records.");
        }
        // The same validated patient-specific offset is returned to the UI and used here
        // for every retrieved timestamp, regardless of record category.
        MimicDemographicsCsv.Timeline? timeline = null;
        try { timeline = MimicDemographicsCsv.ReadTimeline(configuration, patientId); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or InvalidDataException) { }
        if (timeline is not null)
        {
            lines.Add($"[ESTIMATED DEMONSTRATION DATES] Fixed patient-specific offset: {timeline.OffsetDays} days. Anchor year group: {timeline.YearGroup}.");
            lines.Add("All dates below are converted display dates, not actual historical dates. Original source PDFs and database retain shifted MIMIC dates. Do not combine converted and original shifted dates in calculations.");
        }
        else lines.Add("No verified timeline anchor; dates remain original privacy-shifted MIMIC timestamps.");
        var chars = 0;
        foreach (var row in selected)
        {
            var when = row.ObservedAt?.ToString("s") ?? "time not supplied";
            var line = $"Source {row.source}, PDF page {row.page}; {row.Category}/{row.RecordType}; recorded {MimicDemoDates.Convert(when, timeline)}: {MimicDemoDates.Convert(row.CellsJson, timeline)}";
            if (chars + line.Length > 24000) { lines.Add("Context truncated to fit the model budget."); break; }
            lines.Add(line); chars += line.Length; included.Add(row);
        }
        var sources = included.Select(x => new { type = "patient_pdf", source = x.source, page = x.page, title = Path.GetFileName(x.source) }).Distinct().ToList();
        return Ok(new { context = string.Join('\n', lines), sources, matched, total, demographics_available = demographicsAvailable,
            demo_date_offset_days = timeline?.OffsetDays, demo_year_group = timeline?.YearGroup });
    }
}
