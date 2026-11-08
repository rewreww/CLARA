using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Data;

public sealed class ClaraAccount
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Username { get; set; } = "";
    public string DisplayName { get; set; } = "";
    public string Role { get; set; } = "clinician";
    public string Department { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string State { get; set; } = "pending";
    public int SessionVersion { get; set; }
    public int FailedLoginCount { get; set; }
    public DateTimeOffset? LockedUntil { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? LastLoginAt { get; set; }
}
public sealed class ClaraAccountToken
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AccountId { get; set; }
    public string TokenHash { get; set; } = "";
    public string Purpose { get; set; } = "";
    public DateTimeOffset ExpiresAt { get; set; }
    public DateTimeOffset? UsedAt { get; set; }
    public ClaraAccount Account { get; set; } = null!;
}
public sealed class ClaraConversation
{
    public Guid AccountId { get; set; }
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string Payload { get; set; } = "{}";
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
    public ClaraAccount Account { get; set; } = null!;
}
public sealed class ClaraSecurityEvent
{
    public long Id { get; set; }
    public Guid? ActorId { get; set; }
    public Guid? SubjectId { get; set; }
    public string Action { get; set; } = "";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
public static class AccountModelBuilder
{
    public static void ConfigureAccounts(this ModelBuilder m)
    {
        m.Entity<ClaraAccount>(e => {
            e.ToTable("clara_accounts"); e.HasKey(x => x.Id);
            e.Property(x => x.Username).HasMaxLength(120);
            e.HasIndex(x => x.Username).IsUnique();
            e.Property(x => x.Role).HasMaxLength(30);
            e.Property(x => x.State).HasMaxLength(20);
            e.Property(x => x.PasswordHash).HasMaxLength(1024);
        });
        m.Entity<ClaraAccountToken>(e => {
            e.ToTable("clara_account_tokens"); e.HasKey(x => x.Id);
            e.Property(x => x.TokenHash).HasMaxLength(64);
            e.HasIndex(x => x.TokenHash).IsUnique();
            e.HasOne(x => x.Account).WithMany().HasForeignKey(x => x.AccountId).OnDelete(DeleteBehavior.Cascade);
        });
        m.Entity<ClaraConversation>(e => {
            e.ToTable("clara_conversations"); e.HasKey(x => new { x.AccountId, x.Id });
            e.Property(x => x.Id).HasMaxLength(200);
            e.Property(x => x.Title).HasMaxLength(120);
            e.Property(x => x.Payload).HasColumnType("jsonb");
            e.HasIndex(x => new { x.AccountId, x.UpdatedAt });
            e.HasOne(x => x.Account).WithMany().HasForeignKey(x => x.AccountId).OnDelete(DeleteBehavior.Cascade);
        });
        m.Entity<ClaraSecurityEvent>(e => {
            e.ToTable("clara_security_events"); e.HasKey(x => x.Id);
            e.Property(x => x.Action).HasMaxLength(100);
            e.HasIndex(x => x.CreatedAt);
        });
    }
}
