using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;

public class EngineProfile
{
    public string id;
    public string label;
    public string python;
    public int min_driver_api;
    public int priority;
    public int[] archs;
}
public class EngineCatalog { public EngineProfile[] profiles; }
public class DetectedGpu { public int index; public string name; public int capability; }
public class GpuSelection
{
    public string id = "cpu";
    public string label = "CPU";
    public string python = "runtime/pythonw.exe";
    public int gpu_index = -1;
    public int driver_api;
    public string device_name = "CPU";
    public int capability;
    public string reason = "no_nvidia_driver";
    public List<DetectedGpu> gpus = new List<DetectedGpu>();
}

public static class GpuSelector
{
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll")] private static extern int cuInit(uint flags);
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll")] private static extern int cuDriverGetVersion(out int version);
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll")] private static extern int cuDeviceGetCount(out int count);
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll")] private static extern int cuDeviceGet(out int device,int ordinal);
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll")] private static extern int cuDeviceComputeCapability(out int major,out int minor,int device);
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("nvcuda.dll",CharSet=CharSet.Ansi)] private static extern int cuDeviceGetName(StringBuilder name,int length,int device);

    public static GpuSelection Probe()
    {
        var result = new GpuSelection();
        try
        {
            int version; if(cuDriverGetVersion(out version)!=0) return result;
            result.driver_api=version;
            if(cuInit(0)!=0) { result.reason="cuda_initialization_failed"; return result; }
            int count; if(cuDeviceGetCount(out count)!=0) return result;
            for(int i=0;i<count;i++)
            {
                int device,major,minor; if(cuDeviceGet(out device,i)!=0) continue;
                if(cuDeviceComputeCapability(out major,out minor,device)!=0) continue;
                var name=new StringBuilder(256);cuDeviceGetName(name,256,device);
                result.gpus.Add(new DetectedGpu {index=i,name=name.ToString(),capability=major*10+minor});
            }
            result.reason=result.gpus.Count>0?"no_compatible_engine":"no_nvidia_gpu";
        }
        catch(DllNotFoundException) { result.reason="no_nvidia_driver"; }
        catch(EntryPointNotFoundException) { result.reason="unsupported_driver"; }
        catch(BadImageFormatException) { result.reason="unsupported_driver_architecture"; }
        return result;
    }

    public static GpuSelection Choose(GpuSelection result,EngineCatalog catalog,string root,bool requireInstalled)
    {
        if(result.gpus.Count==0) return result;
        bool driverEligible=false;
        foreach(var profile in catalog.profiles.OrderByDescending(x=>x.priority))
        {
            if(requireInstalled && !File.Exists(Path.Combine(root,profile.python))) continue;
            if(result.driver_api<profile.min_driver_api) continue;
            driverEligible=true;
            foreach(var gpu in result.gpus.OrderByDescending(x=>x.capability))
            {
                // NVIDIA cubins support later minor capabilities within their major family.
                bool arch=profile.archs.Any(a=>a/10==gpu.capability/10 && a<=gpu.capability);
                if(!arch) continue;
                result.id=profile.id;result.label=profile.label;result.python=profile.python;
                result.gpu_index=gpu.index;result.device_name=gpu.name;result.capability=gpu.capability;result.reason="compatible";
                return result;
            }
        }
        result.reason=driverEligible?"unsupported_gpu_architecture":"driver_too_old_or_engine_missing";
        return result;
    }

    public static GpuSelection Select(string root,string catalogPath,bool requireInstalled)
    {
        var serializer=new JavaScriptSerializer();
        var catalog=serializer.Deserialize<EngineCatalog>(File.ReadAllText(catalogPath,Encoding.UTF8));
        return Choose(Probe(),catalog,root,requireInstalled);
    }

    public static string Json(object value) { return new JavaScriptSerializer().Serialize(value); }
}

public static class GpuDetect
{
    public static int Main(string[] args)
    {
        string root=AppDomain.CurrentDomain.BaseDirectory;
        string catalog=Path.Combine(root,"engine-catalog.json"),output=null,fixture=null;
        bool requireInstalled=true;
        for(int i=0;i<args.Length;i++)
        {
            if(args[i]=="--catalog") catalog=args[++i];
            else if(args[i]=="--root") root=args[++i];
            else if(args[i]=="--output") output=args[++i];
            else if(args[i]=="--fixture") fixture=args[++i];
            else if(args[i]=="--allow-uninstalled") requireInstalled=false;
        }
        try
        {
            GpuSelection result;
            if(fixture!=null)
            {
                var serializer=new JavaScriptSerializer();
                var probe=serializer.Deserialize<GpuSelection>(File.ReadAllText(fixture,Encoding.UTF8));
                var profiles=serializer.Deserialize<EngineCatalog>(File.ReadAllText(catalog,Encoding.UTF8));
                result=GpuSelector.Choose(probe,profiles,root,requireInstalled);
            }
            else result=GpuSelector.Select(root,catalog,requireInstalled);
            string json=GpuSelector.Json(result);
            if(output!=null)
            {
                File.WriteAllText(output,result.id,Encoding.ASCII);
                File.WriteAllText(output+".json",json,new UTF8Encoding(false));
            }
            else { Console.OutputEncoding=Encoding.UTF8;Console.WriteLine(json); }
            return 0;
        }
        catch(Exception error) { Console.Error.WriteLine(error.Message);return 1; }
    }
}
