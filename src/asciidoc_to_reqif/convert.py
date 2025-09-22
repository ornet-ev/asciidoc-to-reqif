import argparse
import tempfile
from pathlib import Path
import subprocess
import datetime # TODO: remove
import logging

from .parse_custom_xml import parse as parse_xml
from .generate_reqif import build, package


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="input")
    parser.add_argument("output", type=Path, default=None, help="ReqIf-Z output file (.reqifz)")
    parser.add_argument("--base", default=None, type=Path, help="base ReqIF file")
    parser.add_argument("--tmpdir", default=None, type=Path, help="temporary working directory")
    parser.add_argument("--keep-tmp", action="store_true", help="keep temporary working directory for debugging")
    parser.add_argument("--sourcedir", type=Path, help="path for image locations")
    parser.add_argument("--json", type=Path, default=None, help="path to load JSON to verify requirement parsing")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="verbose")
    args = parser.parse_args()
    logging.basicConfig(level={0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}[args.verbose])
    if not args.output:
        args.output = args.input + ".reqifz"
    return args


def main():
    args = parse_args()
    ruby_helper = Path(__file__).parent / "reqif.rb"
    document_name = args.input.stem
    if args.tmpdir:
        tempfile.tempdir = str(args.tmpdir)
    with tempfile.TemporaryDirectory(delete=not args.keep_tmp, prefix=datetime.datetime.now().isoformat(timespec="seconds")) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        subprocess.run([
            "asciidoctor",
            "-r", "asciidoctor-diagram",
            "-r", ruby_helper,
            "--backend", "plainxml",
            "--trace",
            "--destination-dir", tmp_dir,
            args.input], check=True)
        xml_export = tmp_dir / args.input.with_suffix(".xml").name
        req_if = tmp_dir / xml_export.with_suffix(".reqif").name
        id_prefix = document_name
        document, attachments = parse_xml(xml_export, id_prefix, args.input.parent, tmp_dir, args.json)
        build(args.base, req_if , document, document_title=document_name, commit_hash="deadbeef") # TODO: parse revision
        package(req_if, args.output, other_files=attachments)


main()
