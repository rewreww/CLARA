using CLARA.Backend.Ingestion;
using Microsoft.AspNetCore.Mvc;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PdfIngestionController : ControllerBase
{
    private readonly PdfIngestionService _pdfIngestionService;

    public PdfIngestionController(PdfIngestionService pdfIngestionService)
    {
        _pdfIngestionService = pdfIngestionService;
    }

    public sealed record ExtractTextRequest(string FolderName);
    public sealed record ExtractTextResponse(string FolderName, IReadOnlyList<ExtractedPdfResult> Files);
    public sealed record ExtractedPdfResult(string FilePath, string Text);

    [HttpPost("extract")]
    [ProducesResponseType(typeof(ExtractTextResponse), 200)]
    public IActionResult Extract([FromBody] ExtractTextRequest request)
    {
        if (request is null || string.IsNullOrWhiteSpace(request.FolderName))
        {
            return BadRequest(new { error = "FolderName is required." });
        }

        try
        {
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
}
