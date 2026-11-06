using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace CLARA.Backend.Data.Migrations
{
    /// <inheritdoc />
    public partial class MimicPdfRecords : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "mimic_documents",
                columns: table => new
                {
                    DocumentId = table.Column<Guid>(type: "uuid", nullable: false),
                    AdmissionId = table.Column<string>(type: "text", nullable: true),
                    Category = table.Column<string>(type: "text", nullable: false),
                    RecordType = table.Column<string>(type: "text", nullable: false),
                    Fluid = table.Column<string>(type: "text", nullable: true),
                    ParserVersion = table.Column<string>(type: "text", nullable: false),
                    MetadataJson = table.Column<string>(type: "jsonb", nullable: false),
                    Pages = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_mimic_documents", x => x.DocumentId);
                    table.ForeignKey(
                        name: "FK_mimic_documents_patient_documents_DocumentId",
                        column: x => x.DocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "mimic_pdf_rows",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    DocumentId = table.Column<Guid>(type: "uuid", nullable: false),
                    PatientId = table.Column<string>(type: "text", nullable: false),
                    AdmissionId = table.Column<string>(type: "text", nullable: true),
                    Category = table.Column<string>(type: "text", nullable: false),
                    RecordType = table.Column<string>(type: "text", nullable: false),
                    Page = table.Column<int>(type: "integer", nullable: false),
                    RowNumber = table.Column<int>(type: "integer", nullable: false),
                    Label = table.Column<string>(type: "text", nullable: false),
                    ObservedAt = table.Column<DateTime>(type: "timestamp without time zone", nullable: true),
                    RawValue = table.Column<string>(type: "text", nullable: false),
                    NumericValue = table.Column<decimal>(type: "numeric", nullable: true),
                    Unit = table.Column<string>(type: "text", nullable: false),
                    ReferenceLow = table.Column<decimal>(type: "numeric", nullable: true),
                    ReferenceHigh = table.Column<decimal>(type: "numeric", nullable: true),
                    SourceFlag = table.Column<string>(type: "text", nullable: false),
                    Flag = table.Column<string>(type: "text", nullable: true),
                    CellsJson = table.Column<string>(type: "jsonb", nullable: false),
                    SearchText = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_mimic_pdf_rows", x => x.Id);
                    table.ForeignKey(
                        name: "FK_mimic_pdf_rows_patient_documents_DocumentId",
                        column: x => x.DocumentId,
                        principalTable: "patient_documents",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_mimic_documents_AdmissionId_Category",
                table: "mimic_documents",
                columns: new[] { "AdmissionId", "Category" });

            migrationBuilder.CreateIndex(
                name: "IX_mimic_pdf_rows_DocumentId_RowNumber",
                table: "mimic_pdf_rows",
                columns: new[] { "DocumentId", "RowNumber" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_mimic_pdf_rows_PatientId_AdmissionId_Category_ObservedAt",
                table: "mimic_pdf_rows",
                columns: new[] { "PatientId", "AdmissionId", "Category", "ObservedAt" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "mimic_documents");

            migrationBuilder.DropTable(
                name: "mimic_pdf_rows");
        }
    }
}
