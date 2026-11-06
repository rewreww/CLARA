using System.Diagnostics;
using System.Text.Json;

namespace CLARA.Backend.Ingestion;

// One local worker, no network/model calls, no source CSV access.
public sealed class MimicPdfParser(IConfiguration configuration, IWebHostEnvironment environment) : IDisposable
{
    public const string Version = "mimic-grid-v1";
    public static string VersionFor(string relative) => relative.Replace('\\', '/').Split('/').Contains("Microbiology")
        ? "mimic-grid-v2" : Version;
    private readonly SemaphoreSlim gate = new(1, 1);
    private Process? worker;

    public async Task<JsonDocument> ParseAsync(string path, string patient, string relative, CancellationToken cancellationToken)
    {
        await gate.WaitAsync(cancellationToken);
        try
        {
            if (worker is null || worker.HasExited)
            {
                worker?.Dispose();
                var root = Path.GetFullPath(Path.Combine(environment.ContentRootPath, ".."));
                var start = new ProcessStartInfo(configuration["PatientDocumentSync:PythonPath"] ?? Path.Combine(root, ".venv", "Scripts", "python.exe"))
                {
                    UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardInput = true, RedirectStandardOutput = true,
                    WorkingDirectory = root
                };
                start.ArgumentList.Add("-u");
                start.ArgumentList.Add(Path.Combine(root, "ai-services", "mimic_pdf.py"));
                worker = Process.Start(start) ?? throw new InvalidOperationException("Cannot start MIMIC PDF parser");
            }
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromMinutes(5));
            await worker.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { path, patient, relative }));
            await worker.StandardInput.FlushAsync(timeout.Token);
            var line = await worker.StandardOutput.ReadLineAsync(timeout.Token)
                ?? throw new InvalidOperationException("MIMIC PDF parser exited without a result");
            var result = JsonDocument.Parse(line);
            if (result.RootElement.TryGetProperty("error", out var error))
            {
                var message = error.GetString();
                result.Dispose();
                throw new InvalidDataException(message);
            }
            return result;
        }
        catch
        {
            if (worker is { HasExited: false }) worker.Kill(true);
            worker?.Dispose();
            worker = null;
            throw;
        }
        finally { gate.Release(); }
    }

    public void Dispose()
    {
        if (worker is { HasExited: false }) worker.Kill(true);
        worker?.Dispose();
        gate.Dispose();
    }
}
