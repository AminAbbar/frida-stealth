import os
import re
import pathlib
import argparse

# ================= DEFAULT CONFIG =================
DEFAULT_PREFIX = "Banana"
DEFAULT_PORT_CONTROL = "27043"
DEFAULT_PORT_CLUSTER = "27053"

TARGET_SUBPROJECTS = ["frida-core", "frida-gum"]

SKIP_DIRS = {
    ".git", ".github", "releng", "tests",
    "termux-elf-cleaner", "tools"
}

def get_replacements(cfg):
    return [
        # Threads / loops
        (r'"frida-main-loop"', f'"{cfg["thread"]}main-loop"'),
        (r'"gum-js-loop"', f'"{cfg["thread"]}js-loop"'),
        (r'"gmain"', f'"{cfg["thread"]}gmain"'),

        # RPC / protocol
        (r'"frida:rpc"', f'"{cfg["lower"]}:rpc"'),
        (r'27042', cfg["port_control"]),
        (r'27052', cfg["port_cluster"]),

        # User-Agent / strings
        (r'"Frida"', f'"{cfg["name"]}"'),
        (r'"Frida/"', f'"{cfg["name"]}/"'),

        # Android / paths
        (r'"re.frida.server"', f'"re.{cfg["lower"]}.server"'),
        (r'"re.frida.Gadget"', f'"re.{cfg["lower"]}.Gadget"'),
        (r'/frida-', f'/{cfg["thread"]}'),
    ]

def process_file(path, reps):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        new = data
        for pat, rep in reps:
            new = re.sub(pat, rep, new)
        if new != data:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            print(f"[*] Patched: {path}")
    except Exception as e:
        print(f"[!] {path}: {e}")

def patch_server_vala(base, cfg):
    p = base / "subprojects/frida-core/server/server.vala"
    if not p.exists():
        return
    txt = p.read_text()
    if "GLib.Uuid.string_random" not in txt:
        txt = txt.replace(
            'private const string DEFAULT_DIRECTORY = "re.frida.server";',
            'private static string? DEFAULT_DIRECTORY = null;'
        )
        txt = txt.replace(
            'private static int main (string[] args) {',
            'private static int main (string[] args) {\n\tDEFAULT_DIRECTORY = GLib.Uuid.string_random();'
        )
        p.write_text(txt)
        print("[*] Patched server.vala")

def create_anti_anti(base, cfg):
    out = base / "subprojects/frida-core/src/anti-anti-frida.py"
    content = f"""import lief, sys

def patch(path):
    bin = lief.parse(path)
    if not bin:
        return
    for s in bin.symbols:
        if "frida" in s.name.lower():
            s.name = s.name.replace("frida", "{cfg["lower"]}")
    bin.write(path)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
"""
    out.write_text(content)
    print("[*] Created anti-anti-frida.py")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    ap.add_argument("--port-control", default=DEFAULT_PORT_CONTROL)
    ap.add_argument("--port-cluster", default=DEFAULT_PORT_CLUSTER)
    args = ap.parse_args()

    cfg = {
        "name": args.prefix,
        "lower": args.prefix.lower(),
        "thread": args.prefix.lower() + "-",
        "port_control": args.port_control,
        "port_cluster": args.port_cluster,
    }

    base = pathlib.Path.cwd() / "frida"
    if not base.exists():
        base = pathlib.Path.cwd()

    reps = get_replacements(cfg)

    for sub in TARGET_SUBPROJECTS:
        root = base / "subprojects" / sub
        if not root.exists():
            continue
        for r, d, f in os.walk(root):
            d[:] = [x for x in d if x not in SKIP_DIRS]
            for file in f:
                if file.endswith((".c", ".h", ".vala", ".py", "meson.build")):
                    process_file(os.path.join(r, file), reps)

    patch_server_vala(base, cfg)
    create_anti_anti(base, cfg)

if __name__ == "__main__":
    main()
