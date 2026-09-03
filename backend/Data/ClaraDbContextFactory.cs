using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;
using Microsoft.Extensions.Configuration;

namespace CLARA.Backend.Data;

public sealed class ClaraDbContextFactory : IDesignTimeDbContextFactory<ClaraDbContext>
{
    public ClaraDbContext CreateDbContext(string[] args)
    {
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: false)
            .AddJsonFile("appsettings.Development.local.json", optional: true)
            .AddEnvironmentVariables()
            .Build();

        var connectionString = configuration.GetConnectionString("ClaraDatabase")
            ?? throw new InvalidOperationException("Connection string 'ClaraDatabase' is required.");

        var options = new DbContextOptionsBuilder<ClaraDbContext>()
            .UseNpgsql(connectionString)
            .Options;

        return new ClaraDbContext(options);
    }
}
