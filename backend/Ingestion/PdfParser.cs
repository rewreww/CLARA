using UglyToad.PdfPig;
using System.Text;

namespace CLARA.Backend.Ingestion
{
    public class PdfParser
    {
        public string ExtractText(string filePath)
        {
            using var document = PdfDocument.Open(filePath);
            var text = new StringBuilder();

            foreach (var page in document.GetPages())
            {
                text.AppendLine($"[PDF PAGE {page.Number}]");
                text.AppendLine(page.Text);
                text.AppendLine();
            }

            return text.ToString();
        }
    }
}
