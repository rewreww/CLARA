using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CLARA.Backend.Data.Migrations
{
    /// <inheritdoc />
    public partial class InitialPatientRecords : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "patients",
                columns: table => new
                {
                    Id = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    DisplayName = table.Column<string>(type: "character varying(250)", maxLength: 250, nullable: true),
                    AgeYears = table.Column<int>(type: "integer", nullable: true),
                    Sex = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: true),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    UpdatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_patients", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "patient_documents",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "character varying(100)", nullable: false),
                    RelativePath = table.Column<string>(type: "character varying(1000)", maxLength: 1000, nullable: false),
                    FileName = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                    DocumentType = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
                    RecordDate = table.Column<DateOnly>(type: "date", nullable: true),
                    ContentHash = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: false),
                    FileSizeBytes = table.Column<long>(type: "bigint", nullable: true),
                    SourceModifiedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    ExtractionStatus = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: false),
                    ExtractedText = table.Column<string>(type: "text", nullable: true),
                    ExtractedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    UpdatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_patient_documents", x => x.Id);
                    table.ForeignKey(
                        name: "FK_patient_documents_patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "patients",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "diagnoses",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "character varying(100)", nullable: false),
                    SourceDocumentId = table.Column<Guid>(type: "uuid", nullable: true),
                    DiagnosisType = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
                    DiagnosisText = table.Column<string>(type: "text", nullable: false),
                    NormalizedName = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: true),
                    RecordedOn = table.Column<DateOnly>(type: "date", nullable: true),
                    ExtractionConfidence = table.Column<decimal>(type: "numeric(5,4)", precision: 5, scale: 4, nullable: true),
                    IsClinicianReviewed = table.Column<bool>(type: "boolean", nullable: false),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_diagnoses", x => x.Id);
                    table.ForeignKey(
                        name: "FK_diagnoses_patient_documents_SourceDocumentId",
                        column: x => x.SourceDocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_diagnoses_patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "patients",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "discharge_summaries",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "character varying(100)", nullable: false),
                    SourceDocumentId = table.Column<Guid>(type: "uuid", nullable: false),
                    ChiefComplaint = table.Column<string>(type: "text", nullable: true),
                    AdmittingDiagnosis = table.Column<string>(type: "text", nullable: true),
                    FinalDiagnosis = table.Column<string>(type: "text", nullable: true),
                    HistoryOfPresentIllness = table.Column<string>(type: "text", nullable: true),
                    PastMedicalHistory = table.Column<string>(type: "text", nullable: true),
                    Allergies = table.Column<string>(type: "text", nullable: true),
                    ConditionOnDischarge = table.Column<string>(type: "text", nullable: true),
                    FollowUp = table.Column<string>(type: "text", nullable: true),
                    PhysicalExam = table.Column<string>(type: "text", nullable: true),
                    HospitalCourse = table.Column<string>(type: "text", nullable: true),
                    Instructions = table.Column<string>(type: "text", nullable: true),
                    DischargeDate = table.Column<DateOnly>(type: "date", nullable: true),
                    ExtractionConfidence = table.Column<decimal>(type: "numeric(5,4)", precision: 5, scale: 4, nullable: true),
                    IsClinicianReviewed = table.Column<bool>(type: "boolean", nullable: false),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    UpdatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_discharge_summaries", x => x.Id);
                    table.ForeignKey(
                        name: "FK_discharge_summaries_patient_documents_SourceDocumentId",
                        column: x => x.SourceDocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_discharge_summaries_patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "patients",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "lab_results",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "character varying(100)", nullable: false),
                    SourceDocumentId = table.Column<Guid>(type: "uuid", nullable: true),
                    TestName = table.Column<string>(type: "character varying(250)", maxLength: 250, nullable: false),
                    RawValue = table.Column<string>(type: "character varying(250)", maxLength: 250, nullable: false),
                    NumericValue = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    Unit = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    ReferenceLow = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    ReferenceHigh = table.Column<decimal>(type: "numeric(18,6)", precision: 18, scale: 6, nullable: true),
                    Flag = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    ObservedOn = table.Column<DateOnly>(type: "date", nullable: true),
                    ExtractionConfidence = table.Column<decimal>(type: "numeric(5,4)", precision: 5, scale: 4, nullable: true),
                    IsClinicianReviewed = table.Column<bool>(type: "boolean", nullable: false),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_lab_results", x => x.Id);
                    table.ForeignKey(
                        name: "FK_lab_results_patient_documents_SourceDocumentId",
                        column: x => x.SourceDocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_lab_results_patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "patients",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "medications",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "character varying(100)", nullable: false),
                    SourceDocumentId = table.Column<Guid>(type: "uuid", nullable: true),
                    MedicationName = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                    Dose = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    Route = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    Frequency = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    MedicationStatus = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    SourceText = table.Column<string>(type: "text", nullable: false),
                    RecordedOn = table.Column<DateOnly>(type: "date", nullable: true),
                    ExtractionConfidence = table.Column<decimal>(type: "numeric(5,4)", precision: 5, scale: 4, nullable: true),
                    IsClinicianReviewed = table.Column<bool>(type: "boolean", nullable: false),
                    CreatedAtUtc = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_medications", x => x.Id);
                    table.ForeignKey(
                        name: "FK_medications_patient_documents_SourceDocumentId",
                        column: x => x.SourceDocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_medications_patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "patients",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_diagnoses_PatientId_RecordedOn",
                table: "diagnoses",
                columns: new[] { "PatientId", "RecordedOn" });

            migrationBuilder.CreateIndex(
                name: "IX_diagnoses_SourceDocumentId",
                table: "diagnoses",
                column: "SourceDocumentId");

            migrationBuilder.CreateIndex(
                name: "IX_discharge_summaries_PatientId_DischargeDate",
                table: "discharge_summaries",
                columns: new[] { "PatientId", "DischargeDate" });

            migrationBuilder.CreateIndex(
                name: "IX_discharge_summaries_SourceDocumentId",
                table: "discharge_summaries",
                column: "SourceDocumentId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_lab_results_PatientId_TestName_ObservedOn",
                table: "lab_results",
                columns: new[] { "PatientId", "TestName", "ObservedOn" });

            migrationBuilder.CreateIndex(
                name: "IX_lab_results_SourceDocumentId",
                table: "lab_results",
                column: "SourceDocumentId");

            migrationBuilder.CreateIndex(
                name: "IX_medications_PatientId_MedicationName",
                table: "medications",
                columns: new[] { "PatientId", "MedicationName" });

            migrationBuilder.CreateIndex(
                name: "IX_medications_PatientId_RecordedOn",
                table: "medications",
                columns: new[] { "PatientId", "RecordedOn" });

            migrationBuilder.CreateIndex(
                name: "IX_medications_SourceDocumentId",
                table: "medications",
                column: "SourceDocumentId");

            migrationBuilder.CreateIndex(
                name: "IX_patient_documents_PatientId_ContentHash",
                table: "patient_documents",
                columns: new[] { "PatientId", "ContentHash" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_patient_documents_PatientId_DocumentType_RecordDate",
                table: "patient_documents",
                columns: new[] { "PatientId", "DocumentType", "RecordDate" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "diagnoses");

            migrationBuilder.DropTable(
                name: "discharge_summaries");

            migrationBuilder.DropTable(
                name: "lab_results");

            migrationBuilder.DropTable(
                name: "medications");

            migrationBuilder.DropTable(
                name: "patient_documents");

            migrationBuilder.DropTable(
                name: "patients");
        }
    }
}
