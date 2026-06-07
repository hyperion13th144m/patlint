using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using PatlintAddin.Models;

namespace PatlintAddin.Services;

public class ApiClient : IDisposable
{
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(60) };

    public string BaseUrl { get; set; } = "http://localhost:8000";

    public async Task<string> CheckHealthAsync()
    {
        var resp = await _http.GetAsync($"{BaseUrl}/health");
        resp.EnsureSuccessStatusCode();
        var body = await resp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        return doc.RootElement.GetProperty("status").GetString() ?? "unknown";
    }

    public async Task<CheckResponse> CheckTextAsync(string text)
    {
        var payload = JsonSerializer.Serialize(new { text, source = "vsto-addin" });
        var content = new StringContent(payload, Encoding.UTF8, "application/json");
        var resp = await _http.PostAsync($"{BaseUrl}/api/check-text", content);
        resp.EnsureSuccessStatusCode();
        var result = await resp.Content.ReadFromJsonAsync<CheckResponse>();
        return result ?? new CheckResponse();
    }

    public void Dispose() => _http.Dispose();
}
