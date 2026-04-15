using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace CLARA.Backend.Controllers;

/// <summary>
/// Controller for handling chat interactions with the AI system.
/// This implements the hybrid AI approach: LLM + ML + Rules.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class ChatController : ControllerBase
{
    private readonly ILLMService _llmService;
    private readonly IMLService _mlService;
    private readonly IRuleEngine _ruleEngine;

    public ChatController(ILLMService llmService, IMLService mlService, IRuleEngine ruleEngine)
    {
        _llmService = llmService;
        _mlService = mlService;
        _ruleEngine = ruleEngine;
    }

    /// <summary>
    /// Processes a chat request from the user, combining LLM, ML, and rule-based responses.
    /// </summary>
    /// <param name="request">The chat request containing patient data and query.</param>
    /// <returns>Combined AI response with reasoning and safety notes.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(ChatResponseDto), 200)]
    public async Task<IActionResult> PostChat([FromBody] ChatRequestDto request)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        // Step 1: Get LLM response (placeholder)
        var llmResponse = await _llmService.GenerateResponseAsync(request.Message, request.PatientData);

        // Step 2: Get ML prediction
        var prediction = await _mlService.PredictAsync(request.PatientData);

        // Step 3: Apply rule-based safety checks
        var ruleEvaluation = _ruleEngine.EvaluateRules(request.PatientData);

        // Step 4: Combine responses (placeholder logic)
        var combinedResponse = new ChatResponseDto
        {
            Response = $"{llmResponse.Response}\n\nPrediction: {prediction.Diagnosis} (Confidence: {prediction.Confidence:P})\n\nSafety Flags: {string.Join(", ", ruleEvaluation.Flags)}",
            Reasoning = $"LLM Reasoning: {llmResponse.Reasoning}\nML Model: Structured prediction based on patient vitals.\nRules: Applied clinical safety logic.",
            SafetyNote = "This system is for clinical decision support only and does not replace a licensed physician.",
            Timestamp = DateTime.UtcNow
        };

        return Ok(combinedResponse);
    }
}