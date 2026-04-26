# utils/updater_win.py
import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile


def unzip_to(zippath, dest):
    with zipfile.ZipFile(zippath) as zf:
        zf.extractall(dest)


def copy_tree(src, dst):
    for root, _, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--cmd", nargs="+", required=True)  # p.ej. python app.py
    ap.add_argument("--waitpid", type=int, default=0)
    args = ap.parse_args()

    if args.waitpid:
        # esperar a que el proceso principal cierre
        for _ in range(300):
            try:
                os.kill(args.waitpid, 0)
                time.sleep(0.1)
            except OSError:
                break

    tmp = os.path.join(os.path.dirname(args.zip), "_upd_unzip")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    unzip_to(args.zip, tmp)
    copy_tree(tmp, args.target)

    subprocess.Popen(args.cmd, close_fds=True, cwd=args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
