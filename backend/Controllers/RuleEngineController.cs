using CLARA.Backend.Application.DTOs;
using CLARA.Backend.Application.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace CLARA.Backend.Controllers;

/// <summary>
/// Controller for evaluating rule-based clinical logic.
/// </summary>
[ApiController]
[Route("api/rules/[controller]")]
public class RuleEngineController : ControllerBase
{
    private readonly IRuleEngine _ruleEngine;

    public RuleEngineController(IRuleEngine ruleEngine)
    {
        _ruleEngine = ruleEngine;
    }

    /// <summary>
    /// Evaluates clinical rules based on patient data.
    /// </summary>
    /// <param name="patientData">Patient input data.</param>
    /// <returns>Rule evaluation result.</returns>
    [HttpPost("evaluate")]
    [ProducesResponseType(typeof(RuleEvaluationDto), 200)]
    public IActionResult EvaluateRules([FromBody] PatientInputDto patientData)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        var result = _ruleEngine.EvaluateRules(patientData);
        return Ok(result);
    }
}