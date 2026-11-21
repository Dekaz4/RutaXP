using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

// This offline installer carries the already assembled personal ZIP. The public
// installer instead builds it from each player's own installed modules.
internal static class PersonalSetup
{
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("RUTAXP-PERSONAL-1");

    private static void ReadBundle(string destination)
    {
        using (FileStream file = File.OpenRead(Assembly.GetExecutingAssembly().Location))
        using (BinaryReader reader = new BinaryReader(file))
        {
            long footer = file.Length - Magic.Length - sizeof(long) - 32;
            if (footer < 0) throw new InvalidDataException("El instalador está incompleto.");
            file.Position = footer;
            long length = reader.ReadInt64();
            byte[] expected = reader.ReadBytes(32);
            if (length <= 0 || length >= footer || !Equal(reader.ReadBytes(Magic.Length), Magic))
                throw new InvalidDataException("El paquete personal está incompleto.");
            file.Position = footer - length;
            using (SHA256 hash = SHA256.Create())
            using (Stream output = destination == null ? Stream.Null : File.Open(destination, FileMode.CreateNew))
            {
                byte[] buffer = new byte[1024 * 1024];
                while (length > 0)
                {
                    int count = file.Read(buffer, 0, (int)Math.Min(length, buffer.Length));
                    if (count == 0) throw new EndOfStreamException();
                    hash.TransformBlock(buffer, 0, count, buffer, 0);
                    output.Write(buffer, 0, count);
                    length -= count;
                }
                hash.TransformFinalBlock(new byte[0], 0, 0);
                if (!Equal(hash.Hash, expected)) throw new InvalidDataException("El contenido del instalador ha cambiado.");
            }
        }
    }

    private static bool Equal(byte[] a, byte[] b)
    {
        return Convert.ToBase64String(a) == Convert.ToBase64String(b);
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 1 && args[0] == "--verify") { ReadBundle(null); return 0; }
            bool restore = args.Length == 1 && args[0] == "--restore";
            if (args.Length != 0 && !restore) return 2;
            Application.EnableVisualStyles();
            string setting = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RutaXP", "client.txt");
            string client = File.Exists(setting) ? File.ReadAllText(setting).Trim() : "";
            if (!Directory.Exists(client))
            {
                using (FolderBrowserDialog folder = new FolderBrowserDialog())
                {
                    folder.Description = "Selecciona la carpeta de WoW Forever o su carpeta Interface" + Path.DirectorySeparatorChar + "AddOns.";
                    folder.ShowNewFolderButton = false;
                    if (folder.ShowDialog() != DialogResult.OK) return 0;
                    client = folder.SelectedPath;
                }
            }
            client = Path.GetFullPath(client).TrimEnd('\\', '/');
            string prompt = restore ? "¿Restaurar los addons anteriores?" :
                "¿Sustituir la instalación anterior por la nueva versión de RutaXP?\n\nOpenMap, Dungeon Journal y RestedXP quedarán dentro de RutaXP. Las copias anteriores se guardarán fuera de AddOns.";
            if (MessageBox.Show(prompt + "\n\n" + client + "\n\nCierra WoW antes de continuar.", "RutaXP personal",
                    MessageBoxButtons.OKCancel, MessageBoxIcon.Information) != DialogResult.OK) return 0;

            using (Form progress = new Form())
            using (System.ComponentModel.BackgroundWorker worker = new System.ComponentModel.BackgroundWorker())
            {
                progress.Text = restore ? "Restaurando RutaXP" : "Verificando e instalando RutaXP";
                progress.Width = 430;
                progress.Height = 100;
                progress.FormBorderStyle = FormBorderStyle.FixedDialog;
                progress.StartPosition = FormStartPosition.CenterScreen;
                progress.ControlBox = false;
                ProgressBar bar = new ProgressBar { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee };
                progress.Controls.Add(bar);
                Exception failure = null;
                worker.DoWork += delegate { Install(client, restore); };
                worker.RunWorkerCompleted += delegate(object sender, System.ComponentModel.RunWorkerCompletedEventArgs done)
                    { failure = done.Error; progress.Close(); };
                progress.Shown += delegate { worker.RunWorkerAsync(); };
                progress.ShowDialog();
                if (failure != null) throw failure;
            }
            MessageBox.Show(restore ? "Se ha restaurado la instalación anterior." :
                "En la selección de personajes, abre Accesorios y comprueba que RutaXP está activado para tu personaje.\n\nEn el juego, pulsa M para ver el mapa o escribe /rutaxp para abrir el menú.", "RutaXP personal");
            return 0;
        }
        catch (Exception error)
        {
            if (Array.IndexOf(args, "--verify") < 0) MessageBox.Show(error.Message, "RutaXP personal", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    private static void Install(string client, bool restore)
    {
        string temp = Path.Combine(Path.GetTempPath(), "RutaXP-personal-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        string script = Path.Combine(temp, "Install-Suite.ps1"), zip = Path.Combine(temp, "Suite.zip");
        try
        {
            using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("Install-Suite.ps1"))
            using (FileStream target = File.Open(script, FileMode.CreateNew)) resource.CopyTo(target);
            if (!restore) ReadBundle(zip);
            string powershell = Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe");
            ProcessStartInfo start = new ProcessStartInfo(powershell, "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"" + script +
                "\" -Client \"" + client + "\"" + (restore ? " -Restore" : " -Archive \"" + zip + "\""));
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardError = true;
            using (Process proc = Process.Start(start))
            {
                string errors = proc.StandardError.ReadToEnd();
                proc.WaitForExit();
                if (proc.ExitCode != 0) throw new IOException(errors.Trim());
            }
        }
        finally
        {
            if (File.Exists(script)) File.Delete(script);
            if (File.Exists(zip)) File.Delete(zip);
            Directory.Delete(temp);
        }
    }
}
