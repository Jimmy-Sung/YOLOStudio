using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        string app = Path.Combine(root, "app.py");
        string bundledPython = Path.Combine(root, "runtime", "pythonw.exe");
        GpuSelection selected = null;
        if (File.Exists(bundledPython))
        {
            python = bundledPython;
            app = Path.Combine(root, "app", "app.py");
            string catalog = Path.Combine(root,"engine-catalog.json");
            string marker=Path.Combine(root,"distribution.json");
            bool autoCuda=File.Exists(marker) && File.ReadAllText(marker).Contains("auto-cuda");
            if(autoCuda && File.Exists(catalog))
            {
                try
                {
                    selected=GpuSelector.Select(root,catalog,true);
                    python=Path.Combine(root,selected.python);
                }
                catch(Exception) { selected=new GpuSelection { reason="gpu_detection_failed" }; }
            }
        }
        if (!File.Exists(python) || !File.Exists(app))
        {
            MessageBox.Show("請先執行 setup.ps1 安裝環境。\n请先运行 setup.ps1 安装环境。\nRun setup.ps1 to install the environment first.", "YOLO Studio", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        try
        {
            var start = new ProcessStartInfo(python, "-X utf8 -B \"" + app + "\"")
            {
                WorkingDirectory = root,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            if(selected!=null)
            {
                start.EnvironmentVariables["YOLO_STUDIO_ENGINE"]=selected.id;
                start.EnvironmentVariables["YOLO_STUDIO_GPU_INDEX"]=selected.gpu_index.ToString();
                start.EnvironmentVariables["YOLO_STUDIO_ENGINE_INFO"]=GpuSelector.Json(selected);
            }
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "YOLO Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
