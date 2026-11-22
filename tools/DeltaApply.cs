using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using RutaXPInstaller;

namespace RutaXPUpdater
{
    public sealed class IncrementalChange
    {
        public string Path, OldHash, NewHash;
        public byte[] OldData, Data;
    }

    public sealed class IncrementalBaseMismatchException : IOException
    {
        public IncrementalBaseMismatchException(string message) : base(message) {}
    }

    public static class IncrementalInstall
    {
        const string Prefix = "Interface/AddOns/RutaXP/";
        const string PlanType = "RutaXP-native-delta-v1";
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        static readonly StringComparer Paths = StringComparer.OrdinalIgnoreCase;
        static readonly Regex UnsafePart = new Regex(@"[. ]$|[:*?""<>|\x00-\x1f]|^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", RegexOptions.IgnoreCase);
        static readonly Regex ManifestRow = new Regex(@"^([0-9a-f]{64})  (.+)$");
        static readonly Regex MergedHeader = new Regex(@"^## (SavedVariables|SavedVariablesPerCharacter|OptionalDeps):");

        public sealed class Row { public string dest; public bool old, add; public string[] sources = new string[0]; }
        public sealed class Plan { public string type; public List<Row> rows; }

        static void Base(bool valid, string path)
        {
            if (!valid) throw new IncrementalBaseMismatchException("La copia instalada no coincide con la base de la actualizacion: " + path);
        }

        static void CheckName(string name, bool allowManifest)
        {
            if (String.IsNullOrEmpty(name) || name.Contains("\\"))
                throw new InvalidDataException("Ruta de parche no valida.");
            foreach (string part in name.Split('/'))
                if (part.Length == 0 || UnsafePart.IsMatch(part))
                    throw new InvalidDataException("Ruta de parche no valida: " + name);
            string top = name.Split('/')[0];
            if (Paths.Equals(top, "Modules") || Paths.Equals(top, "Source") || Paths.Equals(top, "Bindings.xml") ||
                (Paths.Equals(top, "manifest.sha256") && !(allowManifest && name == "manifest.sha256")))
                throw new InvalidDataException("El archivo no pertenece al parche nativo: " + name);
        }

        static string Safe(string root, string path)
        {
            string result = Path.Combine(root, path.Replace('/', Path.DirectorySeparatorChar));
            InstallerCore.RejectLinks(result);
            return result;
        }

        static string Hex(byte[] hash) { return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant(); }
        static string Hash(byte[] data) { using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(data)); }
        static string FileHash(string path)
        {
            using (var sha = SHA256.Create())
            using (var file = File.OpenRead(path)) return Hex(sha.ComputeHash(file));
        }
        static string[] Lines(byte[] data)
        {
            return Utf8.GetString(data).TrimStart('\uFEFF').Replace("\r\n", "\n").Trim().Split('\n');
        }
        static string[] LoadTemplate(IncrementalChange toc, bool old)
        {
            byte[] data = old ? toc.OldData : toc.Data;
            if (data == null || Hash(data) != (old ? toc.OldHash : toc.NewHash))
                throw new InvalidDataException("El TOC del parche no coincide con su SHA256.");
            return Lines(data);
        }

        // write_suite prefixes metadata from the installed modules, expands three native
        // dependency/settings headers, then appends their load order after the native TOC.
        static byte[] ComposeToc(byte[] current, IncrementalChange toc, out string version)
        {
            string[] actual = Lines(current), oldBase = LoadTemplate(toc, true), next = LoadTemplate(toc, false);
            int start = Array.IndexOf(actual, oldBase[0]);
            Base(start >= 0 && start + oldBase.Length < actual.Length, "RutaXP.toc");
            var headers = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int i = 0; i < oldBase.Length; ++i)
            {
                string line = oldBase[i], live = actual[start + i];
                Match merged = MergedHeader.Match(line);
                if (merged.Success)
                {
                    Base(live.StartsWith(merged.Value, StringComparison.Ordinal), "RutaXP.toc");
                    headers.Add(line, live);
                } else Base(live == line, "RutaXP.toc");
            }
            int tail = start + oldBase.Length;
            Base(actual[tail] == "" && Array.Exists(actual, s => s.StartsWith("## X-RutaXP-Embedded: ", StringComparison.Ordinal)), "RutaXP.toc");
            for (int i = tail + 1; i < actual.Length; ++i)
                Base(actual[i].StartsWith("Modules/", StringComparison.Ordinal), "RutaXP.toc");
            int expanded = 0;
            version = null;
            for (int i = 0; i < next.Length; ++i)
            {
                if (next[i].StartsWith("## Version: ", StringComparison.Ordinal))
                    version = next[i].Substring("## Version: ".Length);
                if (!MergedHeader.IsMatch(next[i])) continue;
                string live;
                Base(headers.TryGetValue(next[i], out live), "declaraciones de la suite en RutaXP.toc");
                next[i] = live;
                ++expanded;
            }
            Base(expanded == headers.Count && version != null, "RutaXP.toc");
            var lines = new List<string>(actual);
            lines.RemoveRange(start, oldBase.Length);
            lines.InsertRange(start, next);
            return Utf8.GetBytes(String.Join("\n", lines) + "\n");
        }

        static List<IncrementalChange> Prepare(string addon, IList<IncrementalChange> changes)
        {
            string manifest = Safe(addon, "manifest.sha256");
            Base(File.Exists(manifest), manifest);
            byte[] previous = File.ReadAllBytes(manifest);
            var entries = new SortedDictionary<string, string>(StringComparer.Ordinal);
            var names = new HashSet<string>(Paths);
            foreach (string line in Lines(previous))
            {
                if (line.StartsWith("#") || line == "") continue;
                Match row = ManifestRow.Match(line);
                Base(row.Success && names.Add(row.Groups[2].Value), "manifest.sha256");
                entries.Add(row.Groups[2].Value, row.Groups[1].Value);
            }
            var seen = new HashSet<string>(Paths);
            var work = new List<IncrementalChange>();
            string version = null;
            foreach (IncrementalChange c in changes)
            {
                CheckName(c.Path, false);
                if (!seen.Add(c.Path) || (c.NewHash == null && c.OldHash == null) ||
                    (c.Data == null) != (c.NewHash == null) || (c.Data != null && Hash(c.Data) != c.NewHash))
                    throw new InvalidDataException("Archivo repetido o SHA256 del parche incorrecto: " + c.Path);
                string file = Safe(addon, c.Path);
                string expected;
                bool tracked = entries.TryGetValue(c.Path, out expected);
                bool isToc = c.Path == "RutaXP.toc";
                Base(tracked == (c.OldHash != null) && File.Exists(file) == tracked && !Directory.Exists(file), c.Path);
                if (tracked)
                    Base((isToc || c.OldHash == expected) && FileHash(file) == expected, c.Path);
                else Base(!names.Contains(c.Path), c.Path);
                byte[] result = isToc ? ComposeToc(File.ReadAllBytes(file), c, out version) : c.Data;
                string finalHash = (isToc ? Hash(result) : c.NewHash);
                if (expected == finalHash) continue;
                if (result == null) entries.Remove(c.Path); else entries[c.Path] = finalHash;
                work.Add(new IncrementalChange { Path = c.Path, OldHash = expected, Data = result, NewHash = finalHash });
            }
            if (version == null) throw new InvalidDataException("Falta el cambio de version del TOC.");
            var text = new StringBuilder("# RutaXP " + version + "\n");
            foreach (var entry in entries)
                text.Append(entry.Value).Append("  ").Append(entry.Key).Append('\n');
            work.Add(new IncrementalChange { Path = "manifest.sha256", OldHash = Hash(previous), Data = Utf8.GetBytes(text.ToString()) });
            return work;
        }

        static string Store(string game)
        {
            if (!InstallerCore.IsForeverClient(game)) throw new IOException("Selecciona el cliente de WoW Forever.");
            return InstallerCore.BackupStore(Path.Combine(game, "Interface", "AddOns"));
        }
        static bool SupportsReplace(string path)
        {
            string root = Path.GetPathRoot(path);
            if (!Regex.IsMatch(root, @"^[a-zA-Z]:")) return false;
            string format = new DriveInfo(root).DriveFormat;
            return format == "NTFS" || format == "ReFS";
        }
        static FileStream Lock(string store)
        {
            Directory.CreateDirectory(store);
            return File.Open(Safe(store, "install.lock"), FileMode.OpenOrCreate, FileAccess.Write, FileShare.None);
        }
        static void Durable(string path, byte[] data)
        {
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            { stream.Write(data, 0, data.Length); stream.Flush(true); }
        }
        static void Mark(string tx, string name)
        {
            string path = Safe(tx, name);
            if (!File.Exists(path)) Durable(path, new byte[0]);
        }
        static void WritePlan(string tx, Plan plan, List<IncrementalChange> work, Action guard)
        {
            Directory.CreateDirectory(Safe(tx, "new"));
            try
            {
                Directory.CreateDirectory(Safe(tx, "prior"));
                for (int i = 0; i < work.Count; ++i)
                {
                    var c = work[i];
                    plan.rows.Add(new Row { dest = Prefix + c.Path, old = c.OldHash != null, add = c.Data != null });
                    if (c.Data != null) Durable(Safe(tx, "new/" + i), c.Data);
                }
                if (guard != null) guard();
                Durable(Safe(tx, "plan.tmp"), Utf8.GetBytes(new JavaScriptSerializer().Serialize(plan)));
                File.Move(Safe(tx, "plan.tmp"), Safe(tx, "plan.json"));
            }
            catch
            {
                // No live file is moved until plan.json exists. Remove only this staging attempt.
                File.Delete(Safe(tx, "plan.tmp"));
                for (int i = 0; i < plan.rows.Count; ++i) File.Delete(Safe(tx, "new/" + i));
                if (Directory.Exists(Safe(tx, "prior"))) Directory.Delete(Safe(tx, "prior"));
                Directory.Delete(Safe(tx, "new"));
                Directory.Delete(tx);
                throw;
            }
        }
        static string Target(string game, Row row)
        {
            if (!row.dest.StartsWith(Prefix, StringComparison.Ordinal)) throw new InvalidDataException("Destino fuera de RutaXP.");
            CheckName(row.dest.Substring(Prefix.Length), true);
            return Safe(game, row.dest);
        }
        static void Rollback(string game, string tx, List<Row> rows)
        {
            Mark(tx, "restoring");
            Directory.CreateDirectory(Safe(tx, "after"));
            for (int i = rows.Count - 1; i >= 0; --i)
            {
                Row row = rows[i];
                string target = Target(game, row), prior = Safe(tx, "prior/" + i);
                if (!File.Exists(prior) && (row.old || !row.add || File.Exists(Safe(tx, "new/" + i)))) continue;
                if (File.Exists(target)) File.Move(target, Safe(tx, "after/" + i));
                if (File.Exists(prior)) File.Move(prior, target);
            }
            Mark(tx, "restored");
        }

        static void RecoverLocked(string game, string store, Action guard)
        {
            foreach (string tx in Directory.GetDirectories(store))
            {
                if (!Regex.IsMatch(Path.GetFileName(tx), @"^\d{17}-[0-9a-f]{32}$")) continue;
                if (File.Exists(Safe(tx, "restored")) || (File.Exists(Safe(tx, "committed")) && !File.Exists(Safe(tx, "restoring")))) continue;
                string path = Safe(tx, "plan.json");
                if (!File.Exists(path)) continue; // Staging was interrupted before the first change.
                Plan plan = new JavaScriptSerializer().Deserialize<Plan>(File.ReadAllText(path, Utf8));
                Base(plan != null && plan.type == PlanType && plan.rows != null, "recuperacion de la instalacion anterior");
                if (guard != null) guard();
                Rollback(game, tx, plan.rows);
            }
        }
        public static void Recover(string gameRoot, Action guard = null)
        {
            string store = Store(gameRoot);
            if (!Directory.Exists(store)) return;
            using (Lock(store)) RecoverLocked(gameRoot, store, guard);
        }
        public static string Apply(string gameRoot, IList<IncrementalChange> changes, Action guard = null)
        {
            string store = Store(gameRoot);
            using (Lock(store))
            {
                RecoverLocked(gameRoot, store, guard);
                var work = Prepare(Safe(gameRoot, "Interface/AddOns/RutaXP"), changes);
                bool replace = SupportsReplace(gameRoot);
                string tx = Safe(store, DateTime.UtcNow.ToString("yyyyMMddHHmmssfff", CultureInfo.InvariantCulture) + "-" + Guid.NewGuid().ToString("N"));
                var plan = new Plan { type = PlanType, rows = new List<Row>() };
                WritePlan(tx, plan, work, guard);
                try
                {
                    for (int i = 0; i < work.Count; ++i)
                    {
                        Row row = plan.rows[i];
                        string file = Target(gameRoot, row), prior = Safe(tx, "prior/" + i), staged = Safe(tx, "new/" + i);
                        // ReplaceFile on NTFS keeps the destination ACL, swaps the file atomically
                        // and retains the prior bytes without starting a permissions utility.
                        bool swapped = replace && row.old && row.add;
                        if (row.old)
                        {
                            if (swapped) File.Replace(staged, file, prior);
                            else File.Move(file, prior);
                            if (FileHash(prior) != work[i].OldHash)
                                throw new IOException("El archivo cambio durante la actualizacion: " + work[i].Path);
                        }
                        if (row.add && !swapped)
                        {
                            Directory.CreateDirectory(Path.GetDirectoryName(file));
                            File.Move(staged, file);
                            InstallerCore.InheritAddonAccess(file);
                        }
                    }
                    Mark(tx, "committed");
                    return tx;
                }
                catch { Rollback(gameRoot, tx, plan.rows); throw; }
            }
        }
    }
}
