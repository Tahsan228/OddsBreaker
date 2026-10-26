"""Build the Windows release.

    python packaging/build.py --exe          PyInstaller: dist/OddsBreaker/ (folder) and
                                             dist/onefile/OddsBreaker.exe (single file)
    python packaging/build.py --package      installer (NSIS), portable zip, checksums
                                             into release/ (works on Windows or Linux)
    python packaging/build.py --all          both

The .exe step has to run on Windows. The package step only needs `makensis`
(NSIS 3) on the PATH, so CI runs it on Linux with the .exe files from the
Windows job.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import make_assets  # noqa: E402
from oddsbreaker import APP_NAME, AUTHOR, REPO_URL, SITE_URL, __version__  # noqa: E402

BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
RELEASE = os.path.join(ROOT, "release")
ASSETS = os.path.join(BUILD, "assets")

VERSION_INFO = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v4}), prodvers=({v4}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable(u'040904B0', [
      StringStruct(u'CompanyName', u'{author}'),
      StringStruct(u'FileDescription', u'{name} - automatic shiny hunter'),
      StringStruct(u'FileVersion', u'{version}'),
      StringStruct(u'InternalName', u'{name}'),
      StringStruct(u'LegalCopyright', u'Copyright (c) 2026 {author}. MIT License.'),
      StringStruct(u'OriginalFilename', u'{name}.exe'),
      StringStruct(u'ProductName', u'{name}'),
      StringStruct(u'ProductVersion', u'{version}')])]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

PORTABLE_README = """{name} {version} (portable)
================================

Double-click {name}.exe to start. Your hunts are saved in the
"{name}_data" folder right here, next to the .exe, because of the
portable.txt file. Delete portable.txt to keep them in %APPDATA% instead.

Windows might say "Windows protected your PC" the first time, because the
app isn't code-signed. Click "More info" and then "Run anyway".

Guide and updates: {site}
Source and help: {repo}
Made by {author}. MIT License.
"""


def run(cmd, **kw):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, **kw)


def build_assets():
    make_assets.main(ASSETS)


def version_tuple():
    parts = [int(p) for p in __version__.split(".")[:3]]
    return ", ".join(str(p) for p in parts + [0] * (4 - len(parts)))


def build_exe():
    if not sys.platform.startswith("win"):
        sys.exit("The .exe has to be built on Windows (CI does this on windows-latest).")
    build_assets()
    vfile = os.path.join(BUILD, "version_info.txt")
    with open(vfile, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO.format(v4=version_tuple(), version=__version__, name=APP_NAME,
                                    author=AUTHOR))
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
              "--name", APP_NAME, "--icon", os.path.join(ASSETS, "icon.ico"),
              "--version-file", vfile, "--collect-submodules", "oddsbreaker",
              "--exclude-module", "PIL", "--exclude-module", "pytest",
              "--exclude-module", "numpy", "--specpath", BUILD]
    entry = os.path.join(ROOT, "OddsBreaker.pyw")
    run(common + ["--onedir", "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyi-dir"),
                  entry], cwd=ROOT)
    run(common + ["--onefile", "--distpath", os.path.join(DIST, "onefile"),
                  "--workpath", os.path.join(BUILD, "pyi-one"), entry], cwd=ROOT)
    print("built", os.path.join(DIST, APP_NAME), "and", os.path.join(DIST, "onefile"))


def find_makensis():
    for name in ("makensis", "makensis.exe"):
        path = shutil.which(name)
        if path:
            return path
    for path in (r"C:\Program Files (x86)\NSIS\makensis.exe", r"C:\Program Files\NSIS\makensis.exe"):
        if os.path.exists(path):
            return path
    return None


def build_package():
    build_assets()
    os.makedirs(RELEASE, exist_ok=True)
    onedir = os.path.join(DIST, APP_NAME)
    onefile = os.path.join(DIST, "onefile", APP_NAME + ".exe")
    if not os.path.exists(os.path.join(onedir, APP_NAME + ".exe")) or not os.path.exists(onefile):
        sys.exit("Run --exe first (or download the windows-build artifact into dist/).")
    out = []
    # 1. installer
    makensis = find_makensis()
    if makensis:
        setup = os.path.join(RELEASE, "%s-%s-Setup.exe" % (APP_NAME, __version__))
        run([makensis, "-V2", "-DVERSION=%s" % __version__, "-DWEBSITE=%s" % SITE_URL, "-DSRCDIR=%s" % onedir,
             "-DOUTFILE=%s" % setup, "-DASSETS=%s" % ASSETS,
             "-DLICENSEFILE=%s" % os.path.join(ROOT, "LICENSE"),
             os.path.join(ROOT, "packaging", "installer.nsi")])
        out.append(setup)
    else:
        print("!! makensis not found: skipping the installer")
    # 2. single exe
    single = os.path.join(RELEASE, "%s-%s.exe" % (APP_NAME, __version__))
    shutil.copyfile(onefile, single)
    out.append(single)
    # 3. portable zip (data stays next to the exe)
    zpath = os.path.join(RELEASE, "%s-%s-Portable.zip" % (APP_NAME, __version__))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        top = "%s-%s" % (APP_NAME, __version__)
        z.write(onefile, top + "/%s.exe" % APP_NAME)
        z.writestr(top + "/portable.txt", "Hunts are saved next to the app because this file exists.\n")
        z.writestr(top + "/README.txt", PORTABLE_README.format(name=APP_NAME, version=__version__,
                                                               author=AUTHOR, site=SITE_URL,
                                                               repo=REPO_URL))
        z.write(os.path.join(ROOT, "LICENSE"), top + "/LICENSE.txt")
    out.append(zpath)
    # 4. checksums
    sums = os.path.join(RELEASE, "SHA256SUMS.txt")
    with open(sums, "w") as f:
        for path in out:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
            f.write("%s  %s\n" % (h.hexdigest(), os.path.basename(path)))
    for path in out + [sums]:
        print("  %-48s %8.1f MB" % (os.path.basename(path), os.path.getsize(path) / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", action="store_true")
    ap.add_argument("--package", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--assets", action="store_true", help="only generate the icon and artwork")
    a = ap.parse_args()
    if a.assets:
        build_assets()
    if a.exe or a.all:
        build_exe()
    if a.package or a.all:
        build_package()
    if not (a.exe or a.package or a.all or a.assets):
        ap.print_help()


if __name__ == "__main__":
    main()
