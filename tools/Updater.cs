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
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using RutaXPInstaller;

namespace RutaXPUpdater
{
    public sealed class ReleaseInfo
    {
        public string Tag, Version, ArchiveName, ArchiveUrl, ChecksumsUrl;
        public long ArchiveSize;
        public readonly Dictionary<string, DeltaAsset> Deltas = new Dictionary<string, DeltaAsset>(StringComparer.Ordinal);
    }
    public sealed class DeltaAsset { public string Name, Url; public long Size; }
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
                Match delta = Regex.Match(name ?? "", @"^RutaXP-([0-9.]+)-a-([0-9.]+)-delta\.zip$");
                if (delta.Success && (delta.Groups[2].Value != version || CompareVersions(delta.Groups[1].Value, version) >= 0))
                    throw new IOException("Version de actualizacion incremental no valida.");
                if (name != result.ArchiveName && name != "SHA256SUMS.txt" && !delta.Success) continue;
                if (!seen.Add(name)) throw new IOException("El release contiene archivos duplicados.");
                string url = Text(asset, "browser_download_url");
                ValidateAssetUrl(url, tag, name);
                object size;
                long length;
                if (!asset.TryGetValue("size", out size) || !long.TryParse(Convert.ToString(size, System.Globalization.CultureInfo.InvariantCulture), out length)
                    || length <= 0 || length > (name == "SHA256SUMS.txt" ? 1024 * 1024 : MaxArchiveBytes))
                    throw new IOException("El archivo publicado supera los limites permitidos.");
                if (name == result.ArchiveName) { result.ArchiveUrl = url; result.ArchiveSize = length; }
                else if (delta.Success) result.Deltas.Add(delta.Groups[1].Value, new DeltaAsset { Name = name, Url = url, Size = length });
                else result.ChecksumsUrl = url;
            }
            if (result.ArchiveUrl == null || result.ChecksumsUrl == null) throw new IOException("El release necesita el ZIP del addon y SHA256SUMS.txt.");
            return result;
        }
        public static string Hash(byte[] data)
        {
            using (SHA256 hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
        }
        static string PublishedHash(string sums, string name)
        {
            if (sums == null || sums.Length > 1024 * 1024)
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
            if (expected == null) throw new IOException("Falta el SHA256 del ZIP publicado.");
            return expected;
        }
        public static void VerifyArchiveHash(byte[] archive, string sums, string name)
        {
            if (archive == null || archive.LongLength == 0 || archive.LongLength > MaxArchiveBytes)
                throw new IOException("Descarga vacia o demasiado grande.");
            if (Hash(archive) != PublishedHash(sums, name)) throw new IOException("El SHA256 del ZIP no coincide; no se ha instalado nada.");
        }
        static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);

        static byte[] ReadDeltaEntry(IDictionary<string, ZipArchiveEntry> entries, string name, long limit)
        {
            ZipArchiveEntry entry;
            if (!entries.TryGetValue(name, out entry) || entry.Length > limit)
                throw new IOException("Falta un archivo del paquete incremental o supera el limite: " + name);
            entries.Remove(name);
            using (Stream input = entry.Open())
            using (BinaryReader reader = new BinaryReader(input))
            {
                byte[] data = reader.ReadBytes(checked((int)entry.Length));
                if (data.LongLength != entry.Length || input.ReadByte() != -1) throw new IOException("Longitud incorrecta: " + name);
                return data;
            }
        }
        static bool ValidDeltaPath(string path)
        {
            if (path.Length == 0 || path.Length > 240 || path.Contains("\\")) return false;
            foreach (string part in path.Split('/'))
                if (part.Length == 0 || part.EndsWith(".") || part.EndsWith(" ") || part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
                    || Regex.IsMatch(part, @"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", RegexOptions.IgnoreCase)) return false;
            return true;
        }
        static string DeltaHash(string text)
        {
            if (text == "-") return null;
            if (!Regex.IsMatch(text, "^[a-f0-9]{64}$")) throw new IOException("Huella de archivo incremental no valida.");
            return text;
        }
        static void CheckDeltaToc(byte[] data, string version)
        {
            if (data == null || data.Length > 1024 * 1024) throw new IOException("Falta el TOC de la actualizacion incremental.");
            var matches = Regex.Matches(StrictUtf8.GetString(data).TrimStart('\uFEFF'), @"^## Version:[ \t]*(\S+)[ \t]*\r?$", RegexOptions.Multiline);
            if (matches.Count != 1 || matches[0].Groups[1].Value != version)
                throw new IOException("La version del TOC no coincide con la actualizacion incremental.");
        }
        static List<IncrementalChange> ReadDelta(byte[] data, string from, string to)
        {
            using (MemoryStream stream = new MemoryStream(data, false))
            using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read))
            {
                if (zip.Entries.Count < 3 || zip.Entries.Count > MaxEntries) throw new IOException("Numero de entradas incremental no valido.");
                var entries = new Dictionary<string, ZipArchiveEntry>(StringComparer.Ordinal);
                long expanded = 0;
                foreach (ZipArchiveEntry entry in zip.Entries)
                {
                    if (!ValidDeltaPath(entry.FullName) || entries.ContainsKey(entry.FullName)
                        || ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000
                        || (entry.ExternalAttributes & (int)FileAttributes.ReparsePoint) != 0
                        || entry.Length < 0 || entry.Length > MaxEntryBytes || entry.Length > MaxArchiveBytes - expanded)
                        throw new IOException("Entrada incremental no valida: " + entry.FullName);
                    expanded += entry.Length;
                    entries.Add(entry.FullName, entry);
                }
                var changes = new List<IncrementalChange>();
                var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                using (var descriptor = new StringReader(StrictUtf8.GetString(ReadDeltaEntry(entries, "delta.tsv", 4 * 1024 * 1024))))
                {
                    if (descriptor.ReadLine() != "RutaXP-delta-v1\t" + from + "\t" + to)
                        throw new IOException("El paquete incremental corresponde a otra version.");
                    string row;
                    while ((row = descriptor.ReadLine()) != null)
                    {
                        string[] cells = row.Split('\t');
                        if (cells.Length != 3 || !ValidDeltaPath(cells[2]) || !paths.Add(cells[2]) || paths.Count > MaxEntries)
                            throw new IOException("Entrada duplicada o no valida en delta.tsv.");
                        var change = new IncrementalChange { Path = cells[2], OldHash = DeltaHash(cells[0]), NewHash = DeltaHash(cells[1]) };
                        if (change.OldHash == change.NewHash) throw new IOException("Cambio incremental vacio: " + change.Path);
                        if (change.NewHash != null)
                        {
                            change.Data = ReadDeltaEntry(entries, "files/" + change.Path, MaxEntryBytes);
                            if (Hash(change.Data) != change.NewHash) throw new IOException("Contenido incremental incorrecto: " + change.Path);
                        }
                        if (change.Path == "RutaXP.toc")
                        {
                            change.OldData = ReadDeltaEntry(entries, "old/RutaXP.toc", 1024 * 1024);
                            if (Hash(change.OldData) != change.OldHash) throw new IOException("TOC de origen incremental incorrecto.");
                            CheckDeltaToc(change.OldData, from);
                            CheckDeltaToc(change.Data, to);
                        }
                        changes.Add(change);
                    }
                }
                if (entries.Count != 0 || !changes.Exists(delegate(IncrementalChange c) { return c.Path == "RutaXP.toc"; }))
                    throw new IOException("El contenido del paquete incremental no coincide con el descriptor.");
                return changes;
            }
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
        internal static bool CompleteSuite(string addons, string version)
        {
            string root = Path.Combine(addons, "RutaXP"), manifest = Path.Combine(root, "manifest.sha256");
            foreach (string entry in new[] { @"RutaXP\RutaXP.toc", @"RutaXP\manifest.sha256", @"RutaXP\Leveling.lua",
                @"RutaXP\Modules\OpenMap\Core.lua", @"RutaXP\Modules\ForeverDungeonJournal\Core\Journal.lua",
                @"LFGForever\LFGForever.toc", @"LFGForeverLanguageSpanish\LFGForeverLanguageSpanish.toc", @"LFGForeverLanguageSpanish\Spanish.lua" })
            {
                string path = Path.Combine(addons, entry);
                InstallerCore.RejectLinks(path);
                if (!File.Exists(path)) return false;
            }
            if (!HasJourneyPresentation(root)) return false;
            string tocLine = Hash(File.ReadAllBytes(Path.Combine(root, "RutaXP.toc"))) + "  RutaXP.toc";
            using (var reader = File.OpenText(manifest))
            {
                if (reader.ReadLine() != "# RutaXP " + version) return false;
                string row;
                while ((row = reader.ReadLine()) != null)
                    if (row == tocLine) return true;
            }
            return false;
        }
        internal static UpdateResult ApplyDelta(string addons, byte[] archive, string from, string to, Action guard)
        {
            if (CompareVersions(from, to) >= 0 || archive == null || archive.LongLength == 0 || archive.LongLength > MaxArchiveBytes)
                throw new IOException("Version o tamano de actualizacion incremental no valido.");
            List<IncrementalChange> changes = ReadDelta(archive, from, to);
            string root = Path.GetDirectoryName(Path.GetDirectoryName(addons));
            string backup = IncrementalInstall.Apply(root, changes, guard);
            return new UpdateResult { Version = to, Target = Path.Combine(addons, "RutaXP"), Backup = backup, Changed = true };
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
            VerifyArchiveHash(archive, sums, release.ArchiveName);
            ExtractVerifiedPackage(archive, release, destination);
        }
        static void ExtractVerifiedPackage(byte[] archive, ReleaseInfo release, string destination)
        {
            if (archive.LongLength != release.ArchiveSize) throw new IOException("El tamano del ZIP no coincide con el publicado.");
            ValidateArchive(archive);
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
        static byte[] ReadMatchingBundle(Func<Stream> openBundled, long size, string expected)
        {
            if (openBundled == null) return null;
            try
            {
                using (Stream stream = openBundled())
                {
                    if (stream == null || !stream.CanRead || stream.CanSeek && stream.Length - stream.Position != size) return null;
                    using (BinaryReader reader = new BinaryReader(stream))
                    {
                        byte[] bytes = reader.ReadBytes((int)size);
                        if (bytes.LongLength == size && stream.ReadByte() == -1 && Hash(bytes) == expected) return bytes;
                    }
                }
            }
            catch (IOException) { /* The release download is still available. */ }
            return null;
        }
        public static UpdateResult Update(string client, bool repair, string versionFloor,
            Func<string, long, byte[]> fetch, Func<bool> running, Action beforeActivate)
        {
            return Update(client, repair, versionFloor, fetch, running, beforeActivate, null);
        }
        public static UpdateResult Update(string client, bool repair, string versionFloor,
            Func<string, long, byte[]> fetch, Func<bool> running, Action beforeActivate, Action<ProcessStartInfo> suiteSetup)
        {
            return Update(client, repair, versionFloor, fetch, running, beforeActivate, suiteSetup, null);
        }
        public static UpdateResult Update(string client, bool repair, string versionFloor,
            Func<string, long, byte[]> fetch, Func<bool> running, Action beforeActivate, Action<ProcessStartInfo> suiteSetup,
            Func<Stream> openBundled)
        {
            if (string.IsNullOrWhiteSpace(versionFloor)) versionFloor = null;
            string addons = ResolveClient(client); RequireClosed(running);
            string target = Path.Combine(addons, "RutaXP");
            if (suiteSetup == null) InstallerCore.RequirePublicTarget(target);
            ReleaseInfo release = ParseRelease(Encoding.UTF8.GetString(Download(fetch, LatestUrl, 1024 * 1024)));
            string gameRoot = Path.GetDirectoryName(Path.GetDirectoryName(addons));
            Action guard = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
            bool fullRequired = false;
            if (suiteSetup != null)
            {
                try { IncrementalInstall.Recover(gameRoot, delegate { RequireClosed(running); }); }
                catch (IncrementalBaseMismatchException) { fullRequired = true; }
            }
            string installed = ReadInstalledVersion(addons);
            if (installed != null && CompareVersions(release.Version, installed) < 0
                || versionFloor != null && CompareVersions(release.Version, versionFloor) < 0)
                throw new IOException("GitHub ofrece una version anterior a la ya verificada. No se permite bajar de version con Actualizar.");
            if (suiteSetup == null && !repair && installed == release.Version)
            {
                bool valid = false;
                try { InstallerCore.Manifest(target); valid = true; } catch (IOException) { }
                if (valid) { RequireClosed(running); return new UpdateResult { Version = release.Version, Target = target, LatestVerified = true }; }
            }
            bool eligibleSuite = suiteSetup != null && !repair && !fullRequired && installed != null && CompleteSuite(addons, installed);
            if (eligibleSuite && installed == release.Version)
                return new UpdateResult { Version = installed, Target = target, LatestVerified = true };
            string sums = Encoding.UTF8.GetString(Download(fetch, release.ChecksumsUrl, 1024 * 1024));
            DeltaAsset delta;
            if (eligibleSuite && release.Deltas.TryGetValue(installed, out delta))
            {
                byte[] patch = Download(fetch, delta.Url, delta.Size);
                if (patch.LongLength != delta.Size) throw new IOException("Tamano de la actualizacion incremental incorrecto.");
                VerifyArchiveHash(patch, sums, delta.Name);
                try
                {
                    UpdateResult patched = ApplyDelta(addons, patch, installed, release.Version, guard);
                    patched.LatestVerified = true;
                    return patched;
                }
                catch (IncrementalBaseMismatchException)
                {
                    // An older launcher or a constructor can finish this release during the download.
                    try
                    {
                        IncrementalInstall.Recover(gameRoot, delegate { RequireClosed(running); });
                        if (ReadInstalledVersion(addons) == release.Version && CompleteSuite(addons, release.Version))
                            return new UpdateResult { Version = release.Version, Target = target, LatestVerified = true };
                    }
                    catch (IncrementalBaseMismatchException) { /* The full constructor owns the pending transaction. */ }
                    fullRequired = true;
                    Console.WriteLine("La instalacion local requiere el paquete completo.");
                }
            }
            string expected = PublishedHash(sums, release.ArchiveName);
            byte[] archive = repair ? null : ReadMatchingBundle(openBundled, release.ArchiveSize, expected);
            if (archive == null)
            {
                archive = Download(fetch, release.ArchiveUrl, MaxArchiveBytes);
                if (Hash(archive) != expected) throw new IOException("El SHA256 del ZIP no coincide; no se ha instalado nada.");
            }
            string temp = Temporary();
            try
            {
                ExtractVerifiedPackage(archive, release, temp);
                UpdateResult result = ActivatePackage(temp, addons, release.Version, running, beforeActivate, suiteSetup,
                    (repair || fullRequired) && CompareVersions(release.Version, "1.2.12") >= 0);
                result.LatestVerified = true;
                return result;
            }
            finally { try { RemoveTemporary(temp); } catch (IOException cleanup) { Console.Error.WriteLine("Temporal conservado: " + cleanup.Message); } }
        }
        public static UpdateResult InstallBundled(Stream stream, string client, Func<bool> running, Action beforeActivate)
        {
            return InstallBundled(stream, client, running, beforeActivate, null);
        }
        public static UpdateResult InstallBundled(Stream stream, string client, Func<bool> running, Action beforeActivate, Action<ProcessStartInfo> suiteSetup)
        {
            string addons = ResolveClient(client); RequireClosed(running);
            if (suiteSetup == null) InstallerCore.RequirePublicTarget(Path.Combine(addons, "RutaXP"));
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
                return ActivatePackage(temp, addons, version, running, beforeActivate, suiteSetup);
            }
            finally { try { RemoveTemporary(temp); } catch (IOException cleanup) { Console.Error.WriteLine("Temporal conservado: " + cleanup.Message); } }
        }
        static bool HasJourneyPresentation(string target)
        {
            string toc = File.ReadAllText(Path.Combine(target, "RutaXP.toc"));
            if (!Regex.IsMatch(toc, @"^##[ \t]*X-RutaXP-Journey-UI[ \t]*:[ \t]*\S+", RegexOptions.IgnoreCase | RegexOptions.Multiline))
                return false;
            HashSet<string> entries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string line in toc.Split('\n')) entries.Add(line.Trim().Replace('\\', '/'));
            foreach (string script in new[] { "Modules/Journey/ui/UI.lua", "Modules/Journey/ui/TaskDetailContainers.lua", "Modules/Journey/lib/TomCats/Arrows.lua" })
            {
                string path = Path.Combine(target, script);
                InstallerCore.RejectLinks(path);
                if (!entries.Contains(script) || !File.Exists(path)) return false;
            }
            return true;
        }
        static UpdateResult ActivatePackage(string verified, string addons, string version,
            Func<bool> running, Action beforeActivate, Action<ProcessStartInfo> suiteSetup, bool forceFull = false)
        {
            RequireClosed(running);
            string target = Path.Combine(addons, "RutaXP");
            string installedVersion = ReadInstalledVersion(addons);
            if (installedVersion != null && CompareVersions(installedVersion, version) > 0)
                throw new IOException("Otro instalador ya aplico una version mas reciente. Vuelve a consultar la ultima version.");
            var result = new UpdateResult { Target = target, Version = version };
            Action guardedActivation = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
            if (suiteSetup != null)
            {
                // The suite's own transaction backs up the current addons before activating the replacement.
                // Leave those sources untouched and run the fixed helper from the verified package.
                string executable = Path.Combine(verified, "Instalar_Suite_RutaXP.exe");
                InstallerCore.RejectLinks(executable);
                if (!File.Exists(executable)) throw new IOException("El paquete no contiene el instalador de la suite.");
                var helper = new ProcessStartInfo(executable, "--addons \"" + addons + "\"" + (forceFull ? " --full" : ""))
                    { WorkingDirectory = verified, UseShellExecute = false, CreateNoWindow = true,
                      RedirectStandardError = true, RedirectStandardOutput = true };
                guardedActivation();
                suiteSetup(helper);
                if (ReadInstalledVersion(addons) != version || !InstallerCore.IsEmbeddedSuite(target) || !HasJourneyPresentation(target)
                    || !Directory.Exists(Path.Combine(target, "Modules", "OpenMap"))
                    || !Directory.Exists(Path.Combine(target, "Modules", "ForeverDungeonJournal"))
                    || (!File.Exists(Path.Combine(target, "Leveling.lua")) &&
                        !Directory.Exists(Path.Combine(target, "Modules", "RXPGuides"))))
                    throw new IOException("No se ha encontrado la suite completa de la version esperada en el cliente elegido.");
            }
            else
            {
                InstallResult installed = InstallerCore.InstallFromDirectory(verified, addons, null, guardedActivation);
                result.Backup = installed.Backup;
            }
            result.Changed = true;
            return result;
        }
        public static List<BackupInfo> Backups(string client)
        {
            string addons = ResolveClient(client); List<BackupInfo> valid = new List<BackupInfo>();
            if (!Directory.Exists(addons)) return valid;
            // Older public installers kept their backups inside AddOns.
            foreach (string folder in new string[] { InstallerCore.BackupStore(addons), addons })
            {
                if (!Directory.Exists(folder)) continue;
                foreach (string path in Directory.GetDirectories(folder, ".RutaXP.backup.*"))
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
            }
            valid.Sort(delegate(BackupInfo a, BackupInfo b) { int n = b.Date.CompareTo(a.Date); return n == 0 ? StringComparer.Ordinal.Compare(a.Name, b.Name) : n; });
            return valid;
        }
        public static InstallResult Restore(string client, string name, Func<bool> running, Action beforeActivate)
        {
            string addons = ResolveClient(client); RequireClosed(running);
            InstallerCore.RequirePublicTarget(Path.Combine(addons, "RutaXP"));
            if (string.IsNullOrWhiteSpace(name)) name = null;
            if (name != null && !Regex.IsMatch(name, @"^\.RutaXP\.backup\.[a-f0-9]{32}$")) throw new IOException("Selecciona una copia anterior de este mismo cliente.");
            List<BackupInfo> copies = Backups(addons); BackupInfo chosen = null;
            foreach (BackupInfo copy in copies) if (name == null || name == copy.Name) { chosen = copy; break; }
            if (chosen == null) throw new IOException("No hay una copia anterior valida para restaurar.");
            InstallerCore.Manifest(chosen.Path); RequireClosed(running);
            Action guardedActivation = delegate { RequireClosed(running); if (beforeActivate != null) beforeActivate(); RequireClosed(running); };
            return InstallerCore.InstallFromDirectory(chosen.Path, addons, null, guardedActivation, true);
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

    // Local entry point bundled by the suite constructor for older launchers.
    public static class DeltaBridge
    {
        public static int Main(string[] args)
        {
            return Run(args, Program.WowRunning);
        }
        internal static int Run(string[] args, Func<bool> running)
        {
            try
            {
                if (args.Length != 4) throw new IOException("Se necesitan AddOns, el paquete incremental, la version anterior y la nueva.");
                string addons = UpdaterCore.ResolveClient(args[0]);
                string from = UpdaterCore.StableVersion(args[2]), to = UpdaterCore.StableVersion(args[3]);
                if (UpdaterCore.CompareVersions(from, to) >= 0) throw new IOException("Versiones incrementales no validas.");
                Action guard = delegate { UpdaterCore.RequireClosed(running); };
                guard();
                IncrementalInstall.Recover(Path.GetDirectoryName(Path.GetDirectoryName(addons)), guard);
                if (UpdaterCore.ReadInstalledVersion(addons) != from || !UpdaterCore.CompleteSuite(addons, from)) return 3;
                string file = Path.GetFullPath(args[1]);
                InstallerCore.RejectLinks(file);
                byte[] patch;
                using (FileStream stream = File.OpenRead(file))
                using (BinaryReader reader = new BinaryReader(stream))
                {
                    if (stream.Length == 0 || stream.Length > UpdaterCore.MaxArchiveBytes) throw new IOException("Paquete incremental demasiado grande o vacio.");
                    patch = reader.ReadBytes((int)stream.Length);
                }
                UpdaterCore.ApplyDelta(addons, patch, from, to, guard);
                return 0;
            }
            catch (IncrementalBaseMismatchException) { return 3; }
            catch (Exception ex) { Console.Error.WriteLine("No se ha completado la actualizacion incremental: " + ex.Message); return 1; }
        }
    }

    public static class Program
    {
        internal static Mutex TryBeginInstallation(string addons)
        {
            string key = UpdaterCore.Hash(Encoding.UTF8.GetBytes(InstallerCore.Normalize(addons).ToUpperInvariant()));
            var mutex = new Mutex(false, @"Local\RutaXP-install-" + key);
            try
            {
                if (mutex.WaitOne(0)) return mutex;
            }
            catch (AbandonedMutexException) { return mutex; }
            catch { mutex.Dispose(); throw; }
            mutex.Dispose();
            return null;
        }
        internal static bool WowRunning()
        {
            foreach (string name in new string[] { "Wow", "WowB", "WowClassicB", "WowClassic", "WowForever", "Wow-64", "WorldOfWarcraft" })
                foreach (Process process in Process.GetProcessesByName(name)) { process.Dispose(); return true; }
            return false;
        }
        public static string SelectClient(string settings, string action, Func<List<string>> discover, Func<List<string>, string> choose)
        {
            if (action != "--choose-client")
            {
                try
                {
                    string saved = ClientSettings.Load(settings, "client");
                    if (!string.IsNullOrWhiteSpace(saved)) return UpdaterCore.ResolveClient(saved);
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
                catch (ArgumentException) { }
                catch (NotSupportedException) { }
            }
            List<string> choices = discover();
            if (action == "--update" && choices.Count == 1) return choices[0];
            return choose(choices);
        }
        static string ChooseClient(List<string> choices)
        {
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
            Console.WriteLine("\nRUTAXP: INSTALACION, ACTUALIZACION Y RECUPERACION\n1. Instalar o actualizar la suite desde GitHub\n2. Reparar (descargar de nuevo)\n3. Restaurar copia del antiguo paquete publico\n4. Elegir cliente\n5. Instalar la suite con el constructor incluido\n0. Salir");
            Console.Write("Opcion (Enter = 1): "); string value = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(value)) value = "1";
            switch (value) { case "1": return "--update"; case "2": return "--repair"; case "3": return "--restore"; case "4": return "--choose-client"; case "5": return "--install-bundled"; case "0": return null; default: throw new IOException("Opcion no valida."); }
        }
        static void InstallSuite(ProcessStartInfo helper)
        {
            Console.WriteLine("Abriendo el instalador de la suite...");
            helper.StandardOutputEncoding = Encoding.UTF8;
            helper.StandardErrorEncoding = Encoding.UTF8;
            helper.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            using (Process setup = Process.Start(helper))
            {
                if (setup == null) throw new IOException("No se ha podido abrir el instalador de la suite.");
                setup.OutputDataReceived += delegate(object sender, DataReceivedEventArgs line) { if (line.Data != null) Console.WriteLine(line.Data); };
                setup.BeginOutputReadLine();
                string detail = setup.StandardError.ReadToEnd().Trim();
                setup.WaitForExit();
                if (setup.ExitCode != 0) throw new IOException(detail.Length > 0 ? detail : "El instalador de la suite ha terminado con un error.");
            }
        }
        static Stream OpenBundled()
        {
            return Assembly.GetExecutingAssembly().GetManifestResourceStream("RutaXPInstaller.payload.zip");
        }

        static byte[] FetchReleaseFile(string url, long maximum)
        {
            if (url.EndsWith("-addon.zip", StringComparison.Ordinal))
                Console.WriteLine("Descargando el paquete de la version publicada...");
            else if (url.EndsWith("-delta.zip", StringComparison.Ordinal))
                Console.WriteLine("Descargando solo los archivos que han cambiado...");
            return HttpDownloads.Fetch(url, maximum);
        }
        [STAThread]
        public static int Main(string[] args)
        {
            bool interactive = args.Length == 0;
            Mutex installation = null;
            try
            {
                Console.OutputEncoding = Encoding.UTF8; Console.Title = "RutaXP: instalar y actualizar";
                string action = null, client = null, backup = null;
                for (int i = 0; i < args.Length; i++)
                {
                    string arg = args[i];
                    if (arg == "--help") { Console.WriteLine("RutaXP: --update | --repair | --restore [nombre-copia] | --install-bundled | --choose-client, y --client \"ruta\". Sin argumentos: menu. Las opciones de instalacion sustituyen la version anterior con WoW cerrado y conservan una copia."); return 0; }
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
                string addons = client == null ? SelectClient(settings, action, InstallerCore.FindWoWAddonFolders, ChooseClient) : UpdaterCore.ResolveClient(client);
                Console.WriteLine("Cliente: " + Path.GetDirectoryName(Path.GetDirectoryName(addons)));
                if (action != "--choose-client")
                {
                    installation = TryBeginInstallation(addons);
                    if (installation == null)
                    {
                        Console.WriteLine("Ya hay otra instalacion de RutaXP en curso para este cliente. Sigue el progreso en la primera ventana.");
                        return 0;
                    }
                }
                ClientSettings.Save(settings, "client", addons);
                if (action == "--choose-client") { Console.WriteLine("Cliente recordado. Cada ordenador guarda su propia ruta."); return 0; }
                if (action == "--install-bundled")
                {
                    UpdateResult bundled;
                    using (Stream stream = OpenBundled())
                        bundled = UpdaterCore.InstallBundled(stream, addons, WowRunning, null, InstallSuite);
                    Console.WriteLine("Suite RutaXP " + bundled.Version + " instalada y verificada en " + bundled.Target + ".");
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
                UpdateResult result = UpdaterCore.Update(addons, action == "--repair", floor, FetchReleaseFile, WowRunning, null, InstallSuite, OpenBundled);
                ClientSettings.Save(settings, "latest", result.Version);
                Console.WriteLine(result.Changed ? "Suite RutaXP " + result.Version + " instalada y verificada en " + result.Target + "."
                    : "RutaXP " + result.Version + " ya esta al dia.");
                return 0;
            }
            catch (Exception problem) { Console.Error.WriteLine("No se ha completado la accion: " + problem.Message + "\nTu instalacion y WTF no se borran. Si hay un fallo de instalacion se intenta recuperar la copia anterior."); return 1; }
            finally
            {
                if (installation != null) { installation.ReleaseMutex(); installation.Dispose(); }
                if (interactive) { Console.WriteLine("Pulsa Enter para cerrar."); try { Console.ReadLine(); } catch { } }
            }
        }
    }
}
