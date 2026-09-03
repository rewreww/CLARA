using System.Globalization;
using System.Text.RegularExpressions;

namespace CLARA.Backend.Ingestion;

public sealed class ClinicalTextExtractor
{
    private static readonly Regex Whitespace = new(@"\s+", RegexOptions.Compiled);

    public PatientMetadata ExtractPatientMetadata(string text)
    {
        var compact = Compact(text);
        var stopLabels = "date\\s+requested|date\\s+rendered|date\\s+performed|date\\s+released|age|gender|sex|birth\\s*date|birthdate|time\\s+released|requesting\\s+physician|physician|clinical\\s+chemistry|hematology|clinical\\s+microscopy|urinalysis|test";
        var name = ExtractMetadataValue(compact, "patient(?:'s)?\\s+name|name", stopLabels);
        var age = ExtractMetadataValue(compact, "age", stopLabels);
        var sex = ExtractMetadataValue(compact, "gender|sex", stopLabels);

        if (!string.IsNullOrWhiteSpace(sex))
        {
            var normalized = sex.Trim().ToUpperInvariant();
            sex = normalized.StartsWith("MALE", StringComparison.Ordinal) ? "M"
                : normalized.StartsWith("FEMALE", StringComparison.Ordinal) ? "F"
                : normalized[..1];
        }

        return new PatientMetadata(TitleCaseName(name), TryInt(age), sex);
    }

    public IReadOnlyList<ExtractedLabValue> ExtractLabResults(string text, string labType)
    {
        var specs = labType switch
        {
            "chemistry" => ChemistryTests,
            "hematology" => HematologyTests,
            "microscopy" => MicroscopyTests,
            _ => AllLabTests
        };

        var normalized = Normalize(text);
        var candidates = specs
            .Select(spec => new { Spec = spec, Match = Regex.Match(normalized, spec.Pattern, RegexOptions.IgnoreCase | RegexOptions.Singleline) })
            .Where(item => item.Match.Success)
            .OrderBy(item => item.Match.Index)
            .ToList();

        var results = new List<ExtractedLabValue>();
        for (var index = 0; index < candidates.Count; index++)
        {
            var candidate = candidates[index];
            var end = index + 1 < candidates.Count ? candidates[index + 1].Match.Index : normalized.Length;
            var segment = normalized[candidate.Match.Index..end];
            var parsed = ParseLabSegment(segment, candidate.Spec);
            if (parsed is not null)
            {
                results.Add(parsed);
            }
        }

        return NormalizeHematologyFractions(results);
    }

    public DischargeExtraction ParseDischarge(string rawText)
    {
        var text = Normalize(rawText);
        var sections = ExtractSections(text);
        var header = ExtractHeader(text);
        var physicalExam = ParsePhysicalExam(Get(sections, "physical_exam"));
        var labItems = ParseDischargeLabItems(Get(sections, "laboratory_data"));

        return new DischargeExtraction(
            Header: header,
            ConditionOnDischarge: Clean(Get(sections, "condition_discharge")),
            ChiefComplaint: Clean(Get(sections, "chief_complaint")),
            AdmittingDiagnosis: Clean(Get(sections, "admitting_dx")),
            FinalDiagnosis: Clean(Get(sections, "final_dx")),
            HistoryOfPresentIllness: Clean(Get(sections, "hpi")),
            PastMedicalHistory: Clean(Get(sections, "pmh")),
            Allergies: ExtractAllergies(text),
            FollowUp: ExtractFollowUp(text),
            PhysicalExam: physicalExam,
            LaboratoryData: Clean(Get(sections, "laboratory_data")),
            Labs: labItems,
            HospitalCourse: ExtractHospitalCourse(Get(sections, "hospital_course") ?? text),
            Medications: ExtractMedications(text),
            Instructions: ExtractInstructions(text));
    }

    public DateOnly? ExtractDateFromPath(string relativePath)
    {
        var match = Regex.Match(relativePath.Replace('\\', '/'), @"(?<year>\d{4})[-_](?<month>\d{2})(?:[-_](?<day>\d{2}))?");
        if (!match.Success)
        {
            return null;
        }

        var day = match.Groups["day"].Success ? int.Parse(match.Groups["day"].Value, CultureInfo.InvariantCulture) : 1;
        return DateOnly.TryParseExact(
            $"{match.Groups["year"].Value}-{match.Groups["month"].Value}-{day:00}",
            "yyyy-MM-dd",
            CultureInfo.InvariantCulture,
            DateTimeStyles.None,
            out var parsed)
            ? parsed
            : null;
    }

    public string InferLabType(string relativePath, string text)
    {
        var source = $"{relativePath} {text[..Math.Min(text.Length, 1000)]}".ToLowerInvariant();
        if (source.Contains("chemistry") || source.Contains("creatinine") || source.Contains("cholesterol")) return "chemistry";
        if (source.Contains("hematology") || source.Contains("hemoglobin") || source.Contains("platelet")) return "hematology";
        if (source.Contains("microscopy") || source.Contains("urinalysis") || source.Contains("pus cells")) return "microscopy";
        return "unknown";
    }

    private static ExtractedLabValue? ParseLabSegment(string segment, LabTestSpec spec)
    {
        var match = Regex.Match(segment, spec.Pattern, RegexOptions.IgnoreCase | RegexOptions.Singleline);
        if (!match.Success)
        {
            return null;
        }

        var matchEnd = match.Index + match.Length;
        var window = segment[matchEnd..Math.Min(segment.Length, matchEnd + 240)];
        string rawValue;
        decimal? numericValue = null;
        string? unit = null;

        if (spec.IsTextValue)
        {
            rawValue = Clean(window.TrimStart(':', ' ', '\t', '\r', '\n')) ?? string.Empty;
            rawValue = rawValue.Length > 120 ? rawValue[..120] : rawValue;
        }
        else
        {
            var valueMatch = Regex.Match(window, @"(?<value>[<>]?\s*\d+(?:\.\d+)?)\s*(?<unit>[A-Za-z0-9/%°µμ\s\^]+(?:/[A-Za-z0-9^]+)?)?");
            if (!valueMatch.Success)
            {
                return null;
            }

            rawValue = valueMatch.Groups["value"].Value.Trim();
            numericValue = TryDecimal(rawValue.TrimStart('<', '>', ' '));
            unit = CleanUnit(valueMatch.Groups["unit"].Value, spec.PreferredUnits, window);
        }

        var (referenceLow, referenceHigh) = ParseReferenceValues(window, spec.PreferredUnits);
        var flag = InferFlag(numericValue, referenceLow, referenceHigh);
        return new ExtractedLabValue(spec.Name, rawValue, numericValue, unit, referenceLow, referenceHigh, flag);
    }

    private static IReadOnlyList<ExtractedLabValue> NormalizeHematologyFractions(IReadOnlyList<ExtractedLabValue> results)
    {
        var fractionTests = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "HEMATOCRIT", "NEUTROPHILS", "LYMPHOCYTES", "MONOCYTES", "EOSINOPHILS", "BASOPHILS", "STABS"
        };

        return results.Select(result =>
        {
            if (!fractionTests.Contains(result.TestName) || result.NumericValue is null or <= 0 or > 1)
            {
                return result;
            }

            var numeric = Math.Round(result.NumericValue.Value * 100, 1);
            decimal? referenceLow = result.ReferenceLow.HasValue ? Math.Round(result.ReferenceLow.Value * 100, 1) : null;
            decimal? referenceHigh = result.ReferenceHigh.HasValue ? Math.Round(result.ReferenceHigh.Value * 100, 1) : null;
            return result with
            {
                RawValue = numeric.ToString(CultureInfo.InvariantCulture),
                NumericValue = numeric,
                Unit = "%",
                ReferenceLow = referenceLow,
                ReferenceHigh = referenceHigh,
                Flag = InferFlag(numeric, referenceLow, referenceHigh)
            };
        }).ToList();
    }

    private static Dictionary<string, string> ExtractSections(string text)
    {
        var matches = SectionLabels
            .SelectMany(item => Regex.Matches(text, item.Pattern, RegexOptions.IgnoreCase)
                .Select(match => new SectionMatch(item.Key, match.Index, match.Index + match.Length)))
            .OrderBy(match => match.Start)
            .ToList();

        var sections = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < matches.Count; index++)
        {
            var current = matches[index];
            var nextStart = index + 1 < matches.Count ? matches[index + 1].Start : text.Length;
            var value = text[current.End..nextStart].Trim(' ', ':', '\r', '\n', '\t');
            if (!string.IsNullOrWhiteSpace(value) && !sections.ContainsKey(current.Key))
            {
                sections[current.Key] = value;
            }
        }

        return sections;
    }

    private static DischargeHeaderExtraction ExtractHeader(string text)
    {
        var firstSection = SectionLabels
            .SelectMany(item => Regex.Matches(text, item.Pattern, RegexOptions.IgnoreCase).Select(match => match.Index))
            .DefaultIfEmpty(text.Length)
            .Min();
        var headerText = text[..firstSection];

        string? Value(string labelPattern)
        {
            var labels = string.Join("|", HeaderLabels.Select(item => item.Pattern));
            var match = Regex.Match(
                headerText,
                $@"(?:{labelPattern})\s*:?\s*(?<value>.*?)(?=\s+(?:{labels})\s*:?\s|$)",
                RegexOptions.IgnoreCase | RegexOptions.Singleline);
            return match.Success ? Clean(match.Groups["value"].Value) : null;
        }

        var titleMatch = Regex.Match(headerText, @"\bDISCHARGE\s+SUMMARY(?:\s*/\s*MEDICAL\s+ABSTRACT)?\b", RegexOptions.IgnoreCase);
        var facility = titleMatch.Success ? Clean(headerText[..titleMatch.Index]) : Clean(headerText);

        return new DischargeHeaderExtraction(
            Facility: facility,
            DocumentTitle: titleMatch.Success ? Clean(titleMatch.Value) : null,
            PatientName: Value(@"patient(?:'s)?\s+name|patient|name"),
            Age: Value("age"),
            Sex: Value("sex|gender"),
            CivilStatus: Value("status"),
            HospitalNo: Value(@"hospital\s+no"),
            Service: Value("service/s"),
            RoomWard: Value("room/ward"),
            AttendingPhysician: Value(@"attending\s+physician"),
            ReferralDoctors: Value("referral\\s+doctor/s"),
            DateAdmitted: Value(@"date\s+admitted|date\s+of\s+admission"),
            TimeAdmitted: Value(@"time\s+admitted"),
            DateDischarged: Value(@"date\s+discharged|date\s+of\s+discharge"),
            TimeDischarged: Value(@"time\s+discharged"));
    }

    private static PhysicalExamExtraction ParsePhysicalExam(string? sectionText)
    {
        var text = Clean(sectionText);
        if (text is null)
        {
            return new PhysicalExamExtraction(null, null);
        }

        var match = Regex.Match(text, @"(?<vitals>.*?\d{2,3}\s*%\.?)\s*(?<rest>.*)", RegexOptions.IgnoreCase);
        if (match.Success && Regex.IsMatch(match.Groups["vitals"].Value, @"\b(?:BP|HR|RR|TEMP|SPO2|PR)\b|(?:\d{2,3}/\d{2,3})|(?:\s>\s)", RegexOptions.IgnoreCase))
        {
            return new PhysicalExamExtraction(Clean(match.Groups["vitals"].Value), Clean(match.Groups["rest"].Value));
        }

        return new PhysicalExamExtraction(null, text);
    }

    private static IReadOnlyList<DischargeLabExtraction> ParseDischargeLabItems(string? sectionText)
    {
        if (string.IsNullOrWhiteSpace(sectionText))
        {
            return [];
        }

        var labs = new List<DischargeLabExtraction>();
        var itemRegex = new Regex(
            @"(?<test>[A-Za-z][A-Za-z0-9 /+^-]*?)(?:\s*\((?<date>\d{2}/\d{2})\))?\s*:\s*(?<value>.*?)(?=\s+[A-Za-z][A-Za-z0-9 /+^-]*?(?:\s*\(\d{2}/\d{2}\))?\s*:|$)",
            RegexOptions.IgnoreCase | RegexOptions.Singleline);

        foreach (Match match in itemRegex.Matches(sectionText))
        {
            var value = match.Groups["value"].Value.Trim(" .;".ToCharArray());
            var flagMatch = Regex.Match(value, @"\((H|HIGH|L|LOW|ABNORMAL)\)$", RegexOptions.IgnoreCase);
            var flag = flagMatch.Success ? NormalizeFlag(flagMatch.Groups[1].Value) : null;
            if (flagMatch.Success)
            {
                value = value[..flagMatch.Index].Trim();
            }

            var unitMatch = Regex.Match(value, @"(?<val>[<>]?\s*\d+(?:\.\d+)?)(?:\s*(?<unit>[A-Za-z/%^0-9]+(?:/[A-Za-z0-9^]+)?))?$");
            labs.Add(new DischargeLabExtraction(
                Test: Clean(match.Groups["test"].Value.Trim(" .;".ToCharArray())),
                Date: match.Groups["date"].Success ? match.Groups["date"].Value : null,
                Value: unitMatch.Success ? unitMatch.Groups["val"].Value.Trim() : value,
                Unit: unitMatch.Success && unitMatch.Groups["unit"].Success ? unitMatch.Groups["unit"].Value : null,
                Flag: flag));
        }

        return labs;
    }

    private static IReadOnlyList<HospitalCourseExtraction> ExtractHospitalCourse(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var regex = new Regex(
            @"((?:on\s+the\s+day\s+of\s+admission)|(?:(?:on\s+the\s+)?\d+(?:st|nd|rd|th)?(?:\s+to\s+\d+(?:st|nd|rd|th)?)?\s+hospital\s+day))\s*\((\d{2}/\d{2}(?:-\d{2}/\d{2})?)\)",
            RegexOptions.IgnoreCase);
        var matches = regex.Matches(text).Cast<Match>().ToList();
        var results = new List<HospitalCourseExtraction>();

        for (var i = 0; i < matches.Count; i++)
        {
            var start = matches[i].Index + matches[i].Length;
            var end = i + 1 < matches.Count ? matches[i + 1].Index : text.Length;
            results.Add(new HospitalCourseExtraction(
                Label: Clean(matches[i].Groups[1].Value),
                Date: matches[i].Groups[2].Value,
                Content: Clean(text[start..end].Trim(' ', ':', '\r', '\n', '\t'))));
        }

        return results;
    }

    private static IReadOnlyList<string> ExtractMedications(string text)
    {
        var match = Regex.Match(
            text,
            @"home\s+medications?|medications?\s+(?:on\s+)?discharge|discharge\s+medications?|medications?\s+(?:given|prescribed|to\s+be\s+taken)|(?:to\s+)?continue\s+(?:the\s+following\s+)?medications?",
            RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            return [];
        }

        var block = text[(match.Index + match.Length)..].TrimStart(':', ' ', '\r', '\n', '\t');
        var stop = Regex.Match(block, @"\n\s*(?:INSTRUCTIONS?|FOLLOW[\s\-]?UP|ACTIVITY|DIET|DISPOSITION|SIGNATURE)\s*[:\n]", RegexOptions.IgnoreCase);
        if (stop.Success)
        {
            block = block[..stop.Index];
        }

        var meds = new List<string>();
        var current = "";
        foreach (var rawLine in block.Split('\n'))
        {
            var line = Regex.Replace(rawLine.Trim(), @"^[\d\.\-\*\)\s]+", "");
            if (string.IsNullOrWhiteSpace(line))
            {
                if (!string.IsNullOrWhiteSpace(current))
                {
                    meds.Add(current.Trim());
                    current = "";
                }
                continue;
            }

            if (Regex.IsMatch(line, @"\d+\.?\d*\s*(?:mg|mcg|iu|ml|meq|\bg\b|tab|cap|amp|vial|unit|drop)", RegexOptions.IgnoreCase))
            {
                if (!string.IsNullOrWhiteSpace(current))
                {
                    meds.Add(current.Trim());
                }
                current = line;
            }
            else
            {
                current = string.IsNullOrWhiteSpace(current) ? line : $"{current} {line}";
            }
        }

        if (!string.IsNullOrWhiteSpace(current))
        {
            meds.Add(current.Trim());
        }

        return meds.Where(item => item.Length > 3).Take(20).ToList();
    }

    private static IReadOnlyList<string> ExtractInstructions(string text)
    {
        var match = Regex.Match(text, @"\bINSTRUCTIONS?\s*[:\n]", RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            return [];
        }

        var block = text[(match.Index + match.Length)..];
        var stop = Regex.Match(block, @"FOLLOW[\s\-]?UP\s*[:\n]", RegexOptions.IgnoreCase);
        if (stop.Success)
        {
            block = block[..stop.Index];
        }

        return block.Split('\n')
            .Select(line => Regex.Replace(line, @"^[\s\*\-\d\.]+", "").Trim())
            .Select(line => Regex.Replace(line, @"\s*FOLLOW[\s\-]?UP.*$", "", RegexOptions.IgnoreCase).Trim())
            .Where(line => line.Length > 3)
            .Take(10)
            .ToList();
    }

    private static string? ExtractFollowUp(string text)
    {
        var match = Regex.Match(text, @"FOLLOW[\s\-]?UP\s*[:\n]?", RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            return null;
        }

        var lines = text[(match.Index + match.Length)..]
            .Split('\n')
            .Select(line => line.Trim())
            .Where(line => line.Length > 0)
            .Take(4);
        return Clean(string.Join(' ', lines));
    }

    private static string? ExtractAllergies(string text)
    {
        var match = Regex.Match(text, @"(?:drug\s+)?allergi(?:es|c\s+to|a)\s*:?\s*([^\n\r]{2,80})", RegexOptions.IgnoreCase);
        if (match.Success)
        {
            return Clean(match.Groups[1].Value);
        }

        return Regex.IsMatch(text, @"\bNKDA\b", RegexOptions.IgnoreCase) ? "NKDA (No Known Drug Allergies)" : null;
    }

    private static string Normalize(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "";
        }

        var cleaned = text.Replace("\r\n", "\n").Replace('\r', '\n').Replace('\0', ' ');
        cleaned = Regex.Replace(cleaned, @"[|]{2,}|_{3,}|\.{4,}|-{3,}", " ");
        cleaned = Regex.Replace(cleaned, @"[^\x09\x0A\x20-\x7E]", " ");
        cleaned = Regex.Replace(cleaned, @"[ \t]{2,}", " ");
        cleaned = Regex.Replace(cleaned, @"\n{3,}", "\n\n");
        return cleaned.Trim();
    }

    private static string Compact(string? text) => Whitespace.Replace(Normalize(text ?? ""), " ").Trim();

    private static string? Clean(string? text)
    {
        var value = Compact(text);
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    private static string? ExtractMetadataValue(string text, string labelPattern, string stopPattern)
    {
        var match = Regex.Match(text, $@"(?:{labelPattern})\s*:?\s*(.*?)(?=\s+(?:{stopPattern})\s*:?\s|$)", RegexOptions.IgnoreCase);
        return match.Success ? Clean(match.Groups[1].Value) : null;
    }

    private static string? TitleCaseName(string? name)
    {
        var cleaned = Clean(name);
        if (cleaned is null || cleaned != cleaned.ToUpperInvariant())
        {
            return cleaned;
        }

        return CultureInfo.CurrentCulture.TextInfo.ToTitleCase(cleaned.ToLowerInvariant());
    }

    private static int? TryInt(string? value)
    {
        var match = Regex.Match(value ?? "", @"\d+");
        return match.Success && int.TryParse(match.Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static decimal? TryDecimal(string value)
    {
        var match = Regex.Match(value, @"[-+]?\d+(?:\.\d+)?");
        return match.Success && decimal.TryParse(match.Value, NumberStyles.Number, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static string? CleanUnit(string rawUnit, IReadOnlyList<string> preferredUnits, string window)
    {
        var unit = Clean(rawUnit);
        if (unit is not null && Regex.IsMatch(unit, @"^(mg/dl|mmol/l|u/l|g/l|g/dl|%|fl|pg|x\s*10\^?12/l|x\s*10\^?9/l|sec|mins?|mm/hr)$", RegexOptions.IgnoreCase))
        {
            return unit;
        }

        return preferredUnits.FirstOrDefault(candidate => window.Contains(candidate, StringComparison.OrdinalIgnoreCase));
    }

    private static (decimal? Low, decimal? High) ParseReferenceValues(string text, IReadOnlyList<string> preferredUnits)
    {
        foreach (var unit in preferredUnits.DefaultIfEmpty(""))
        {
            var escapedUnit = string.IsNullOrWhiteSpace(unit) ? "" : $@"\s*{Regex.Escape(unit)}";
            var range = Regex.Match(text, $@"(?<low>\d+(?:\.\d+)?)\s*-\s*(?<high>\d+(?:\.\d+)?){escapedUnit}", RegexOptions.IgnoreCase);
            if (range.Success)
            {
                return (TryDecimal(range.Groups["low"].Value), TryDecimal(range.Groups["high"].Value));
            }

            var lessThan = Regex.Match(text, $@"less than\s*(?<high>\d+(?:\.\d+)?){escapedUnit}", RegexOptions.IgnoreCase);
            if (lessThan.Success)
            {
                return (null, TryDecimal(lessThan.Groups["high"].Value));
            }

            var greaterThan = Regex.Match(text, $@">\s*(?<low>\d+(?:\.\d+)?){escapedUnit}", RegexOptions.IgnoreCase);
            if (greaterThan.Success)
            {
                return (TryDecimal(greaterThan.Groups["low"].Value), null);
            }
        }

        return (null, null);
    }

    private static string? InferFlag(decimal? value, decimal? low, decimal? high)
    {
        if (value is null)
        {
            return null;
        }

        if (high.HasValue && value.Value > high.Value) return "high";
        if (low.HasValue && value.Value < low.Value) return "low";
        return null;
    }

    private static string? NormalizeFlag(string rawFlag)
    {
        var flag = rawFlag.Trim().ToLowerInvariant();
        if (flag is "h" or "high") return "high";
        if (flag is "l" or "low") return "low";
        return "abnormal";
    }

    private static string? Get(IReadOnlyDictionary<string, string> values, string key) =>
        values.TryGetValue(key, out var value) ? value : null;

    private static readonly LabTestSpec[] ChemistryTests =
    [
        new("CREATININE", "creatinine", ["mg/dL"]),
        new("BLOOD URIC ACID", "blood uric acid", ["mg/dL"]),
        new("FBS", "(?:fbs|fasting blood sugar)", ["mg/dL"]),
        new("TOTAL CHOLESTEROL", "total\\s*cholesterol", ["mg/dL"]),
        new("TRIGLYCERIDES", "triglycerides", ["mg/dL"]),
        new("HDL", "\\bhdl\\b", ["mg/dL"]),
        new("LDL", "\\bldl\\b", ["mg/dL"]),
        new("VLDL", "\\bvldl\\b", ["mg/dL"]),
        new("CHOLESTEROL/HDL RATIO", "cholesterol\\s*/\\s*hdl\\s*ratio|cholesterol\\s*hdl\\s*ratio", []),
        new("SGPT/ALT", "sgpt\\s*/\\s*alt|alt\\b", ["U/L"]),
        new("SODIUM", "sodium", ["mmol/L"]),
        new("POTASSIUM", "potassium", ["mmol/L"]),
        new("CHLORIDE", "chloride", ["mmol/L"])
    ];

    private static readonly LabTestSpec[] HematologyTests =
    [
        new("HEMOGLOBIN", "hemoglobin", ["g/L"]),
        new("HEMATOCRIT", "hematocrit", ["%"]),
        new("RBC", "r\\.b\\.c\\.|rbc", ["x 10^12/L"]),
        new("WBC", "w\\.b\\.c\\.|wbc", ["x 10^9/L"]),
        new("NEUTROPHILS", "neutrophils", ["%"]),
        new("LYMPHOCYTES", "lymphocytes", ["%"]),
        new("MONOCYTES", "monocytes", ["%"]),
        new("EOSINOPHILS", "eosinophils", ["%"]),
        new("BASOPHILS", "basophils", ["%"]),
        new("STABS", "stabs", ["%"]),
        new("PLATELET COUNT", "platelet count", ["x 10^9/L"]),
        new("MCV", "\\bmcv\\b", ["fl"]),
        new("MCH", "\\bmch\\b", ["pg"]),
        new("MCHC", "\\bmchc\\b", ["g/dl"]),
        new("ESR", "\\besr\\b", ["mm/hr"]),
        new("BLEEDING TIME", "bleeding time", ["min"]),
        new("CLOTTING TIME", "clotting time", ["min"]),
        new("PROTIME CONTROL TEST", "protime control test", ["sec"]),
        new("%ACT INR", "%act inr", []),
        new("APTT CONTROL TEST", "aptt control test", ["sec"]),
        new("ABO TYPE", "abo type", [], true),
        new("RH TYPE", "rh type", [], true),
        new("REMARKS", "remarks", [], true)
    ];

    private static readonly LabTestSpec[] MicroscopyTests =
    [
        new("COLOR", "\\bcolor\\b", [], true),
        new("TRANSPARENCY", "transparency", [], true),
        new("RBC", "r\\.b\\.c\\.|rbc", []),
        new("PUS CELLS", "pus cells", []),
        new("LEUKOCYTES", "leukocytes", []),
        new("PH", "\\bph\\b", []),
        new("SP. GRAVITY", "sp\\.\\s*gravity", []),
        new("EPITHELIAL CELLS", "epithelial cells", [], true),
        new("HYALINE", "hyaline", [], true),
        new("FINE GRANULAR", "fine granular", [], true),
        new("COARSE GRANULAR", "coarse granular", [], true),
        new("BILIRUBIN", "bilirubin", [], true),
        new("MUCUS THREADS", "mucus threads", [], true),
        new("UROBILINOGEN", "urobilinogen", [], true),
        new("YEAST CELLS", "yeast cells", [], true),
        new("RENAL CELLS", "renal cells", [], true),
        new("KETONE", "ketone", [], true),
        new("PROTEIN", "protein", [], true),
        new("NITRITE", "nitrite", [], true),
        new("GLUCOSE", "glucose", [], true),
        new("URINE PREGNANCY TEST", "urine pregnancy test", [], true),
        new("URINE MICRAL TEST", "urine micral test", ["mg/L"], true),
        new("AMORPHOUS URATES", "amorphous urates", [], true),
        new("URIC ACID", "uric acid", [], true),
        new("CALCIUM OXALATE", "calcium oxalate", [], true),
        new("AMORPHOUS PHOSPHATES", "amorphous phosphates", [], true),
        new("TRIPLE PHOSPHATES", "triple phosphates", [], true)
    ];

    private static readonly LabTestSpec[] AllLabTests = ChemistryTests.Concat(HematologyTests).Concat(MicroscopyTests).ToArray();

    private static readonly (string Key, string Pattern)[] SectionLabels =
    [
        ("condition_discharge", @"(?<![A-Za-z0-9])condition\s+upon\s+discharge\s*:"),
        ("chief_complaint", @"(?<![A-Za-z0-9])chief\s+complaint\s*:"),
        ("admitting_dx", @"(?<![A-Za-z0-9])admitting\s+diagnosis\s*:"),
        ("final_dx", @"(?<![A-Za-z0-9])final\s+diagnosis\s*:"),
        ("hpi", @"(?<![A-Za-z0-9])history\s+of\s+present\s+illness\s*:"),
        ("pmh", @"(?<![A-Za-z0-9])past\s+(?:medical\s+)?history\s*:"),
        ("physical_exam", @"(?<![A-Za-z0-9])physical\s+exam(?:ination)?\s*:"),
        ("laboratory_data", @"(?<![A-Za-z0-9])laboratory\s+(?:data|results?)\s*:"),
        ("hospital_course", @"(?<![A-Za-z0-9])(?:hospital\s+course|course\s+in\s+the\s+ward|course\s+in\s+ward)\s*:?")
    ];

    private static readonly (string Key, string Pattern)[] HeaderLabels =
    [
        ("patient_name", @"patient(?:'s)?\s+name|patient|name"),
        ("age", "age"),
        ("sex", "sex|gender"),
        ("civil_status", "status"),
        ("hospital_no", @"hospital\s+no"),
        ("service", "service/s"),
        ("room_ward", "room/ward"),
        ("attending_physician", @"attending\s+physician"),
        ("referral_doctors", @"referral\s+doctor/s"),
        ("date_admitted", @"date\s+admitted|date\s+of\s+admission"),
        ("time_admitted", @"time\s+admitted"),
        ("date_discharged", @"date\s+discharged|date\s+of\s+discharge"),
        ("time_discharged", @"time\s+discharged")
    ];

    private sealed record LabTestSpec(string Name, string Pattern, IReadOnlyList<string> PreferredUnits, bool IsTextValue = false);
    private sealed record SectionMatch(string Key, int Start, int End);
}

public sealed record PatientMetadata(string? Name, int? AgeYears, string? Sex);

public sealed record ExtractedLabValue(
    string TestName,
    string RawValue,
    decimal? NumericValue,
    string? Unit,
    decimal? ReferenceLow,
    decimal? ReferenceHigh,
    string? Flag);

public sealed record DischargeHeaderExtraction(
    string? Facility,
    string? DocumentTitle,
    string? PatientName,
    string? Age,
    string? Sex,
    string? CivilStatus,
    string? HospitalNo,
    string? Service,
    string? RoomWard,
    string? AttendingPhysician,
    string? ReferralDoctors,
    string? DateAdmitted,
    string? TimeAdmitted,
    string? DateDischarged,
    string? TimeDischarged);

public sealed record PhysicalExamExtraction(string? Vitals, string? Findings);

public sealed record DischargeLabExtraction(string? Test, string? Date, string? Value, string? Unit, string? Flag);

public sealed record HospitalCourseExtraction(string? Label, string? Date, string? Content);

public sealed record DischargeExtraction(
    DischargeHeaderExtraction Header,
    string? ConditionOnDischarge,
    string? ChiefComplaint,
    string? AdmittingDiagnosis,
    string? FinalDiagnosis,
    string? HistoryOfPresentIllness,
    string? PastMedicalHistory,
    string? Allergies,
    string? FollowUp,
    PhysicalExamExtraction PhysicalExam,
    string? LaboratoryData,
    IReadOnlyList<DischargeLabExtraction> Labs,
    IReadOnlyList<HospitalCourseExtraction> HospitalCourse,
    IReadOnlyList<string> Medications,
    IReadOnlyList<string> Instructions);
