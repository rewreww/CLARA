using CLARA.Backend.Data;
using CLARA.Backend.Controllers;
using CLARA.Backend.Ingestion;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using System.Text.Json;

// Audit only: no migrations, ingestion, SaveChanges, or patient-value output.
var configuration = new ConfigurationBuilder()
    .SetBasePath(Path.GetFullPath("backend"))
    .AddJsonFile("appsettings.json")
    .AddJsonFile("appsettings.Development.local.json", optional: true)
    .AddEnvironmentVariables()
    .Build();
var options = new DbContextOptionsBuilder<ClaraDbContext>()
    .UseNpgsql(configuration.GetConnectionString("ClaraDatabase")).Options;
await using var db = new ClaraDbContext(options);
await db.Database.OpenConnectionAsync();
await db.Database.ExecuteSqlRawAsync("SET default_transaction_read_only = on");
var pending = (await db.Database.GetPendingMigrationsAsync()).ToArray();
Console.WriteLine(JsonSerializer.Serialize(new {
    pendingMigrations = pending.Length,
    patients = await db.Patients.CountAsync(),
    documents = await db.PatientDocuments.CountAsync(),
    failedDocuments = await db.PatientDocuments.CountAsync(d => d.ExtractionStatus == "failed"),
    labs = await db.LabResults.CountAsync(),
    dischargeSummaries = await db.DischargeSummaries.CountAsync()
}));
var controller = new PatientDataController(db);
var patients = await controller.Patients(default);
Console.WriteLine($"Patient list controller: PASS ({patients.Patients.Count} records)");
foreach (var patient in patients.Patients)
{
    var req = new PatientDataController.DischargeRequest(patient.Id, null);
    await controller.ChemistryResults(new(patient.Id, "chemistry"), default);
    await controller.HematologyResults(new(patient.Id, "hematology"), default);
    await controller.MicroscopyResults(new(patient.Id, "microscopy"), default);
    await controller.DischargeList(req, default);
    await controller.DischargeParsed(req, default);
    await controller.Vitals(req, default);
    await controller.VitalsTimeline(req, default);
    await controller.RagContext(patient.Id, default);
}
Console.WriteLine("Read-only controller smoke checks: PASS (8 calls per patient)");

// Reproduce the exact semaphore/WhenAny pattern used by the sync worker.
using var signal = new SemaphoreSlim(0, 1);
var abandonedWait = signal.WaitAsync();
await Task.WhenAny(abandonedWait, Task.Delay(10));
var currentWait = signal.WaitAsync();
signal.Release();
Console.WriteLine($"Sync worker pattern: abandoned waiter consumed event={abandonedWait.IsCompleted}; current waiter awakened={currentWait.IsCompleted}");

var extractor = new ClinicalTextExtractor();
var labs = extractor.ExtractLabResults("CREATININE 1.2 mg/dL", "chemistry");
Console.WriteLine($"Production C# parser synthetic lab count: {labs.Count}");
var discharge = extractor.ParseDischarge("FINAL DIAGNOSIS:\nSYNTHETIC DIAGNOSIS\nCHIEF COMPLAINT:\nSYNTHETIC COMPLAINT");
Console.WriteLine($"Production C# parser synthetic diagnosis boundary: {discharge.FinalDiagnosis == "SYNTHETIC DIAGNOSIS"}");
