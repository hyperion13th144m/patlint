using Microsoft.Office.Tools.Word;
using PatlintAddin.TaskPane;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Windows.Forms.Integration;
using System.Xml.Linq;
using Office = Microsoft.Office.Core;
using Word = Microsoft.Office.Interop.Word;

namespace PatlintAddin
{
    public partial class ThisAddIn
    {
        private Microsoft.Office.Tools.CustomTaskPane _taskPane;

        private void ThisAddIn_Startup(object sender, System.EventArgs e)
        {
            var wpfControl = new TaskPaneControl(this.Application);
            var host = new ElementHost
            {
                Child = wpfControl,
                Dock = System.Windows.Forms.DockStyle.Fill,
            };
            var container = new System.Windows.Forms.UserControl();
            container.Controls.Add(host);

            _taskPane = this.CustomTaskPanes.Add(container, "PatLint");
            _taskPane.Width = 360;
            _taskPane.Visible = true;
        }

        private void ThisAddIn_Shutdown(object sender, System.EventArgs e)
        {
        }


        public void ToggleTaskPane()
        {
            if (_taskPane != null)
                _taskPane.Visible = !_taskPane.Visible;
        }

        protected override Microsoft.Office.Core.IRibbonExtensibility CreateRibbonExtensibilityObject()
        {
            return new Ribbon();
        }

        #region VSTO で生成されたコード

        /// <summary>
        /// デザイナー サポートに必要なメソッドです。このメソッドの内容を
        /// コード エディターで変更しないでください。
        /// </summary>
        private void InternalStartup()
        {
            this.Startup += new System.EventHandler(ThisAddIn_Startup);
            this.Shutdown += new System.EventHandler(ThisAddIn_Shutdown);
        }
        
        #endregion
    }
}
