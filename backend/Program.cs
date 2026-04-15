using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using CLARA.Backend.Domain.Entities;
using CLARA.Backend.Infrastructure.Services;
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

// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();