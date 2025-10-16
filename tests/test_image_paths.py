import re
from pathlib import Path
import tempfile
import subprocess

import pytest

from asciidoc_to_reqif.parse_custom_xml import parse_adoc



@pytest.fixture(params=["imagesdir_set", "imagesdir_notset"])
def dataset_name(request) -> str:
    return request.param

@pytest.fixture
def source_dir(dataset_name: str):
    return Path(__file__).parent / "image_paths_data" / dataset_name


def test_image_path_reqif(source_dir: Path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        _, attachments = parse_adoc(filename=source_dir / "good_practice.adoc", enable_plantuml=True, json_file=None,
                                    tmp_dir=Path(tmp_dir))
        assert len(attachments) == 2
        for relative, absolute in attachments.items():
            assert absolute.is_absolute()
            assert absolute.exists()  # check must be performed while tmp_dir still exists

# tests that the paths for the normal asciidoc generation also work
# this is a regression tests for the test suite in case the test data changes
def test_image_path_html(dataset_name: str, source_dir: Path):
    #tmp_dir = Path("test_tmp") / dataset_name
    #if True:
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(
                ["asciidoctor", "--backend", "html", "--destination-dir", tmp_dir, source_dir / "good_practice.adoc"],
                check=True, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as e:
            e.add_note(e.stderr)
            raise
        with open(Path(tmp_dir)/"good_practice.html", "r") as f:
            html = f.read()
        matches = re.findall(r'img src="(.*?)"', html)
        assert len(matches) == 1
        relative_path = matches[0]
        assert (source_dir / relative_path).exists()
