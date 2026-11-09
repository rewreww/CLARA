using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using CLARA.Backend.Data;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Controllers;

[ApiController]
[Route("api/account")]
[ResponseCache(NoStore = true, Location = ResponseCacheLocation.None)]
public sealed class AccountController(ClaraDbContext db, IConfiguration config) : ControllerBase
{
    private readonly PasswordHasher<ClaraAccount> hasher = new();
    private bool Enabled => config.GetValue<bool>("ClaraAuth:Enabled");
    private static readonly string[] Roles = ["admin", "clinician", "trainee", "auditor"];
    private Guid UserId => Guid.TryParse(User.FindFirstValue(ClaimTypes.NameIdentifier), out var id) ? id : Guid.Empty;
    private bool Admin => User.IsInRole("admin");
    private IActionResult Disabled() => StatusCode(503, new { error = "Account management is not configured." });
    private async Task Audit(string action, Guid? subject = null)
    {
        db.SecurityEvents.Add(new ClaraSecurityEvent { ActorId = UserId == Guid.Empty ? null : UserId, SubjectId = subject, Action = action });
        await db.SaveChangesAsync();
    }
    private static string HashToken(string token) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(token)));
    private static string GenerateToken() => Convert.ToBase64String(RandomNumberGenerator.GetBytes(32)).Replace('+', '-').Replace('/', '_').TrimEnd('=');
    private static object Profile(ClaraAccount a) => new { id = a.Id, username = a.Username, displayName = a.DisplayName, role = a.Role, department = a.Department, state = a.State };
    private static readonly TimeSpan ReenableCooldown = TimeSpan.FromMinutes(1);
    private async Task<DateTimeOffset?> ReenableAt(Guid id)
    {
        var lastDisabled = await db.SecurityEvents.AsNoTracking()
            .Where(x => x.SubjectId == id && x.Action == "disabled")
            .OrderByDescending(x => x.CreatedAt)
            .Select(x => (DateTimeOffset?)x.CreatedAt)
            .FirstOrDefaultAsync();
        return lastDisabled?.Add(ReenableCooldown);
    }
    private static bool ValidPassword(string password) => !string.IsNullOrWhiteSpace(password) && password.Length >= 12 && password.Length <= 256;
    private async Task IssueCookie(ClaraAccount a)
    {
        var identity = new ClaimsIdentity(new[] {
            new Claim(ClaimTypes.NameIdentifier, a.Id.ToString()),
            new Claim(ClaimTypes.Name, a.Username),
            new Claim(ClaimTypes.Role, a.Role),
            new Claim("session_version", a.SessionVersion.ToString())
        }, CookieAuthenticationDefaults.AuthenticationScheme);
        await HttpContext.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme,
            new ClaimsPrincipal(identity), new AuthenticationProperties { IsPersistent = false, AllowRefresh = false });
    }

    [HttpGet("config")]
    [AllowAnonymous]
    public IActionResult Config() => Ok(new { enabled = Enabled });

    [HttpGet("me")]
    [AllowAnonymous]
    public async Task<IActionResult> Me()
    {
        if (!Enabled) return Disabled();
        // The cookie validator rejects disabled sessions before authorization; preserve
        // only the disabled status for this response, never an authenticated principal.
        if (HttpContext.Items.ContainsKey("ClaraAccountDisabled"))
            return StatusCode(423, new { code = "ACCOUNT_DISABLED", error = "Your CLARA account has been disabled. Please contact your hospital IT administrator for assistance." });
        if (User.Identity?.IsAuthenticated != true) return Unauthorized();
        var a = await db.Accounts.AsNoTracking().FirstOrDefaultAsync(x => x.Id == UserId && x.State == "active");
        return a is null ? Unauthorized() : Ok(Profile(a));
    }

    public record LoginRequest(string Username, string Password);
    [HttpPost("login")]
    [AllowAnonymous]
    public async Task<IActionResult> Login(LoginRequest value)
    {
        if (!Enabled) return Disabled();
        var username = (value.Username ?? "").Trim().ToLowerInvariant();
        var a = await db.Accounts.FirstOrDefaultAsync(x => x.Username == username);
        if (a is null || a.LockedUntil > DateTimeOffset.UtcNow)
            return Unauthorized(new { error = "Invalid credentials or account unavailable." });
        var checkedPassword = hasher.VerifyHashedPassword(a, a.PasswordHash, value.Password ?? "");
        if (checkedPassword == PasswordVerificationResult.Failed) {
            a.FailedLoginCount++;
            if (a.FailedLoginCount >= 5) { a.LockedUntil = DateTimeOffset.UtcNow.AddMinutes(15); a.FailedLoginCount = 0; }
            await db.SaveChangesAsync();
            return Unauthorized(new { error = "Invalid credentials or account unavailable." });
        }
        if (a.State == "disabled")
            return StatusCode(423, new { code = "ACCOUNT_DISABLED", error = "Your CLARA account has been disabled. Please contact your hospital IT administrator for assistance." });
        if (a.State != "active") return Unauthorized(new { error = "Invalid credentials or account unavailable." });
        if (checkedPassword == PasswordVerificationResult.SuccessRehashNeeded)
            a.PasswordHash = hasher.HashPassword(a, value.Password);
        a.FailedLoginCount = 0; a.LockedUntil = null; a.LastLoginAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync();
        await IssueCookie(a);
        await Audit("login", a.Id);
        return Ok(Profile(a));
    }

    [HttpPost("logout")]
    [Authorize]
    public async Task<IActionResult> Logout()
    {
        if (!Enabled) return Disabled();
        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        await Audit("logout", UserId);
        return Ok(new { success = true });
    }

    public record ChangePasswordRequest(string OldPassword, string NewPassword);
    [HttpPost("change-password")]
    [Authorize]
    public async Task<IActionResult> ChangePassword(ChangePasswordRequest value)
    {
        if (!Enabled) return Disabled();
        if (!ValidPassword(value.NewPassword)) return BadRequest(new { error = "Use a password of 12–256 characters." });
        var a = await db.Accounts.SingleAsync(x => x.Id == UserId);
        if (hasher.VerifyHashedPassword(a, a.PasswordHash, value.OldPassword ?? "") == PasswordVerificationResult.Failed)
            return BadRequest(new { error = "Current password is incorrect." });
        a.PasswordHash = hasher.HashPassword(a, value.NewPassword); a.SessionVersion++;
        await db.SaveChangesAsync();
        await Audit("password_changed", a.Id);
        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return Ok(new { success = true, relogin = true });
    }

    public record TokenPasswordRequest(string Token, string NewPassword);
    [HttpPost("activate")]
    [AllowAnonymous]
    public async Task<IActionResult> Activate(TokenPasswordRequest value)
    {
        if (!Enabled) return Disabled();
        return await CompleteToken(value, "activation");
    }
    [HttpPost("reset-password")]
    [AllowAnonymous]
    public async Task<IActionResult> ResetPassword(TokenPasswordRequest value)
    {
        if (!Enabled) return Disabled();
        return await CompleteToken(value, "recovery");
    }
    private async Task<IActionResult> CompleteToken(TokenPasswordRequest value, string purpose)
    {
        if (!ValidPassword(value.NewPassword)) return BadRequest(new { error = "Use a password of 12–256 characters." });
        if (string.IsNullOrWhiteSpace(value.Token) || value.Token.Length > 200) return BadRequest(new { error = "Invalid or expired code." });
        var hash = HashToken(value.Token);
        var token = await db.AccountTokens.Include(x => x.Account)
            .FirstOrDefaultAsync(x => x.TokenHash == hash && x.Purpose == purpose && x.UsedAt == null && x.ExpiresAt > DateTimeOffset.UtcNow);
        if (token is null || token.Account.State == "disabled") return BadRequest(new { error = "Invalid or expired code." });
        var a = token.Account;
        // Consume all previous recovery or activation codes for this account.
        var tokens = await db.AccountTokens.Where(x => x.AccountId == a.Id && x.UsedAt == null).ToListAsync();
        foreach (var t in tokens) t.UsedAt = DateTimeOffset.UtcNow;
        a.PasswordHash = hasher.HashPassword(a, value.NewPassword);
        a.State = "active"; a.SessionVersion++; a.FailedLoginCount = 0; a.LockedUntil = null;
        await db.SaveChangesAsync();
        await Audit(purpose == "activation" ? "activated" : "password_recovered", a.Id);
        return Ok(new { success = true });
    }

    [HttpGet("users")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Users()
    {
        if (!Enabled) return Disabled();
        var users = await db.Accounts.AsNoTracking().OrderBy(x => x.Username).ToListAsync();
        var latestDisables = await db.SecurityEvents.AsNoTracking()
            .Where(x => x.Action == "disabled" && x.SubjectId != null)
            .GroupBy(x => x.SubjectId)
            .Select(g => new { subjectId = g.Key, at = g.Max(x => x.CreatedAt) })
            .ToListAsync();
        var times = latestDisables.ToDictionary(x => x.subjectId!.Value, x => x.at);
        return Ok(users.Select(a => new {
            id = a.Id, username = a.Username, displayName = a.DisplayName,
            role = a.Role, department = a.Department, state = a.State,
            reenableAt = a.State == "disabled" && times.TryGetValue(a.Id, out var at)
                ? (DateTimeOffset?)at.Add(ReenableCooldown) : null
        }));
    }
    public record InviteRequest(string Username, string DisplayName, string Department, string Role);
    [HttpPost("users/invite")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Invite(InviteRequest value)
    {
        if (!Enabled) return Disabled();
        var name = (value.Username ?? "").Trim().ToLowerInvariant();
        if (name.Length is < 3 or > 120 || !System.Text.RegularExpressions.Regex.IsMatch(name, @"^[a-z0-9._-]+$")
            || !Roles.Contains(value.Role) || string.IsNullOrWhiteSpace(value.DisplayName) || value.DisplayName.Length > 200)
            return BadRequest(new { error = "Invalid account details." });
        if (await db.Accounts.AnyAsync(x => x.Username == name)) return Conflict(new { error = "Username already exists." });
        var a = new ClaraAccount { Username = name, DisplayName = value.DisplayName.Trim(), Department = (value.Department ?? "").Trim()[..Math.Min((value.Department ?? "").Trim().Length, 120)], Role = value.Role, State = "pending" };
        a.PasswordHash = hasher.HashPassword(a, GenerateToken()); // Not a usable known password.
        db.Accounts.Add(a);
        var code = GenerateToken();
        db.AccountTokens.Add(new ClaraAccountToken { AccountId = a.Id, TokenHash = HashToken(code), Purpose = "activation", ExpiresAt = DateTimeOffset.UtcNow.AddHours(24) });
        await db.SaveChangesAsync();
        await Audit("invited", a.Id);
        return Ok(new { account = Profile(a), activationCode = code, expiresInHours = 24 });
    }
    public record RoleRequest(string Role);
    [HttpPut("users/{id:guid}/role")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Role(Guid id, RoleRequest value)
    {
        if (!Enabled) return Disabled();
        if (!Roles.Contains(value.Role)) return BadRequest(new { error = "Invalid role." });
        if (id == UserId) return BadRequest(new { error = "Administrators cannot change their own role." });
        var a = await db.Accounts.FindAsync(id);
        if (a is null) return NotFound();
        a.Role = value.Role; a.SessionVersion++;
        await db.SaveChangesAsync(); await Audit("role_changed", id);
        return Ok(Profile(a));
    }
    [HttpPost("users/{id:guid}/disable")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Disable(Guid id)
    {
        if (!Enabled) return Disabled();
        if (id == UserId) return BadRequest(new { error = "Cannot disable your own administrator account." });
        var a = await db.Accounts.FindAsync(id);
        if (a is null) return NotFound();
        if (a.State != "active") return Conflict(new { error = "Only active accounts can be disabled." });
        a.State = "disabled"; a.SessionVersion++;
        db.SecurityEvents.Add(new ClaraSecurityEvent { ActorId = UserId, SubjectId = id, Action = "disabled" });
        await db.SaveChangesAsync();
        return Ok(Profile(a));
    }
    [HttpPost("users/{id:guid}/enable")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Enable(Guid id)
    {
        if (!Enabled) return Disabled();
        var a = await db.Accounts.FindAsync(id);
        if (a is null || a.State == "pending") return NotFound();
        if (a.State != "disabled") return Conflict(new { error = "This account is not disabled." });
        var reenableAt = await ReenableAt(id);
        if (reenableAt > DateTimeOffset.UtcNow)
            return StatusCode(409, new {
                error = "This account cannot be re-enabled until the 60-second security hold has elapsed.",
                reenableAt,
                remainingSeconds = (int)Math.Ceiling((reenableAt.Value - DateTimeOffset.UtcNow).TotalSeconds)
            });
        a.State = "active"; a.SessionVersion++;
        await db.SaveChangesAsync(); await Audit("enabled", id);
        return Ok(Profile(a));
    }
    [HttpPost("users/{id:guid}/recovery")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> Recovery(Guid id)
    {
        if (!Enabled) return Disabled();
        var a = await db.Accounts.FindAsync(id);
        if (a is null || a.State != "active") return NotFound();
        var older = await db.AccountTokens.Where(x => x.AccountId == id && x.UsedAt == null).ToListAsync();
        foreach (var t in older) t.UsedAt = DateTimeOffset.UtcNow;
        var code = GenerateToken();
        db.AccountTokens.Add(new ClaraAccountToken { AccountId = id, TokenHash = HashToken(code), Purpose = "recovery", ExpiresAt = DateTimeOffset.UtcNow.AddMinutes(20) });
        a.SessionVersion++; // Revoke other sessions immediately.
        await db.SaveChangesAsync(); await Audit("recovery_issued", id);
        return Ok(new { recoveryCode = code, expiresInMinutes = 20 });
    }
    [HttpGet("audit")]
    [Authorize(Roles = "admin,auditor")]
    public async Task<IActionResult> AuditList()
    {
        if (!Enabled) return Disabled();
        var entries = await db.SecurityEvents.AsNoTracking().OrderByDescending(x => x.CreatedAt).Take(200).ToListAsync();
        return Ok(entries);
    }

    [HttpGet("conversations")]
    [Authorize]
    public async Task<IActionResult> Conversations()
    {
        if (!Enabled) return Disabled();
        if (Admin || User.IsInRole("auditor")) return Forbid();
        var items = await db.Conversations.AsNoTracking().Where(x => x.AccountId == UserId).OrderByDescending(x => x.UpdatedAt).Take(200).ToListAsync();
        return Ok(items.Select(x => JsonDocument.Parse(x.Payload).RootElement.Clone()));
    }
    public record ConversationRequest(string Id, string Title, JsonElement Conversation);
    [HttpPut("conversations/{id}")]
    [Authorize]
    public async Task<IActionResult> SaveConversation(string id, [FromBody] ConversationRequest value)
    {
        if (!Enabled) return Disabled();
        if (Admin || User.IsInRole("auditor")) return Forbid();
        if (id.Length is < 8 or > 200 || value.Id != id || value.Conversation.ValueKind != JsonValueKind.Object
            || value.Conversation.GetRawText().Length > 1000000
            || !value.Conversation.TryGetProperty("id", out var jsonId) || jsonId.ValueKind != JsonValueKind.String || jsonId.GetString() != id
            || !value.Conversation.TryGetProperty("messages", out var msgs) || msgs.ValueKind != JsonValueKind.Array)
            return BadRequest(new { error = "Invalid conversation." });
        var item = await db.Conversations.FindAsync(UserId, id);
        if (item is null) {
            item = new ClaraConversation { AccountId = UserId, Id = id };
            db.Conversations.Add(item);
        }
        item.Title = (value.Title ?? "")[..Math.Min((value.Title ?? "").Length, 120)];
        item.Payload = value.Conversation.GetRawText();
        item.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync();
        return Ok(new { saved = true });
    }
    [HttpDelete("conversations/{id}")]
    [Authorize]
    public async Task<IActionResult> DeleteConversation(string id)
    {
        if (!Enabled) return Disabled();
        if (Admin || User.IsInRole("auditor")) return Forbid();
        var conversation = await db.Conversations.FindAsync(UserId, id);
        if (conversation is not null) { db.Conversations.Remove(conversation); await db.SaveChangesAsync(); }
        return NoContent();
    }
}
