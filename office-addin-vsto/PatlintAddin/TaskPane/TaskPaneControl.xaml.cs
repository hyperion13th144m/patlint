using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using PatlintAddin.Models;
using PatlintAddin.Properties;
using PatlintAddin.Services;
using Word = Microsoft.Office.Interop.Word;

namespace PatlintAddin.TaskPane
{
    public partial class TaskPaneControl : UserControl
    {
        private readonly ApiClient _api = new ApiClient();
        private List<DiagnosticView> _lastDiagnostics = new List<DiagnosticView>();

        // Word.Application は ThisAddIn からコンストラクタで渡す
        private readonly Word.Application _wordApp;

        public TaskPaneControl(Word.Application wordApp)
        {
            InitializeComponent();
            _wordApp = wordApp;
            _api.BaseUrl = Settings.Default.ApiUrl;
            ApiUrlBox.Text = _api.BaseUrl;
        }

        // ------------------------------------------------------------------ //
        //  Settings
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

        // ------------------------------------------------------------------ //
        //  API health check
        // ------------------------------------------------------------------ //

        private async void CheckApi_Click(object sender, RoutedEventArgs e)
        {
            SetBusy(true);
            try
            {
                var status = await _api.CheckHealthAsync();
                SetStatus(status == "ok" ? "API ready" : "API status: " + status, isError: status != "ok");
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, isError: true);
            }
            finally { SetBusy(false); }
        }

        // ------------------------------------------------------------------ //
        //  Document check
        // ------------------------------------------------------------------ //

        private async void CheckDocument_Click(object sender, RoutedEventArgs e)
        {
            SetBusy(true);
            SetStatus("文書を読み取っています...");
            try
            {
                var doc = _wordApp.ActiveDocument;
                if (doc == null) throw new InvalidOperationException("アクティブな文書がありません。");

                string text = doc.Content.Text;
                if (string.IsNullOrWhiteSpace(text)) throw new InvalidOperationException("文書本文が空です。");

                SetStatus("解析中...");
                var response = await _api.CheckTextAsync(text);
                _lastDiagnostics = response.DiagnosticViews;
                Render(response);
                SetStatus("解析が完了しました。");
            }
            catch (Exception ex)
            {
                SetStatus(ex.Message, isError: true);
            }
            finally { SetBusy(false); }
        }

        // ------------------------------------------------------------------ //
        //  Render
        // ------------------------------------------------------------------ //

        private void Render(CheckResponse data)
        {
            RenderSummary(data.Summary);
            ResultsPanel.Children.Clear();
            ResultsPanel.Children.Add(BuildDiagnosticsSection(data.DiagnosticViews));
            ResultsPanel.Children.Add(BuildClaimsSection(data.Claims));
            ResultsPanel.Children.Add(BuildReferenceSignsSection(data.ReferenceSignEntries));
            ResultsPanel.Children.Add(BuildTermOccurrencesSection(data.TermOccurrences));
            ResultsPanel.Children.Add(BuildUnitChecksSection(data.UnitChecks));
        }

        private void RenderSummary(SummaryCount counts)
        {
            SummaryPanel.Children.Clear();
            SummaryPanel.Children.Add(MakePill("Error "   + counts.Error,   "#b91c1c", "#fef2f2", "#fecaca"));
            SummaryPanel.Children.Add(MakePill("Warning " + counts.Warning, "#a16207", "#fffbeb", "#fde68a"));
            SummaryPanel.Children.Add(MakePill("Info "    + counts.Info,    "#1d4ed8", "#eff6ff", "#bfdbfe"));
        }

        private Border MakePill(string text, string fg, string bg, string border)
        {
            var tb = new TextBlock
            {
                Text = text,
                Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(fg)),
            };
            return new Border
            {
                Child = tb,
                Background      = new SolidColorBrush((Color)ColorConverter.ConvertFromString(bg)),
                BorderBrush     = new SolidColorBrush((Color)ColorConverter.ConvertFromString(border)),
                BorderThickness = new Thickness(1),
                CornerRadius    = new CornerRadius(999),
                Padding         = new Thickness(8, 3, 8, 3),
                Margin          = new Thickness(0, 0, 6, 0),
            };
        }

        // ------------------------------------------------------------------ //
        //  Section builders
        // ------------------------------------------------------------------ //

        private UIElement BuildDiagnosticsSection(List<DiagnosticView> items)
        {
            var grid = MakeSectionGrid(new[] { "区分", "内容" }, new[] { 70.0, double.NaN });
            int row = 1;
            foreach (var item in items)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

                AddCell(grid, item.SeverityLabel, row, 0);

                var stack = new StackPanel();
                stack.Children.Add(new TextBlock { Text = item.Message, TextWrapping = TextWrapping.Wrap });
                stack.Children.Add(new TextBlock
                {
                    Text = item.RuleLabel + " / " + item.Location,
                    FontSize = 11,
                    Foreground = Brushes.Gray,
                    TextWrapping = TextWrapping.Wrap,
                    Margin = new Thickness(0, 2, 0, 0),
                });

                var loc = item.LocationData;
                if (loc != null && (loc.SearchText != null || loc.BlockIndex != null))
                {
                    var capturedIdx = row - 1;
                    var btn = new Button
                    {
                        Content = "移動",
                        FontSize = 11,
                        Padding = new Thickness(6, 2, 6, 2),
                        Margin = new Thickness(0, 4, 0, 0),
                        HorizontalAlignment = HorizontalAlignment.Left,
                        Tag = capturedIdx,
                    };
                    btn.Click += JumpBtn_Click;
                    stack.Children.Add(btn);
                }

                var cell = new Border
                {
                    Child = stack,
                    Padding = new Thickness(6),
                    BorderBrush = Brushes.LightGray,
                    BorderThickness = new Thickness(0, 0, 0, 1),
                };
                Grid.SetRow(cell, row);
                Grid.SetColumn(cell, 1);
                grid.Children.Add(cell);
                row++;
            }
            return MakeSection("診断結果", grid, items.Count == 0);
        }

        private void JumpBtn_Click(object sender, RoutedEventArgs e)
        {
            var btn = sender as Button;
            if (btn == null) return;
            int idx = (int)btn.Tag;
            if (idx >= _lastDiagnostics.Count) return;
            var loc = _lastDiagnostics[idx].LocationData;
            if (loc == null) return;
            bool ok = WordJumpService.JumpTo(_wordApp, loc);
            if (!ok) SetStatus("該当箇所が見つかりませんでした。", isError: true);
        }

        private UIElement BuildClaimsSection(List<ClaimView> claims)
        {
            var incoming = new Dictionary<int, List<int>>();
            foreach (var c in claims)
                foreach (var r in c.ReferencedClaims)
                {
                    List<int> list;
                    if (!incoming.TryGetValue(r, out list))
                    {
                        list = new List<int>();
                        incoming[r] = list;
                    }
                    list.Add(c.Number);
                }

            var grid = MakeSectionGrid(
                new[] { "請求項", "従属先", "被従属", "種別" },
                new[] { double.NaN, double.NaN, double.NaN, double.NaN });
            int row = 1;
            foreach (var c in claims)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                var refs = c.ReferencedClaims;
                var kind = refs.Count == 0 ? "独立項" : (c.IsMultipleDependent ? "複数従属項" : "従属項");
                List<int> il;
                var inList = incoming.TryGetValue(c.Number, out il) ? il : new List<int>();
                AddCell(grid, "請求項" + c.Number, row, 0);
                AddCell(grid, refs.Count > 0 ? string.Join("、", refs.ConvertAll(n => "請求項" + n)) : "－", row, 1);
                AddCell(grid, inList.Count > 0 ? string.Join("、", inList.ConvertAll(n => "請求項" + n)) : "－", row, 2);
                AddCell(grid, kind, row, 3);
                row++;
            }
            return MakeSection("請求項の関係", grid, claims.Count == 0);
        }

        private UIElement BuildReferenceSignsSection(List<ReferenceSignEntry> entries)
        {
            var summary = string.Join("，", entries.ConvertAll(e => e.Sign + "…" + e.Term));
            var grid = MakeSectionGrid(
                new[] { "符号", "語句", "出現場所" },
                new[] { double.NaN, double.NaN, double.NaN });
            int row = 1;
            foreach (var entry in entries)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                AddCell(grid, entry.Sign,   row, 0);
                AddCell(grid, entry.Term,   row, 1);
                AddCell(grid, entry.Source, row, 2);
                row++;
            }
            var stack = new StackPanel();
            stack.Children.Add(new TextBlock { Text = summary, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
            stack.Children.Add(grid);
            return MakeSection("符号の説明用一覧", stack, entries.Count == 0);
        }

        private UIElement BuildTermOccurrencesSection(Dictionary<string, List<string>> occurrences)
        {
            var grid = MakeSectionGrid(new[] { "語句", "出現場所" }, new[] { double.NaN, double.NaN });
            int row = 1;
            foreach (var kv in occurrences)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                AddCell(grid, kv.Key, row, 0);
                AddCell(grid, string.Join("、", kv.Value), row, 1);
                row++;
            }
            return MakeSection("語句出現表", grid, occurrences.Count == 0);
        }

        private UIElement BuildUnitChecksSection(List<UnitCheck> units)
        {
            var grid = MakeSectionGrid(new[] { "マッチ", "単位", "内容" }, new[] { double.NaN, double.NaN, double.NaN });
            int row = 1;
            foreach (var u in units)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                AddCell(grid, u.Matched, row, 0);
                AddCell(grid, u.Unit,    row, 1);
                AddCell(grid, u.Message, row, 2);
                row++;
            }
            return MakeSection("単位チェック", grid, units.Count == 0);
        }

        // ------------------------------------------------------------------ //
        //  Grid / section helpers
        // ------------------------------------------------------------------ //

        private static Grid MakeSectionGrid(string[] headers, double[] widths)
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
            {
                var header = new Border
                {
                    Background      = new SolidColorBrush(Color.FromRgb(243, 244, 246)),
                    BorderBrush     = Brushes.LightGray,
                    BorderThickness = new Thickness(0, 0, 0, 1),
                    Padding         = new Thickness(6),
                    Child           = new TextBlock { Text = headers[i], FontWeight = FontWeights.Bold },
                };
                Grid.SetRow(header, 0);
                Grid.SetColumn(header, i);
                grid.Children.Add(header);
            }
            return grid;
        }

        private static void AddCell(Grid grid, string text, int row, int col)
        {
            var cell = new Border
            {
                Child           = new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap },
                Padding         = new Thickness(6),
                BorderBrush     = Brushes.LightGray,
                BorderThickness = new Thickness(0, 0, 0, 1),
            };
            Grid.SetRow(cell, row);
            Grid.SetColumn(cell, col);
            grid.Children.Add(cell);
        }

        private static UIElement MakeSection(string title, UIElement content, bool empty)
        {
            var stack = new StackPanel { Margin = new Thickness(0, 18, 0, 0) };
            stack.Children.Add(new TextBlock
            {
                Text       = title,
                FontSize   = 15,
                FontWeight = FontWeights.SemiBold,
                Margin     = new Thickness(0, 0, 0, 8),
            });
            if (empty)
            {
                stack.Children.Add(new Border
                {
                    Child = new TextBlock
                    {
                        Text                = "No data.",
                        Foreground          = Brushes.Gray,
                        HorizontalAlignment = HorizontalAlignment.Center,
                    },
                    BorderBrush     = Brushes.LightGray,
                    BorderThickness = new Thickness(1),
                    CornerRadius    = new CornerRadius(4),
                    Padding         = new Thickness(16),
                    Background      = new SolidColorBrush(Color.FromRgb(249, 250, 251)),
                });
            }
            else
            {
                stack.Children.Add(content);
            }
            return stack;
        }

        // ------------------------------------------------------------------ //
        //  Utilities
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
                ? new SolidColorBrush((Color)ColorConverter.ConvertFromString("#b91c1c"))
                : Brushes.Gray;
        }
    }
}
