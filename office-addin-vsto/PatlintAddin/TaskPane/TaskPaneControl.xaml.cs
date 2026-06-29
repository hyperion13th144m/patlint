using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using Docs = System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Navigation;
using PatlintAddin.Models;
using PatlintAddin.Properties;
using PatlintAddin.Services;
using Word = Microsoft.Office.Interop.Word;

namespace PatlintAddin.TaskPane
{
    public partial class TaskPaneControl : UserControl
    {
        // ------------------------------------------------------------------ //
        //  Fields
        // ------------------------------------------------------------------ //

        private readonly ApiClient      _api     = new ApiClient();
        private readonly Word.Application _wordApp;

        private List<DiagnosticView>    _lastDiagnostics  = new List<DiagnosticView>();
        private List<ReferenceSignEntry> _referenceEntries = new List<ReferenceSignEntry>();
        private string                  _documentId       = null;
        private List<ProofreadItem>     _proofreadItems   = new List<ProofreadItem>();
        private bool                    _proofreadDone    = false;
        private CancellationTokenSource _aiCts            = null;

        // Severity filter state: true = visible
        private readonly Dictionary<string, bool> _sevActive =
            new Dictionary<string, bool> { { "error", true }, { "warning", true }, { "info", true } };
        // Maps each issue element to its severity for filtering
        private readonly List<(string Sev, FrameworkElement El)> _diagIssueElements =
            new List<(string, FrameworkElement)>();
        // Maps each group row (Border) so we can hide when all children are hidden
        private readonly List<(Border Row, List<FrameworkElement> Issues)> _diagGroupRows =
            new List<(Border, List<FrameworkElement>)>();

        private class ProofreadItem
        {
            public string Label         { get; set; }
            public bool   HasCorrection { get; set; }
            public string OriginalText  { get; set; }
            public string CorrectedText { get; set; }
            public bool   Displayed     { get; set; }
        }

        // ------------------------------------------------------------------ //
        //  Colors (matching Web UI CSS vars)
        // ------------------------------------------------------------------ //

        private static readonly Color CAccent  = (Color)ColorConverter.ConvertFromString("#1f6f5b");
        private static readonly Color CAi      = (Color)ColorConverter.ConvertFromString("#6d28d9");
        private static readonly Color CError   = (Color)ColorConverter.ConvertFromString("#b91c1c");
        private static readonly Color CWarning = (Color)ColorConverter.ConvertFromString("#a16207");
        private static readonly Color CInfo    = (Color)ColorConverter.ConvertFromString("#1d4ed8");
        private static readonly Color CMuted   = (Color)ColorConverter.ConvertFromString("#6b7280");
        private static readonly Color CBorder  = (Color)ColorConverter.ConvertFromString("#d1d5db");
        private static readonly Color CPanel   = (Color)ColorConverter.ConvertFromString("#f9fafb");

        // ------------------------------------------------------------------ //
        //  Constructor
        // ------------------------------------------------------------------ //

        public TaskPaneControl(Word.Application wordApp)
        {
            InitializeComponent();
            _wordApp = wordApp;
            _api.BaseUrl = Settings.Default.ApiUrl;
            ApiUrlBox.Text = _api.BaseUrl;
        }

        // ------------------------------------------------------------------ //
        //  Settings / header
        // ------------------------------------------------------------------ //

        private void ApiUrlBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            _api.BaseUrl = ApiUrlBox.Text.TrimEnd('/');
        }

        private void SaveApiUrl_Click(object sender, RoutedEventArgs e)
        {
            Settings.Default.ApiUrl = ApiUrlBox.Text.TrimEnd('/');
            Settings.Default.Save();
            SetStatus("API URLを保存しました。");
        }

        private void OpenUi_Click(object sender, RoutedEventArgs e)
        {
            var url = ApiUrlBox.Text.TrimEnd('/') + "/ui";
            try { System.Diagnostics.Process.Start(url); } catch { }
        }

        private void HelpLink_Click(object sender, RequestNavigateEventArgs e)
        {
            try { System.Diagnostics.Process.Start(_api.BaseUrl.TrimEnd('/') + "/help"); } catch { }
            e.Handled = true;
        }

        // ------------------------------------------------------------------ //
        //  API health check
        // ------------------------------------------------------------------ //

        private async void CheckApi_Click(object sender, RoutedEventArgs e)
        {
            SetBusy(true);
            try
            {
                var status = await _api.CheckHealthAsync();
                var ok = status == "ok";
                SetStatus(ok ? "API ready" : "API status: " + status, isError: !ok);
                HealthText.Text = ok ? "API ready" : "API unavailable";
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, isError: true);
                HealthText.Text = "API unavailable";
            }
            finally { SetBusy(false); }
        }

        // ------------------------------------------------------------------ //
        //  Document check
        // ------------------------------------------------------------------ //

        private void CopyDocument_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                var doc = _wordApp.ActiveDocument;
                if (doc == null) { SetStatus("アクティブな文書がありません。"); return; }
                string text = doc.Content.Text;
                System.Windows.Clipboard.SetText(text);
                SetStatus("文書全体をクリップボードにコピーしました。");
            }
            catch (Exception ex)
            {
                SetStatus($"コピーに失敗しました: {ex.Message}");
            }
        }

        private async void CheckDocument_Click(object sender, RoutedEventArgs e)
        {
            SetBusy(true);
            SetStatus("文書を読み取っています...");
            ResetResultArea();

            try
            {
                var doc = _wordApp.ActiveDocument;
                if (doc == null) throw new InvalidOperationException("アクティブな文書がありません。");
                string text = doc.Content.Text;
                if (string.IsNullOrWhiteSpace(text)) throw new InvalidOperationException("文書本文が空です。");

                SetStatus("解析中...");
                var response = await _api.UploadTextAsync(text);
                _lastDiagnostics = response.DiagnosticViews;
                _documentId = response.DocumentId;
                Render(response);
                SetStatus("解析が完了しました。");

                if (_documentId != null)
                {
                    AiPanel.Visibility = Visibility.Visible;
                    UpdateAiSubmitState();
                }
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, isError: true);
            }
            finally { SetBusy(false); }
        }

        private void ResetResultArea()
        {
            _documentId = null;
            _proofreadItems.Clear();
            _proofreadDone = false;
            _diagIssueElements.Clear();
            _diagGroupRows.Clear();
            AiPanel.Visibility = Visibility.Collapsed;
            EmptyState.Visibility = Visibility.Visible;
            ResultTabs.Visibility = Visibility.Collapsed;
            DiagPanel.Children.Clear();
            ClaimsPanel.Children.Clear();
            ReferencePanel.Children.Clear();
            TermsPanel.Children.Clear();
            AiResultPanel.Children.Clear();
            SummaryPanel.Children.Clear();
            TokenLogPanel.Children.Clear();
            AiStatusText.Text = "";
            UpdateAiTabHeader(0);
        }

        // ------------------------------------------------------------------ //
        //  Main render
        // ------------------------------------------------------------------ //

        private void Render(CheckResponse data)
        {
            RenderSummary(data.Summary);

            var ruleViews = data.DiagnosticViews.Where(d => !d.RuleId.StartsWith("AI_")).ToList();
            RenderDiagnosticsPanel(ruleViews, data.Blocks);
            RenderClaimsPanel(data.Claims);
            RenderReferencePanel(data.ReferenceSignEntries);
            RenderTermsPanel(data.TermOccurrences, data.UnitChecks);

            EmptyState.Visibility = Visibility.Collapsed;
            ResultTabs.Visibility = Visibility.Visible;
            ResultTabs.SelectedIndex = 0;
        }

        // ------------------------------------------------------------------ //
        //  Summary pills
        // ------------------------------------------------------------------ //

        private void RenderSummary(SummaryCount counts)
        {
            SummaryPanel.Children.Clear();
            SummaryPanel.Children.Add(MakePill("Error "   + counts.Error,   "#b91c1c", "#fef2f2", "#fecaca"));
            SummaryPanel.Children.Add(MakePill("Warning " + counts.Warning, "#a16207", "#fffbeb", "#fde68a"));
            SummaryPanel.Children.Add(MakePill("Info "    + counts.Info,    "#1d4ed8", "#eff6ff", "#bfdbfe"));
        }

        private Border MakePill(string text, string fg, string bg, string border)
        {
            return new Border
            {
                Child = new TextBlock { Text = text, FontSize = 12,
                    Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(fg)) },
                Background      = new SolidColorBrush((Color)ColorConverter.ConvertFromString(bg)),
                BorderBrush     = new SolidColorBrush((Color)ColorConverter.ConvertFromString(border)),
                BorderThickness = new Thickness(1),
                CornerRadius    = new CornerRadius(999),
                Padding         = new Thickness(8, 3, 8, 3),
                Margin          = new Thickness(0, 0, 5, 3),
            };
        }

        // ------------------------------------------------------------------ //
        //  Diagnostics panel (grouped by location)
        // ------------------------------------------------------------------ //

        private void RenderDiagnosticsPanel(List<DiagnosticView> diagnostics, List<Block> blocks)
        {
            DiagPanel.Children.Clear();
            _diagIssueElements.Clear();
            _diagGroupRows.Clear();
            _sevActive["error"] = _sevActive["warning"] = _sevActive["info"] = true;

            if (!diagnostics.Any())
            {
                DiagPanel.Children.Add(MakeEmpty("指摘事項はありません。"));
                return;
            }

            var blockMap = blocks.ToDictionary(b => b.Index, b => b);

            Block FindBlockBySearchText(string searchText)
            {
                if (string.IsNullOrEmpty(searchText)) return null;
                var header = ExtractHeader(searchText) ?? searchText;
                return blocks.FirstOrDefault(b => b.Text.StartsWith(header));
            }

            // Associate each diagnostic with a block
            var withBlock = diagnostics.Select(d =>
            {
                var loc = d.LocationData;
                Block block = null;
                if (loc?.BlockIndex != null && blockMap.TryGetValue(loc.BlockIndex.Value, out var b)) block = b;
                if (block == null && loc?.SearchText != null) block = FindBlockBySearchText(loc.SearchText);
                return (d, block);
            }).ToList();

            // Group by block index (null → unknown)
            var groups = new Dictionary<string, (Block block, List<DiagnosticView> items)>();
            var groupOrder = new List<string>();
            foreach (var (d, block) in withBlock)
            {
                var key = block != null ? block.Index.ToString() : "__unknown__";
                if (!groups.ContainsKey(key))
                {
                    groups[key] = (block, new List<DiagnosticView>());
                    groupOrder.Add(key);
                }
                groups[key].items.Add(d);
            }
            groupOrder.Sort((a, b) =>
            {
                if (a == "__unknown__") return 1;
                if (b == "__unknown__") return -1;
                return int.Parse(a) - int.Parse(b);
            });

            // Severity filter bar
            var sevCount = new Dictionary<string, int> { { "error", 0 }, { "warning", 0 }, { "info", 0 } };
            foreach (var key in groupOrder)
                foreach (var d in groups[key].items)
                    if (sevCount.ContainsKey(d.Severity)) sevCount[d.Severity]++;

            var filterBar = new WrapPanel { Margin = new Thickness(0, 0, 0, 8) };
            filterBar.Children.Add(new TextBlock { Text = "表示：", FontSize = 11,
                Foreground = new SolidColorBrush(CMuted), VerticalAlignment = VerticalAlignment.Center });

            if (sevCount["error"] > 0)
                filterBar.Children.Add(MakeSevFilterBtn("error",   $"● Error {sevCount["error"]}",   "#fee2e2", "#fca5a5", "#991b1b"));
            if (sevCount["warning"] > 0)
                filterBar.Children.Add(MakeSevFilterBtn("warning", $"▲ Warning {sevCount["warning"]}", "#fef3c7", "#fcd34d", "#92400e"));
            if (sevCount["info"] > 0)
                filterBar.Children.Add(MakeSevFilterBtn("info",    $"◆ Info {sevCount["info"]}",      "#dbeafe", "#93c5fd", "#1e40af"));

            DiagPanel.Children.Add(filterBar);

            // Group rows
            var SEVERITY_ORDER = new Dictionary<string, int> { { "error", 0 }, { "warning", 1 }, { "info", 2 } };
            foreach (var key in groupOrder)
            {
                var (block, items) = groups[key];
                var header = block != null
                    ? (ExtractHeader(block.Text) ?? "(位置不明)")
                    : (items[0].LocationData?.SearchText ?? "(位置不明)");

                if (block != null && ExtractHeader(block.Text) == null) continue;

                var sortedItems = items
                    .OrderBy(d => SEVERITY_ORDER.TryGetValue(d.Severity, out var o) ? o : 9)
                    .ToList();

                // Header cell
                var headerTb = new TextBlock
                {
                    Text = header, FontSize = 11, FontWeight = FontWeights.Bold,
                    FontFamily = new FontFamily("Consolas, Courier New"),
                    TextWrapping = TextWrapping.Wrap,
                };
                var headerCell = new Border
                {
                    Child = headerTb, Width = 82,
                    Padding = new Thickness(5), VerticalAlignment = VerticalAlignment.Top,
                    BorderBrush = new SolidColorBrush(CBorder), BorderThickness = new Thickness(0, 0, 1, 0),
                };

                // Issues cell
                var issuesStack = new StackPanel();
                var issueElements = new List<FrameworkElement>();

                foreach (var d in sortedItems)
                {
                    var issueEl = BuildIssueElement(d);
                    issueElements.Add(issueEl);
                    _diagIssueElements.Add((d.Severity, issueEl));
                    issuesStack.Children.Add(issueEl);
                }

                var issuesCell = new Border
                {
                    Child = issuesStack,
                    Padding = new Thickness(6),
                };

                // Row grid
                var rowGrid = new Grid();
                rowGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(82) });
                rowGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                Grid.SetColumn(headerCell, 0);
                Grid.SetColumn(issuesCell, 1);
                rowGrid.Children.Add(headerCell);
                rowGrid.Children.Add(issuesCell);

                var rowBorder = new Border
                {
                    Child = rowGrid,
                    BorderBrush = new SolidColorBrush(CBorder),
                    BorderThickness = new Thickness(1),
                    Margin = new Thickness(0, 0, 0, -1),
                };

                _diagGroupRows.Add((rowBorder, issueElements));
                DiagPanel.Children.Add(rowBorder);
            }
        }

        private Button MakeSevFilterBtn(string sev, string label, string bg, string border, string fg)
        {
            var btn = new Button
            {
                Content = label,
                Tag = sev,
                Style = (Style)FindResource("SevBtn"),
                Background  = new SolidColorBrush((Color)ColorConverter.ConvertFromString(bg)),
                BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(border)),
                Foreground  = new SolidColorBrush((Color)ColorConverter.ConvertFromString(fg)),
                Margin = new Thickness(0, 0, 4, 0),
            };
            btn.Click += SevFilterBtn_Click;
            return btn;
        }

        private void SevFilterBtn_Click(object sender, RoutedEventArgs e)
        {
            var btn = (Button)sender;
            var sev = (string)btn.Tag;
            _sevActive[sev] = !_sevActive[sev];

            // Dim/restore button appearance
            btn.Opacity = _sevActive[sev] ? 1.0 : 0.4;

            // Show/hide individual issue elements
            foreach (var (elSev, el) in _diagIssueElements)
                if (elSev == sev) el.Visibility = _sevActive[sev] ? Visibility.Visible : Visibility.Collapsed;

            // Hide entire row if all issues are hidden
            foreach (var (row, issues) in _diagGroupRows)
            {
                var allHidden = issues.All(el => el.Visibility == Visibility.Collapsed);
                row.Visibility = allHidden ? Visibility.Collapsed : Visibility.Visible;
            }
        }

        private FrameworkElement BuildIssueElement(DiagnosticView d)
        {
            var isAi = d.RuleId.StartsWith("AI_");
            var hasDetail = d.OriginalText != null || d.Reason != null || d.Suggestion != null;
            var hasLocation = d.LocationData != null &&
                              (d.LocationData.SearchText != null || d.LocationData.BlockIndex != null);

            var dot = new TextBlock
            {
                Text = d.Severity == "error" ? "●" : d.Severity == "warning" ? "▲" : "◆",
                FontSize = 11,
                Foreground = d.Severity == "error"   ? new SolidColorBrush(CError)
                           : d.Severity == "warning" ? new SolidColorBrush(CWarning)
                                                     : new SolidColorBrush(CInfo),
                Margin = new Thickness(0, 2, 5, 0),
                VerticalAlignment = VerticalAlignment.Top,
            };

            // Label row
            var labelStack = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 2) };
            if (isAi)
            {
                labelStack.Children.Add(new Border
                {
                    Child = new TextBlock { Text = "AI", FontSize = 10, FontWeight = FontWeights.Bold,
                        Foreground = new SolidColorBrush(CAi) },
                    Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#f5f3ff")),
                    BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#ddd6fe")),
                    BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(4, 1, 4, 1), Margin = new Thickness(0, 0, 4, 0),
                    VerticalAlignment = VerticalAlignment.Center,
                });
            }
            labelStack.Children.Add(new TextBlock
            {
                Text = d.RuleLabel, FontSize = 11, FontWeight = FontWeights.Bold,
                Foreground = new SolidColorBrush(CMuted), TextWrapping = TextWrapping.Wrap,
            });

            var messageTb = new TextBlock
            {
                Text = d.Message, FontSize = 12, TextWrapping = TextWrapping.Wrap,
            };

            var bodyStack = new StackPanel { Margin = new Thickness(0, 0, 0, 0) };
            bodyStack.Children.Add(labelStack);
            bodyStack.Children.Add(messageTb);

            // Expandable detail
            if (hasDetail)
            {
                var detailStack = new StackPanel
                {
                    Margin = new Thickness(0, 4, 0, 0),
                };
                if (d.OriginalText != null) detailStack.Children.Add(MakeDetailRow("原文", d.OriginalText));
                if (d.Reason != null)       detailStack.Children.Add(MakeDetailRow("根拠", d.Reason));
                if (d.Suggestion != null)   detailStack.Children.Add(MakeDetailRow("修正案", d.Suggestion));

                var expander = new Expander
                {
                    Header = "詳細",
                    FontSize = 11,
                    Content = new Border
                    {
                        Child = detailStack,
                        Background = new SolidColorBrush(CPanel),
                        BorderBrush = new SolidColorBrush(CBorder),
                        BorderThickness = new Thickness(1),
                        CornerRadius = new CornerRadius(4),
                        Padding = new Thickness(8, 6, 8, 6),
                        Margin = new Thickness(0, 4, 0, 0),
                    },
                };
                bodyStack.Children.Add(expander);
            }

            // Jump button
            if (hasLocation)
            {
                var capturedD = d;
                var jumpBtn = new Button
                {
                    Content = "移動", Style = (Style)FindResource("SmallBtn"),
                    HorizontalAlignment = HorizontalAlignment.Left,
                    Margin = new Thickness(0, 4, 0, 0),
                };
                jumpBtn.Click += (_, __) =>
                {
                    if (capturedD.LocationData != null)
                    {
                        bool ok = WordJumpService.JumpTo(_wordApp, capturedD.LocationData);
                        if (!ok) SetStatus("該当箇所が見つかりませんでした。", isError: true);
                    }
                };
                bodyStack.Children.Add(jumpBtn);
            }

            var row = new DockPanel { Margin = new Thickness(0, 0, 0, 6), LastChildFill = true };
            DockPanel.SetDock(dot, Dock.Left);
            row.Children.Add(dot);
            row.Children.Add(bodyStack);
            return row;
        }

        private static UIElement MakeDetailRow(string key, string value)
        {
            var panel = new WrapPanel { Margin = new Thickness(0, 0, 0, 3) };
            panel.Children.Add(new TextBlock { Text = key + "：", FontWeight = FontWeights.Bold,
                FontSize = 11, Foreground = new SolidColorBrush(CMuted) });
            panel.Children.Add(new TextBlock { Text = value, FontSize = 11,
                TextWrapping = TextWrapping.Wrap });
            return panel;
        }

        // ------------------------------------------------------------------ //
        //  Claims panel
        // ------------------------------------------------------------------ //

        private void RenderClaimsPanel(List<ClaimView> claims)
        {
            ClaimsPanel.Children.Clear();
            if (!claims.Any()) { ClaimsPanel.Children.Add(MakeEmpty("請求項データがありません。")); return; }

            var incoming = new Dictionary<int, List<int>>();
            foreach (var c in claims)
                foreach (var r in c.ReferencedClaims)
                {
                    if (!incoming.ContainsKey(r)) incoming[r] = new List<int>();
                    incoming[r].Add(c.Number);
                }

            var headers = new[] { "請求項", "従属先", "被従属", "種別", "状態" };
            var widths  = new[] { 48.0, double.NaN, double.NaN, 60.0, double.NaN };
            var grid = MakeTableGrid(headers, widths);
            int row = 1;

            foreach (var c in claims.OrderBy(x => x.Number))
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                var refs = c.ReferencedClaims;
                var kind = refs.Count == 0 ? "独立項"
                         : new HashSet<int>(refs).Count > 1 ? "複数従属項" : "従属項";
                var states = new List<string>();
                if (c.IsMultiMulti)                states.Add("マルチマルチ");
                if (c.ReferencesMultiMulti)        states.Add("MM引用");
                if (c.ReferencesMultipleDependent) states.Add("複数従属引用");

                var inList = incoming.ContainsKey(c.Number) ? incoming[c.Number] : new List<int>();
                AddTableCell(grid, "請求項" + c.Number, row, 0);
                AddTableCell(grid, refs.Count > 0 ? string.Join("、", refs.Select(n => "請求項" + n)) : "－", row, 1);
                AddTableCell(grid, inList.Count > 0 ? string.Join("、", inList.Distinct().OrderBy(x => x).Select(n => "請求項" + n)) : "－", row, 2);
                AddTableCell(grid, kind, row, 3);
                AddTableCell(grid, states.Count > 0 ? string.Join("、", states) : "－", row, 4);
                row++;
            }
            ClaimsPanel.Children.Add(grid);
        }

        // ------------------------------------------------------------------ //
        //  Reference signs panel
        // ------------------------------------------------------------------ //

        private void RenderReferencePanel(List<ReferenceSignEntry> entries)
        {
            _referenceEntries = entries;
            ReferencePanel.Children.Clear();

            // Output area
            var outputBorder = new Border
            {
                BorderBrush = new SolidColorBrush(CBorder), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(4), Background = new SolidColorBrush(CPanel),
                Padding = new Thickness(8), Margin = new Thickness(0, 0, 0, 8),
            };
            var outputTb = new TextBlock { TextWrapping = TextWrapping.Wrap, FontSize = 12, LineHeight = 20 };
            outputBorder.Child = outputTb;

            // Controls
            var joinerCombo = new ComboBox { FontSize = 12, Margin = new Thickness(0, 0, 8, 0) };
            joinerCombo.Items.Add(new ComboBoxItem { Content = "三点リーダ（…）", Tag = "…" });
            joinerCombo.Items.Add(new ComboBoxItem { Content = "空白（　）",      Tag = "　" });
            joinerCombo.SelectedIndex = 0;

            var separatorCombo = new ComboBox { FontSize = 12, Margin = new Thickness(0, 0, 8, 0) };
            separatorCombo.Items.Add(new ComboBoxItem { Content = "読点（、）",   Tag = "、" });
            separatorCombo.Items.Add(new ComboBoxItem { Content = "カンマ（，）", Tag = "，", IsSelected = true });
            separatorCombo.Items.Add(new ComboBoxItem { Content = "改行",         Tag = "__newline__" });
            separatorCombo.SelectedIndex = 1;

            var widthCombo = new ComboBox { FontSize = 12, Margin = new Thickness(0, 0, 8, 0) };
            widthCombo.Items.Add(new ComboBoxItem { Content = "全角", Tag = "full", IsSelected = true });
            widthCombo.Items.Add(new ComboBoxItem { Content = "半角", Tag = "half" });
            widthCombo.SelectedIndex = 0;

            var sortCheck = new CheckBox { Content = "昇順ソート", IsChecked = true, FontSize = 12,
                VerticalAlignment = VerticalAlignment.Center };

            void UpdateOutput()
            {
                var joiner    = ((ComboBoxItem)joinerCombo.SelectedItem)?.Tag as string ?? "…";
                var sepTag    = ((ComboBoxItem)separatorCombo.SelectedItem)?.Tag as string ?? "，";
                var separator = sepTag == "__newline__" ? "\n" : sepTag;
                var width     = ((ComboBoxItem)widthCombo.SelectedItem)?.Tag as string ?? "full";
                var doSort    = sortCheck.IsChecked == true;

                var items = _referenceEntries.Select((e, i) => (e, i)).ToList();
                if (doSort) items = items.OrderBy(x => SignRankKey(x.e.Sign)).ToList();

                outputTb.Text = string.Join(separator, items.Select(x =>
                {
                    var sign = width == "full" ? ToFullWidth(x.e.Sign) : ToHalfWidth(x.e.Sign);
                    return sign + joiner + x.e.Term;
                }));
            }

            joinerCombo.SelectionChanged    += (_, __) => UpdateOutput();
            separatorCombo.SelectionChanged += (_, __) => UpdateOutput();
            widthCombo.SelectionChanged     += (_, __) => UpdateOutput();
            sortCheck.Checked               += (_, __) => UpdateOutput();
            sortCheck.Unchecked             += (_, __) => UpdateOutput();

            var controlsPanel = new WrapPanel { Margin = new Thickness(0, 0, 0, 6) };
            controlsPanel.Children.Add(MakeLabeledControl("連結記号", joinerCombo));
            controlsPanel.Children.Add(MakeLabeledControl("区切り",   separatorCombo));
            controlsPanel.Children.Add(MakeLabeledControl("符号",     widthCombo));
            controlsPanel.Children.Add(sortCheck);

            ReferencePanel.Children.Add(controlsPanel);
            ReferencePanel.Children.Add(outputBorder);

            // Extraction table
            if (entries.Any())
            {
                ReferencePanel.Children.Add(new TextBlock { Text = "抽出元", FontWeight = FontWeights.Bold,
                    FontSize = 13, Margin = new Thickness(0, 4, 0, 6) });
                var grid = MakeTableGrid(new[] { "符号", "語句", "出現場所" },
                                         new[] { double.NaN, double.NaN, double.NaN });
                int row = 1;
                foreach (var entry in entries)
                {
                    grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                    AddTableCell(grid, entry.Sign,   row, 0);
                    AddTableCell(grid, entry.Term,   row, 1);
                    AddTableCell(grid, entry.Source, row, 2);
                    row++;
                }
                ReferencePanel.Children.Add(grid);
            }
            else
            {
                ReferencePanel.Children.Add(MakeEmpty("No signed terms."));
            }

            UpdateOutput();
        }

        private static UIElement MakeLabeledControl(string label, UIElement control)
        {
            var sp = new StackPanel { Margin = new Thickness(0, 0, 8, 4) };
            sp.Children.Add(new TextBlock { Text = label, FontSize = 11, FontWeight = FontWeights.Bold,
                Foreground = new SolidColorBrush(CMuted), Margin = new Thickness(0, 0, 0, 2) });
            sp.Children.Add(control);
            return sp;
        }

        // ------------------------------------------------------------------ //
        //  Terms / units panel
        // ------------------------------------------------------------------ //

        private void RenderTermsPanel(Dictionary<string, List<string>> occurrences, List<UnitCheck> units)
        {
            TermsPanel.Children.Clear();

            if (occurrences.Any())
            {
                TermsPanel.Children.Add(new TextBlock { Text = "語句出現表", FontWeight = FontWeights.Bold,
                    FontSize = 13, Margin = new Thickness(0, 0, 0, 6) });
                var grid = MakeTableGrid(new[] { "語句", "出現場所" }, new[] { double.NaN, double.NaN });
                int row = 1;
                foreach (var kv in occurrences.OrderBy(x => x.Key))
                {
                    grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                    AddTableCell(grid, kv.Key, row, 0);
                    AddTableCell(grid, string.Join("、", kv.Value), row, 1);
                    row++;
                }
                TermsPanel.Children.Add(grid);
            }
            else
            {
                TermsPanel.Children.Add(new TextBlock { Text = "語句出現表", FontWeight = FontWeights.Bold,
                    FontSize = 13, Margin = new Thickness(0, 0, 0, 6) });
                TermsPanel.Children.Add(MakeEmpty("No term occurrences."));
            }

            TermsPanel.Children.Add(new TextBlock { Text = "単位チェック", FontWeight = FontWeights.Bold,
                FontSize = 13, Margin = new Thickness(0, 14, 0, 6) });
            if (units.Any())
            {
                var grid = MakeTableGrid(
                    new[] { "行", "桁", "マッチ", "数値", "単位", "Level", "内容" },
                    new[] { 28.0, 28.0, double.NaN, double.NaN, double.NaN, 40.0, double.NaN });
                int row = 1;
                foreach (var u in units)
                {
                    grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                    AddTableCell(grid, u.Line.ToString(),    row, 0);
                    AddTableCell(grid, u.Col.ToString(),     row, 1);
                    AddTableCell(grid, u.Matched, row, 2);
                    AddTableCell(grid, u.Number,  row, 3);
                    AddTableCell(grid, u.Unit,    row, 4);
                    AddTableCell(grid, u.Level,   row, 5);
                    AddTableCell(grid, u.Message, row, 6);
                    row++;
                }
                TermsPanel.Children.Add(grid);
            }
            else
            {
                TermsPanel.Children.Add(MakeEmpty("No unit expressions."));
            }
        }

        // ------------------------------------------------------------------ //
        //  AI proofreading
        // ------------------------------------------------------------------ //

        private void ProviderCombo_Changed(object sender, SelectionChangedEventArgs e)
        {
            if (OllamaModelRow == null) return;
            var tag = ((ComboBoxItem)ProviderCombo.SelectedItem)?.Tag as string ?? "anthropic";
            OllamaModelRow.Visibility = tag == "ollama" ? Visibility.Visible : Visibility.Collapsed;
        }

        private void UpdateAiSubmitState()
        {
            AiSubmitBtn.IsEnabled = !_proofreadDone;
            AiClearBtn.Visibility = _proofreadDone ? Visibility.Visible : Visibility.Collapsed;
            if (_proofreadDone)
                AiStatusText.Text = "校正済みです。クリアして再実行できます。";
            else if (!AiStatusText.Text.Contains("実行中") && !AiStatusText.Text.Contains("エラー"))
                AiStatusText.Text = "";
        }

        private async void AiSubmit_Click(object sender, RoutedEventArgs e)
        {
            if (_documentId == null) { AiStatusText.Text = "先に文書をチェックしてください。"; return; }

            var provider  = ((ComboBoxItem)ProviderCombo.SelectedItem)?.Tag as string ?? "anthropic";
            var model     = provider == "ollama" ? OllamaModelBox.Text.Trim() : null;
            var anonymize = AnonymizeCheck.IsChecked == true;

            _aiCts = new CancellationTokenSource();
            AiSubmitBtn.IsEnabled = false;
            AiCancelBtn.Visibility = Visibility.Visible;
            AiStatusText.Text = "AI文書校正実行中...";
            _proofreadItems.Clear();
            TokenLogPanel.Children.Clear();
            AiResultPanel.Children.Clear();

            int totalBlocks = 0, processed = 0;
            StackPanel proofTbody = null;
            TextBlock titleTb = null;

            void EnsureProofreadSection()
            {
                if (proofTbody != null) return;

                titleTb = new TextBlock { Text = "AI文書校正結果（0件）",
                    FontWeight = FontWeights.Bold, FontSize = 13, Margin = new Thickness(0, 0, 0, 8) };

                // Table headers
                var headerGrid = new Grid();
                headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(55) });
                headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                AddTableHeader(headerGrid, "箇所", 0);
                AddTableHeader(headerGrid, "校正前", 1);
                AddTableHeader(headerGrid, "校正後", 2);

                proofTbody = new StackPanel();
                AiResultPanel.Children.Clear();
                AiResultPanel.Children.Add(titleTb);
                AiResultPanel.Children.Add(headerGrid);
                AiResultPanel.Children.Add(proofTbody);

                // Switch to AI tab
                Dispatcher.Invoke(() => ResultTabs.SelectedItem = AiResultTab);
            }

            void AppendProofRow(ProofreadItem item)
            {
                if (proofTbody == null) return;
                var rowGrid = new Grid();
                rowGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(55) });
                rowGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                rowGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

                var labelCell = new Border { Child = new TextBlock {
                        Text = item.Label, FontSize = 11, FontWeight = FontWeights.Bold,
                        FontFamily = new FontFamily("Consolas, Courier New"), TextWrapping = TextWrapping.Wrap },
                    Padding = new Thickness(5), BorderBrush = new SolidColorBrush(CBorder),
                    BorderThickness = new Thickness(1, 0, 1, 1), VerticalAlignment = VerticalAlignment.Stretch };

                var beforeContent = BuildDiffBlock(item.OriginalText, item.CorrectedText, isBefore: true);
                var beforeCell = new Border { Child = beforeContent,
                    Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#fef2f2")),
                    Padding = new Thickness(5), BorderBrush = new SolidColorBrush(CBorder),
                    BorderThickness = new Thickness(0, 0, 1, 1) };

                var afterContent = BuildDiffBlock(item.OriginalText, item.CorrectedText, isBefore: false);
                var afterCell = new Border { Child = afterContent,
                    Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#f0fdf4")),
                    Padding = new Thickness(5), BorderBrush = new SolidColorBrush(CBorder),
                    BorderThickness = new Thickness(0, 0, 0, 1) };

                Grid.SetColumn(labelCell,  0);
                Grid.SetColumn(beforeCell, 1);
                Grid.SetColumn(afterCell,  2);
                rowGrid.Children.Add(labelCell);
                rowGrid.Children.Add(beforeCell);
                rowGrid.Children.Add(afterCell);
                proofTbody.Children.Add(rowGrid);
            }

            void UpdateProofSummary()
            {
                var count = _proofreadItems.Count(x => x.Displayed);
                if (titleTb != null) titleTb.Text = $"AI文書校正結果（{count}件）";

                // Update or add AI pill in summary
                Dispatcher.Invoke(() => UpdateAiSummaryPill(count));
                UpdateAiTabHeader(count);
            }

            try
            {
                await Task.Run(async () =>
                {
                    await _api.ProofreadAsync(_documentId, provider, model, anonymize,
                        async (eventName, data) =>
                        {
                            await Dispatcher.InvokeAsync(() =>
                            {
                                if (eventName == "start")
                                {
                                    totalBlocks = data.TryGetProperty("total", out var t) ? t.GetInt32() : 0;
                                }
                                else if (eventName == "result")
                                {
                                    processed++;
                                    var item = new ProofreadItem
                                    {
                                        Label         = data.TryGetProperty("label",          out var l)  ? l.GetString()  : "",
                                        HasCorrection = data.TryGetProperty("has_correction", out var hc) ? hc.GetBoolean(): false,
                                        OriginalText  = data.TryGetProperty("original_text",  out var ot) ? ot.GetString()  : "",
                                        CorrectedText = data.TryGetProperty("corrected_text", out var ct) && ct.ValueKind != System.Text.Json.JsonValueKind.Null
                                                        ? ct.GetString() : null,
                                    };
                                    _proofreadItems.Add(item);

                                    var isReal = item.HasCorrection && item.CorrectedText != null
                                                 && item.CorrectedText != item.OriginalText;
                                    if (isReal)
                                    {
                                        item.Displayed = true;
                                        EnsureProofreadSection();
                                        AppendProofRow(item);
                                    }
                                    UpdateProofSummary();

                                    var prog = totalBlocks > 0 ? $" ({processed}/{totalBlocks})" : "";
                                    var correctedSoFar = _proofreadItems.Count(x => x.Displayed);
                                    AiStatusText.Text = $"校正中{prog}… 修正あり {correctedSoFar} 件";

                                    if (data.TryGetProperty("token_usage", out var u) && u.ValueKind != System.Text.Json.JsonValueKind.Null)
                                        AppendTokenEntry(item.Label, u);
                                }
                                else if (eventName == "done")
                                {
                                    var correctionCount = _proofreadItems.Count(x => x.Displayed);
                                    _proofreadDone = true;
                                    UpdateAiSubmitState();
                                    AiStatusText.Text = $"AI文書校正完了（修正あり {correctionCount} 件）";

                                    if (data.TryGetProperty("total_token_usage", out var tu) && tu.ValueKind != System.Text.Json.JsonValueKind.Null)
                                        AppendTokenEntry("合計", tu, bold: true);
                                }
                                else if (eventName == "error")
                                {
                                    var msg = data.TryGetProperty("message", out var m) ? m.GetString() : "AI校正エラー";
                                    AiStatusText.Text = "エラー: " + msg;
                                }
                            });
                        },
                        _aiCts.Token);
                }, _aiCts.Token);
            }
            catch (OperationCanceledException)
            {
                Dispatcher.Invoke(() => AiStatusText.Text = "キャンセルしました。");
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() => AiStatusText.Text = "エラー: " + ex.Message);
            }
            finally
            {
                _aiCts = null;
                Dispatcher.Invoke(() =>
                {
                    AiCancelBtn.Visibility = Visibility.Collapsed;
                    UpdateAiSubmitState();
                });
            }
        }

        private void AiCancel_Click(object sender, RoutedEventArgs e)
        {
            _aiCts?.Cancel();
        }

        private void AiClear_Click(object sender, RoutedEventArgs e)
        {
            _proofreadItems.Clear();
            _proofreadDone = false;
            AiResultPanel.Children.Clear();
            TokenLogPanel.Children.Clear();
            AiStatusText.Text = "";
            UpdateAiSummaryPill(0);
            UpdateAiTabHeader(0);
            UpdateAiSubmitState();
        }

        private void AppendTokenEntry(string label, System.Text.Json.JsonElement u, bool bold = false)
        {
            var inputTokens  = u.TryGetProperty("input_tokens",  out var it) ? it.GetInt32() : 0;
            var outputTokens = u.TryGetProperty("output_tokens", out var ot) ? ot.GetInt32() : 0;
            var totalTokens  = u.TryGetProperty("total_tokens",  out var tt) ? tt.GetInt32() : 0;
            var now = DateTime.Now.ToString("HH:mm:ss");

            var entry = new StackPanel { Margin = new Thickness(0, 3, 0, 0) };
            entry.Children.Add(new TextBlock { Text = $"{now} {label}",
                FontSize = 11, FontWeight = bold ? FontWeights.Bold : FontWeights.Normal,
                Foreground = new SolidColorBrush(CMuted) });
            entry.Children.Add(new TextBlock
            {
                Text = $"入力 {inputTokens:N0} / 出力 {outputTokens:N0} / 合計 {totalTokens:N0} トークン",
                FontSize = 11, Foreground = new SolidColorBrush(CMuted),
            });
            TokenLogPanel.Children.Add(entry);
        }

        private void UpdateAiSummaryPill(int count)
        {
            var existing = SummaryPanel.Children.OfType<Border>()
                .FirstOrDefault(b => b.Tag as string == "ai-pill");
            if (count > 0)
            {
                if (existing == null)
                {
                    existing = MakePill("AI校正 0件", "#6d28d9", "#f5f3ff", "#ddd6fe");
                    existing.Tag = "ai-pill";
                    SummaryPanel.Children.Add(existing);
                }
                ((TextBlock)existing.Child).Text = $"AI校正 {count}件";
            }
            else if (existing != null)
            {
                SummaryPanel.Children.Remove(existing);
            }
        }

        private void UpdateAiTabHeader(int count)
        {
            AiResultTab.Header = count > 0 ? $"AI校正 ({count})" : "AI校正";
        }

        // ------------------------------------------------------------------ //
        //  Diff rendering
        // ------------------------------------------------------------------ //

        private static TextBlock BuildDiffBlock(string original, string corrected, bool isBefore)
        {
            var tb = new TextBlock { TextWrapping = TextWrapping.Wrap, FontSize = 12 };
            if (string.IsNullOrEmpty(corrected))
            {
                tb.Text = original ?? "";
                return tb;
            }
            var runs = DiffChars(original ?? "", corrected);
            foreach (var (text, type) in runs)
            {
                if (type == "eq")
                {
                    tb.Inlines.Add(new Docs.Run(text));
                }
                else if (type == "del" && isBefore)
                {
                    tb.Inlines.Add(new Docs.Run(text)
                    {
                        Foreground     = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#b91c1c")),
                        TextDecorations = TextDecorations.Underline,
                    });
                }
                else if (type == "ins" && !isBefore)
                {
                    tb.Inlines.Add(new Docs.Run(text)
                    {
                        Foreground     = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#15803d")),
                        TextDecorations = TextDecorations.Underline,
                    });
                }
                // del in "after" view and ins in "before" view → skip
            }
            return tb;
        }

        private static List<(string text, string type)> DiffChars(string a, string b)
        {
            int m = a.Length, n = b.Length;
            if ((long)m * n > 400000)
                return new List<(string, string)> { (a, "del"), (b, "ins") };

            var dp = new ushort[m + 1, n + 1];
            for (int i = m - 1; i >= 0; i--)
                for (int j = n - 1; j >= 0; j--)
                    dp[i, j] = a[i] == b[j]
                        ? (ushort)(dp[i + 1, j + 1] + 1)
                        : Math.Max(dp[i + 1, j], dp[i, j + 1]);

            var ops = new List<(char ch, string type)>();
            int ci = 0, cj = 0;
            while (ci < m || cj < n)
            {
                if (ci < m && cj < n && a[ci] == b[cj]) { ops.Add((a[ci], "eq")); ci++; cj++; }
                else if (cj < n && (ci >= m || dp[ci, cj + 1] >= dp[ci + 1, cj])) { ops.Add((b[cj], "ins")); cj++; }
                else { ops.Add((a[ci], "del")); ci++; }
            }

            var runs = new List<(string text, string type)>();
            foreach (var (ch, type) in ops)
            {
                if (runs.Count > 0 && runs[runs.Count - 1].type == type)
                    runs[runs.Count - 1] = (runs[runs.Count - 1].text + ch, type);
                else
                    runs.Add((ch.ToString(), type));
            }
            return runs;
        }

        // ------------------------------------------------------------------ //
        //  Reference sign sort helpers (port of JS signRank)
        // ------------------------------------------------------------------ //

        private static string NormalizeSign(string value)
        {
            var sb = new StringBuilder();
            foreach (char c in value)
            {
                if (c >= 'Ａ' && c <= 'Ｚ') sb.Append((char)(c - 'Ａ' + 'A'));
                else if (c >= 'ａ' && c <= 'ｚ') sb.Append((char)(c - 'ａ' + 'a'));
                else if (c >= '０' && c <= '９') sb.Append((char)(c - '０' + '0'));
                else if (c == '－' || c == 'ー' || c == '―' || c == '‐') sb.Append('-');
                else if (c == '　' || c == ' ') { /* skip */ }
                else sb.Append(c);
            }
            return sb.ToString().ToUpper();
        }

        private static string ToFullWidth(string value)
        {
            var sb = new StringBuilder();
            foreach (char c in value)
            {
                if (c >= 'A' && c <= 'Z') sb.Append((char)(c - 'A' + 'Ａ'));
                else if (c >= 'a' && c <= 'z') sb.Append((char)(c - 'a' + 'ａ'));
                else if (c >= '0' && c <= '9') sb.Append((char)(c - '0' + '０'));
                else if (c == '-') sb.Append('－');
                else if (c == '\'') sb.Append('’');
                else sb.Append(c);
            }
            return sb.ToString();
        }

        private static string ToHalfWidth(string value) => NormalizeSign(value).Replace("’", "'");

        private static string SignRankKey(string sign)
        {
            var n = NormalizeSign(sign);
            var m = Regex.Match(n, @"^([A-Z]+)?-?(\d+)?(.*)$");
            if (!m.Success) return "3" + n;
            var letters = m.Groups[1].Value;
            var digits  = m.Groups[2].Value;
            var rest    = m.Groups[3].Value;
            if (letters.Length > 0 && digits.Length == 0) return "0" + letters + rest;
            if (letters.Length > 0 && digits.Length > 0)  return "0" + letters + int.Parse(digits).ToString("D10") + rest;
            if (digits.Length > 0)                         return "1" + int.Parse(digits).ToString("D10") + rest;
            return "2" + n;
        }

        // ------------------------------------------------------------------ //
        //  Table / section builder helpers
        // ------------------------------------------------------------------ //

        private static Grid MakeTableGrid(string[] headers, double[] widths)
        {
            var grid = new Grid();
            for (int i = 0; i < widths.Length; i++)
                grid.ColumnDefinitions.Add(new ColumnDefinition
                {
                    Width = double.IsNaN(widths[i])
                        ? new GridLength(1, GridUnitType.Star)
                        : new GridLength(widths[i]),
                });
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            for (int i = 0; i < headers.Length; i++)
                AddTableHeader(grid, headers[i], i);
            return grid;
        }

        private static void AddTableHeader(Grid grid, string text, int col)
        {
            var cell = new Border
            {
                Child = new TextBlock { Text = text, FontWeight = FontWeights.Bold, FontSize = 12 },
                Background      = new SolidColorBrush(Color.FromRgb(243, 244, 246)),
                BorderBrush     = new SolidColorBrush(CBorder),
                BorderThickness = new Thickness(col == 0 ? 1 : 0, 1, 1, 1),
                Padding         = new Thickness(5),
            };
            Grid.SetRow(cell, 0);
            Grid.SetColumn(cell, col);
            grid.Children.Add(cell);
        }

        private static void AddTableCell(Grid grid, string text, int row, int col)
        {
            var cell = new Border
            {
                Child = new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap, FontSize = 12 },
                BorderBrush     = new SolidColorBrush(CBorder),
                BorderThickness = new Thickness(col == 0 ? 1 : 0, 0, 1, 1),
                Padding         = new Thickness(5),
                VerticalAlignment = VerticalAlignment.Stretch,
            };
            Grid.SetRow(cell, row);
            Grid.SetColumn(cell, col);
            grid.Children.Add(cell);
        }

        private static Border MakeEmpty(string text) => new Border
        {
            Child = new TextBlock { Text = text, Foreground = new SolidColorBrush(CMuted),
                HorizontalAlignment = HorizontalAlignment.Center },
            BorderBrush     = new SolidColorBrush(CBorder),
            BorderThickness = new Thickness(1),
            CornerRadius    = new CornerRadius(4),
            Padding         = new Thickness(16),
            Background      = new SolidColorBrush(CPanel),
        };

        private static string ExtractHeader(string text)
        {
            var m = Regex.Match(text ?? "", @"^(【[^】]*】)");
            return m.Success ? m.Groups[1].Value : null;
        }

        // ------------------------------------------------------------------ //
        //  Busy / status utilities
        // ------------------------------------------------------------------ //

        private void SetBusy(bool busy)
        {
            CheckApiBtn.IsEnabled = !busy;
            CheckDocBtn.IsEnabled = !busy;
        }

        private void SetStatus(string message, bool isError = false)
        {
            StatusText.Text = message;
            StatusText.Foreground = isError
                ? new SolidColorBrush(CError)
                : new SolidColorBrush(CMuted);
        }
    }
}
