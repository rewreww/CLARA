using Microsoft.AspNetCore.Mvc;
using CLARA.Backend.Infrastructure.Services;

namespace CLARA.Backend.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ChatController : ControllerBase
    {
        private readonly OllamaService _ollamaService;

        public ChatController()
        {
            _ollamaService = new OllamaService();
        }

        [HttpPost("ask")]
        public async Task<IActionResult> Ask([FromBody] string prompt)
        {
            var result = await _ollamaService.AskLLM(prompt);
            return Ok(result);
        }
    }
}