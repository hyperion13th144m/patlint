using System.Windows.Forms;
using System.Windows.Forms.Integration;
using Microsoft.Office.Tools;
using PatlintAddin.TaskPane;

namespace PatlintAddin;

public partial class ThisAddIn
{
    private CustomTaskPane? _taskPane;

    private void ThisAddIn_Startup(object sender, System.EventArgs e)
    {
        // Word.Application を TaskPaneControl に渡す
        var wpfControl = new TaskPaneControl(Application);
        var host = new ElementHost { Child = wpfControl, Dock = DockStyle.Fill };
        var container = new System.Windows.Forms.UserControl();
        container.Controls.Add(host);

        _taskPane = CustomTaskPanes.Add(container, "PatLint");
        _taskPane.Width = 360;
        _taskPane.Visible = true;
    }

    private void ThisAddIn_Shutdown(object sender, System.EventArgs e) { }

    #region VSTO generated code
    private void InternalStartup()
    {
        Startup  += ThisAddIn_Startup;
        Shutdown += ThisAddIn_Shutdown;
    }
    #endregion
}
