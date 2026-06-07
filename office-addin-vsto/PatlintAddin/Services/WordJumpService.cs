using PatlintAddin.Models;
using Word = Microsoft.Office.Interop.Word;

namespace PatlintAddin.Services
{
    /// <summary>
    /// Moves the Word selection to the location indicated by a DiagnosticView.
    /// Strategy: try Find with search_text first; fall back to paragraph by block_index.
    /// </summary>
    public static class WordJumpService
    {
        public static bool JumpTo(Word.Application app, LocationData location)
        {
            var doc = app.ActiveDocument;
            if (doc == null) return false;

            if (!string.IsNullOrEmpty(location.SearchText) && TryFindText(app, location.SearchText))
                return true;

            if (location.BlockIndex.HasValue)
                return TrySelectParagraph(doc, location.BlockIndex.Value);

            return false;
        }

        private static bool TryFindText(Word.Application app, string searchText)
        {
            var doc = app.ActiveDocument;
            Word.Range range = doc.Content;

            range.Find.ClearFormatting();
            range.Find.Text = searchText;
            range.Find.Forward = true;
            range.Find.Wrap = Word.WdFindWrap.wdFindStop;
            range.Find.MatchCase = false;
            range.Find.MatchWholeWord = false;

            bool found = range.Find.Execute();
            if (found)
            {
                range.Select();
                app.ActiveWindow.ScrollIntoView(range);
            }
            return found;
        }

        private static bool TrySelectParagraph(Word.Document doc, int blockIndex)
        {
            // block_index は 0-based; Word の Paragraphs は 1-based
            int wordIndex = blockIndex + 1;
            if (wordIndex < 1 || wordIndex > doc.Paragraphs.Count)
                return false;

            Word.Range para = doc.Paragraphs[wordIndex].Range;
            para.Select();
            doc.Application.ActiveWindow.ScrollIntoView(para);
            return true;
        }
    }
}
