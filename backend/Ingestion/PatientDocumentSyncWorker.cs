namespace CLARA.Backend.Ingestion;

public sealed class PatientDocumentSyncWorker(
    IServiceScopeFactory scopeFactory,
    IConfiguration configuration,
    ILogger<PatientDocumentSyncWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var enabled = configuration.GetValue("PatientDocumentSync:Enabled", true);
        if (!enabled)
        {
            logger.LogInformation("Patient document background sync is disabled.");
            return;
        }

        var intervalMinutes = Math.Clamp(configuration.GetValue("PatientDocumentSync:IntervalMinutes", 15), 1, 1440);
        var interval = TimeSpan.FromMinutes(intervalMinutes);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                using var scope = scopeFactory.CreateScope();
                var syncService = scope.ServiceProvider.GetRequiredService<PatientDocumentSyncService>();
                var result = await syncService.SyncAsync(cancellationToken: stoppingToken);
                logger.LogInformation(
                    "Patient document sync finished: {FilesSeen} seen, {FilesExtracted} extracted, {StructuredItemsSaved} structured records saved, {FilesUnchanged} unchanged, {FailedFiles} failed.",
                    result.FilesSeen,
                    result.FilesExtracted,
                    result.StructuredItemsSaved,
                    result.FilesUnchanged,
                    result.FailedFiles);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Patient document background sync failed.");
            }

            await Task.Delay(interval, stoppingToken);
        }
    }
}
