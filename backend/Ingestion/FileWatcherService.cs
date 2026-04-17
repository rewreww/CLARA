using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Configuration;

namespace CLARA.Backend.Ingestion
{
    public class FileWatcherService : BackgroundService
    {
        private FileSystemWatcher? _watcher;
        private readonly string _folderPath;

        public FileWatcherService(IConfiguration configuration)
        {
            // Set the path to Desktop/Patients
            _folderPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Desktop), "Patients");
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            // 1. Ensure directory exists
            if (!Directory.Exists(_folderPath))
            {
                Directory.CreateDirectory(_folderPath);
            }

            // 2. Perform the INITIAL SCAN immediately on startup
            RefreshDisplay();

            // 3. Setup the Watcher
            _watcher = new FileSystemWatcher(_folderPath);
            _watcher.Filter = "*.pdf";
            
            // Watch for moves, saves, renames, and deletes
            _watcher.NotifyFilter = NotifyFilters.FileName 
                                  | NotifyFilters.LastWrite 
                                  | NotifyFilters.Size;

            // Subscribe to all changes
            _watcher.Created += (s, e) => RefreshDisplay();
            _watcher.Deleted += (s, e) => RefreshDisplay();
            _watcher.Renamed += (s, e) => RefreshDisplay();
            _watcher.Changed += (s, e) => RefreshDisplay();

            _watcher.EnableRaisingEvents = true;

            // Keep the background service alive
            try
            {
                await Task.Delay(Timeout.Infinite, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                // Graceful shutdown
            }
        }

        private void RefreshDisplay()
        {
            try
            {
                // Clear the screen for a "Live" dashboard look
                Console.Clear();
                Console.WriteLine("====================================================");
                Console.WriteLine("          📄 CLARA PDF MONITOR ACTIVE");
                Console.WriteLine($"  Path: {_folderPath}");
                Console.WriteLine($"  Status: Last updated {DateTime.Now:HH:mm:ss}");
                Console.WriteLine("====================================================\n");

                var files = Directory.GetFiles(_folderPath, "*.pdf");

                if (files.Length == 0)
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("  [!] Folder is currently empty.");
                    Console.ResetColor();
                }
                else
                {
                    Console.WriteLine($"  Found {files.Length} file(s):");
                    Console.WriteLine("  --------------------------------------------------");
                    foreach (var file in files)
                    {
                        var info = new FileInfo(file);
                        Console.WriteLine($"  ▶ {info.Name,-30} | {info.Length / 1024:N0} KB");
                    }
                }

                Console.WriteLine("\n====================================================");
                Console.WriteLine("  Waiting for changes (Drop, Move, or Delete PDF)...");
            }
            catch (IOException)
            {
                // If a file is locked during a move, wait for the next event
            }
        }

        public override void Dispose()
        {
            _watcher?.Dispose();
            base.Dispose();
        }
    }
}