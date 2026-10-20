using CLARA.Backend.Data;
using CLARA.Backend.Ingestion;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/patientdata/{patientId}/document")]
public sealed class DocumentPreviewController(ClaraDbContext db, IConfiguration configuration) : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> Get(string patientId, [FromQuery] string source, CancellationToken cancellationToken)
    {
        // Only serve a document registered to this patient, never an arbitrary client path.
        if (string.IsNullOrWhiteSpace(patientId) || patientId is "." or ".."
            || patientId.IndexOfAny(['/', '\\', ':']) >= 0 || string.IsNullOrWhiteSpace(source)) return NotFound();
        var document = await db.PatientDocuments.AsNoTracking().SingleOrDefaultAsync(
            item => item.PatientId == patientId && item.RelativePath == source, cancellationToken);
        if (document is null) return NotFound();

        var root = Path.GetFullPath(PatientDocumentSyncService.ResolvePatientsFolderPath(configuration));
        var patientRoot = Path.GetFullPath(Path.Combine(root, patientId));
        var path = Path.GetFullPath(Path.Combine(patientRoot, document.RelativePath));
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!path.StartsWith(patientRoot + Path.DirectorySeparatorChar, comparison)
            || !string.Equals(Path.GetExtension(path), ".pdf", StringComparison.OrdinalIgnoreCase)
            || !System.IO.File.Exists(path)) return NotFound();

        // Reject links/junctions so a registered relative path cannot escape the patient folder.
        for (var current = path; current != null; current = Path.GetDirectoryName(current))
        {
            if ((System.IO.File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return NotFound();
            if (string.Equals(current, root, comparison)) break;
        }
        Response.Headers.CacheControl = "no-store";
        Response.Headers["X-Content-Type-Options"] = "nosniff";
        return PhysicalFile(path, "application/pdf", enableRangeProcessing: true);
    }
}
