// Auto-generated settings wrapper.
using System.Configuration;
using System.CodeDom.Compiler;

namespace PatlintAddin.Properties;

[GeneratedCode("Microsoft.VisualStudio.Editors.SettingsDesigner.SettingsSingleFileGenerator", "17.0.0.0")]
internal sealed partial class Settings : ApplicationSettingsBase
{
    private static readonly Settings _default = (Settings)Synchronized(new Settings());

    public static Settings Default => _default;

    [UserScopedSetting]
    [DefaultSettingValue("http://localhost:8000")]
    public string ApiUrl
    {
        get => (string)this[nameof(ApiUrl)];
        set => this[nameof(ApiUrl)] = value;
    }
}
