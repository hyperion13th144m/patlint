using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using PatlintAddin.Models;

namespace PatlintAddin.Services
{
    public class ApiClient : IDisposable
    {
        private readonly HttpClient _http = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };
        private readonly HttpClient _streamHttp = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };

        public string BaseUrl { get; set; } = "http://localhost:8000";

        public async Task<string> CheckHealthAsync()
        {
            var resp = await _http.GetAsync(BaseUrl + "/health");
            resp.EnsureSuccessStatusCode();
            var body = await resp.Content.ReadAsStringAsync();
            using (var doc = JsonDocument.Parse(body))
                return doc.RootElement.GetProperty("status").GetString() ?? "unknown";
        }

        public async Task<CheckResponse> UploadTextAsync(string text)
        {
            var payload = JsonSerializer.Serialize(new { text = text, source = "vsto-addin" });
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(BaseUrl + "/api/documents/upload-text", content);
            resp.EnsureSuccessStatusCode();
            var json = await resp.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<CheckResponse>(json) ?? new CheckResponse();
        }

        public async Task ProofreadAsync(
            string documentId,
            string provider,
            string model,
            bool anonymize,
            Func<string, JsonElement, Task> onEvent,
            CancellationToken ct)
        {
            var payload = JsonSerializer.Serialize(new
            {
                provider = provider,
                model    = string.IsNullOrEmpty(model) ? (object)null : model,
                anonymize = anonymize,
            });
            var request = new HttpRequestMessage(HttpMethod.Post,
                BaseUrl + $"/api/documents/{documentId}/proofread")
            {
                Content = new StringContent(payload, Encoding.UTF8, "application/json"),
            };

            var resp = await _streamHttp.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            if (!resp.IsSuccessStatusCode)
            {
                var body = await resp.Content.ReadAsStringAsync();
                throw new HttpRequestException($"応答の状態コードは成功を示していません：{(int)resp.StatusCode}（{resp.ReasonPhrase}）\n{body}");
            }

            using (var stream = await resp.Content.ReadAsStreamAsync())
            using (var reader = new StreamReader(stream))
            {
                string currentEvent = "message";
                string currentData  = null;

                while (!reader.EndOfStream && !ct.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync();
                    if (line == null) break;

                    if (line == "")
                    {
                        if (currentData != null)
                        {
                            try
                            {
                                using (var doc = JsonDocument.Parse(currentData))
                                    await onEvent(currentEvent, doc.RootElement.Clone());
                            }
                            catch { /* ignore malformed events */ }
                            currentData  = null;
                            currentEvent = "message";
                        }
                    }
                    else if (line.StartsWith("event:"))
                        currentEvent = line.Substring(6).Trim();
                    else if (line.StartsWith("data:"))
                        currentData = line.Substring(5).Trim();
                }
            }
        }

        public void Dispose()
        {
            _http.Dispose();
            _streamHttp.Dispose();
        }
    }
}
