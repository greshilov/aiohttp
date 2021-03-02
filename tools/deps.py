#!/usr/bin/env python3

import argparse
import collections
import hashlib
import os
import pathlib
import platform
import subprocess
import sys

PLATFORM_NAME = sys.platform if platform.python_implementation() != "PyPy" else "pypy"
ROOT = pathlib.Path(__file__).parent.parent
REQ_FOLDER = ROOT / "requirements"
PIN_FOLDER = REQ_FOLDER / "pinned"


def txt_file_name(in_file_name):
    components = (
        PLATFORM_NAME,
        f"{sys.version_info.major}.{sys.version_info.minor}",
        in_file_name,
    )
    txt_name = f"{'-'.join(components)}.txt"
    return PIN_FOLDER / txt_name


def compile_dependencies():
    for in_file in REQ_FOLDER.glob("*.in"):
        output_file = txt_file_name(in_file.stem)

        subprocess.call(
            (
                "pip-compile",
                "--allow-unsafe",
                "--generate-hashes",
                "--no-header",
                "--no-annotate",
                "--quiet",
                "--output-file",
                str(output_file),
                str(in_file),
            )
        )


def install_dependencies(in_name):
    txt_file = txt_file_name(in_name)

    subprocess.call(
        (
            "pip",
            "install",
            "--require-hashes",
            "-r",
            str(txt_file),
        )
    )


def replace_duplicates_with_symlinks():
    hash_to_file = collections.defaultdict(list)

    orig_dir = os.getcwd()
    os.chdir(PIN_FOLDER)
    try:
        for txt_fname in pathlib.Path(".").glob("*.txt"):
            if not txt_fname.is_symlink():
                with open(txt_fname, "rb") as f:
                    digest = hashlib.sha1(f.read()).hexdigest()
                    hash_to_file[digest].append(txt_fname)

        for digest, files in hash_to_file.items():
            if len(files) > 1:
                base_file, *other_files = files
                for other_file in other_files:
                    os.unlink(other_file)
                    os.symlink(base_file, other_file)
    finally:
        os.chdir(orig_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", help="sub-command help")

    install_parser = subparsers.add_parser("install", help="install dependencies")
    compile_parser = subparsers.add_parser("compile", help="compile dependencies")
    remove_duplicates = subparsers.add_parser(
        "rdup", help="remove duplicate .txt files"
    )

    install_parser.add_argument("file", type=str, help="dep to install", default="dev")

    args = parser.parse_args()
    if args.cmd == "install":
        install_dependencies(args.file)
    elif args.cmd == "compile":
        compile_dependencies()
    elif args.cmd == "rdup":
        replace_duplicates_with_symlinks()
