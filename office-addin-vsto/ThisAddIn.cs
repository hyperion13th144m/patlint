using System.Windows.Forms.Integration;
using Microsoft.Office.Tools;
using PatlintAddin.TaskPane;
using Word = Microsoft.Office.Interop.Word;

namespace PatlintAddin;

public partial class ThisAddIn
{
    private CustomTaskPane? _taskPane;

    private void ThisAddIn_Startup(object sender, System.EventArgs e)
    {
        var wpfControl = new TaskPaneControl();
        var host = new ElementHost { Child = wpfControl, Dock = System.Windows.Forms.DockStyle.Fill };
        var winFormsContainer = new System.Windows.Forms.UserControl();
        winFormsContainer.Controls.Add(host);

        _taskPane = CustomTaskPanes.Add(winFormsContainer, "PatLint");
        _taskPane.Width = 360;
        _taskPane.Visible = true;
    }

    private void ThisAddIn_Shutdown(object sender, System.EventArgs e) { }

    #region VSTO generated code
    protected override Microsoft.Office.Core.IRibbonExtensibility? CreateRibbonExtensibilityObject() => null;

    private void InternalStartup()
    {
        Startup += ThisAddIn_Startup;
        Shutdown += ThisAddIn_Shutdown;
    }
    #endregion
}
