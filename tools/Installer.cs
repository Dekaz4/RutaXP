using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace RutaXPInstaller
{
    public sealed class InstallResult
    {
        public string Target;
        public string Backup;
    }

    // Public helpers are also tested against temporary fixtures, never a real
    // WoW installation. No detection or user prompts run when used as a library.
    public static class InstallerCore
    {
        public static string Normalize(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) throw new ArgumentException("Introduce una ruta absoluta.");
            string value = path.Trim().Trim('"').Trim();
            if (!Path.IsPathRooted(value) || (Path.GetPathRoot(value).Length < 3 && !value.StartsWith(@"\\")))
                throw new ArgumentException("Introduce una ruta absoluta.");
            string full = Path.GetFullPath(value);
            return full.Length > Path.GetPathRoot(full).Length ? full.TrimEnd('\\', '/') : full;
        }

        public static void RejectLinks(string path)
        {
            string current = Normalize(path);
            while (!string.IsNullOrEmpty(current))
            {
                if (File.Exists(current) || Directory.Exists(current))
                    if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                        throw new IOException("No se permiten enlaces o junctions: " + current);
                string parent = Path.GetDirectoryName(current);
                if (parent == current) break;
                current = parent;
            }
        }

        public static bool IsForeverClient(string path)
        {
            if (!Directory.Exists(path)) return false;
            string leaf = Path.GetFileName(Normalize(path));
            if (leaf.Equals("_classic_beta_", StringComparison.OrdinalIgnoreCase) || leaf.Equals("_forever_", StringComparison.OrdinalIgnoreCase)) return true;
            foreach (string name in new string[] { "Wow.exe", "WowB.exe", "WowClassic.exe" })
            {
                string exe = Path.Combine(path, name);
                if (File.Exists(exe))
                    try { if (Regex.IsMatch(FileVersionInfo.GetVersionInfo(exe).FileVersion ?? "", @"^1\.60\.")) return true; } catch { }
            }
            return false;
        }

        public static List<string> ResolveDestinations(string path)
        {
            string full = Normalize(path);
            RejectLinks(full);
            string client = full;
            if (Path.GetFileName(full).Equals("AddOns", StringComparison.OrdinalIgnoreCase))
            {
                string parent = Path.GetDirectoryName(full);
                if (!Path.GetFileName(parent).Equals("Interface", StringComparison.OrdinalIgnoreCase)) throw new IOException("AddOns debe estar dentro de Interface.");
                client = Path.GetDirectoryName(parent);
            }
            else if (Path.GetFileName(full).Equals("Interface", StringComparison.OrdinalIgnoreCase)) client = Path.GetDirectoryName(full);
            List<string> clients = new List<string>();
            if (IsForeverClient(client)) clients.Add(client);
            else if (Directory.Exists(full))
                foreach (string flavor in new string[] { "_classic_beta_", "_forever_" })
                {
                    string candidate = Path.Combine(full, flavor);
                    if (IsForeverClient(candidate)) clients.Add(candidate);
                }
            if (clients.Count == 0) throw new IOException("No se encuentra WoW Forever. Elige _classic_beta_, _forever_ o su Interface\\AddOns.");
            List<string> results = new List<string>();
            foreach (string item in clients)
            {
                string addons = Normalize(Path.Combine(item, "Interface", "AddOns"));
                RejectLinks(addons);
                results.Add(addons);
            }
            return SortDestinations(results);
        }

        public static List<string> SortDestinations(IEnumerable<string> paths)
        {
            List<string> result = new List<string>(new HashSet<string>(paths, StringComparer.OrdinalIgnoreCase));
            result.Sort(delegate(string a, string b)
            {
                bool first = a.IndexOf("\\_classic_beta_\\", StringComparison.OrdinalIgnoreCase) >= 0;
                bool second = b.IndexOf("\\_classic_beta_\\", StringComparison.OrdinalIgnoreCase) >= 0;
                return first == second ? StringComparer.OrdinalIgnoreCase.Compare(a, b) : (first ? -1 : 1);
            });
            return result;
        }

        public static List<string> Files(string root)
        {
            root = Normalize(root);
            RejectLinks(root);
            if (!Directory.Exists(root)) throw new IOException("No existe la carpeta: " + root);
            Stack<string> pending = new Stack<string>();
            List<string> files = new List<string>();
            pending.Push(root);
            while (pending.Count > 0)
                foreach (string entry in Directory.GetFileSystemEntries(pending.Pop()))
                {
                    FileAttributes attributes = File.GetAttributes(entry);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("No se permiten enlaces: " + entry);
                    if ((attributes & FileAttributes.Directory) != 0) pending.Push(entry); else files.Add(entry);
                }
            return files;
        }

        public static void ValidateToc(string root)
        {
            root = Normalize(root);
            string toc = Path.Combine(root, "RutaXP.toc");
            if (!File.Exists(toc)) throw new IOException("Falta RutaXP.toc.");
            int scripts = 0;
            foreach (string raw in File.ReadAllLines(toc))
            {
                string entry = raw.Trim();
                if (entry.Length == 0 || entry.StartsWith("#")) continue;
                if (Path.IsPathRooted(entry)) throw new IOException("Ruta absoluta no permitida en TOC: " + entry);
                string file = Normalize(Path.Combine(root, entry));
                if (!file.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase)) throw new IOException("Entrada TOC fuera del addon: " + entry);
                RejectLinks(file);
                if (!File.Exists(file)) throw new IOException("Falta un archivo del TOC: " + entry);
                scripts++;
            }
            if (scripts == 0) throw new IOException("El TOC no contiene archivos del addon.");
        }

        public static Dictionary<string, string> Manifest(string root)
        {
            root = Normalize(root);
            ValidateToc(root);
            string manifestFile = Path.Combine(root, "manifest.sha256");
            if (!File.Exists(manifestFile)) throw new IOException("Falta manifest.sha256. Extrae el paquete de publicacion completo.");
            Dictionary<string, string> expected = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (string line in File.ReadAllLines(manifestFile))
            {
                if (line.Trim().Length == 0 || line.TrimStart().StartsWith("#")) continue;
                Match match = Regex.Match(line, @"^([a-fA-F0-9]{64})  (.+)$");
                if (!match.Success) throw new IOException("Formato de manifest.sha256 no valido.");
                string relative = match.Groups[2].Value.Replace('/', '\\');
                if (Path.IsPathRooted(relative) || relative.IndexOf(':') >= 0) throw new IOException("Ruta no valida en manifest.sha256.");
                string file = Normalize(Path.Combine(root, relative));
                if (!file.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase)) throw new IOException("Ruta del manifiesto fuera del addon.");
                string key = file.Substring(root.Length + 1);
                if (key.Equals("manifest.sha256", StringComparison.OrdinalIgnoreCase) || expected.ContainsKey(key)) throw new IOException("Entrada duplicada o circular en manifest.sha256.");
                expected.Add(key, match.Groups[1].Value.ToLowerInvariant());
            }
            Dictionary<string, string> result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            using (SHA256 hash = SHA256.Create())
                foreach (string file in Files(root))
                    using (FileStream stream = File.OpenRead(file))
                        result.Add(file.Substring(root.Length + 1), BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant());
            if (result.Count != expected.Count + 1) throw new IOException("El paquete no coincide con la lista de manifest.sha256.");
            foreach (KeyValuePair<string, string> file in expected)
                if (!result.ContainsKey(file.Key) || result[file.Key] != file.Value) throw new IOException("Archivo ausente o alterado: " + file.Key);
            return result;
        }

        public static void ValidateManifest(string root, IDictionary<string, string> expected)
        {
            Dictionary<string, string> actual = Manifest(root);
            if (actual.Count != expected.Count) throw new IOException("La copia esta incompleta o contiene archivos inesperados.");
            foreach (KeyValuePair<string, string> file in expected)
                if (!actual.ContainsKey(file.Key) || actual[file.Key] != file.Value) throw new IOException("La copia no coincide: " + file.Key);
        }

        static void GuardChild(string parent, string child, string name)
        {
            parent = Normalize(parent); child = Normalize(child);
            if (!string.Equals(Path.GetDirectoryName(child), parent, StringComparison.OrdinalIgnoreCase) || !string.Equals(Path.GetFileName(child), name, StringComparison.OrdinalIgnoreCase))
                throw new IOException("Destino fuera de la carpeta elegida.");
            RejectLinks(child);
        }

        static void RemoveWorkDirectory(string parent, string path, string prefix)
        {
            string name = Path.GetFileName(path);
            if (!Regex.IsMatch(name, "^" + Regex.Escape(prefix) + "[a-f0-9]{32}$")) throw new IOException("Nombre temporal no valido.");
            GuardChild(parent, path, name);
            if (Directory.Exists(path)) { Files(path); Directory.Delete(path, true); }
        }

        public static InstallResult InstallFromDirectory(string source, string addons)
        {
            return InstallFromDirectory(source, addons, null, null);
        }

        // Optional callbacks make copy and commit failures testable without
        // changing real permissions, running WoW or invoking the UI.
        public static InstallResult InstallFromDirectory(string source, string addons, Action<string, string> copy, Action beforeActivate)
        {
            source = Normalize(source); addons = Normalize(addons);
            List<string> resolved = ResolveDestinations(addons);
            if (resolved.Count != 1 || !resolved[0].Equals(addons, StringComparison.OrdinalIgnoreCase)) throw new IOException("Selecciona una sola carpeta Interface\\AddOns de Forever.");
            string target = Path.Combine(addons, "RutaXP");
            GuardChild(addons, target, "RutaXP");
            if (source.Equals(target, StringComparison.OrdinalIgnoreCase) || source.StartsWith(target + "\\", StringComparison.OrdinalIgnoreCase) || target.StartsWith(source + "\\", StringComparison.OrdinalIgnoreCase))
                throw new IOException("Origen y destino deben ser distintos y no contenerse entre si.");
            Dictionary<string, string> manifest = Manifest(source);
            if (Directory.Exists(target)) Files(target);
            RejectLinks(addons);
            Directory.CreateDirectory(addons);
            string token = Guid.NewGuid().ToString("N");
            string stage = Path.Combine(addons, ".RutaXP.stage." + token);
            string backup = Path.Combine(addons, ".RutaXP.backup." + token);
            string failed = Path.Combine(addons, ".RutaXP.failed." + token);
            bool oldMoved = false, activated = false;
            try
            {
                GuardChild(addons, stage, ".RutaXP.stage." + token);
                Directory.CreateDirectory(stage);
                foreach (string relative in manifest.Keys)
                {
                    string from = Path.Combine(source, relative), to = Path.Combine(stage, relative);
                    RejectLinks(from);
                    Directory.CreateDirectory(Path.GetDirectoryName(to));
                    if (copy == null) File.Copy(from, to, false); else copy(from, to);
                }
                ValidateManifest(stage, manifest);
                GuardChild(addons, target, "RutaXP"); GuardChild(addons, backup, ".RutaXP.backup." + token);
                if (Directory.Exists(target)) { Files(target); Directory.Move(target, backup); oldMoved = true; }
                if (beforeActivate != null) beforeActivate();
                GuardChild(addons, stage, ".RutaXP.stage." + token); GuardChild(addons, target, "RutaXP");
                Directory.Move(stage, target); activated = true;
                ValidateManifest(target, manifest);
                return new InstallResult { Target = target, Backup = oldMoved ? backup : null };
            }
            catch (Exception problem)
            {
                try
                {
                    if (activated && Directory.Exists(target)) { GuardChild(addons, target, "RutaXP"); GuardChild(addons, failed, ".RutaXP.failed." + token); Directory.Move(target, failed); }
                    if (oldMoved) { GuardChild(addons, backup, ".RutaXP.backup." + token); GuardChild(addons, target, "RutaXP"); Directory.Move(backup, target); }
                }
                catch (Exception restore)
                {
                    throw new IOException("Fallo: " + problem.Message + ". Restauracion automatica imposible; tu copia anterior se conserva en " + backup + ". " + restore.Message, problem);
                }
                throw new IOException("Instalacion cancelada; se conserva la version anterior. " + problem.Message, problem);
            }
            finally
            {
                foreach (string path in new string[] { stage, failed })
                    try { RemoveWorkDirectory(addons, path, Path.GetFileName(path).StartsWith(".RutaXP.stage.") ? ".RutaXP.stage." : ".RutaXP.failed."); }
                    catch (Exception cleanup) { Console.Error.WriteLine("Carpeta temporal conservada: " + path + ". " + cleanup.Message); }
            }
        }

        public static void ExtractArchive(Stream stream, string root)
        {
            root = Normalize(root); RejectLinks(root);
            Directory.CreateDirectory(root);
            HashSet<string> entries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            using (ZipArchive archive = new ZipArchive(stream, ZipArchiveMode.Read, true))
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string name = entry.FullName.Replace('/', '\\');
                    if (!name.StartsWith("RutaXP\\", StringComparison.OrdinalIgnoreCase)) throw new IOException("Archivo fuera de RutaXP en el ZIP.");
                    name = name.Substring(7);
                    if (name.Length == 0) continue;
                    if (Path.IsPathRooted(name) || name.IndexOf(':') >= 0 || ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000) throw new IOException("Ruta o enlace no valido en ZIP.");
                    string destination = Normalize(Path.Combine(root, name));
                    if (!destination.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase)) throw new IOException("Ruta ZIP fuera del addon.");
                    RejectLinks(destination);
                    if (name.EndsWith("\\")) { Directory.CreateDirectory(destination); continue; }
                    if (!entries.Add(destination)) throw new IOException("Archivo duplicado en ZIP.");
                    Directory.CreateDirectory(Path.GetDirectoryName(destination));
                    using (Stream input = entry.Open())
                    using (FileStream output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write)) input.CopyTo(output);
                    if (new FileInfo(destination).Length != entry.Length) throw new IOException("Archivo ZIP incompleto: " + name);
                }
            ValidateToc(root);
        }

        public static InstallResult InstallFromArchive(Stream stream, string addons)
        {
            string parent = Normalize(Path.GetTempPath());
            RejectLinks(parent);
            string source = Path.Combine(parent, "RutaXP-source." + Guid.NewGuid().ToString("N"));
            try { ExtractArchive(stream, source); return InstallFromDirectory(source, addons); }
            finally
            {
                try { RemoveWorkDirectory(parent, source, "RutaXP-source."); }
                catch (Exception cleanup) { Console.Error.WriteLine("Carpeta temporal conservada: " + source + ". " + cleanup.Message); }
            }
        }
    }

    class Program
    {
        static void Main(string[] args)
        {
            try { Console.OutputEncoding = Encoding.UTF8; Console.Title = "Instalador automatico de RutaXP"; } catch { }
            int code;
            try { code = Run(); } catch (Exception problem) { Console.Error.WriteLine("Error: " + problem.Message); code = 1; }
            Console.WriteLine("Presiona cualquier tecla para salir...");
            try { Console.ReadKey(true); } catch { }
            Environment.Exit(code);
        }

        static string Choose(List<string> choices)
        {
            if (choices.Count == 1)
            {
                Console.WriteLine("Cliente Forever: " + choices[0]);
                Console.Write("Instalar aqui (S/N; Enter = S): ");
                string answer = Console.ReadLine();
                return string.IsNullOrWhiteSpace(answer) || answer.Trim().Equals("S", StringComparison.OrdinalIgnoreCase) || answer.Trim().Equals("SI", StringComparison.OrdinalIgnoreCase) ? choices[0] : null;
            }
            for (int i = 0; i < choices.Count; i++) Console.WriteLine("  [" + (i + 1) + "] " + choices[i]);
            if (choices.Count == 0) return null;
            Console.Write("Elige UN cliente (numero; M = otra carpeta; Enter = 1): ");
            string choice = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(choice)) choice = "1";
            if (choice.Trim().Equals("M", StringComparison.OrdinalIgnoreCase)) return null;
            int number;
            if (!int.TryParse(choice, out number) || number < 1 || number > choices.Count) throw new IOException("Opcion no valida; no se ha instalado nada.");
            return choices[number - 1];
        }

        static int Run()
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("\nINSTALADOR DE RUTAXP PARA WOW FOREVER\n");
            Console.ResetColor();
            Console.WriteLine("Buscando clientes de Forever...");
            string target = Choose(FindWoWAddonFolders());
            if (target == null)
            {
                Console.Write("Ruta de WoW Forever, carpeta principal de WoW o Interface\\AddOns: ");
                target = Choose(InstallerCore.ResolveDestinations(Console.ReadLine()));
            }
            if (target == null) { Console.WriteLine("Instalacion cancelada."); return 1; }
            string local = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "RutaXP");
            InstallResult result = null;
            // The self-contained executable must install its own release,
            // even when an older/unpacked developer folder sits beside it.
            Assembly assembly = Assembly.GetExecutingAssembly();
            foreach (string name in assembly.GetManifestResourceNames())
                if (name.EndsWith("payload.zip", StringComparison.OrdinalIgnoreCase))
                    using (Stream stream = assembly.GetManifestResourceStream(name)) { result = InstallerCore.InstallFromArchive(stream, target); break; }
            if (result == null && Directory.Exists(local)) result = InstallerCore.InstallFromDirectory(local, target);
            if (result == null) throw new IOException("No se encuentra el paquete RutaXP. Extrae el ZIP completo.");
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("Instalado correctamente en: " + result.Target);
            Console.ResetColor();
            if (result.Backup != null) Console.WriteLine("Copia anterior conservada en: " + result.Backup);
            Console.WriteLine("Cierra WoW completamente y vuelve a abrirlo; /reload no descubre addons nuevos.");
            Console.WriteLine("Activa RutaXP en Accesorios. Usa /rutaxp para las guias y N para los talentos.");
            return 0;
        }

        static List<string> FindWoWAddonFolders()
        {
            List<string> roots = new List<string>();
            foreach (string name in new string[] { "Wow", "WowB", "WowClassic", "WorldOfWarcraft", "Wow-64" })
                try
                {
                    foreach (Process process in Process.GetProcessesByName(name))
                        try { string folder = Path.GetDirectoryName(process.MainModule.FileName); roots.Add(folder); roots.Add(Path.GetDirectoryName(folder)); } catch { }
                } catch { }
            foreach (string keyName in new string[] { @"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft", @"SOFTWARE\Blizzard Entertainment\World of Warcraft", @"SOFTWARE\Blizzard Entertainment\Battle.net\Default Installations" })
                foreach (RegistryKey hive in new RegistryKey[] { Registry.LocalMachine, Registry.CurrentUser })
                    try
                    {
                        using (RegistryKey key = hive.OpenSubKey(keyName))
                            if (key != null)
                                foreach (string property in new string[] { "InstallPath", "Path", "Install_Path" })
                                { string path = key.GetValue(property) as string; if (!string.IsNullOrEmpty(path)) roots.Add(path); }
                    } catch { }
            string[] common = new string[] { @"World of Warcraft", @"Program Files (x86)\World of Warcraft", @"Program Files\World of Warcraft", @"Games\World of Warcraft", @"Juegos\World of Warcraft", @"WOW\World of Warcraft", @"WOW", @"WoW Forever", @"World of Warcraft Forever", @"Forever" };
            try
            {
                foreach (DriveInfo drive in DriveInfo.GetDrives())
                    if (drive.IsReady && drive.DriveType == DriveType.Fixed)
                        foreach (string sub in common) roots.Add(Path.Combine(drive.RootDirectory.FullName, sub));
            } catch { }
            List<string> found = new List<string>();
            foreach (string root in roots) try { found.AddRange(InstallerCore.ResolveDestinations(root)); } catch { }
            return InstallerCore.SortDestinations(found);
        }
    }
}
