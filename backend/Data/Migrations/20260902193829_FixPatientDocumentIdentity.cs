using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CLARA.Backend.Data.Migrations
{
    /// <inheritdoc />
    public partial class FixPatientDocumentIdentity : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_patient_documents_PatientId_ContentHash",
                table: "patient_documents");

            migrationBuilder.CreateIndex(
                name: "IX_patient_documents_PatientId_ContentHash",
                table: "patient_documents",
                columns: new[] { "PatientId", "ContentHash" });

            migrationBuilder.CreateIndex(
                name: "IX_patient_documents_PatientId_RelativePath",
                table: "patient_documents",
                columns: new[] { "PatientId", "RelativePath" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_patient_documents_PatientId_ContentHash",
                table: "patient_documents");

            migrationBuilder.DropIndex(
                name: "IX_patient_documents_PatientId_RelativePath",
                table: "patient_documents");

            migrationBuilder.CreateIndex(
                name: "IX_patient_documents_PatientId_ContentHash",
                table: "patient_documents",
                columns: new[] { "PatientId", "ContentHash" },
                unique: true);
        }
    }
}
