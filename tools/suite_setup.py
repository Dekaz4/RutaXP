"""Portable installer entry point. With no arguments it opens the Windows setup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading

# Support both a direct tools/ script and imports from the source checkout.
if __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_personal_suite as composer


def resources():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def settings_root():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RutaXP"


def client_from(path):
    path = Path(path).expanduser().resolve()
    if path.name.casefold() == "addons" and path.parent.name.casefold() == "interface":
        path = path.parent.parent
    if (path / "Interface/AddOns").is_dir():
        return path
    for flavor in ("_forever_", "_classic_beta_"):
        candidate = path / flavor
        if (candidate / "Interface/AddOns").is_dir():
            return candidate
    raise ValueError("Selecciona la carpeta de WoW Forever o su carpeta Interface/AddOns.")


def detect_client():
    saved = settings_root() / "client.txt"
    if saved.is_file():
        try:
            return client_from(saved.read_text(encoding="utf-8-sig").strip())
        except (OSError, UnicodeError, ValueError):
            pass
    return None


def game_root(client):
    if client.name.casefold() in {"_forever_", "_classic_beta_"} or (client.parent / ".build.info").is_file():
        if client.parent.name or (client.parent / ".build.info").is_file():
            return client.parent
    return client


def backup_store(client):
    game = game_root(client)
    if not game.name:
        raise ValueError("La instalación ocupa la raíz de la unidad. Usa una carpeta de juego para conservar copias externas en la misma unidad.")
    folder = "RutaXP-Suite-Backups"
    if game.name.casefold() == folder.casefold():
        folder += "-External"
    store = game.parent / folder / game.name
    return store / client.name if client != game else store


def find_native_sources(client):
    def backup_path(path):
        if path.resolve() != path.absolute():
            raise ValueError("La carpeta de copias de RutaXP contiene un enlace o junction.")
        return path

    addons = client / "Interface/AddOns"
    roots = {}
    needed = ("OpenMap", "ForeverDungeonJournal")
    candidates = (*needed, "Journey")
    integrated = [addons / "RutaXP"]
    for name in candidates:
        if (addons / name / (name + ".toc")).is_file():
            roots[name] = addons / name
    external = backup_store(client)
    if len(roots) != len(candidates):
        transactions = [tx for store in (external, client / "RutaXP-Suite-Backups") if backup_path(store).is_dir()
                        for tx in store.iterdir()]
        for tx in sorted(transactions, key=lambda p: p.name, reverse=True):
            if (not re.fullmatch(r"\d{17}-[0-9a-f]{32}", tx.name)
                    or not backup_path(tx / "committed").is_file() or (tx / "restoring").exists() or (tx / "restored").exists()):
                continue
            rows = json.loads(backup_path(tx / "plan.json").read_text(encoding="utf-8-sig"))["rows"]
            for index, row in enumerate(rows):
                dest = row.get("dest", "")
                if dest == "Interface/AddOns/RutaXP" or re.fullmatch(r"Interface/AddOns/\.RutaXP\.backup\.[0-9a-f]{32}", dest):
                    integrated.append(backup_path(tx / "prior" / str(index)))
                for name in candidates:
                    if name not in roots and dest == f"Interface/AddOns/{name}":
                        original = tx / "prior" / str(index)
                        if backup_path(original / (name + ".toc")).is_file():
                            roots[name] = original
            if len(roots) == len(candidates):
                break
    # The 0.7 updater may have placed an earlier integrated installation in
    # one of its named backups before handing control to the suite installer.
    if len(roots) != len(candidates):
        integrated.extend(sorted((backup_path(p) for store in (external, addons) for p in store.glob(".RutaXP.backup.*")
                                  if re.fullmatch(r"\.RutaXP\.backup\.[0-9a-f]{32}", p.name)),
                                 key=lambda p: p.stat().st_mtime, reverse=True))
    for installed in integrated:
        if len(roots) == len(candidates):
            break
        if not (installed / "manifest.sha256").is_file() or not (installed / "RutaXP.toc").is_file():
            continue
        _, meta = composer.lines_and_metadata((installed / "RutaXP.toc").read_text(encoding="utf-8-sig"))
        embedded = {name.strip() for name in meta.get("X-RutaXP-Embedded", "").split(",")}
        if meta.get("X-RutaXP-Journey-UI"):
            embedded.add("Journey")
        for name in candidates:
            if name not in roots and name in embedded and (installed / "Modules" / name).is_dir():
                roots[name] = installed
    missing = [name for name in needed if name not in roots]
    if missing:
        raise ValueError("Instala primero " + " y ".join(missing) + " en " + str(addons) + ".")
    return roots


def compose_bundle(client, destination, cache):
    destination = destination.resolve()
    if destination.is_relative_to(game_root(client)):
        raise ValueError("Elige un destino para el ZIP fuera de la instalación del juego.")
    roots = find_native_sources(client)
    return composer.compose(resources() / "RutaXP", roots, destination)


def activate(client, archive=None, *, prepared=None):
    script = resources() / "tools/Install-Suite.ps1"
    powershell = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    args = [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Client", str(client)]
    if prepared is not None:
        args += ["-PreparedDirectory", str(prepared.resolve(strict=True))]
    elif archive is not None:
        args += ["-Archive", str(archive.resolve(strict=True))]
    else:
        args += ["-Restore"]
    # Install-Suite verifies the selected client and that WoW is closed both
    # before the transaction and immediately before switching directories.
    process = subprocess.run(args, cwd=resources(), capture_output=True, text=True,
                             errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if process.returncode:
        detail = next((line.strip() for line in process.stderr.splitlines() if line.strip()), "")
        raise RuntimeError(detail or "No se ha podido completar la instalación.")
    return process.stdout.strip()


def run(client, cache, output=None, restore=False, archive=None, compose_only=False, report=print):
    if restore:
        return activate(client)
    if archive:
        return activate(client, archive)
    if compose_only or output:
        destination = output or (Path.cwd() / "RutaXP-personal.zip")
        compose_bundle(client, destination, cache)
        return f"Paquete preparado en {destination.resolve()}" if compose_only else activate(client, destination)
    store = backup_store(client)
    if store.resolve() != store.absolute():
        raise ValueError("La carpeta de copias de RutaXP contiene un enlace o junction.")
    roots = find_native_sources(client)
    store.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".RutaXP-stage-", dir=store) as work:
        prepared = Path(work) / "RutaXP"
        report("Preparando las guías de RutaXP…")
        composer.prepare_directory(resources() / "RutaXP", roots, prepared, report)
        report("Verificando los archivos e instalando la suite…")
        return activate(client, prepared=prepared)


def show_window(client, cache):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    window = tk.Tk()
    window.title("Instalar RutaXP")
    window.resizable(True, False)
    frame = ttk.Frame(window, padding=16)
    frame.grid(sticky="ew")
    window.columnconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    location = tk.StringVar(value=str(client) if client else "")
    status = tk.StringVar(value="Cierra WoW antes de instalar o restaurar.")
    ttk.Label(frame, text="Carpeta de World of Warcraft Forever").grid(row=0, column=0, columnspan=2, sticky="w")
    entry = ttk.Entry(frame, textvariable=location, width=64)
    entry.grid(row=1, column=0, sticky="ew", pady=6)

    def browse():
        path = filedialog.askdirectory(parent=window, initialdir=location.get() or str(Path.home()))
        if path:
            location.set(path)

    browse_btn = ttk.Button(frame, text="Examinar…", command=browse)
    browse_btn.grid(row=1, column=1, padx=(6, 0))
    ttk.Label(frame, textvariable=status, wraplength=520).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
    actions = ttk.Frame(frame)
    actions.grid(row=3, column=0, columnspan=2, sticky="e")
    queue = Queue()
    running = False

    def start(restore):
        nonlocal running
        if running:
            return
        try:
            path = client_from(location.get()) if location.get().strip() else None
            if path is None:
                raise ValueError("Selecciona la carpeta de WoW Forever.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("RutaXP", str(exc), parent=window)
            return
        if restore and not messagebox.askyesno("Restaurar RutaXP",
                "¿Quieres recuperar los addons y los ajustes anteriores a la integración?", parent=window):
            return
        running = True
        for widget in (install_btn, restore_btn, browse_btn, entry):
            widget.configure(state="disabled")
        status.set("Restaurando los addons…" if restore else "Preparando la suite…")

        def worker():
            try:
                msg = run(path, cache, restore=restore, report=lambda text: queue.put(("progress", text)))
                queue.put(("done", msg))
            except Exception as exc:
                queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=False).start()
        window.after(150, poll)

    def poll():
        nonlocal running
        try:
            while True:
                kind, text = queue.get_nowait()
                status.set(text)
                if kind != "progress":
                    running = False
                    for widget in (install_btn, restore_btn, browse_btn, entry):
                        widget.configure(state="normal")
                    if kind == "error":
                        messagebox.showerror("RutaXP", text, parent=window)
                    return
        except Empty:
            window.after(150, poll)

    install_btn = ttk.Button(actions, text="Instalar o actualizar", command=lambda: start(False))
    install_btn.pack(side="left")
    restore_btn = ttk.Button(actions, text="Restaurar addons anteriores", command=lambda: start(True))
    restore_btn.pack(side="left", padx=(8, 0))
    window.protocol("WM_DELETE_WINDOW", lambda: None if running else window.destroy())
    window.mainloop()


def relocate_if_inside_addon(client, argv, gui):
    if not getattr(sys, "frozen", False):
        return False
    executable = Path(sys.executable).resolve()
    folder = executable.parent
    if folder.name.casefold() != "rutaxp" or folder.parent.name.casefold() != "addons":
        return False
    stable = settings_root() / "Suite/Instaladores" / hashlib.sha256(executable.read_bytes()).hexdigest()
    stable.mkdir(parents=True, exist_ok=True)
    copy = stable / executable.name
    if not copy.exists() or copy.read_bytes() != executable.read_bytes():
        with tempfile.NamedTemporaryFile(dir=stable, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            shutil.copyfile(executable, temporary)
            temporary.replace(copy)
        finally:
            temporary.unlink(missing_ok=True)
    arguments = list(argv)
    if client is None:
        arguments.extend(["--client", str(client_from(folder.parent))])
    if gui and "--gui" not in arguments:
        arguments.append("--gui")
    # The onefile bootstrap waits for its Python child. Releasing the
    # bootstrap's executable handle permits the transaction to move RutaXP.
    arguments.extend(["--wait-launcher", str(os.getppid())])
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    subprocess.Popen([str(copy), *arguments], cwd=stable, env=env)
    return True


def wait_for_launcher(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x100000, False, pid)
    if handle:
        try:
            if kernel.WaitForSingleObject(handle, 30000) != 0:
                raise RuntimeError("Cierra el primer instalador y vuelve a abrir la copia de RutaXP.")
        finally:
            kernel.CloseHandle(handle)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Instala las guías de RutaXP con OpenMap, el diario de mazmorras y la interfaz local de Journey.")
    paths = parser.add_mutually_exclusive_group()
    paths.add_argument("--client", type=Path)
    paths.add_argument("--addons", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compose-only", action="store_true", help="Prepara el ZIP sin instalar.")
    mode.add_argument("--restore", action="store_true", help="Restaura los addons anteriores.")
    mode.add_argument("--archive", type=Path, help="Instala un paquete personal preparado previamente.")
    mode.add_argument("--gui", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache", type=Path, default=settings_root() / "Suite/Descargas")
    parser.add_argument("--wait-launcher", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    gui = args.gui or not argv
    try:
        path = args.addons or args.client
        client = client_from(path) if path else None
        if args.wait_launcher and sys.platform == "win32":
            wait_for_launcher(args.wait_launcher)
        if not args.compose_only and relocate_if_inside_addon(client, argv, gui):
            return 0
        client = client or detect_client()
        if gui:
            show_window(client, args.cache)
        elif client:
            # The desktop installer reads a pipe. Show each completed phase while
            # the helper is running, including when an older launcher invokes it.
            for stream in (sys.stdout, sys.stderr):
                if hasattr(stream, "reconfigure") and not stream.isatty():
                    stream.reconfigure(encoding="utf-8", line_buffering=True)
            print(run(client, args.cache, args.output, args.restore, args.archive, args.compose_only))
        else:
            raise ValueError("Indica la ruta de WoW Forever con --client o --addons.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        if gui:
            from tkinter import messagebox
            messagebox.showerror("Instalar RutaXP", str(exc))
        else:
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
