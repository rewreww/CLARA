using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace CLARA.Backend.Controllers;

/// <summary>
/// Controller for handling ML-based predictions.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class PredictionController : ControllerBase
{
    private readonly IMLService _mlService;

    public PredictionController(IMLService mlService)
    {
        _mlService = mlService;
    }

    /// <summary>
    /// Gets a prediction based on patient data.
    /// </summary>
    /// <param name="patientData">Patient input data.</param>
    /// <returns>Prediction result.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(PredictionResultDto), 200)]
    public async Task<IActionResult> PostPredict([FromBody] PatientInputDto patientData)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        var result = await _mlService.PredictAsync(patientData);
        return Ok(result);
    }
}