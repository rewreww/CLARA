using System.Diagnostics;
using System.Threading.Channels;

namespace CLARA.Backend.Ingestion;

public sealed class PatientDocumentDesktopNotificationWorker(
    PatientDocumentSyncProgress progress,
    IConfiguration configuration,
    ILogger<PatientDocumentDesktopNotificationWorker> logger) : BackgroundService
{
    private const int NotificationSeconds = 7;
    private readonly Channel<PatientDocumentSyncEvent> _events =
        Channel.CreateUnbounded<PatientDocumentSyncEvent>();
    private Process? _nativeNotifierProcess;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var enabled = configuration.GetValue("PatientDocumentSync:DesktopNotificationsEnabled", true);
        if (!enabled)
        {
            logger.LogInformation("Patient document desktop notifications are disabled.");
            return;
        }

        if (!OperatingSystem.IsWindows())
        {
            logger.LogInformation("Patient document desktop notifications require Windows.");
            return;
        }

        StartNativeNotifierServer();
        progress.EventAdded += QueueEvent;
        try
        {
            await foreach (var syncEvent in _events.Reader.ReadAllAsync(stoppingToken))
            {
                if (!ShouldNotify(syncEvent))
                {
                    continue;
                }

                ShowDesktopNotification(syncEvent);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
        finally
        {
            progress.EventAdded -= QueueEvent;
            StopNativeNotifierServer();
        }
    }

    private void QueueEvent(PatientDocumentSyncEvent syncEvent)
    {
        _events.Writer.TryWrite(syncEvent);
    }

    private static bool ShouldNotify(PatientDocumentSyncEvent syncEvent)
    {
        return syncEvent.Level == "error" || !string.IsNullOrWhiteSpace(syncEvent.FileName);
    }

    private void ShowDesktopNotification(PatientDocumentSyncEvent syncEvent)
    {
        var title = BuildTitle(syncEvent);
        var body = BuildBody(syncEvent);
        if (!ShowNativeNotifier(title, body, syncEvent.Level))
        {
            logger.LogWarning("CLARA Windows App SDK notifier was not available; desktop notification was skipped.");
        }
    }

    private bool ShowNativeNotifier(string title, string body, string level)
    {
        var notifierPath = ResolveNotifierPath();
        if (string.IsNullOrWhiteSpace(notifierPath))
        {
            logger.LogWarning("CLARA Windows App SDK notifier was not found.");
            return false;
        }

        try
        {
            using var process = Process.Start(new ProcessStartInfo
            {
                FileName = notifierPath,
                UseShellExecute = false,
                CreateNoWindow = true,
                ArgumentList =
                {
                    "--title",
                    title,
                    "--body",
                    body,
                    "--level",
                    level,
                    "--duration",
                    (NotificationSeconds * 1000).ToString(),
                    "--icon",
                    ResolveIconPath() ?? ""
                }
            });

            return process is not null;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "CLARA Windows App SDK notifier failed.");
            return false;
        }
    }

    private void StartNativeNotifierServer()
    {
        var notifierPath = ResolveNotifierPath();
        if (string.IsNullOrWhiteSpace(notifierPath))
        {
            logger.LogWarning("CLARA Windows App SDK notifier was not found; desktop notifications will be skipped.");
            return;
        }

        try
        {
            var iconPath = ResolveIconPath();
            _nativeNotifierProcess = Process.Start(new ProcessStartInfo
            {
                FileName = notifierPath,
                UseShellExecute = false,
                CreateNoWindow = true,
                ArgumentList =
                {
                    "--background",
                    "--icon",
                    iconPath ?? ""
                }
            });
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "CLARA native notifier background process could not be started.");
        }
    }

    private void StopNativeNotifierServer()
    {
        try
        {
            if (_nativeNotifierProcess is not null && !_nativeNotifierProcess.HasExited)
            {
                _nativeNotifierProcess.Kill(entireProcessTree: true);
            }

            _nativeNotifierProcess?.Dispose();
        }
        catch (Exception ex)
        {
            logger.LogDebug(ex, "CLARA native notifier background process could not be stopped.");
        }
    }

    private string? ResolveNotifierPath()
    {
        var configuredPath = configuration["PatientDocumentSync:DesktopNotifierPath"];
        if (!string.IsNullOrWhiteSpace(configuredPath))
        {
            var expanded = Path.GetFullPath(Environment.ExpandEnvironmentVariables(configuredPath.Trim()));
            if (File.Exists(expanded))
            {
                return expanded;
            }
        }

        var repoRoot = FindRepoRoot();
        if (repoRoot is null)
        {
            return null;
        }

        var candidates = new[]
        {
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Debug", "net8.0-windows10.0.17763.0", "win-x64", "CLARA.Notifier.exe"),
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Release", "net8.0-windows10.0.17763.0", "win-x64", "CLARA.Notifier.exe"),
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Debug", "net8.0-windows10.0.17763.0", "CLARA.Notifier.exe"),
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Release", "net8.0-windows10.0.17763.0", "CLARA.Notifier.exe"),
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Debug", "net8.0-windows", "CLARA.Notifier.exe"),
            Path.Combine(repoRoot, "tools", "CLARA.Notifier", "bin", "Release", "net8.0-windows", "CLARA.Notifier.exe")
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private string? ResolveIconPath()
    {
        var repoRoot = FindRepoRoot();
        if (repoRoot is null)
        {
            return null;
        }

        var iconPath = Path.Combine(repoRoot, "backend", "Assets", "clara-notification.ico");
        return File.Exists(iconPath) ? iconPath : null;
    }

    private static string? FindRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "backend", "CLARA.Backend.csproj"))
                && Directory.Exists(Path.Combine(directory.FullName, "tools", "CLARA.Notifier")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        return null;
    }

    private static string BuildTitle(PatientDocumentSyncEvent syncEvent)
    {
        if (syncEvent.Level == "error") return "CLARA sync needs attention";
        if (syncEvent.Message.Contains("Deleted PDF data removed", StringComparison.OrdinalIgnoreCase)) return "CLARA PDF removed";
        if (syncEvent.Message.Contains("successfully saved", StringComparison.OrdinalIgnoreCase)) return "CLARA PDF saved";
        return "CLARA PDF sync";
    }

    private static string BuildBody(PatientDocumentSyncEvent syncEvent)
    {
        var context = string.Join(" / ", new[] { syncEvent.PatientId, syncEvent.FileName }
            .Where(value => !string.IsNullOrWhiteSpace(value)));
        return string.IsNullOrWhiteSpace(context)
            ? syncEvent.Message
            : $"{context}: {syncEvent.Message}";
    }

}
