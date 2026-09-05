
using CLARA.Backend.Ingestion;
using CLARA.Backend.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile("appsettings.Development.local.json", optional: true, reloadOnChange: true);

var connectionString = builder.Configuration.GetConnectionString("ClaraDatabase")
    ?? throw new InvalidOperationException("Connection string 'ClaraDatabase' is required.");

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddDbContext<ClaraDbContext>(options => options.UseNpgsql(connectionString));

// Register ingestion service for PDF text extraction
builder.Services.AddScoped<PdfIngestionService>();
builder.Services.AddSingleton<PdfParser>();
builder.Services.AddSingleton<ClinicalTextExtractor>();
builder.Services.AddSingleton<PatientDocumentSyncProgress>();
builder.Services.AddScoped<PatientDocumentSyncService>();
builder.Services.AddHostedService<PatientDocumentSyncWorker>();
builder.Services.AddHostedService<PatientDocumentDesktopNotificationWorker>();

builder.Services.AddCors(o =>
    o.AddDefaultPolicy(p =>
        p.WithOrigins("http://localhost:3000", "http://127.0.0.1:3000").AllowAnyHeader().AllowAnyMethod()));

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ClaraDbContext>();
    db.Database.Migrate();
}

// Middleware
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

var urls = builder.Configuration["ASPNETCORE_URLS"] ?? string.Empty;
var hasHttpsEndpoint = urls.Contains("https://", StringComparison.OrdinalIgnoreCase)
    || !string.IsNullOrWhiteSpace(builder.Configuration["ASPNETCORE_HTTPS_PORT"]);

if (hasHttpsEndpoint)
{
    app.UseHttpsRedirection();
}

app.UseCors();

app.UseAuthorization();

app.MapControllers();

app.Run();
