using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using CLARA.Backend.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/patientdata")]
public sealed class PatientDataController(ClaraDbContext db) : ControllerBase
{
    private static readonly HashSet<string> ChemistryTests = new(StringComparer.OrdinalIgnoreCase)
    {
        "CREATININE", "BLOOD URIC ACID", "FBS", "TOTAL CHOLESTEROL", "TRIGLYCERIDES",
        "HDL", "LDL", "VLDL", "CHOLESTEROL/HDL RATIO", "SGPT/ALT", "SODIUM", "POTASSIUM", "CHLORIDE"
    };

    private static readonly HashSet<string> HematologyTests = new(StringComparer.OrdinalIgnoreCase)
    {
        "HEMOGLOBIN", "HEMATOCRIT", "WBC", "NEUTROPHILS", "LYMPHOCYTES", "MONOCYTES",
        "EOSINOPHILS", "BASOPHILS", "STABS", "PLATELET COUNT", "MCV", "MCH", "MCHC", "ESR",
        "BLEEDING TIME", "CLOTTING TIME", "PROTIME CONTROL TEST", "%ACT INR", "APTT CONTROL TEST",
        "ABO TYPE", "RH TYPE", "REMARKS"
    };

    private static readonly HashSet<string> DocumentQueryStopWords = new(StringComparer.OrdinalIgnoreCase)
    {
        "pdf", "document", "documents", "file", "files", "page", "pages", "source", "sources",
        "content", "contents", "text", "extracted", "raw", "read", "summarize", "summary",
        "what", "does", "say", "says", "based", "from", "about", "according", "patient",
        "this", "that", "please", "tell", "show", "opened"
    };

    private static readonly HashSet<string> MicroscopyTests = new(StringComparer.OrdinalIgnoreCase)
    {
        "COLOR", "TRANSPARENCY", "PUS CELLS", "LEUKOCYTES", "PH", "SP. GRAVITY",
        "EPITHELIAL CELLS", "HYALINE", "FINE GRANULAR", "COARSE GRANULAR", "BILIRUBIN",
        "MUCUS THREADS", "UROBILINOGEN", "YEAST CELLS", "RENAL CELLS", "KETONE", "PROTEIN",
        "NITRITE", "GLUCOSE", "URINE PREGNANCY TEST", "URINE MICRAL TEST", "AMORPHOUS URATES",
        "URIC ACID", "CALCIUM OXALATE", "AMORPHOUS PHOSPHATES", "TRIPLE PHOSPHATES"
    };

    public sealed record PatientsResponse([property: JsonPropertyName("patients")] IReadOnlyList<PatientSummaryDto> Patients);

    public sealed record PatientSummaryDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("age")] string? Age,
        [property: JsonPropertyName("sex")] string? Sex,
        [property: JsonPropertyName("status")] string Status,
        [property: JsonPropertyName("available_sections")] IReadOnlyList<string> AvailableSections,
        [property: JsonPropertyName("files")] IReadOnlyList<PatientFileDto> Files);

    public sealed record PatientFileDto(
        [property: JsonPropertyName("file_path")] string FilePath,
        [property: JsonPropertyName("file_name")] string FileName,
        [property: JsonPropertyName("section")] string Section,
        [property: JsonPropertyName("lab_type")] string? LabType,
        [property: JsonPropertyName("date")] string? Date);

    public sealed record LabRequest(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("labs")] string? Labs);

    public sealed record LabResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("results")] IReadOnlyList<LabResultDto> Results);

    public sealed record LabResultDto(
        [property: JsonPropertyName("test_name")] string TestName,
        [property: JsonPropertyName("value")] object Value,
        [property: JsonPropertyName("unit")] string? Unit,
        [property: JsonPropertyName("reference_low")] decimal? ReferenceLow,
        [property: JsonPropertyName("reference_high")] decimal? ReferenceHigh,
        [property: JsonPropertyName("flag")] string? Flag);

    public sealed record TimelineRequest(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("lab_type")] string LabType);

    public sealed record TimelineResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("lab_type")] string LabType,
        [property: JsonPropertyName("timeline")] IReadOnlyList<DateLabResultDto> Timeline);

    public sealed record DateLabResultDto(
        [property: JsonPropertyName("date")] string Date,
        [property: JsonPropertyName("results")] IReadOnlyList<LabResultDto> Results);

    public sealed record DischargeRequest(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("file_name")] string? FileName = null);

    public sealed record DischargeListResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("files")] IReadOnlyList<DischargeFileDto> Files);

    public sealed record DischargeFileDto(
        [property: JsonPropertyName("file_name")] string FileName,
        [property: JsonPropertyName("date_label")] string DateLabel);

    public sealed record ParsedDischargeResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("found")] bool Found,
        [property: JsonPropertyName("header")] DischargeHeaderDto Header,
        [property: JsonPropertyName("condition_discharge")] string? ConditionDischarge,
        [property: JsonPropertyName("chief_complaint")] string? ChiefComplaint,
        [property: JsonPropertyName("admitting_dx")] string? AdmittingDx,
        [property: JsonPropertyName("final_dx")] string? FinalDx,
        [property: JsonPropertyName("hpi")] string? Hpi,
        [property: JsonPropertyName("pmh")] string? Pmh,
        [property: JsonPropertyName("allergies")] string? Allergies,
        [property: JsonPropertyName("medications")] IReadOnlyList<string> Medications,
        [property: JsonPropertyName("instructions")] IReadOnlyList<string> Instructions,
        [property: JsonPropertyName("followup")] string? FollowUp,
        [property: JsonPropertyName("physical_exam")] PhysicalExamDto PhysicalExam,
        [property: JsonPropertyName("laboratory_data")] string? LaboratoryData,
        [property: JsonPropertyName("labs")] IReadOnlyList<DischargeLabDto> Labs,
        [property: JsonPropertyName("hospital_course")] IReadOnlyList<HospitalCourseDto> HospitalCourse,
        [property: JsonPropertyName("raw_text")] string? RawText);

    public sealed record DischargeHeaderDto(
        [property: JsonPropertyName("facility")] string? Facility = null,
        [property: JsonPropertyName("document_title")] string? DocumentTitle = null,
        [property: JsonPropertyName("patient_name")] string? PatientName = null,
        [property: JsonPropertyName("age")] string? Age = null,
        [property: JsonPropertyName("sex")] string? Sex = null,
        [property: JsonPropertyName("civil_status")] string? CivilStatus = null,
        [property: JsonPropertyName("hospital_no")] string? HospitalNo = null,
        [property: JsonPropertyName("service")] string? Service = null,
        [property: JsonPropertyName("room_ward")] string? RoomWard = null,
        [property: JsonPropertyName("attending_physician")] string? AttendingPhysician = null,
        [property: JsonPropertyName("referral_doctors")] string? ReferralDoctors = null,
        [property: JsonPropertyName("date_admitted")] string? DateAdmitted = null,
        [property: JsonPropertyName("time_admitted")] string? TimeAdmitted = null,
        [property: JsonPropertyName("date_discharged")] string? DateDischarged = null,
        [property: JsonPropertyName("time_discharged")] string? TimeDischarged = null);

    public sealed record PhysicalExamDto(
        [property: JsonPropertyName("vitals")] string? Vitals = null,
        [property: JsonPropertyName("findings")] string? Findings = null);

    public sealed record DischargeLabDto(
        [property: JsonPropertyName("test")] string? Test,
        [property: JsonPropertyName("date")] string? Date,
        [property: JsonPropertyName("val")] string Value,
        [property: JsonPropertyName("unit")] string? Unit,
        [property: JsonPropertyName("flag")] string? Flag);

    public sealed record HospitalCourseDto(
        [property: JsonPropertyName("label")] string? Label,
        [property: JsonPropertyName("date")] string? Date,
        [property: JsonPropertyName("content")] string? Content);

    public sealed record VitalEntryDto(
        [property: JsonPropertyName("value")] string Value,
        [property: JsonPropertyName("numeric")] decimal? Numeric,
        [property: JsonPropertyName("status")] string Status,
        [property: JsonPropertyName("label")] string Label);

    public sealed record VitalsResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("found")] bool Found,
        [property: JsonPropertyName("raw")] string? Raw,
        [property: JsonPropertyName("bp")] VitalEntryDto? Bp,
        [property: JsonPropertyName("hr")] VitalEntryDto? Hr,
        [property: JsonPropertyName("rr")] VitalEntryDto? Rr,
        [property: JsonPropertyName("temp")] VitalEntryDto? Temp,
        [property: JsonPropertyName("o2")] VitalEntryDto? O2);

    public sealed record VitalsTimelineResponse(
        [property: JsonPropertyName("patient")] string Patient,
        [property: JsonPropertyName("timeline")] IReadOnlyList<VitalsTimelinePointDto> Timeline);

    public sealed record VitalsTimelinePointDto(
        [property: JsonPropertyName("date")] string Date,
        [property: JsonPropertyName("bp")] decimal? Bp,
        [property: JsonPropertyName("hr")] decimal? Hr,
        [property: JsonPropertyName("rr")] decimal? Rr,
        [property: JsonPropertyName("temp")] decimal? Temp,
        [property: JsonPropertyName("o2")] decimal? O2);

    public sealed record DocumentContextSourceDto(
        [property: JsonPropertyName("title")] string Title,
        [property: JsonPropertyName("source")] string Source,
        [property: JsonPropertyName("page")] int? Page,
        [property: JsonPropertyName("section")] string Section,
        [property: JsonPropertyName("type")] string Type);

    public sealed record DocumentContextResponse(
        [property: JsonPropertyName("patient_id")] string PatientId,
        [property: JsonPropertyName("context")] string Context,
        [property: JsonPropertyName("sources")] IReadOnlyList<DocumentContextSourceDto> Sources);

    [HttpGet("patients")]
    public async Task<PatientsResponse> Patients(CancellationToken cancellationToken)
    {
        var patients = await db.Patients
            .AsNoTracking()
            .Include(patient => patient.Documents)
            .Include(patient => patient.LabResults)
            .OrderBy(patient => patient.Id)
            .ToListAsync(cancellationToken);

        var result = patients.Select(patient =>
        {
            var files = patient.Documents
                .OrderBy(document => document.RelativePath)
                .Select(ToFileDto)
                .ToList();
            var sections = files
                .Select(file => file.LabType ?? file.Section)
                .Where(section => section != "other")
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(section => section)
                .ToList();
            var hasAbnormal = patient.LabResults.Any(result => result.Flag is "high" or "low");

            return new PatientSummaryDto(
                Id: patient.Id,
                Name: string.IsNullOrWhiteSpace(patient.DisplayName) ? patient.Id : patient.DisplayName,
                Age: patient.AgeYears?.ToString(),
                Sex: patient.Sex,
                Status: hasAbnormal ? "review" : "stable",
                AvailableSections: sections,
                Files: files);
        }).ToList();

        return new PatientsResponse(result);
    }

    [HttpPost("chemistry-results")]
    public Task<LabResponse> ChemistryResults([FromBody] LabRequest request, CancellationToken cancellationToken) =>
        LabResults(request.Patient, "chemistry", cancellationToken);

    [HttpPost("hematology-results")]
    public Task<LabResponse> HematologyResults([FromBody] LabRequest request, CancellationToken cancellationToken) =>
        LabResults(request.Patient, "hematology", cancellationToken);

    [HttpPost("microscopy-results")]
    public Task<LabResponse> MicroscopyResults([FromBody] LabRequest request, CancellationToken cancellationToken) =>
        LabResults(request.Patient, "microscopy", cancellationToken);

    [HttpPost("labs-timeline")]
    public async Task<ActionResult<TimelineResponse>> LabsTimeline([FromBody] TimelineRequest request, CancellationToken cancellationToken)
    {
        var rows = await PatientLabRows(request.Patient, cancellationToken);
        var filtered = rows.Where(row => MatchesLabType(row, request.LabType) && row.ObservedOn.HasValue).ToList();
        if (filtered.Count == 0)
        {
            return NotFound(new { detail = $"No dated {request.LabType} results found." });
        }

        var timeline = filtered
            .GroupBy(row => row.ObservedOn!.Value)
            .OrderBy(group => group.Key)
            .Select(group => new DateLabResultDto(
                group.Key.ToString("yyyy-MM-dd"),
                LatestByTest(group).Select(ToLabDto).ToList()))
            .ToList();

        return new TimelineResponse(request.Patient, request.LabType, timeline);
    }

    [HttpPost("discharge-list")]
    public async Task<DischargeListResponse> DischargeList([FromBody] DischargeRequest request, CancellationToken cancellationToken)
    {
        var files = await db.PatientDocuments
            .AsNoTracking()
            .Where(document => document.PatientId == request.Patient && document.DocumentType == "discharge_summary")
            .OrderBy(document => document.RelativePath)
            .Select(document => new DischargeFileDto(document.RelativePath, DateLabel(document.RecordDate, document.RelativePath)))
            .ToListAsync(cancellationToken);

        return new DischargeListResponse(request.Patient, files);
    }

    [HttpPost("discharge-parsed")]
    public async Task<ParsedDischargeResponse> DischargeParsed([FromBody] DischargeRequest request, CancellationToken cancellationToken)
    {
        var query = db.DischargeSummaries
            .AsNoTracking()
            .Include(summary => summary.SourceDocument)
            .Where(summary => summary.PatientId == request.Patient);

        if (!string.IsNullOrWhiteSpace(request.FileName))
        {
            query = query.Where(summary => summary.SourceDocument.RelativePath == request.FileName);
        }

        var summary = await query
            .OrderBy(summary => summary.DischargeDate ?? DateOnly.MinValue)
            .ThenBy(summary => summary.SourceDocument.RelativePath)
            .LastOrDefaultAsync(cancellationToken);

        if (summary is null)
        {
            return EmptyDischarge(request.Patient);
        }

        var medications = await db.Medications
            .AsNoTracking()
            .Where(medication => medication.SourceDocumentId == summary.SourceDocumentId)
            .OrderBy(medication => medication.MedicationName)
            .Select(medication => medication.SourceText)
            .ToListAsync(cancellationToken);
        var labs = await db.LabResults
            .AsNoTracking()
            .Where(lab => lab.SourceDocumentId == summary.SourceDocumentId)
            .OrderBy(lab => lab.TestName)
            .Select(lab => new DischargeLabDto(lab.TestName, null, lab.RawValue, lab.Unit, lab.Flag))
            .ToListAsync(cancellationToken);

        return new ParsedDischargeResponse(
            Patient: request.Patient,
            Found: true,
            Header: new DischargeHeaderDto(DocumentTitle: "Discharge Summary"),
            ConditionDischarge: summary.ConditionOnDischarge,
            ChiefComplaint: summary.ChiefComplaint,
            AdmittingDx: summary.AdmittingDiagnosis,
            FinalDx: summary.FinalDiagnosis,
            Hpi: summary.HistoryOfPresentIllness,
            Pmh: summary.PastMedicalHistory,
            Allergies: summary.Allergies,
            Medications: medications,
            Instructions: JsonList<string>(summary.Instructions),
            FollowUp: summary.FollowUp,
            PhysicalExam: JsonObject(summary.PhysicalExam, new PhysicalExamDto()),
            LaboratoryData: null,
            Labs: labs,
            HospitalCourse: JsonList<HospitalCourseDto>(summary.HospitalCourse),
            RawText: summary.SourceDocument.ExtractedText);
    }

    [HttpPost("vitals")]
    public async Task<VitalsResponse> Vitals([FromBody] DischargeRequest request, CancellationToken cancellationToken)
    {
        var summary = await LatestDischarge(request.Patient, cancellationToken);
        if (summary is null)
        {
            return new VitalsResponse(request.Patient, false, null, null, null, null, null, null);
        }

        var exam = JsonObject(summary.PhysicalExam, new PhysicalExamDto());
        return ParseVitals(request.Patient, exam.Vitals ?? ExtractVitalsFromText(summary.SourceDocument?.ExtractedText));
    }

    [HttpPost("vitals-timeline")]
    public async Task<VitalsTimelineResponse> VitalsTimeline([FromBody] DischargeRequest request, CancellationToken cancellationToken)
    {
        var summaries = await db.DischargeSummaries
            .AsNoTracking()
            .Include(summary => summary.SourceDocument)
            .Where(summary => summary.PatientId == request.Patient)
            .OrderBy(summary => summary.DischargeDate ?? DateOnly.MinValue)
            .ToListAsync(cancellationToken);

        var points = summaries.Select(summary =>
        {
            var parsed = ParseVitals(request.Patient, JsonObject(summary.PhysicalExam, new PhysicalExamDto()).Vitals);
            if (!parsed.Found)
            {
                parsed = ParseVitals(request.Patient, ExtractVitalsFromText(summary.SourceDocument?.ExtractedText));
            }

            return new VitalsTimelinePointDto(
                summary.DischargeDate?.ToString("yyyy-MM-dd") ?? "undated",
                parsed.Bp?.Numeric,
                parsed.Hr?.Numeric,
                parsed.Rr?.Numeric,
                parsed.Temp?.Numeric,
                parsed.O2?.Numeric);
        }).ToList();

        return new VitalsTimelineResponse(request.Patient, points);
    }

    [HttpGet("{patientId}/rag-context")]
    public async Task<IActionResult> RagContext([FromRoute] string patientId, CancellationToken cancellationToken)
    {
        var patient = await db.Patients
            .AsNoTracking()
            .FirstOrDefaultAsync(item => item.Id == patientId, cancellationToken);
        if (patient is null)
        {
            return NotFound(new { error = "Patient not found." });
        }

        var diagnoses = await db.Diagnoses.AsNoTracking()
            .Where(item => item.PatientId == patientId)
            .OrderByDescending(item => item.RecordedOn ?? DateOnly.MinValue)
            .Take(8)
            .ToListAsync(cancellationToken);
        var medications = await db.Medications.AsNoTracking()
            .Where(item => item.PatientId == patientId)
            .OrderByDescending(item => item.RecordedOn ?? DateOnly.MinValue)
            .Take(20)
            .ToListAsync(cancellationToken);
        var labs = await PatientLabRows(patientId, cancellationToken);
        var recentLabs = LatestByTest(labs).Take(40).ToList();
        var abnormalLabs = recentLabs.Where(item => item.Flag is "high" or "low").ToList();
        var discharge = await LatestDischarge(patientId, cancellationToken);

        var lines = new List<string>
        {
            "[PATIENT CONTEXT]",
            $"Patient: {patient.DisplayName ?? patient.Id} ({patient.Id})",
            $"Age: {patient.AgeYears?.ToString() ?? "unknown"}; Sex: {patient.Sex ?? "unknown"}"
        };

        if (diagnoses.Count > 0)
        {
            lines.Add("[DIAGNOSES]");
            lines.AddRange(diagnoses.Select(item => $"- {item.DiagnosisType}: {item.DiagnosisText}"));
        }

        if (medications.Count > 0)
        {
            lines.Add("[MEDICATIONS]");
            lines.AddRange(medications.Select(item => $"- {item.SourceText}"));
        }

        if (abnormalLabs.Count > 0)
        {
            lines.Add("[ABNORMAL LABS]");
            lines.AddRange(abnormalLabs.Select(item => $"- {item.TestName}: {item.RawValue} {item.Unit} ({item.Flag})"));
        }

        if (recentLabs.Count > 0)
        {
            lines.Add("[RECENT LABS]");
            lines.AddRange(recentLabs.Select(item => $"- {item.TestName}: {item.RawValue} {item.Unit}".Trim()));
        }

        if (discharge is not null)
        {
            lines.Add("[LATEST DISCHARGE SUMMARY]");
            if (!string.IsNullOrWhiteSpace(discharge.FinalDiagnosis)) lines.Add($"Final diagnosis: {discharge.FinalDiagnosis}");
            if (!string.IsNullOrWhiteSpace(discharge.HistoryOfPresentIllness)) lines.Add($"HPI: {discharge.HistoryOfPresentIllness}");
            if (!string.IsNullOrWhiteSpace(discharge.FollowUp)) lines.Add($"Follow-up: {discharge.FollowUp}");
        }

        return Ok(new { patient_id = patientId, context = string.Join('\n', lines) });
    }

    [HttpGet("{patientId}/document-context")]
    public async Task<ActionResult<DocumentContextResponse>> DocumentContext(
        [FromRoute] string patientId,
        [FromQuery] string? query,
        CancellationToken cancellationToken)
    {
        var documents = await db.PatientDocuments
            .AsNoTracking()
            .Where(document =>
                document.PatientId == patientId
                && document.ExtractionStatus == "completed"
                && document.ExtractedText != null
                && document.ExtractedText != "")
            .OrderBy(document => document.RecordDate ?? DateOnly.MinValue)
            .ThenBy(document => document.RelativePath)
            .ToListAsync(cancellationToken);

        if (documents.Count == 0)
        {
            return new DocumentContextResponse(patientId, "No extracted patient PDF text found.", []);
        }

        var terms = QueryTerms(query);
        var documentReferenceTerms = DocumentReferenceTerms(query);
        var scoredSnippets = documents
            .SelectMany(document => PageSnippets(document)
                .Select(page => new DocumentSnippet(
                    document.RelativePath,
                    document.FileName,
                    document.DocumentType,
                    page.Page,
                    page.Text,
                    ScoreDocumentPage(document, page.Text, terms))))
            .ToList();

        if (documentReferenceTerms.Count > 0)
        {
            scoredSnippets = scoredSnippets
                .Where(snippet => MatchesAnyTerm(snippet, documentReferenceTerms))
                .ToList();
        }

        if (documentReferenceTerms.Count > 0 && scoredSnippets.Count == 0)
        {
            return new DocumentContextResponse(patientId, "No matching extracted patient PDF text found.", []);
        }

        if (terms.Count > 0 && scoredSnippets.All(snippet => snippet.Score <= 0))
        {
            return new DocumentContextResponse(patientId, "No matching extracted patient PDF text found.", []);
        }

        var snippets = scoredSnippets
            .Where(snippet => terms.Count == 0 || snippet.Score > 0)
            .OrderByDescending(snippet => snippet.Score)
            .ThenBy(snippet => snippet.Source)
            .ThenBy(snippet => snippet.Page ?? int.MaxValue)
            .Take(5)
            .ToList();

        if (snippets.Count == 0)
        {
            return new DocumentContextResponse(patientId, "No matching extracted patient PDF text found.", []);
        }

        var lines = new List<string>
        {
            "[PATIENT PDF CONTEXT]",
            "Use only these patient PDF excerpts for questions about a PDF, file, page, or document content.",
            "Start the answer by naming the PDF source and page when a page is available.",
            ""
        };
        foreach (var snippet in snippets)
        {
            var pageLabel = snippet.Page.HasValue ? $" p.{snippet.Page.Value}" : "";
            lines.Add($"--- Patient PDF: {snippet.Source}{pageLabel} ---");
            lines.Add(TrimContext(snippet.Text, 1800));
            lines.Add("");
        }

        var sources = snippets
            .GroupBy(snippet => new { snippet.Source, snippet.Page })
            .Select(group => group.First())
            .Take(4)
            .Select(snippet => new DocumentContextSourceDto(
                snippet.Title,
                snippet.Source,
                snippet.Page,
                snippet.DocumentType,
                "patient_pdf"))
            .ToList();

        return new DocumentContextResponse(patientId, string.Join('\n', lines).Trim(), sources);
    }

    private async Task<LabResponse> LabResults(string patientId, string labType, CancellationToken cancellationToken)
    {
        var rows = await PatientLabRows(patientId, cancellationToken);
        var results = LatestByTest(rows.Where(row => MatchesLabType(row, labType))).Select(ToLabDto).ToList();
        return new LabResponse(patientId, results);
    }

    private sealed record PageText(int? Page, string Text);

    private sealed record DocumentSnippet(
        string Source,
        string Title,
        string DocumentType,
        int? Page,
        string Text,
        int Score);

    private static IReadOnlyList<string> QueryTerms(string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return [];
        }

        return Regex.Matches(query.ToLowerInvariant(), @"[a-z0-9]{3,}")
            .Select(match => match.Value)
            .Where(term => !DocumentQueryStopWords.Contains(term))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .ToList();
    }

    private static IReadOnlyList<string> DocumentReferenceTerms(string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return [];
        }

        return Regex.Matches(query, @"\b[A-Z]{2,10}[-_ ]?\d{2}[-_ ]?\d{3,}\b|[\w.-]+\.pdf\b", RegexOptions.IgnoreCase)
            .SelectMany(match => Regex.Matches(match.Value.ToLowerInvariant(), @"[a-z0-9]{3,}").Select(token => token.Value))
            .Where(term => !DocumentQueryStopWords.Contains(term))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(8)
            .ToList();
    }

    private static bool MatchesAnyTerm(DocumentSnippet snippet, IReadOnlyList<string> terms)
    {
        var haystack = $"{snippet.Source} {snippet.Title} {snippet.Text}".ToLowerInvariant();
        return terms.Any(term => haystack.Contains(term, StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<PageText> PageSnippets(PatientDocument document)
    {
        var text = document.ExtractedText?.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var matches = Regex.Matches(
            text,
            @"(?m)^\[PDF PAGE (?<page>\d+)\]\s*$",
            RegexOptions.IgnoreCase);

        if (matches.Count == 0)
        {
            return [new PageText(null, text)];
        }

        var pages = new List<PageText>();
        for (var index = 0; index < matches.Count; index++)
        {
            var page = int.TryParse(matches[index].Groups["page"].Value, out var parsedPage)
                ? parsedPage
                : (int?)null;
            var start = matches[index].Index + matches[index].Length;
            var end = index + 1 < matches.Count ? matches[index + 1].Index : text.Length;
            var pageText = text[start..end].Trim();
            if (!string.IsNullOrWhiteSpace(pageText))
            {
                pages.Add(new PageText(page, pageText));
            }
        }

        return pages;
    }

    private static int ScoreDocumentPage(PatientDocument document, string pageText, IReadOnlyList<string> terms)
    {
        if (terms.Count == 0)
        {
            return 0;
        }

        var source = $"{document.RelativePath} {document.FileName}".ToLowerInvariant();
        var text = pageText.ToLowerInvariant();
        var score = 0;
        foreach (var term in terms)
        {
            if (source.Contains(term, StringComparison.OrdinalIgnoreCase))
            {
                score += 10;
            }

            if (text.Contains(term, StringComparison.OrdinalIgnoreCase))
            {
                score += 2;
            }
        }

        return score;
    }

    private static string TrimContext(string text, int maxLength)
    {
        text = Regex.Replace(text.Trim(), @"[ \t]+", " ");
        if (text.Length <= maxLength)
        {
            return text;
        }

        var cut = text.LastIndexOfAny(new[] { '.', '\n', ';' }, Math.Min(maxLength, text.Length - 1));
        if (cut < maxLength / 2)
        {
            cut = maxLength;
        }

        return text[..cut].Trim() + "...";
    }

    private async Task<List<LabResultRecord>> PatientLabRows(string patientId, CancellationToken cancellationToken)
    {
        return await db.LabResults
            .AsNoTracking()
            .Include(result => result.SourceDocument)
            .Where(result => result.PatientId == patientId)
            .OrderBy(result => result.ObservedOn ?? DateOnly.MinValue)
            .ThenBy(result => result.TestName)
            .ToListAsync(cancellationToken);
    }

    private static IReadOnlyList<LabResultRecord> LatestByTest(IEnumerable<LabResultRecord> rows)
    {
        return rows
            .GroupBy(row => row.TestName, StringComparer.OrdinalIgnoreCase)
            .Select(group => group
                .OrderBy(row => row.ObservedOn ?? DateOnly.MinValue)
                .ThenBy(row => row.CreatedAtUtc)
                .Last())
            .OrderBy(row => row.TestName)
            .ToList();
    }

    private static bool MatchesLabType(LabResultRecord row, string labType)
    {
        var source = row.SourceDocument?.RelativePath ?? "";
        if (source.Contains(labType, StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (labType == "microscopy"
            && (source.Contains("micoscopy", StringComparison.OrdinalIgnoreCase)
                || source.Contains("urinalysis", StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        var tests = labType switch
        {
            "chemistry" => ChemistryTests,
            "hematology" => HematologyTests,
            "microscopy" => MicroscopyTests,
            _ => []
        };
        return tests.Contains(row.TestName);
    }

    private static LabResultDto ToLabDto(LabResultRecord row) =>
        new(
            row.TestName,
            row.NumericValue.HasValue ? row.NumericValue.Value : row.RawValue,
            row.Unit,
            row.ReferenceLow,
            row.ReferenceHigh,
            row.Flag);

    private static PatientFileDto ToFileDto(PatientDocument document)
    {
        var section = document.DocumentType switch
        {
            "discharge_summary" => "discharge",
            "laboratory" => "labs",
            "prescription" => "prescriptions",
            "imaging" => "imaging",
            _ => "other"
        };
        var labType = section == "labs" ? LabTypeFromPath(document.RelativePath) : null;
        return new PatientFileDto(
            document.RelativePath,
            document.FileName,
            section,
            labType,
            document.RecordDate?.ToString("yyyy-MM-dd"));
    }

    private static string? LabTypeFromPath(string path)
    {
        foreach (var labType in new[] { "chemistry", "hematology", "microscopy" })
        {
            if (path.Contains(labType, StringComparison.OrdinalIgnoreCase))
            {
                return labType;
            }
        }

        if (path.Contains("micoscopy", StringComparison.OrdinalIgnoreCase)
            || path.Contains("urinalysis", StringComparison.OrdinalIgnoreCase))
        {
            return "microscopy";
        }

        return null;
    }

    private async Task<DischargeSummaryRecord?> LatestDischarge(string patientId, CancellationToken cancellationToken) =>
        await db.DischargeSummaries
            .AsNoTracking()
            .Include(summary => summary.SourceDocument)
            .Where(summary => summary.PatientId == patientId)
            .OrderBy(summary => summary.DischargeDate ?? DateOnly.MinValue)
            .LastOrDefaultAsync(cancellationToken);

    private static string? ExtractVitalsFromText(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var match = Regex.Match(
            text,
            @"physical\s+exam(?:ination)?\s*:?\s*(?<vitals>\d{2,3}\s*/\s*\d{2,3}\s*>\s*\d{1,3}\s*>\s*\d{1,3}\s*>\s*\d{2,3}(?:\.\d+)?\s*>\s*\d{2,3}\s*%)",
            RegexOptions.IgnoreCase);

        if (match.Success)
        {
            return match.Groups["vitals"].Value;
        }

        match = Regex.Match(
            text,
            @"(?<vitals>\d{2,3}\s*/\s*\d{2,3}\s*>\s*\d{1,3}\s*>\s*\d{1,3}\s*>\s*\d{2,3}(?:\.\d+)?\s*>\s*\d{2,3}\s*%)",
            RegexOptions.IgnoreCase);

        return match.Success ? match.Groups["vitals"].Value : null;
    }

    private static ParsedDischargeResponse EmptyDischarge(string patientId) =>
        new(patientId, false, new DischargeHeaderDto(), null, null, null, null, null, null, null, [], [], null, new PhysicalExamDto(), null, [], [], null);

    private static IReadOnlyList<T> JsonList<T>(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return [];
        }

        try
        {
            return JsonSerializer.Deserialize<List<T>>(json) ?? [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static T JsonObject<T>(string? json, T fallback)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return fallback;
        }

        try
        {
            return JsonSerializer.Deserialize<T>(json) ?? fallback;
        }
        catch (JsonException)
        {
            return fallback;
        }
    }

    private static string DateLabel(DateOnly? date, string fallback)
    {
        if (date.HasValue)
        {
            return date.Value.ToString("MMM dd, yyyy");
        }

        return Regex.Replace(Path.GetFileNameWithoutExtension(fallback), @"[_\-]", " ");
    }

    private static VitalsResponse ParseVitals(string patientId, string? rawVitals)
    {
        if (string.IsNullOrWhiteSpace(rawVitals))
        {
            return new VitalsResponse(patientId, false, null, null, null, null, null, null);
        }

        var parts = rawVitals.Split(['>', '|', ',', ';'], StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var bp = parts.FirstOrDefault(part => Regex.IsMatch(part, @"\d+\s*/\s*\d+"));
        var o2 = parts.FirstOrDefault(part => part.Contains('%'));
        var temp = parts.FirstOrDefault(part => part.Contains('.') && Number(part).HasValue);
        var remaining = parts.Where(part => part != bp && part != o2 && part != temp).ToList();
        var hr = remaining.ElementAtOrDefault(0);
        var rr = remaining.ElementAtOrDefault(1);

        return new VitalsResponse(
            patientId,
            true,
            rawVitals,
            ParseBp(bp),
            ParseSimpleVital(hr, "hr"),
            ParseSimpleVital(rr, "rr"),
            ParseSimpleVital(temp, "temp"),
            ParseSimpleVital(o2, "o2"));
    }

    private static VitalEntryDto? ParseBp(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var match = Regex.Match(value, @"(?<sys>\d+)\s*/\s*(?<dia>\d+)");
        if (!match.Success)
        {
            return null;
        }

        var sys = decimal.Parse(match.Groups["sys"].Value);
        var dia = decimal.Parse(match.Groups["dia"].Value);
        var status = sys < 90 || dia < 60 || sys >= 140 || dia >= 90 ? "critical"
            : sys >= 130 || dia >= 80 ? "warning"
            : "normal";
        var label = sys < 90 ? "Hypotensive"
            : sys >= 160 || dia >= 100 ? "HTN Crisis"
            : sys >= 140 || dia >= 90 ? "Hypertensive"
            : sys >= 130 || dia >= 80 ? "Elevated"
            : "Normal";
        return new VitalEntryDto($"{sys:0}/{dia:0}", sys, status, label);
    }

    private static VitalEntryDto? ParseSimpleVital(string? value, string kind)
    {
        var numeric = Number(value);
        if (!numeric.HasValue)
        {
            return null;
        }

        var (status, label) = kind switch
        {
            "hr" => numeric < 50 || numeric > 150 ? ("critical", numeric < 50 ? "Bradycardic" : "Severe Tachy")
                : numeric < 60 || numeric > 100 ? ("warning", numeric < 60 ? "Bradycardic" : "Tachycardic")
                : ("normal", "Normal"),
            "rr" => numeric < 8 || numeric > 30 ? ("critical", numeric < 8 ? "Apneic" : "Severe Tachypnea")
                : numeric < 12 || numeric > 20 ? ("warning", numeric < 12 ? "Bradypnea" : "Tachypnea")
                : ("normal", "Normal"),
            "temp" => numeric < 35.0m || numeric >= 39.5m ? ("critical", numeric < 35.0m ? "Hypothermic" : "High Fever")
                : numeric < 36.5m || numeric >= 38.0m ? ("warning", numeric < 36.5m ? "Subnormal" : "Febrile")
                : ("normal", "Afebrile"),
            "o2" => numeric < 90 ? ("critical", "Severe Hypoxia")
                : numeric < 95 ? ("warning", "Hypoxic")
                : ("normal", "Normal"),
            _ => ("normal", "Normal")
        };

        return new VitalEntryDto(numeric.Value.ToString("0.#"), numeric, status, label);
    }

    private static decimal? Number(string? value)
    {
        var match = Regex.Match(value ?? "", @"[-+]?\d+(?:\.\d+)?");
        return match.Success && decimal.TryParse(match.Value, out var parsed) ? parsed : null;
    }
}
