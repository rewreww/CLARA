using Microsoft.EntityFrameworkCore;

namespace CLARA.Backend.Data;

public sealed class ClaraDbContext(DbContextOptions<ClaraDbContext> options) : DbContext(options)
{
    public DbSet<PatientRecord> Patients => Set<PatientRecord>();
    public DbSet<PatientDocument> PatientDocuments => Set<PatientDocument>();
    public DbSet<DiagnosisRecord> Diagnoses => Set<DiagnosisRecord>();
    public DbSet<MedicationRecord> Medications => Set<MedicationRecord>();
    public DbSet<LabResultRecord> LabResults => Set<LabResultRecord>();
    public DbSet<DischargeSummaryRecord> DischargeSummaries => Set<DischargeSummaryRecord>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<PatientRecord>(entity =>
        {
            entity.ToTable("patients");
            entity.HasKey(patient => patient.Id);
            entity.Property(patient => patient.Id).HasMaxLength(100);
            entity.Property(patient => patient.DisplayName).HasMaxLength(250);
            entity.Property(patient => patient.Sex).HasMaxLength(32);
        });

        modelBuilder.Entity<PatientDocument>(entity =>
        {
            entity.ToTable("patient_documents");
            entity.HasKey(document => document.Id);
            entity.Property(document => document.RelativePath).HasMaxLength(1000);
            entity.Property(document => document.FileName).HasMaxLength(500);
            entity.Property(document => document.DocumentType).HasMaxLength(64);
            entity.Property(document => document.ContentHash).HasMaxLength(128);
            entity.Property(document => document.ExtractionStatus).HasMaxLength(32);
            entity.Property(document => document.ExtractedText).HasColumnType("text");
            // A file's path identifies its source record. Different documents may legitimately
            // have the same contents, so the content hash is retained for change detection only.
            entity.HasIndex(document => new { document.PatientId, document.RelativePath }).IsUnique();
            entity.HasIndex(document => new { document.PatientId, document.ContentHash });
            entity.HasIndex(document => new { document.PatientId, document.DocumentType, document.RecordDate });
            entity.HasOne(document => document.Patient)
                .WithMany(patient => patient.Documents)
                .HasForeignKey(document => document.PatientId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<DiagnosisRecord>(entity =>
        {
            entity.ToTable("diagnoses");
            entity.HasKey(diagnosis => diagnosis.Id);
            entity.Property(diagnosis => diagnosis.DiagnosisType).HasMaxLength(64);
            entity.Property(diagnosis => diagnosis.DiagnosisText).HasColumnType("text");
            entity.Property(diagnosis => diagnosis.NormalizedName).HasMaxLength(500);
            entity.Property(diagnosis => diagnosis.ExtractionConfidence).HasPrecision(5, 4);
            entity.HasIndex(diagnosis => new { diagnosis.PatientId, diagnosis.RecordedOn });
            entity.HasOne(diagnosis => diagnosis.Patient)
                .WithMany(patient => patient.Diagnoses)
                .HasForeignKey(diagnosis => diagnosis.PatientId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasOne(diagnosis => diagnosis.SourceDocument)
                .WithMany()
                .HasForeignKey(diagnosis => diagnosis.SourceDocumentId)
                .OnDelete(DeleteBehavior.SetNull);
        });

        modelBuilder.Entity<MedicationRecord>(entity =>
        {
            entity.ToTable("medications");
            entity.HasKey(medication => medication.Id);
            entity.Property(medication => medication.MedicationName).HasMaxLength(500);
            entity.Property(medication => medication.Dose).HasMaxLength(128);
            entity.Property(medication => medication.Route).HasMaxLength(128);
            entity.Property(medication => medication.Frequency).HasMaxLength(128);
            entity.Property(medication => medication.MedicationStatus).HasMaxLength(64);
            entity.Property(medication => medication.SourceText).HasColumnType("text");
            entity.Property(medication => medication.ExtractionConfidence).HasPrecision(5, 4);
            entity.HasIndex(medication => new { medication.PatientId, medication.RecordedOn });
            entity.HasIndex(medication => new { medication.PatientId, medication.MedicationName });
            entity.HasOne(medication => medication.Patient)
                .WithMany(patient => patient.Medications)
                .HasForeignKey(medication => medication.PatientId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasOne(medication => medication.SourceDocument)
                .WithMany()
                .HasForeignKey(medication => medication.SourceDocumentId)
                .OnDelete(DeleteBehavior.SetNull);
        });

        modelBuilder.Entity<LabResultRecord>(entity =>
        {
            entity.ToTable("lab_results");
            entity.HasKey(result => result.Id);
            entity.Property(result => result.TestName).HasMaxLength(250);
            entity.Property(result => result.RawValue).HasMaxLength(250);
            entity.Property(result => result.NumericValue).HasPrecision(18, 6);
            entity.Property(result => result.Unit).HasMaxLength(128);
            entity.Property(result => result.ReferenceLow).HasPrecision(18, 6);
            entity.Property(result => result.ReferenceHigh).HasPrecision(18, 6);
            entity.Property(result => result.Flag).HasMaxLength(64);
            entity.Property(result => result.ExtractionConfidence).HasPrecision(5, 4);
            entity.HasIndex(result => new { result.PatientId, result.TestName, result.ObservedOn });
            entity.HasOne(result => result.Patient)
                .WithMany(patient => patient.LabResults)
                .HasForeignKey(result => result.PatientId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasOne(result => result.SourceDocument)
                .WithMany(document => document.LabResults)
                .HasForeignKey(result => result.SourceDocumentId)
                .OnDelete(DeleteBehavior.SetNull);
        });

        modelBuilder.Entity<DischargeSummaryRecord>(entity =>
        {
            entity.ToTable("discharge_summaries");
            entity.HasKey(summary => summary.Id);
            entity.Property(summary => summary.ChiefComplaint).HasColumnType("text");
            entity.Property(summary => summary.AdmittingDiagnosis).HasColumnType("text");
            entity.Property(summary => summary.FinalDiagnosis).HasColumnType("text");
            entity.Property(summary => summary.HistoryOfPresentIllness).HasColumnType("text");
            entity.Property(summary => summary.PastMedicalHistory).HasColumnType("text");
            entity.Property(summary => summary.Allergies).HasColumnType("text");
            entity.Property(summary => summary.ConditionOnDischarge).HasColumnType("text");
            entity.Property(summary => summary.FollowUp).HasColumnType("text");
            entity.Property(summary => summary.PhysicalExam).HasColumnType("text");
            entity.Property(summary => summary.HospitalCourse).HasColumnType("text");
            entity.Property(summary => summary.Instructions).HasColumnType("text");
            entity.Property(summary => summary.ExtractionConfidence).HasPrecision(5, 4);
            entity.HasIndex(summary => new { summary.PatientId, summary.DischargeDate });
            entity.HasIndex(summary => summary.SourceDocumentId).IsUnique();
            entity.HasOne(summary => summary.Patient)
                .WithMany(patient => patient.DischargeSummaries)
                .HasForeignKey(summary => summary.PatientId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasOne(summary => summary.SourceDocument)
                .WithMany()
                .HasForeignKey(summary => summary.SourceDocumentId)
                .OnDelete(DeleteBehavior.Cascade);
        });
    }
}
