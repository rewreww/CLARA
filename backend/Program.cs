using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;
using System.Security.Claims;
using System.Net;

using CLARA.Backend.Ingestion;
using CLARA.Backend.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile("appsettings.Development.local.json", optional: true, reloadOnChange: true);

var connectionString = builder.Configuration.GetConnectionString("ClaraDatabase")
    ?? throw new InvalidOperationException("Connection string 'ClaraDatabase' is required.");
// Reuse local credentials, but never import the new source into the legacy DB.
var databaseName = builder.Configuration["PatientDocumentSync:DatabaseName"];
if (!string.IsNullOrWhiteSpace(databaseName))
    connectionString = new Npgsql.NpgsqlConnectionStringBuilder(connectionString) { Database = databaseName }.ConnectionString;

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(o => {
        o.Cookie.Name = "clara_session";
        o.Cookie.HttpOnly = true;
        o.Cookie.SameSite = SameSiteMode.Lax;
        o.Cookie.SecurePolicy = appCookieSecurePolicy(builder.Environment);
        o.Cookie.Path = "/";
        o.ExpireTimeSpan = TimeSpan.FromHours(8);
        o.SlidingExpiration = false;
        o.Events.OnRedirectToLogin = context => { context.Response.StatusCode = 401; return Task.CompletedTask; };
        o.Events.OnRedirectToAccessDenied = context => { context.Response.StatusCode = 403; return Task.CompletedTask; };
        o.Events.OnValidatePrincipal = async context => {
            var userId = context.Principal?.FindFirstValue(ClaimTypes.NameIdentifier);
            var version = context.Principal?.FindFirstValue("session_version");
            if (!Guid.TryParse(userId, out var id) || !int.TryParse(version, out var v)) {
                context.RejectPrincipal(); return;
            }
            var db = context.HttpContext.RequestServices.GetRequiredService<ClaraDbContext>();
            var a = await db.Accounts.FindAsync(id);
            if (a is null || a.State != "active" || a.SessionVersion != v) context.RejectPrincipal();
        };
    });
builder.Services.AddAuthorization();
static CookieSecurePolicy appCookieSecurePolicy(IHostEnvironment env) =>
    env.IsDevelopment() ? CookieSecurePolicy.SameAsRequest : CookieSecurePolicy.Always;

builder.Services.AddDbContext<ClaraDbContext>(options => options.UseNpgsql(connectionString));

// Register ingestion service for PDF text extraction
builder.Services.AddScoped<PdfIngestionService>();
builder.Services.AddSingleton<PdfParser>();
builder.Services.AddSingleton<MimicPdfParser>();
builder.Services.AddSingleton<ClinicalTextExtractor>();
builder.Services.AddSingleton<PatientDocumentSyncProgress>();
builder.Services.AddScoped<PatientDocumentSyncService>();
builder.Services.AddHostedService<PatientDocumentSyncWorker>();
builder.Services.AddHostedService<PatientDocumentDesktopNotificationWorker>();

builder.Services.AddCors(o =>
    o.AddDefaultPolicy(p =>
        p.WithOrigins("http://localhost:3000", "http://127.0.0.1:3000").AllowAnyHeader().AllowAnyMethod()));

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ClaraDbContext>();
    db.Database.Migrate();
    // Bootstrap the first administrator only from private deployment configuration.
    // Never expose this operation via a web route or commit bootstrap secrets.
    if (builder.Configuration.GetValue<bool>("ClaraAuth:Enabled") && !db.Accounts.Any()) {
        var username = builder.Configuration["ClaraAuth:BootstrapUsername"];
        var password = builder.Configuration["ClaraAuth:BootstrapPassword"];
        if (string.IsNullOrWhiteSpace(username) || !System.Text.RegularExpressions.Regex.IsMatch(username, @"^[a-z0-9._-]{3,120}$")
            || string.IsNullOrWhiteSpace(password) || password.Length < 12)
            throw new InvalidOperationException("CLARA authentication requires a securely configured first administrator (username and password of at least 12 characters).");
        var admin = new ClaraAccount { Username = username, DisplayName = "Hospital Administrator", Role = "admin", State = "active" };
        admin.PasswordHash = new PasswordHasher<ClaraAccount>().HashPassword(admin, password);
        db.Accounts.Add(admin);
        db.SaveChanges();
    }
}

// Middleware
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

var urls = builder.Configuration["ASPNETCORE_URLS"] ?? string.Empty;
var hasHttpsEndpoint = urls.Contains("https://", StringComparison.OrdinalIgnoreCase)
    || !string.IsNullOrWhiteSpace(builder.Configuration["ASPNETCORE_HTTPS_PORT"]);

if (hasHttpsEndpoint)
{
    app.UseHttpsRedirection();
}

app.UseCors();
// Protect cookie-authenticated account writes against cross-origin form submissions.
// The development/demo browser origins are limited to loopback (doctor) and private
// LAN IPv4 on admin port 3001. Production should use an explicit HTTPS origin list.
app.Use(async (ctx, next) => {
    if (builder.Configuration.GetValue<bool>("ClaraAuth:Enabled")
        && ctx.Request.Path.StartsWithSegments("/api/account")
        && (HttpMethods.IsPost(ctx.Request.Method) || HttpMethods.IsPut(ctx.Request.Method)
            || HttpMethods.IsDelete(ctx.Request.Method))) {
        var origin = ctx.Request.Headers.Origin.ToString();
        var fetchSite = ctx.Request.Headers["Sec-Fetch-Site"].ToString();
        if (fetchSite == "cross-site") { ctx.Response.StatusCode = 403; return; }
        if (origin.Length > 0) {
            var allowed = Uri.TryCreate(origin, UriKind.Absolute, out var u)
                && u.Scheme == "http" && u.UserInfo.Length == 0
                && (((u.Host is "localhost" or "127.0.0.1") && (u.Port == 3000 || u.Port == 3001))
                    || (u.Port == 3001 && IPAddress.TryParse(u.Host, out var address)
                        && address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork
                        && (address.GetAddressBytes()[0] == 10
                            || address.GetAddressBytes()[0] == 192 && address.GetAddressBytes()[1] == 168
                            || address.GetAddressBytes()[0] == 172 && address.GetAddressBytes()[1] is >= 16 and <= 31)));
            if (!allowed) { ctx.Response.StatusCode = 403; return; }
        }
    }
    await next();
});
app.UseAuthentication();
// When enabled, both patient records and the AI backend-facing routes must
// require an authenticated clinical user, not merely a frontend login screen.
app.Use(async (ctx, next) => {
    if (builder.Configuration.GetValue<bool>("ClaraAuth:Enabled")
        && ctx.Request.Path.StartsWithSegments("/api/patientdata")) {
        if (ctx.User.Identity?.IsAuthenticated != true) { ctx.Response.StatusCode = 401; return; }
        if (!ctx.User.IsInRole("clinician") && !ctx.User.IsInRole("trainee")) {
            ctx.Response.StatusCode = 403; return;
        }
    }
    await next();
});
app.UseAuthorization();

app.MapControllers();

app.Run();
