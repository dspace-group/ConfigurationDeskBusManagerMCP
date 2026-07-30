"""Create a ZIP archive containing license and notice files for installed dependencies."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from importlib.metadata import Distribution, distribution
from pathlib import Path


LICENSE_TOKENS = ("license", "copying", "notice", "authors", "copyright")


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "", name).lower()


def is_license_file(relative_path: Path) -> bool:
    return any(token in part.lower() for part in relative_path.parts for token in LICENSE_TOKENS)


def archive_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value)


def get_license_files(distribution: Distribution) -> list[Path]:
    return [
        Path(file)
        for file in distribution.files or ()
        if is_license_file(Path(file)) and distribution.locate_file(file).is_file()
    ]


def get_runtime_package_names(notice_path: Path) -> list[str]:
    package_names: list[str] = []
    in_runtime_section = False
    for line in notice_path.read_text(encoding="utf-8").splitlines():
        if line == "## Runtime and Executable Dependencies":
            in_runtime_section = True
            continue
        if in_runtime_section and line.startswith("## "):
            break
        match = re.match(r"\| ([^|]+) \|", line)
        if in_runtime_section and match:
            package_name = match.group(1)
            if package_name != "Package" and set(package_name) != {"-"}:
                package_names.append(package_name)
    if not package_names:
        raise RuntimeError("No runtime and executable dependencies found in the third-party notice.")
    return package_names


def create_bundle(destination: Path, notice_path: Path) -> None:
    packages: list[tuple[str, str, Distribution, list[Path]]] = []
    missing: list[str] = []

    for package_name in get_runtime_package_names(notice_path):
        package_distribution = distribution(package_name)
        name = package_distribution.metadata["Name"]
        version = package_distribution.version
        license_files = get_license_files(package_distribution)
        if not license_files:
            missing.append(f"{name}=={version}")
            continue
        packages.append((name, version, package_distribution, license_files))

    if missing:
        missing_text = ", ".join(sorted(missing, key=str.lower))
        raise RuntimeError(f"Missing upstream license or notice files: {missing_text}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, object]] = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, version, package_distribution, license_files in sorted(
            packages, key=lambda package: package[0].lower()
        ):
            package_root = f"THIRD-PARTY-LICENSES/{archive_name(name)}-{archive_name(version)}"
            entries: list[str] = []
            for relative_path in sorted(license_files):
                source_path = package_distribution.locate_file(relative_path)
                entry = f"{package_root}/{relative_path.as_posix()}"
                archive.write(source_path, entry)
                entries.append(entry)
            index.append({"name": name, "version": version, "files": entries})
        archive.writestr(
            "THIRD-PARTY-LICENSES/index.json",
            json.dumps({"packages": index}, indent=2) + "\n",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--notice", type=Path, required=True)
    arguments = parser.parse_args()
    create_bundle(arguments.destination, arguments.notice)


if __name__ == "__main__":
    main()