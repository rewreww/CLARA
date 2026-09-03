using System.Collections.Concurrent;

namespace CLARA.Backend.Ingestion;

public sealed class PatientDocumentSyncProgress
{
    private const int MaxEvents = 80;
    private readonly ConcurrentQueue<PatientDocumentSyncEvent> _events = new();
    private long _nextSequence;

    public void Info(string message, string? patientId = null, string? fileName = null) =>
        Add("info", message, patientId, fileName);

    public void Working(string message, string? patientId = null, string? fileName = null) =>
        Add("working", message, patientId, fileName);

    public void Success(string message, string? patientId = null, string? fileName = null) =>
        Add("success", message, patientId, fileName);

    public void Error(string message, string? patientId = null, string? fileName = null) =>
        Add("error", message, patientId, fileName);

    public IReadOnlyList<PatientDocumentSyncEvent> Snapshot(long afterSequence = 0)
    {
        return _events
            .Where(item => item.Sequence > afterSequence)
            .OrderBy(item => item.Sequence)
            .ToList();
    }

    private void Add(string level, string message, string? patientId, string? fileName)
    {
        _events.Enqueue(new PatientDocumentSyncEvent(
            Sequence: Interlocked.Increment(ref _nextSequence),
            Level: level,
            Message: message,
            PatientId: patientId,
            FileName: fileName,
            TimestampUtc: DateTimeOffset.UtcNow));

        while (_events.Count > MaxEvents && _events.TryDequeue(out _))
        {
        }
    }
}

public sealed record PatientDocumentSyncEvent(
    long Sequence,
    string Level,
    string Message,
    string? PatientId,
    string? FileName,
    DateTimeOffset TimestampUtc);
