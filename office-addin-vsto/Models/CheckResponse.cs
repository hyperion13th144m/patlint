using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PatlintAddin.Models;

public class CheckResponse
{
    [JsonPropertyName("diagnostic_views")]
    public List<DiagnosticView> DiagnosticViews { get; set; } = new();

    [JsonPropertyName("claims")]
    public List<ClaimView> Claims { get; set; } = new();

    [JsonPropertyName("reference_sign_entries")]
    public List<ReferenceSignEntry> ReferenceSignEntries { get; set; } = new();

    [JsonPropertyName("term_occurrences")]
    public Dictionary<string, List<string>> TermOccurrences { get; set; } = new();

    [JsonPropertyName("unit_checks")]
    public List<UnitCheck> UnitChecks { get; set; } = new();

    [JsonPropertyName("summary")]
    public SummaryCount Summary { get; set; } = new();
}

public class SummaryCount
{
    [JsonPropertyName("error")]   public int Error   { get; set; }
    [JsonPropertyName("warning")] public int Warning { get; set; }
    [JsonPropertyName("info")]    public int Info    { get; set; }
}

public class DiagnosticView
{
    [JsonPropertyName("severity")]       public string Severity      { get; set; } = "";
    [JsonPropertyName("severity_label")] public string SeverityLabel { get; set; } = "";
    [JsonPropertyName("rule_id")]        public string RuleId        { get; set; } = "";
    [JsonPropertyName("rule_label")]     public string RuleLabel     { get; set; } = "";
    [JsonPropertyName("message")]        public string Message       { get; set; } = "";
    [JsonPropertyName("location")]       public string Location      { get; set; } = "";
    [JsonPropertyName("location_data")]  public LocationData? LocationData { get; set; }
}

public class LocationData
{
    [JsonPropertyName("block_index")]   public int?    BlockIndex   { get; set; }
    [JsonPropertyName("section_type")]  public string? SectionType  { get; set; }
    [JsonPropertyName("claim_number")]  public int?    ClaimNumber  { get; set; }
    [JsonPropertyName("search_text")]   public string? SearchText   { get; set; }
}

public class ClaimView
{
    [JsonPropertyName("number")]                    public int    Number                   { get; set; }
    [JsonPropertyName("text")]                      public string Text                     { get; set; } = "";
    [JsonPropertyName("referenced_claims")]         public List<int> ReferencedClaims      { get; set; } = new();
    [JsonPropertyName("is_multiple_dependent")]     public bool   IsMultipleDependent      { get; set; }
    [JsonPropertyName("is_multi_multi")]            public bool   IsMultiMulti             { get; set; }
}

public class ReferenceSignEntry
{
    [JsonPropertyName("sign")]   public string Sign   { get; set; } = "";
    [JsonPropertyName("term")]   public string Term   { get; set; } = "";
    [JsonPropertyName("source")] public string Source { get; set; } = "";
}

public class UnitCheck
{
    [JsonPropertyName("matched")]  public string Matched  { get; set; } = "";
    [JsonPropertyName("unit")]     public string Unit     { get; set; } = "";
    [JsonPropertyName("message")]  public string Message  { get; set; } = "";
}
