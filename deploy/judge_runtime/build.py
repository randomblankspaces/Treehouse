"""Package Linux ARM64 wheels; never copy the Mac virtualenv into Runtime."""

import argparse
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "main.py" not in names or "strands/__init__.py" not in names or "boto3/__init__.py" not in names:
            raise ValueError("Runtime archive lacks entrypoint or dependencies")
        if (
            sum(info.file_size for info in archive.infolist()) > 750 * 1024 * 1024
            or Path(path).stat().st_size > 250 * 1024 * 1024
        ):
            raise ValueError("Runtime archive exceeds AWS limits")
        for name in names:
            if name.startswith("/") or ".." in Path(name).parts or "__pycache__" in name:
                raise ValueError("Unsafe archive entry")
            if name.endswith(".so"):
                header = archive.read(name)[:20]
                if header[:4] != b"\x7fELF" or struct.unpack("<H", header[18:20])[0] != 183:
                    raise ValueError(f"Native dependency is not Linux ARM64: {name}")


def build(output):
    source = Path(__file__).resolve().parent
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "package"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python-platform",
                "aarch64-manylinux2014",
                "--python-version",
                "3.12",
                "--only-binary=:all:",
                "--no-compile-bytecode",
                "--target",
                str(target),
                "-r",
                str(source / "requirements.txt"),
            ],
            check=True,
        )
        shutil.copyfile(source / "main.py", target / "main.py")
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    info = zipfile.ZipInfo(path.relative_to(target).as_posix())
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    validate_archive(output)
    print(f"Validated Linux ARM64 archive: {output} ({output.stat().st_size} bytes). No AWS calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args().output)
