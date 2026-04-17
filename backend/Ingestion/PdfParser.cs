using UglyToad.PdfPig;

namespace CLARA.Backend.Ingestion
{
    public class PdfParser
    {
        public string ExtractText(string filePath)
        {
            using (var document = PdfDocument.Open(filePath))
            {
                var text = "";
                foreach (var page in document.GetPages())
                {
                    text += page.Text;
                }
                return text;
            }
        }
    }
}