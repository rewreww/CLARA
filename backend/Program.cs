using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using CLARA.Backend.Domain.Entities;
using CLARA.Backend.Infrastructure.Services;
using CLARA.Backend.Ingestion;

using FluentValidation;
using FluentValidation.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();

// Register FluentValidation
builder.Services.AddValidatorsFromAssemblyContaining<PatientInputDto>();
builder.Services.AddFluentValidationAutoValidation();
builder.Services.AddFluentValidationClientsideAdapters();

// Register application services
builder.Services.AddScoped<ILLMService, LLMService>();
builder.Services.AddScoped<IMLService, MLService>();
builder.Services.AddScoped<IRuleEngine, RuleEngineService>();

// Register FileWatcherService
builder.Services.AddHostedService<FileWatcherService>();

// ✅ Register Command Console Service (NEW)
builder.Services.AddHostedService<CommandConsoleService>();

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// Middleware
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();


// =====================================================
// ✅ COMMAND CONSOLE SERVICE (ADD THIS BELOW)
// =====================================================

public class CommandConsoleService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        Console.WriteLine("\n[Command Console Ready]");
        Console.WriteLine("Type: parse | exit\n");

        while (!stoppingToken.IsCancellationRequested)
        {
            var input = Console.ReadLine();

            if (input == "parse")
            {
                RunManualParser();
            }
            else if (input == "exit")
            {
                Console.WriteLine("Shutting down...");
                Environment.Exit(0);
            }

            await Task.Delay(100, stoppingToken);
        }
    }

    private void RunManualParser()
    {
        var folderPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            "Patients"
        );

        if (!Directory.Exists(folderPath))
        {
            Console.WriteLine("[ERROR] Patients folder not found.");
            return;
        }

        var pdfFiles = Directory.GetFiles(folderPath, "*.pdf");

        if (pdfFiles.Length == 0)
        {
            Console.WriteLine("[INFO] No PDF files found.");
            return;
        }

        Console.WriteLine("\nAvailable PDF files:");

        for (int i = 0; i < pdfFiles.Length; i++)
        {
            Console.WriteLine($"{i}: {Path.GetFileName(pdfFiles[i])}");
        }

        Console.Write("\nSelect file index: ");

        if (!int.TryParse(Console.ReadLine(), out int index) || index < 0 || index >= pdfFiles.Length)
        {
            Console.WriteLine("[ERROR] Invalid selection.");
            return;
        }

        var selectedFile = pdfFiles[index];

        Console.WriteLine($"\n[INFO] Parsing: {selectedFile}\n");

        var parser = new PdfParser();
        var text = parser.ExtractText(selectedFile);

        Console.WriteLine("----- EXTRACTED TEXT START -----\n");
        Console.WriteLine(text);
        Console.WriteLine("\n----- EXTRACTED TEXT END -----");
    }
}