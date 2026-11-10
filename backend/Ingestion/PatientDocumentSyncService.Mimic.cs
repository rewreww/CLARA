using System.Globalization;
using System.Text.Json;
using CLARA.Backend.Data;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Ingestion;

public sealed partial class PatientDocumentSyncService
{
    private async Task SyncMimicFileAsync(PatientRecord patient, string path, string relative,
        MutableSyncResult result, CancellationToken token)
    {
        var file = new FileInfo(path);
        var document = await _db.PatientDocuments.SingleOrDefaultAsync(x => x.PatientId == patient.Id && x.RelativePath == relative, token);
        var info = document is null ? null : await _db.MimicDocuments.SingleOrDefaultAsync(x => x.DocumentId == document.Id, token);
        // The export is immutable during validation. Changed files get a fresh hash
        // and atomic reparse; parser upgrades invalidate the cached extraction.
        if (document?.ExtractionStatus == "completed" && info?.ParserVersion == MimicPdfParser.VersionFor(relative)
            && document.FileSizeBytes == file.Length && document.SourceModifiedAtUtc is { } storedTime
            // PostgreSQL stores microseconds; Windows file times have 100 ns ticks.
            && Math.Abs((storedTime - new DateTimeOffset(file.LastWriteTimeUtc)).Ticks) < 10)
        {
            result.FilesUnchanged++;
            if (document is not null) _db.Entry(document).State = EntityState.Detached;
            if (info is not null) _db.Entry(info).State = EntityState.Detached;
            return;
        }
        var hash = await ComputeSha256Async(path, token);
        using var parsed = await _mimicParser.ParseAsync(path, patient.Id, relative, token);
        var data = parsed.RootElement;
        await using var transaction = await _db.Database.BeginTransactionAsync(token);
        var now = DateTimeOffset.UtcNow;
        var created = document is null;
        document ??= new PatientDocument { Id = Guid.NewGuid(), PatientId = patient.Id, RelativePath = relative, CreatedAtUtc = now };
        if (created) _db.PatientDocuments.Add(document);
        document.FileName = file.Name;
        document.DocumentType = "mimic_pdf";
        document.ContentHash = hash;
        document.FileSizeBytes = file.Length;
        document.SourceModifiedAtUtc = file.LastWriteTimeUtc;
        document.ExtractedText = data.GetProperty("text").GetString();
        document.ExtractionStatus = "completed";
        document.ExtractedAtUtc = document.UpdatedAtUtc = now;
        document.RecordDate = _clinicalTextExtractor.ExtractDateFromPath(relative);
        patient.UpdatedAtUtc = now;
        info ??= new MimicDocumentInfo { DocumentId = document.Id };
        if (_db.Entry(info).State == EntityState.Detached) _db.MimicDocuments.Add(info);
        info.AdmissionId = data.GetProperty("admission").GetString();
        info.Category = data.GetProperty("category").GetString()!;
        info.RecordType = data.GetProperty("record_type").GetString()!;
        info.Fluid = data.GetProperty("fluid").GetString();
        info.ParserVersion = MimicPdfParser.VersionFor(relative);
        info.MetadataJson = data.GetProperty("metadata").GetRawText();
        info.Pages = data.GetProperty("pages").GetInt32();
        await _db.MimicRows.Where(x => x.DocumentId == document.Id).ExecuteDeleteAsync(token);
        var inserted = new List<MimicPdfRow>();
        foreach (var row in data.GetProperty("rows").EnumerateArray())
        {
            string S(string name) => row.GetProperty(name).ValueKind == JsonValueKind.Null ? "" : row.GetProperty(name).GetString() ?? "";
            decimal? N(string name) => row.GetProperty(name).ValueKind == JsonValueKind.Number && row.GetProperty(name).TryGetDecimal(out var n) ? n : null;
            var cells = row.GetProperty("cells");
            var record = new MimicPdfRow {
                DocumentId = document.Id, PatientId = patient.Id, AdmissionId = info.AdmissionId,
                Category = info.Category, RecordType = info.RecordType, Page = row.GetProperty("page").GetInt32(),
                RowNumber = row.GetProperty("row").GetInt32(), Label = S("label"),
                ObservedAt = DateTime.TryParse(S("observed_at"), CultureInfo.InvariantCulture, DateTimeStyles.None, out var at) ? DateTime.SpecifyKind(at, DateTimeKind.Unspecified) : null,
                RawValue = S("value"), NumericValue = N("numeric"), Unit = S("unit"),
                ReferenceLow = N("reference_low"), ReferenceHigh = N("reference_high"),
                SourceFlag = S("source_flag"), Flag = row.GetProperty("flag").GetString(),
                CellsJson = cells.GetRawText(), SearchText = string.Join(" ", cells.EnumerateObject().Select(x => x.Value.GetString()))
            };
            inserted.Add(record);
        }
        _db.MimicRows.AddRange(inserted);
        await _db.SaveChangesAsync(token);
        await transaction.CommitAsync(token);
        result.FilesExtracted++;
        result.StructuredItemsSaved += inserted.Count;
        if (created) result.DocumentsCreated++;
        _progress.Success($"Parsed {inserted.Count} PDF table rows", patient.Id, file.Name);
        // Notify only after the new chemistry document and extracted results are committed.
        // Updates and unchanged files must not be reported as newly added lab tests.
        if (created && info.Category == "chemistry" && inserted.Count > 0)
        {
            _progress.Success($"New chemistry lab test added ({inserted.Count} results)", patient.Id, file.Name);
        }
        foreach (var row in inserted) _db.Entry(row).State = EntityState.Detached;
        _db.Entry(info).State = EntityState.Detached;
        _db.Entry(document).State = EntityState.Detached;
    }
}
