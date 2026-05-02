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
builder.Services.AddScoped<OllamaService>();
builder.Services.AddScoped<IMLService, MLService>();
builder.Services.AddScoped<IRuleEngine, RuleEngineService>();

// Register ingestion service for PDF text extraction
builder.Services.AddScoped<PdfIngestionService>();

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
