using System.Collections.Concurrent;

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

        var intervalMinutes = Math.Clamp(configuration.GetValue("PatientDocumentSync:IntervalMinutes", 1), 1, 1440);
        var interval = TimeSpan.FromMinutes(intervalMinutes);
        var debounceSeconds = Math.Clamp(configuration.GetValue("PatientDocumentSync:DebounceSeconds", 4), 1, 60);
        var debounce = TimeSpan.FromSeconds(debounceSeconds);
        var patientsFolderPath = PatientDocumentSyncService.ResolvePatientsFolderPath(configuration);
        var pendingPatientIds = new ConcurrentDictionary<string, byte>(StringComparer.OrdinalIgnoreCase);
        using var syncSignal = new SemaphoreSlim(0, 1);
        using var watcher = TryCreateWatcher(patientsFolderPath, pendingPatientIds, syncSignal);

        if (watcher is null)
        {
            logger.LogWarning(
                "Patient document folder watcher is inactive because the folder does not exist: {PatientsFolderPath}",
                patientsFolderPath);
        }
        else
        {
            logger.LogInformation("Watching patient PDF folder for changes: {PatientsFolderPath}", patientsFolderPath);
        }

        while (!stoppingToken.IsCancellationRequested)
        {
            await RunPendingSyncAsync(pendingPatientIds, stoppingToken);

            var signalTask = syncSignal.WaitAsync(stoppingToken);
            var intervalTask = Task.Delay(interval, stoppingToken);
            var completed = await Task.WhenAny(signalTask, intervalTask);
            if (completed == signalTask)
            {
                await signalTask;
                await Task.Delay(debounce, stoppingToken);
                DrainSignal(syncSignal);
            }
        }

        async Task RunPendingSyncAsync(
            ConcurrentDictionary<string, byte> queuedPatientIds,
            CancellationToken cancellationToken)
        {
            var patientIds = queuedPatientIds.Keys.ToList();
            foreach (var patientId in patientIds)
            {
                queuedPatientIds.TryRemove(patientId, out _);
            }

            if (patientIds.Count == 0)
            {
                await RunSyncAsync(null, cancellationToken);
                return;
            }

            foreach (var patientId in patientIds.Order(StringComparer.OrdinalIgnoreCase))
            {
                await RunSyncAsync(patientId, cancellationToken);
            }
        }

        async Task RunSyncAsync(string? patientId, CancellationToken cancellationToken)
        {
            try
            {
                using var scope = scopeFactory.CreateScope();
                var syncService = scope.ServiceProvider.GetRequiredService<PatientDocumentSyncService>();
                var result = await syncService.SyncAsync(patientId, cancellationToken);
                logger.LogInformation(
                    "Patient document sync finished: {PatientId} {FilesSeen} seen, {FilesExtracted} extracted, {StructuredItemsSaved} structured records saved, {FilesUnchanged} unchanged, {FailedFiles} failed.",
                    patientId ?? "all-patients",
                    result.FilesSeen,
                    result.FilesExtracted,
                    result.StructuredItemsSaved,
                    result.FilesUnchanged,
                    result.FailedFiles);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Patient document background sync failed.");
            }
        }
    }

    private FileSystemWatcher? TryCreateWatcher(
        string patientsFolderPath,
        ConcurrentDictionary<string, byte> pendingPatientIds,
        SemaphoreSlim syncSignal)
    {
        if (!Directory.Exists(patientsFolderPath))
        {
            return null;
        }

        var watcher = new FileSystemWatcher(patientsFolderPath)
        {
            IncludeSubdirectories = true,
            Filter = "*",
            NotifyFilter = NotifyFilters.FileName
                | NotifyFilters.DirectoryName
                | NotifyFilters.LastWrite
                | NotifyFilters.Size
                | NotifyFilters.CreationTime,
            EnableRaisingEvents = true
        };

        FileSystemEventHandler queueChangedPath = (_, args) =>
            QueueSyncForPath(patientsFolderPath, args.FullPath, pendingPatientIds, syncSignal);
        RenamedEventHandler queueRenamedPath = (_, args) =>
            QueueSyncForPath(patientsFolderPath, args.FullPath, pendingPatientIds, syncSignal);

        watcher.Created += queueChangedPath;
        watcher.Changed += queueChangedPath;
        watcher.Renamed += queueRenamedPath;
        watcher.Error += (_, args) =>
        {
            logger.LogWarning(args.GetException(), "Patient document folder watcher failed; timed sync will continue.");
            ReleaseSignal(syncSignal);
        };

        return watcher;
    }

    private static void QueueSyncForPath(
        string patientsFolderPath,
        string path,
        ConcurrentDictionary<string, byte> pendingPatientIds,
        SemaphoreSlim syncSignal)
    {
        if (!IsRelevantChange(path))
        {
            return;
        }

        var patientId = TryGetPatientId(patientsFolderPath, path);
        if (!string.IsNullOrWhiteSpace(patientId))
        {
            pendingPatientIds[patientId] = 0;
        }

        ReleaseSignal(syncSignal);
    }

    private static bool IsRelevantChange(string path)
    {
        return Directory.Exists(path)
            || string.Equals(Path.GetExtension(path), ".pdf", StringComparison.OrdinalIgnoreCase);
    }

    private static string? TryGetPatientId(string patientsFolderPath, string path)
    {
        var relativePath = Path.GetRelativePath(patientsFolderPath, path);
        if (relativePath.StartsWith("..", StringComparison.Ordinal) || Path.IsPathRooted(relativePath))
        {
            return null;
        }

        var parts = relativePath.Split(
            [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
            StringSplitOptions.RemoveEmptyEntries);
        return parts.Length > 0 ? parts[0] : null;
    }

    private static void ReleaseSignal(SemaphoreSlim syncSignal)
    {
        try
        {
            syncSignal.Release();
        }
        catch (SemaphoreFullException)
        {
        }
    }

    private static void DrainSignal(SemaphoreSlim syncSignal)
    {
        while (syncSignal.Wait(0))
        {
        }
    }
}
