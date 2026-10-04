using System.Text.Json;
using System.Text.RegularExpressions;
using CLARA.Backend.Ingestion;

var parser = new PdfParser();
var extractor = new ClinicalTextExtractor();
var cases = new[] {
    new { Name="Explicit low percentage", Text="BASOPHILS 0.5 % 0 - 1", Kind="hematology", Expected="BASOPHILS numeric value 0.5, unit %" },
    new { Name="Scientific notation", Text="CREATININE 1.2e3 mg/dL", Kind="chemistry", Expected="CREATININE numeric value 1200, unit mg/dL (deliberate numeric stress case)" },
    new { Name="Repeated dated result", Text="01/01/2026 CREATININE 1.2 mg/dL\n02/01/2026 CREATININE 1.8 mg/dL", Kind="chemistry", Expected="Two distinct creatinine observations with their dates" },
    new { Name="Unicode unit", Text="CREATININE 98 µmol/L", Kind="chemistry", Expected="CREATININE value 98 and unit µmol/L" }
};
var probes = cases.Select(c => new { c.Name, c.Text, c.Expected, Observed=extractor.ExtractLabResults(c.Text,c.Kind) }).ToArray();
var dischargeText = "DISCHARGE SUMMARY\nChief Complaint\nShortness of breath.\nPrincipal diagnosis:\nAortic stenosis.\nClinical course:\nThe patient improved and was discharged.";
var options = new JsonSerializerOptions { WriteIndented=true };
var root = Path.GetFullPath("output/research/extraction-samples");
var pdfs = new List<object>();
foreach(var file in Directory.GetFiles(root,"*.pdf",SearchOption.AllDirectories).Order()) {
    var text = parser.ExtractText(file);
    var kind = extractor.InferLabType(file,text);
    pdfs.Add(new { File=Path.GetRelativePath(root,file), TextCharacters=Regex.Replace(text,@"\[PDF PAGE \d+\]|\s+","").Length, InferredLabType=kind, Labs=extractor.ExtractLabResults(text,kind), Discharge=extractor.ParseDischarge(text) });
}
File.WriteAllText(Path.Combine(root,"current-parser-probe.json"),JsonSerializer.Serialize(new { Scope="Read-only isolated invocation of current production C# parsers. Synthetic probes and public sample documents; not an F1 evaluation.", Probes=probes, AlternateHeadings=new { Input=dischargeText,Observed=extractor.ParseDischarge(dischargeText) }, Documents=pdfs },options));
Console.WriteLine(JsonSerializer.Serialize(new { Probes=probes, AlternateHeadings=new { FinalDiagnosis=extractor.ParseDischarge(dischargeText).FinalDiagnosis,ChiefComplaint=extractor.ParseDischarge(dischargeText).ChiefComplaint },PdfFiles=pdfs.Count },options));
