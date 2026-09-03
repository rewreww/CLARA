using CLARA.Backend.Ingestion;
using CLARA.Backend.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Mvc;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PdfIngestionController : ControllerBase
{
    private readonly PdfIngestionService _pdfIngestionService;
    private readonly PatientDocumentSyncService _patientDocumentSyncService;
    private readonly PatientDocumentSyncProgress _syncProgress;
    private readonly ClaraDbContext _db;

    public PdfIngestionController(
        PdfIngestionService pdfIngestionService,
        PatientDocumentSyncService patientDocumentSyncService,
        PatientDocumentSyncProgress syncProgress,
        ClaraDbContext db)
    {
        _pdfIngestionService = pdfIngestionService;
        _patientDocumentSyncService = patientDocumentSyncService;
        _syncProgress = syncProgress;
        _db = db;
    }

    public sealed record ExtractTextRequest(string FolderName);
    public sealed record ExtractTextResponse(string FolderName, IReadOnlyList<ExtractedPdfResult> Files);
    public sealed record ExtractedPdfResult(string FilePath, string Text);
    public sealed record PatientFoldersResponse(IReadOnlyList<string> Patients);
    public sealed record SyncRequest(string? FolderName);
    public sealed record SyncProgressResponse(IReadOnlyList<PatientDocumentSyncEvent> Events);

    [HttpGet("patients")]
    [ProducesResponseType(typeof(PatientFoldersResponse), 200)]
    public IActionResult Patients()
    {
        var patients = _pdfIngestionService.ListPatientFolders();
        return Ok(new PatientFoldersResponse(patients));
    }

    [HttpPost("extract")]
    [ProducesResponseType(typeof(ExtractTextResponse), 200)]
    public async Task<IActionResult> Extract([FromBody] ExtractTextRequest request, CancellationToken cancellationToken)
    {
        if (request is null || string.IsNullOrWhiteSpace(request.FolderName))
        {
            return BadRequest(new { error = "FolderName is required." });
        }

        try
        {
            var storedFiles = await _db.PatientDocuments
                .AsNoTracking()
                .Where(document => document.PatientId == request.FolderName
                    && document.ExtractionStatus == "completed"
                    && document.ExtractedText != null)
                .OrderBy(document => document.RelativePath)
                .Select(document => new ExtractedPdfResult(document.RelativePath, document.ExtractedText!))
                .ToListAsync(cancellationToken);

            if (storedFiles.Count > 0)
            {
                return Ok(new ExtractTextResponse(request.FolderName, storedFiles));
            }

            var files = _pdfIngestionService.ExtractTextFromFolder(request.FolderName);
            return Ok(new ExtractTextResponse(request.FolderName, files.Select(x => new ExtractedPdfResult(x.FilePath, x.Text)).ToList()));
        }
        catch (DirectoryNotFoundException ex)
        {
            return NotFound(new { error = ex.Message });
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { error = "Failed to extract text from PDF folder.", details = ex.Message });
        }
    }

    [HttpPost("sync")]
    [ProducesResponseType(typeof(PatientDocumentSyncResult), 200)]
    public async Task<IActionResult> Sync([FromBody] SyncRequest? request, CancellationToken cancellationToken)
    {
        try
        {
            var result = await _patientDocumentSyncService.SyncAsync(request?.FolderName, cancellationToken);
            return Ok(result);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpGet("sync/status")]
    [ProducesResponseType(typeof(SyncProgressResponse), 200)]
    public IActionResult SyncStatus([FromQuery] long after = 0)
    {
        return Ok(new SyncProgressResponse(_syncProgress.Snapshot(after)));
    }
}
