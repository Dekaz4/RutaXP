using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;
using RutaXPInstaller;

namespace RutaXPUpdater
{
    public sealed class ReleaseInfo
    {
        public string Tag, Version, ArchiveName, ArchiveUrl, ChecksumsUrl;
        public long ArchiveSize;
    }
    public sealed class UpdateResult
    {
        public string Version, Target, Backup;
        public bool Changed, LatestVerified;
    }
    public sealed class BackupInfo
    {
        public string Name, Path, Version;
        public DateTime Date;
    }

    // All state-changing helpers take explicit paths. Tests provide bytes and
    // process checks; compiling this source as a library never starts the UI.
    public static class UpdaterCore
    {
        public const string LatestUrl = "https://api.github.com/repos/Dekaz4/RutaXP/releases/latest";
        public const long MaxArchiveBytes = 128L * 1024 * 1024;
        public const long MaxExpandedBytes = 512L * 1024 * 1024;
        public const long MaxEntryBytes = 64L * 1024 * 1024;
        public const int MaxEntries = 20000;

        public static string StableVersion(string value)
        {
            if (value == null || !Regex.IsMatch(value, @"^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$"))
                throw new IOException("La version debe tener formato estable mayor.menor.parche.");
            return value;
        }
        public static string TagVersion(string tag)
        {
            return StableVersion(tag != null && tag.StartsWith("v", StringComparison.Ordinal) ? tag.Substring(1) : tag);
        }
        public static int CompareVersions(string a, string b)
        {
            return new Version(StableVersion(a)).CompareTo(new Version(StableVersion(b)));
        }
        static string Text(IDictionary<string, object> value, string key)
        {
            object item;
            return value.TryGetValue(key, out item) ? item as string : null;
        }
        static bool Flag(IDictionary<string, object> value, string key)
        {
            object item;
            if (!value.TryGetValue(key, out item) || !(item is bool)) throw new IOException("Respuesta de GitHub incompleta: " + key);
            return (bool)item;
        }
        public static void ValidateAssetUrl(string url, string tag, string filename)
        {
            Uri uri;
            string path = "/Dekaz4/RutaXP/releases/download/" + Uri.EscapeDataString(tag) + "/" + Uri.EscapeDataString(filename);
            if (!Uri.TryCreate(url, UriKind.Absolute, out uri) || uri.Scheme != "https" || uri.Host != "github.com"
                || !uri.IsDefaultPort || uri.UserInfo.Length != 0 || uri.Query.Length != 0 || uri.Fragment.Length != 0
                || !uri.AbsolutePath.Equals(path, StringComparison.Ordinal))
                throw new IOException("La descarga no pertenece al release HTTPS de Dekaz4/RutaXP.");
        }
        public static ReleaseInfo ParseRelease(string json)
        {
            if (json == null || json.Length > 1024 * 1024) throw new IOException("Respuesta de GitHub demasiado grande.");
            JavaScriptSerializer parser = new JavaScriptSerializer();
            parser.MaxJsonLength = 1024 * 1024; parser.RecursionLimit = 32;
            IDictionary<string, object> data = parser.DeserializeObject(json) as IDictionary<string, object>;
            if (data == null || Flag(data, "draft") || Flag(data, "prerelease")) throw new IOException("GitHub no devolvio una publicacion estable.");
            string tag = Text(data, "tag_name"), version = TagVersion(tag);
            ReleaseInfo result = new ReleaseInfo { Tag = tag, Version = version, ArchiveName = "RutaXP-" + version + "-addon.zip" };
            object raw;
            IEnumerable assets = data.TryGetValue("assets", out raw) ? raw as IEnumerable : null;
            if (assets == null || raw is string) throw new IOException("Faltan los archivos del release.");
            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (object item in assets)
            {
                IDictionary<string, object> asset = item as IDictionary<string, object>;
                if (asset == null) throw new IOException("Archivo de release no valido.");
                string name = Text(asset, "name");
                if (name != result.ArchiveName && name != "SHA256SUMS.txt") continue;
                if (!seen.Add(name)) throw new IOException("El release contiene archivos duplicados.");
                string url = Text(asset, "browser_download_url");
                ValidateAssetUrl(url, tag, name);
                object size;
                long length;
                if (!asset.TryGetValue("size", out size) || !long.TryParse(Convert.ToString(size, System.Globalization.CultureInfo.InvariantCulture), out length)
                    || length <= 0 || length > (name == result.ArchiveName ? MaxArchiveBytes : 1024 * 1024))
                    throw new IOException("El archivo publicado supera los limites permitidos.");
                if (name == result.ArchiveName) { result.ArchiveUrl = url; result.ArchiveSize = length; }
                else result.ChecksumsUrl = url;
            }
            if (result.ArchiveUrl == null || result.ChecksumsUrl == null) throw new IOException("El release necesita el ZIP del addon y SHA256SUMS.txt.");
            return result;
        }
        public static string Hash(byte[] data)
        {
            using (SHA256 hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
        }
        public static void VerifyArchiveHash(byte[] archive, string sums, string name)
        {
            if (archive == null || archive.LongLength == 0 || archive.LongLength > MaxArchiveBytes || sums == null || sums.Length > 1024 * 1024)
                throw new IOException("Descarga vacia o demasiado grande.");
            string expected = null;
            foreach (string raw in sums.Split('\n'))
            {
                string line = raw.TrimEnd('\r');
                if (line.Trim().Length == 0 || line.StartsWith("#", StringComparison.Ordinal)) continue;
                Match match = Regex.Match(line, @"^([a-fA-F0-9]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)$");
                if (!match.Success) throw new IOException("Formato de SHA256SUMS.txt no valido.");
                if (match.Groups[2].Value == name)
                {
                    if (expected != null) throw new IOException("Hash de archivo duplicado.");
                    expected = match.Groups[1].Value.ToLowerInvariant();
                }
            }
            if (expected == null || Hash(archive) != expected) throw new IOException("El SHA256 del ZIP no coincide; no se ha instalado nada.");
        }
        public static void ValidateArchive(byte[] data)
        {
            if (data == null || data.LongLength == 0 || data.LongLength > MaxArchiveBytes) throw new IOException("ZIP fuera del limite permitido.");
            long total = 0, actualTotal = 0;
            HashSet<string> names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            using (MemoryStream bytes = new MemoryStream(data, false))
            using (ZipArchive zip = new ZipArchive(bytes, ZipArchiveMode.Read))
            {
                if (zip.Entries.Count == 0 || zip.Entries.Count > MaxEntries) throw new IOException("Demasiadas entradas en el ZIP.");
                foreach (ZipArchiveEntry entry in zip.Entries)
                {
                    string name = entry.FullName.Replace('\\', '/');
                    if (!name.StartsWith("RutaXP/", StringComparison.Ordinal) || name.IndexOf(':') >= 0
                        || ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000
                        || (entry.ExternalAttributes & (int)FileAttributes.ReparsePoint) != 0 || !names.Add(name.TrimEnd('/')))
                        throw new IOException("Ruta, enlace o duplicado no permitido en el ZIP.");
                    foreach (string part in name.TrimEnd('/').Split('/'))
                        if (part.Length == 0 || part == "." || part == ".." || part.EndsWith(".") || part.EndsWith(" ")
                            || Regex.IsMatch(part, @"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", RegexOptions.IgnoreCase))
                            throw new IOException("Nombre de archivo no permitido en el ZIP.");
                    if (entry.Length < 0 || entry.Length > MaxEntryBytes || entry.Length > MaxExpandedBytes - total)
                        throw new IOException("El ZIP supera el limite de extraccion.");
                    total += entry.Length;
                    long actual = 0;
                    using (Stream input = entry.Open())
                    {
                        byte[] buffer = new byte[65536]; int count;
                        while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            if (actual > MaxEntryBytes - count || actualTotal > MaxExpandedBytes - count)
                                throw new IOException("Los datos descomprimidos superan el limite permitido.");
                            actual += count; actualTotal += count;
                        }
                    }
                    if (actual != entry.Length) throw new IOException("El tamano ZIP declarado no coincide con sus datos.");
                }
            }
        }
        public static string TocVersion(string addon)
        {
            string found = null;
            foreach (string line in File.ReadAllLines(Path.Combine(addon, "RutaXP.toc")))
            {
                Match match = Regex.Match(line, @"^## Version:\s*(\S+)\s*$");
                if (match.Success)
                {
                    if (found != null) throw new IOException("Version duplicada en RutaXP.toc.");
                    found = StableVersion(match.Groups[1].Value);
                }
            }
            if (found == null) throw new IOException("Falta la version de RutaXP.toc.");
            return found;
        }
        public static string ReadInstalledVersion(string addons)
        {
            string root = Path.Combine(ResolveClient(addons), "RutaXP");
            InstallerCore.RejectLinks(root);
            if (!File.Exists(Path.Combine(root, "RutaXP.toc"))) return null;
            try { return TocVersion(root); } catch (IOException) { return null; }
        }
        public static string ResolveClient(string path)
        {
            List<string> targets = InstallerCore.ResolveDestinations(path);
            if (targets.Count != 1) throw new IOException("Elige un solo cliente Forever o su carpeta Interface\\AddOns.");
            return targets[0];
        }
        public static void RequireClosed(Func<bool> running)
        {
            if (running == null || running()) throw new IOException("Cierra WoW completamente antes de actualizar, reparar o restaurar. El actualizador no cerrara el juego.");
        }
        static string Temporary()
        {
            string parent = InstallerCore.Normalize(Path.GetTempPath()); InstallerCore.RejectLinks(parent);
            string path = Path.Combine(parent, "RutaXP-update." + Guid.NewGuid().ToString("N"));
            InstallerCore.RejectLinks(path); Directory.CreateDirectory(path); return path;
        }
        static void RemoveTemporary(string path)
        {
            string parent = InstallerCore.Normalize(Path.GetTempPath()); path = InstallerCore.Normalize(path);
            if (!Path.GetDirectoryName(path).Equals(parent, StringComparison.OrdinalIgnoreCase)
                || !Regex.IsMatch(Path.GetFileName(path), @"^RutaXP-update\.[a-f0-9]{32}$")) throw new IOException("Carpeta temporal no valida.");
            if (Directory.Exists(path)) { InstallerCore.Files(path); Directory.Delete(path, true); }
        }
        public static void PreparePackage(byte[] archive, string sums, ReleaseInfo release, string destination)
        {
            VerifyArchiveHash(archive, sums, release.ArchiveName); ValidateArchive(archive);
            if (archive.LongLength != release.ArchiveSize) throw new IOException("El tamano del ZIP no coincide con el publicado.");
            using (MemoryStream input = new MemoryStream(archive, false)) InstallerCore.ExtractArchive(input, destination);
            InstallerCore.Manifest(destination);
            if (TocVersion(destination) != release.Version) throw new IOException("El tag de GitHub y la version del addon no coinciden.");
        }
        static byte[] Download(Func<string, long, byte[]> fetch, string url, long maximum)
        {
            if (fetch == null) throw new IOException("No hay proveedor de descarga.");
            byte[] data = fetch(url, maximum);
            if (data == null || data.LongLength == 0 || data.LongLength > maximum) throw new IOException("Descarga vacia o fuera del limite permitido.");
            return data;
        }
        public static UpdateResult Update(string client, bool repair, string versionFloor,
            Func<string, long, byte[]> fetch, Func<bool> running, Action beforeActivate)
        {
            if (string.IsNullOrWhiteSpace(versionFloor)) versionFloor = null;
            string addons = ResolveClient(client); RequireClosed(running);
            ReleaseInfo release = ParseRelease(Encoding.UTF8.GetString(Download(fetch, LatestUrl, 1024 * 1024)));
            string installed = ReadInstalledVersion(addons);
            if (installed != null && CompareVersions(release.Version, installed) < 0
                || versionFloor != null && CompareVersions(release.Version, versionFloor) < 0)
                throw new IOException("GitHub ofrece una version anterior a la ya verificada. No se permite bajar de version con Actualizar.");
            string target = Path.Combine(addons, "RutaXP");
            if (!repair && installed == release.Version)
            {
                bool valid = false;
                try { InstallerCore.Manifest(target); valid = true; } catch (IOException) { }
                if (valid) { RequireClosed(running); return new UpdateResult { Version = release.Version, Target = target, LatestVerified = true }; }
            }
            string sums = Encoding.UTF8.GetString(Download(fetch, release.ChecksumsUrl, 1024 * 1024));
            byte[] archive = Download(fetch, release.ArchiveUrl, MaxArchiveBytes);
            string temp = Temporary();
            try
            {
                PreparePackage(archive, sums, release, temp); RequireClosed(running);
                Action guardedActivation = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
                InstallResult installedResult = InstallerCore.InstallFromDirectory(temp, addons, null, guardedActivation);
                return new UpdateResult { Version = release.Version, Target = installedResult.Target, Backup = installedResult.Backup,
                    Changed = true, LatestVerified = true };
            }
            finally { try { RemoveTemporary(temp); } catch (IOException cleanup) { Console.Error.WriteLine("Temporal conservado: " + cleanup.Message); } }
        }
        public static UpdateResult InstallBundled(Stream stream, string client, Func<bool> running, Action beforeActivate)
        {
            string addons = ResolveClient(client); RequireClosed(running);
            if (stream == null || !stream.CanRead) throw new IOException("No se encuentra la copia incluida en este instalador.");
            byte[] archive;
            using (MemoryStream bytes = new MemoryStream())
            {
                byte[] buffer = new byte[65536]; int count;
                while ((count = stream.Read(buffer, 0, buffer.Length)) > 0)
                {
                    if (bytes.Length > MaxArchiveBytes - count) throw new IOException("La copia incluida supera el limite permitido.");
                    bytes.Write(buffer, 0, count);
                }
                archive = bytes.ToArray();
            }
            ValidateArchive(archive);
            string temp = Temporary();
            try
            {
                using (MemoryStream bytes = new MemoryStream(archive, false)) InstallerCore.ExtractArchive(bytes, temp);
                InstallerCore.Manifest(temp); string version = TocVersion(temp), installed = ReadInstalledVersion(addons);
                if (installed != null && CompareVersions(version, installed) < 0)
                    throw new IOException("La copia incluida es anterior a la instalada. Usa Actualizar o una copia de recuperacion explicita.");
                RequireClosed(running);
                Action guardedActivation = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
                InstallResult result = InstallerCore.InstallFromDirectory(temp, addons, null, guardedActivation);
                return new UpdateResult { Version = version, Target = result.Target, Backup = result.Backup, Changed = true, LatestVerified = false };
            }
            finally { try { RemoveTemporary(temp); } catch (IOException cleanup) { Console.Error.WriteLine("Temporal conservado: " + cleanup.Message); } }
        }
        public static List<BackupInfo> Backups(string client)
        {
            string addons = ResolveClient(client); List<BackupInfo> valid = new List<BackupInfo>();
            if (!Directory.Exists(addons)) return valid;
            foreach (string path in Directory.GetDirectories(addons, ".RutaXP.backup.*"))
            {
                string name = Path.GetFileName(path);
                if (!Regex.IsMatch(name, @"^\.RutaXP\.backup\.[a-f0-9]{32}$")) continue;
                try
                {
                    InstallerCore.RejectLinks(path); InstallerCore.Manifest(path);
                    valid.Add(new BackupInfo { Name = name, Path = path, Version = TocVersion(path), Date = Directory.GetLastWriteTimeUtc(path) });
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
            valid.Sort(delegate(BackupInfo a, BackupInfo b) { int n = b.Date.CompareTo(a.Date); return n == 0 ? StringComparer.Ordinal.Compare(a.Name, b.Name) : n; });
            return valid;
        }
        public static InstallResult Restore(string client, string name, Func<bool> running, Action beforeActivate)
        {
            string addons = ResolveClient(client); RequireClosed(running);
            if (string.IsNullOrWhiteSpace(name)) name = null;
            if (name != null && !Regex.IsMatch(name, @"^\.RutaXP\.backup\.[a-f0-9]{32}$")) throw new IOException("Selecciona una copia anterior de este mismo cliente.");
            List<BackupInfo> copies = Backups(addons); BackupInfo chosen = null;
            foreach (BackupInfo copy in copies) if (name == null || name == copy.Name) { chosen = copy; break; }
            if (chosen == null || !Path.GetDirectoryName(chosen.Path).Equals(addons, StringComparison.OrdinalIgnoreCase)) throw new IOException("No hay una copia anterior valida para restaurar.");
            InstallerCore.Manifest(chosen.Path); RequireClosed(running);
            Action guardedActivation = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
            return InstallerCore.InstallFromDirectory(chosen.Path, addons, null, guardedActivation);
        }
    }

    public static class HttpDownloads
    {
        public static byte[] Fetch(string url, long maximum)
        {
            ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; // TLS 1.2; normal certificate validation remains enabled.
            Uri current = new Uri(url);
            for (int redirects = 0; redirects <= 5; redirects++)
            {
                if (current.Scheme != "https" || current.UserInfo.Length != 0 || !current.IsDefaultPort) throw new IOException("Redireccion no segura.");
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(current);
                request.UserAgent = "RutaXP-Updater/1.0"; request.Accept = "application/vnd.github+json";
                request.AllowAutoRedirect = false; request.Timeout = 30000; request.ReadWriteTimeout = 30000;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                {
                    int code = (int)response.StatusCode;
                    if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308)
                    {
                        Uri next = new Uri(current, response.Headers["Location"] ?? "");
                        if (url == UpdaterCore.LatestUrl || next.Scheme != "https" || next.UserInfo.Length != 0 || !next.IsDefaultPort
                            || !(next.Host == "release-assets.githubusercontent.com" || next.Host == "objects.githubusercontent.com"
                                || next.Host == "github-releases.githubusercontent.com")) throw new IOException("Redireccion de GitHub no permitida.");
                        current = next; continue;
                    }
                    if (code != 200 || response.ContentLength > maximum) throw new IOException("Respuesta de descarga no valida.");
                    using (Stream input = response.GetResponseStream())
                    using (MemoryStream output = new MemoryStream())
                    {
                        byte[] buffer = new byte[65536]; int count;
                        while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            if (output.Length > maximum - count) throw new IOException("La descarga supera el limite permitido.");
                            output.Write(buffer, 0, count);
                        }
                        return output.ToArray();
                    }
                }
            }
            throw new IOException("Demasiadas redirecciones al descargar.");
        }
    }

    public static class ClientSettings
    {
        public static string DirectoryPath { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RutaXP"); } }
        public static string Load(string directory, string key)
        {
            if (key != "client" && key != "latest") throw new IOException("Ajuste no valido.");
            string file = Path.Combine(InstallerCore.Normalize(directory), key + ".txt"); InstallerCore.RejectLinks(file);
            return File.Exists(file) ? File.ReadAllText(file, Encoding.UTF8).Trim() : null;
        }
        public static void Save(string directory, string key, string value)
        {
            if (key != "client" && key != "latest") throw new IOException("Ajuste no valido.");
            directory = InstallerCore.Normalize(directory); InstallerCore.RejectLinks(directory); Directory.CreateDirectory(directory);
            string file = Path.Combine(directory, key + ".txt"); InstallerCore.RejectLinks(file);
            string temporary = Path.Combine(directory, "setting." + Guid.NewGuid().ToString("N"));
            try
            {
                File.WriteAllText(temporary, value, new UTF8Encoding(false));
                if (File.Exists(file)) File.Replace(temporary, file, null); else File.Move(temporary, file);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
    }

    public static class Program
    {
        static bool WowRunning()
        {
            foreach (string name in new string[] { "Wow", "WowB", "WowClassicB", "WowClassic", "Wow-64", "WorldOfWarcraft" })
                foreach (Process process in Process.GetProcessesByName(name)) { process.Dispose(); return true; }
            return false;
        }
        static List<string> Discover()
        {
            List<string> roots = new List<string>();
            foreach (string sub in new string[] { @"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft", @"SOFTWARE\Blizzard Entertainment\World of Warcraft" })
                foreach (RegistryKey hive in new RegistryKey[] { Registry.LocalMachine, Registry.CurrentUser })
                    try { using (RegistryKey key = hive.OpenSubKey(sub)) if (key != null) foreach (string name in new string[] { "InstallPath", "Path" }) { string path = key.GetValue(name) as string; if (path != null) roots.Add(path); } } catch { }
            foreach (DriveInfo drive in DriveInfo.GetDrives())
                try { if (drive.IsReady && drive.DriveType == DriveType.Fixed) foreach (string path in new string[] { @"World of Warcraft", @"WOW\World of Warcraft", @"Games\World of Warcraft", @"Program Files (x86)\World of Warcraft", @"WoW Forever", @"World of Warcraft Forever" }) roots.Add(Path.Combine(drive.RootDirectory.FullName, path)); } catch { }
            List<string> found = new List<string>(); foreach (string path in roots) try { found.AddRange(InstallerCore.ResolveDestinations(path)); } catch { }
            return InstallerCore.SortDestinations(found);
        }
        static string ChooseClient()
        {
            List<string> choices = Discover();
            for (int i = 0; i < choices.Count; i++) Console.WriteLine("  " + (i + 1) + ". " + choices[i]);
            if (choices.Count > 0)
            {
                Console.Write("Cliente (numero; Enter = elegir carpeta): "); string answer = Console.ReadLine(); int index;
                if (int.TryParse(answer, out index) && index >= 1 && index <= choices.Count) return choices[index - 1];
            }
            using (FolderBrowserDialog dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Elige _classic_beta_, _forever_ o su Interface\\AddOns"; dialog.ShowNewFolderButton = false;
                if (dialog.ShowDialog() != DialogResult.OK) throw new IOException("Seleccion de cliente cancelada.");
                List<string> resolved = InstallerCore.ResolveDestinations(dialog.SelectedPath);
                if (resolved.Count == 1) return resolved[0];
                for (int i = 0; i < resolved.Count; i++) Console.WriteLine("  " + (i + 1) + ". " + resolved[i]);
                Console.Write("Elige un cliente (numero): "); int index;
                if (!int.TryParse(Console.ReadLine(), out index) || index < 1 || index > resolved.Count) throw new IOException("Seleccion no valida.");
                return resolved[index - 1];
            }
        }
        static string Menu()
        {
            Console.WriteLine("\nRUTAXP: INSTALACION, ACTUALIZACION Y RECUPERACION\n1. Instalar o actualizar desde GitHub\n2. Reparar (descargar de nuevo)\n3. Restaurar copia anterior\n4. Elegir cliente\n5. Instalar copia incluida (sin conexion)\n0. Salir");
            Console.Write("Opcion (Enter = 1): "); string value = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(value)) value = "1";
            switch (value) { case "1": return "--update"; case "2": return "--repair"; case "3": return "--restore"; case "4": return "--choose-client"; case "5": return "--install-bundled"; case "0": return null; default: throw new IOException("Opcion no valida."); }
        }
        [STAThread]
        public static int Main(string[] args)
        {
            bool interactive = args.Length == 0;
            try
            {
                Console.OutputEncoding = Encoding.UTF8; Console.Title = "RutaXP: instalar y actualizar";
                string action = null, client = null, backup = null;
                for (int i = 0; i < args.Length; i++)
                {
                    string arg = args[i];
                    if (arg == "--help") { Console.WriteLine("RutaXP: --update | --repair | --restore [nombre-copia] | --install-bundled | --choose-client, y --client \"ruta\". Sin argumentos: menu. La copia incluida permite instalar sin conexion. WoW se abre desde su acceso habitual: este instalador nunca lo abre ni lo cierra. No modifica WTF."); return 0; }
                    if (arg == "--client") { if (++i == args.Length) throw new IOException("Falta la ruta del cliente."); client = args[i]; }
                    else if (arg == "--update" || arg == "--repair" || arg == "--restore" || arg == "--choose-client" || arg == "--install-bundled")
                    {
                        if (action != null) throw new IOException("Elige una sola accion."); action = arg;
                        if (arg == "--restore" && i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal)) backup = args[++i];
                    }
                    else throw new IOException("Argumento desconocido: " + arg);
                }
                if (interactive) action = Menu(); else if (action == null) action = "--update";
                if (action == null) return 0;
                string settings = ClientSettings.DirectoryPath;
                if (client == null && action != "--choose-client") try { client = ClientSettings.Load(settings, "client"); } catch (IOException) { }
                if (client == null) client = ChooseClient();
                string addons = UpdaterCore.ResolveClient(client);
                ClientSettings.Save(settings, "client", addons);
                Console.WriteLine("Cliente: " + Path.GetDirectoryName(Path.GetDirectoryName(addons)));
                if (action == "--choose-client") { Console.WriteLine("Cliente recordado. Cada ordenador guarda su propia ruta."); return 0; }
                if (action == "--install-bundled")
                {
                    UpdateResult bundled = null; Assembly assembly = Assembly.GetExecutingAssembly();
                    foreach (string name in assembly.GetManifestResourceNames())
                        if (name.EndsWith("payload.zip", StringComparison.Ordinal))
                            using (Stream stream = assembly.GetManifestResourceStream(name)) { bundled = UpdaterCore.InstallBundled(stream, addons, WowRunning, null); break; }
                    if (bundled == null) throw new IOException("Este ejecutable no contiene una copia del addon.");
                    Console.WriteLine("Copia incluida instalada y validada: " + bundled.Version + ". No se ha comprobado GitHub ni se abrira WoW.");
                    if (bundled.Backup != null) Console.WriteLine("Copia anterior: " + bundled.Backup);
                    return 0;
                }
                if (action == "--restore")
                {
                    if (interactive)
                    {
                        List<BackupInfo> copies = UpdaterCore.Backups(addons);
                        for (int i = 0; i < copies.Count; i++) Console.WriteLine("  " + (i + 1) + ". " + copies[i].Version + " · " + copies[i].Date.ToLocalTime());
                        if (copies.Count == 0) throw new IOException("No hay copias anteriores validadas.");
                        Console.Write("Copia a restaurar (Enter = 1): "); string answer = Console.ReadLine(); int index = 1;
                        if (!string.IsNullOrWhiteSpace(answer) && !int.TryParse(answer, out index) || index < 1 || index > copies.Count) throw new IOException("Seleccion no valida.");
                        backup = copies[index - 1].Name;
                    }
                    InstallResult restored = UpdaterCore.Restore(addons, backup, WowRunning, null);
                    Console.WriteLine("Copia restaurada y validada. No se ha abierto el juego. Copia conservada: " + restored.Backup);
                    Console.WriteLine("Abre WoW desde su acceso habitual. Actualizar volvera a instalar la ultima version publicada."); return 0;
                }
                string floor = null;
                try { floor = ClientSettings.Load(settings, "latest"); if (floor != null) UpdaterCore.StableVersion(floor); } catch (IOException) { floor = null; }
                Console.WriteLine("Consultando la ultima version publica de Dekaz4/RutaXP...");
                UpdateResult result = UpdaterCore.Update(addons, action == "--repair", floor, HttpDownloads.Fetch, WowRunning, null);
                ClientSettings.Save(settings, "latest", result.Version);
                Console.WriteLine((result.Changed ? "Instalacion verificada: " : "Ya tienes la ultima version verificada: ") + result.Version);
                if (result.Backup != null) Console.WriteLine("Copia anterior: " + result.Backup);
                return 0;
            }
            catch (Exception problem) { Console.Error.WriteLine("No se ha completado la accion: " + problem.Message + "\nTu instalacion y WTF no se borran. Si hay un fallo de instalacion se intenta recuperar la copia anterior."); return 1; }
            finally { if (interactive) { Console.WriteLine("Pulsa Enter para cerrar."); try { Console.ReadLine(); } catch { } } }
        }
    }
}
