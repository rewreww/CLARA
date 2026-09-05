using System.IO.Pipes;
using System.Text.Json;
using Microsoft.Windows.AppNotifications;
using Microsoft.Windows.AppNotifications.Builder;

namespace CLARA.Notifier;

internal static class Program
{
    private const string PipeName = "CLARA.Notifier.Sync";

    [STAThread]
    private static async Task Main(string[] args)
    {
        var runMode = NotifierRunMode.Parse(args);
        if (!OperatingSystem.IsWindows() || !AppNotificationManager.IsSupported())
        {
            return;
        }

        if (runMode.Background)
        {
            using var mutex = new Mutex(true, @"Local\CLARA.Notifier.Sync", out var createdNew);
            if (!createdNew)
            {
                return;
            }

            using var bridge = NotificationBridge.Create(runMode.IconPath);
            await bridge.RunPipeServerAsync(PipeName, CancellationToken.None);
            return;
        }

        if (runMode.Payload is not null && await TrySendToExistingInstanceAsync(runMode.Payload))
        {
            return;
        }

        using var oneShotBridge = NotificationBridge.Create(runMode.IconPath);
        if (runMode.Payload is not null)
        {
            oneShotBridge.Show(runMode.Payload);
            await Task.Delay(350);
        }
    }

    private static async Task<bool> TrySendToExistingInstanceAsync(NotificationPayload payload)
    {
        try
        {
            await using var client = new NamedPipeClientStream(
                ".",
                PipeName,
                PipeDirection.Out,
                PipeOptions.Asynchronous);
            await client.ConnectAsync(120);
            await JsonSerializer.SerializeAsync(client, payload);
            await client.FlushAsync();
            return true;
        }
        catch
        {
            return false;
        }
    }
}

internal sealed class NotificationBridge : IDisposable
{
    private const string DisplayName = "CLARA";
    private const string NotificationTag = "patient-documents";
    private const string NotificationGroup = "clara-sync";
    private readonly AppNotificationManager _manager;
    private bool _disposed;

    private NotificationBridge(AppNotificationManager manager)
    {
        _manager = manager;
    }

    public static NotificationBridge Create(string? iconPath)
    {
        var manager = AppNotificationManager.Default;
        manager.NotificationInvoked += (_, _) => { };

        var iconUri = TryBuildIconUri(iconPath);
        if (iconUri is not null)
        {
            manager.Register(DisplayName, iconUri);
        }
        else
        {
            manager.Register();
        }

        return new NotificationBridge(manager);
    }

    public async Task RunPipeServerAsync(string pipeName, CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                await using var server = new NamedPipeServerStream(
                    pipeName,
                    PipeDirection.In,
                    1,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous);

                await server.WaitForConnectionAsync(cancellationToken);
                var payload = await JsonSerializer.DeserializeAsync<NotificationPayload>(
                    server,
                    cancellationToken: cancellationToken);

                if (payload is not null)
                {
                    Show(payload);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (JsonException)
            {
            }
        }
    }

    public void Show(NotificationPayload payload)
    {
        var notification = new AppNotificationBuilder()
            .AddArgument("source", "clara-patient-document-sync")
            .AddText(payload.Title)
            .AddText(payload.Body)
            .BuildNotification();

        notification.Tag = NotificationTag;
        notification.Group = NotificationGroup;
        notification.Expiration = DateTimeOffset.Now.AddMilliseconds(payload.DurationMilliseconds);
        notification.Priority = payload.Level.Equals("error", StringComparison.OrdinalIgnoreCase)
            ? AppNotificationPriority.High
            : AppNotificationPriority.Default;

        _manager.Show(notification);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
    }

    private static Uri? TryBuildIconUri(string? iconPath)
    {
        if (string.IsNullOrWhiteSpace(iconPath))
        {
            return null;
        }

        try
        {
            var fullPath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(iconPath.Trim()));
            return File.Exists(fullPath) ? new Uri(fullPath) : null;
        }
        catch
        {
            return null;
        }
    }
}

internal sealed record NotificationPayload(
    string Title,
    string Body,
    string Level,
    int DurationMilliseconds)
{
    public static NotificationPayload Parse(IReadOnlyDictionary<string, string> values)
    {
        var duration = values.TryGetValue("duration", out var rawDuration)
            && int.TryParse(rawDuration, out var parsedDuration)
                ? Math.Clamp(parsedDuration, 1000, 30000)
                : 7000;

        return new NotificationPayload(
            Title: ValueOrDefault(values, "title", "CLARA"),
            Body: ValueOrDefault(values, "body", "Patient document sync update."),
            Level: ValueOrDefault(values, "level", "info"),
            DurationMilliseconds: duration);
    }

    private static string ValueOrDefault(
        IReadOnlyDictionary<string, string> values,
        string key,
        string fallback)
    {
        return values.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : fallback;
    }
}

internal sealed record NotifierRunMode(
    bool Background,
    NotificationPayload? Payload,
    string? IconPath)
{
    public static NotifierRunMode Parse(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (!args[index].StartsWith("--", StringComparison.Ordinal))
            {
                continue;
            }

            values[args[index][2..]] = args[index + 1];
            index++;
        }

        var background = args.Any(arg => arg.Equals("--background", StringComparison.OrdinalIgnoreCase));
        return new NotifierRunMode(
            Background: background,
            Payload: background ? null : NotificationPayload.Parse(values),
            IconPath: ValueOrDefault(values, "icon", null));
    }

    private static string? ValueOrDefault(
        IReadOnlyDictionary<string, string> values,
        string key,
        string? fallback)
        => values.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : fallback;
}
