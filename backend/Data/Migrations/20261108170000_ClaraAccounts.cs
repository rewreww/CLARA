using System;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using CLARA.Backend.Data;

#nullable disable

namespace CLARA.Backend.Data.Migrations;

[DbContext(typeof(ClaraDbContext))]
[Migration("20261108170000_ClaraAccounts")]
public sealed class ClaraAccounts : Migration
{
    protected override void Up(MigrationBuilder m)
    {
        m.CreateTable("clara_accounts", columns: t => new {
            Id = t.Column<Guid>(type: "uuid", nullable: false),
            Username = t.Column<string>(type: "character varying(120)", maxLength: 120, nullable: false),
            DisplayName = t.Column<string>(type: "text", nullable: false),
            Role = t.Column<string>(type: "character varying(30)", maxLength: 30, nullable: false),
            Department = t.Column<string>(type: "text", nullable: false),
            PasswordHash = t.Column<string>(type: "character varying(1024)", maxLength: 1024, nullable: false),
            State = t.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
            SessionVersion = t.Column<int>(type: "integer", nullable: false),
            FailedLoginCount = t.Column<int>(type: "integer", nullable: false),
            LockedUntil = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
            CreatedAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
            LastLoginAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
        }, constraints: t => t.PrimaryKey("PK_clara_accounts", x => x.Id));
        m.CreateIndex("IX_clara_accounts_Username", "clara_accounts", "Username", unique: true);

        m.CreateTable("clara_account_tokens", columns: t => new {
            Id = t.Column<Guid>(type: "uuid", nullable: false),
            AccountId = t.Column<Guid>(type: "uuid", nullable: false),
            TokenHash = t.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
            Purpose = t.Column<string>(type: "text", nullable: false),
            ExpiresAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
            UsedAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
        }, constraints: t => {
            t.PrimaryKey("PK_clara_account_tokens", x => x.Id);
            t.ForeignKey("FK_clara_account_tokens_clara_accounts_AccountId", x => x.AccountId, "clara_accounts", "Id", onDelete: ReferentialAction.Cascade);
        });
        m.CreateIndex("IX_clara_account_tokens_AccountId", "clara_account_tokens", "AccountId");
        m.CreateIndex("IX_clara_account_tokens_TokenHash", "clara_account_tokens", "TokenHash", unique: true);

        m.CreateTable("clara_conversations", columns: t => new {
            AccountId = t.Column<Guid>(type: "uuid", nullable: false),
            Id = t.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
            Title = t.Column<string>(type: "character varying(120)", maxLength: 120, nullable: false),
            Payload = t.Column<string>(type: "jsonb", nullable: false),
            UpdatedAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
        }, constraints: t => {
            t.PrimaryKey("PK_clara_conversations", x => new { x.AccountId, x.Id });
            t.ForeignKey("FK_clara_conversations_clara_accounts_AccountId", x => x.AccountId, "clara_accounts", "Id", onDelete: ReferentialAction.Cascade);
        });
        m.CreateIndex("IX_clara_conversations_AccountId_UpdatedAt", "clara_conversations", new[] {"AccountId", "UpdatedAt"});

        m.CreateTable("clara_security_events", columns: t => new {
            Id = t.Column<long>(type: "bigint", nullable: false)
                .Annotation("Npgsql:ValueGenerationStrategy", Npgsql.EntityFrameworkCore.PostgreSQL.Metadata.NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
            ActorId = t.Column<Guid>(type: "uuid", nullable: true),
            SubjectId = t.Column<Guid>(type: "uuid", nullable: true),
            Action = t.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
            CreatedAt = t.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
        }, constraints: t => t.PrimaryKey("PK_clara_security_events", x => x.Id));
        m.CreateIndex("IX_clara_security_events_CreatedAt", "clara_security_events", "CreatedAt");
    }

    protected override void Down(MigrationBuilder m)
    {
        m.DropTable("clara_account_tokens");
        m.DropTable("clara_conversations");
        m.DropTable("clara_security_events");
        m.DropTable("clara_accounts");
    }
}
