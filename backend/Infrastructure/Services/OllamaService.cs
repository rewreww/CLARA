using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using CLARA.Backend.Models;

namespace CLARA.Backend.Infrastructure.Services
{
    public class OllamaService
    {
        private readonly HttpClient _httpClient;

        public OllamaService()
        {
            _httpClient = new HttpClient();
        }

        public async Task<string> AskLLM(string prompt)
        {
            var request = new
            {
                model = "llama3.2:1b",
                prompt = prompt,
                stream = false
            };

            var response = await _httpClient.PostAsJsonAsync(
                "http://localhost:11434/api/generate",
                request
            );

            var json = await response.Content.ReadAsStringAsync();

            var parsed = JsonSerializer.Deserialize<OllamaResponse>(json);

            return parsed?.response ?? "No response";
        }
    }
}