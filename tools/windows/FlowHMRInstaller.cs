using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;

[assembly: AssemblyTitle("FlowHMR Windows Setup")]
[assembly: AssemblyProduct("FlowHMR")]

internal sealed class VolumeStream : Stream
{
    private readonly List<FileStream> files = new List<FileStream>();
    private long length, position;

    public VolumeStream(string directory, Action<string, int> report)
    {
        try
        {
            using (var reader = new StreamReader(Assembly.GetExecutingAssembly().GetManifestResourceStream("FlowHMR.volumes")))
            using (var sha = SHA256.Create())
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    var fields = line.Split('|');
                    if (fields.Length != 3 || Path.GetFileName(fields[0]) != fields[0]) throw new InvalidDataException();
                    var path = Path.Combine(directory, fields[0]);
                    if (!File.Exists(path)) throw new FileNotFoundException("缺少分卷：" + fields[0]);
                    report("正在校验 " + fields[0], 0);
                    var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
                    files.Add(file);
                    if (file.Length != long.Parse(fields[1], CultureInfo.InvariantCulture) ||
                        !String.Equals(BitConverter.ToString(sha.ComputeHash(file)).Replace("-", ""), fields[2], StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("分卷校验失败，请重新下载 " + fields[0]);
                    file.Position = 0;
                    length += file.Length;
                }
            }
        }
        catch { Dispose(); throw; }
    }

    public override bool CanRead { get { return true; } }
    public override bool CanSeek { get { return true; } }
    public override bool CanWrite { get { return false; } }
    public override long Length { get { return length; } }
    public override long Position
    {
        get { return position; }
        set { if (value < 0) throw new IOException(); position = value; }
    }

    public override int Read(byte[] buffer, int offset, int count)
    {
        int copied = 0;
        long start = 0;
        foreach (var file in files)
        {
            long end = start + file.Length;
            if (position < end && copied < count)
            {
                file.Position = position - start;
                int n = file.Read(buffer, offset + copied, (int)Math.Min(count - copied, end - position));
                copied += n;
                position += n;
                if (position < end) break;
            }
            start = end;
        }
        return copied;
    }

    public override long Seek(long offset, SeekOrigin origin)
    {
        Position = offset + (origin == SeekOrigin.End ? Length : origin == SeekOrigin.Current ? Position : 0);
        return Position;
    }

    public override void Flush() { }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
    protected override void Dispose(bool disposing)
    {
        if (disposing) foreach (var file in files) file.Dispose();
        base.Dispose(disposing);
    }
}

internal static class FlowHMRInstaller
{
    private static void Extract(string target, Action<string, int> report)
    {
        target = Path.GetFullPath(target);
        if (Directory.Exists(target) || File.Exists(target))
            throw new IOException("目标文件夹已存在。请选择新位置，以保留已有模型和任务。");
        var parent = Path.GetDirectoryName(target);
        if (String.IsNullOrEmpty(parent) || !Directory.Exists(parent)) throw new IOException("目标位置不存在。");
        using (var volumes = new VolumeStream(AppDomain.CurrentDomain.BaseDirectory, report))
        using (var archive = new ZipArchive(volumes, ZipArchiveMode.Read))
        {
            long total = 0;
            foreach (var entry in archive.Entries) total += entry.Length;
            string stage = Path.Combine(parent, ".FlowHMR-installing-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(stage);
            string prefix = stage + Path.DirectorySeparatorChar;
            var buffer = new byte[1024 * 1024];
            long written = 0;
            var clock = Stopwatch.StartNew();
            foreach (var entry in archive.Entries)
            {
                var path = Path.GetFullPath(Path.Combine(stage, entry.FullName));
                if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("发布包文件路径无效。");
                if (entry.Name.Length == 0) { Directory.CreateDirectory(path); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using (var input = entry.Open())
                using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    int size;
                    while ((size = input.Read(buffer, 0, buffer.Length)) != 0)
                    {
                        output.Write(buffer, 0, size);
                        written += size;
                        if (clock.ElapsedMilliseconds >= 120)
                        {
                            report("正在解包 FlowHMR…", total == 0 ? 0 : (int)(written * 100 / total));
                            clock.Restart();
                        }
                    }
                }
            }
            if (!File.Exists(Path.Combine(stage, "FlowHMR.exe")) || !File.Exists(Path.Combine(stage, "runtime", "python.exe")))
                throw new InvalidDataException("发布包不完整。");
            Directory.Move(stage, target);
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        bool unattended = args.Length == 2 && args[0] == "--extract-to";
        try
        {
            if (unattended) { Extract(args[1], (message, progress) => { }); return 0; }
            Application.EnableVisualStyles();
            using (var dialog = new FolderBrowserDialog { Description = "选择解包位置，程序会创建 FlowHMR 文件夹。" })
            {
                if (dialog.ShowDialog() != DialogResult.OK) return 0;
                var target = Path.Combine(dialog.SelectedPath, "FlowHMR");
                using (var form = new Form { Text = "FlowHMR", Width = 430, Height = 126, ControlBox = false, StartPosition = FormStartPosition.CenterScreen })
                using (var label = new Label { Left = 12, Top = 12, Width = 392, Height = 22 })
                using (var progress = new ProgressBar { Left = 12, Top = 39, Width = 392 })
                {
                    form.Controls.Add(label);
                    form.Controls.Add(progress);
                    form.Show();
                    Extract(target, (message, percent) => { label.Text = message; progress.Value = percent; Application.DoEvents(); });
                    form.Close();
                }
                MessageBox.Show("解包完成。打开 FlowHMR 文件夹，双击 FlowHMR.exe。\n\n" + target, "FlowHMR");
            }
            return 0;
        }
        catch (Exception error)
        {
            if (unattended) Console.Error.WriteLine(error.Message);
            else MessageBox.Show(error.Message, "FlowHMR", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
