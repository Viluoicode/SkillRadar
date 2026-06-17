using System.Net;

namespace SkillRadar.Tests.Ingestion;

/// <summary>Returns a canned response (or throws) for any request, for connector tests.</summary>
public class StubHttpMessageHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, HttpResponseMessage> _responder;

    public StubHttpMessageHandler(string body, HttpStatusCode status = HttpStatusCode.OK)
        : this(_ => new HttpResponseMessage(status)
        {
            Content = new StringContent(body, System.Text.Encoding.UTF8, "application/json")
        })
    {
    }

    public StubHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> responder)
    {
        _responder = responder;
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        => Task.FromResult(_responder(request));

    public static HttpClient Client(string body, string baseAddress) =>
        new(new StubHttpMessageHandler(body)) { BaseAddress = new Uri(baseAddress) };
}
