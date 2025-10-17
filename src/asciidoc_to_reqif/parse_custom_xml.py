import hashlib
import json
import logging
import random
import re
import string
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from .model import Requirement, Heading, InfoItem, Document, WorkItem, get_all_items


def random_id():
    return "".join(random.choices(string.ascii_lowercase, k=20))


Attachments = dict[str, Path]

logger = logging.getLogger(__name__)

def path_or_none(s: str) -> Path|None:
    if s:
        return Path(s)
    else:
        return None

class ParagraphQueue:
    def __init__(self, ref_id_prefix: str):
        self.queued_paragraphs: list[ET.Element] = []
        self.paragraph_index = 0
        self.ref_id_prefix: str = ref_id_prefix

    def push(self, element: ET.Element):
        self.queued_paragraphs.append(element)

    def flush(self) -> list[WorkItem]:
        result = []
        if self.queued_paragraphs:
            ref_id = f"{self.ref_id_prefix}_{self.paragraph_index}"
            logger.debug("flushing item with %s sub-items: %s", len(self.queued_paragraphs), self.queued_paragraphs)
            item = InfoItem(text=self.queued_paragraphs, ref_id=ref_id, title=ref_id, has_stable_id=False)
            logger.debug("%s", item)
            result.append(item)
            self.paragraph_index += 1
            self.queued_paragraphs = []
        return result


class _Parser:
    def __init__(self, id_prefix: str, source_base: Path, generated_base: Path):
        self.parent_map = {}
        self.id_prefix: str = id_prefix
        self.source_base: Path = source_base
        self.generated_base: Path = generated_base
        self.images_dir: Path|None = None

    def make_id(self, original_ref_id):
        return f"{self.id_prefix}_{original_ref_id}"

    def parse_document(self, node: ET.Element) -> tuple[Document, Attachments]:
        assert node.tag == "document"
        self.images_dir = node.attrib["imagesdir"]
        children, attachments = self.parse_children(node, chapter_ref_id="document")
        return Document(
            name=node.attrib["name"],
            ref_id=self.make_id(node.attrib["name"]),
            children=children,
        ), attachments

    def parse_children(self, document_or_section: ET.Element, chapter_ref_id: str) -> tuple[list[WorkItem], Attachments]:
        paragraph_queue = ParagraphQueue(ref_id_prefix=chapter_ref_id)
        child_wi: list[WorkItem] = []
        attachments: Attachments = {}
        for i, child in enumerate(document_or_section):
            if child.tag == "section":
                child_wi += paragraph_queue.flush()
                c, a = self.parse_section(child, chapter_ref_id=f"{chapter_ref_id}_{i}")
                child_wi.append(c)
                attachments.update(a)
            elif child.tag == "requirement":
                child_wi += paragraph_queue.flush()
                c, a = self.parse_requirement(child)
                child_wi.append(c)
                attachments.update(a)
            elif child.tag in ("image",):
                child_wi += paragraph_queue.flush()
                c, a = self.parse_image(child)
                child_wi.append(c)
                attachments.update(a)
            elif child.tag in ("table",):
                child_wi += paragraph_queue.flush()
                c, a = self.parse_table(child)
                child_wi.append(c)
                attachments.update(a)
            # 'note's cannot occur here
            else:
                p, a = self.parse_leaf_block(child)
                attachments.update(a)
                paragraph_queue.push(p)
        child_wi += paragraph_queue.flush()
        return child_wi, attachments

    def parse_section(self, section: ET.Element, chapter_ref_id: str) -> tuple[Heading, Attachments]:
        children, attachments = self.parse_children(section, chapter_ref_id=chapter_ref_id)
        return Heading(
            ref_id=self.make_id(self.get_heading_id(section)),
            title=section.attrib["title"],
            children=children,
        ), attachments

    def parse_leaf_block(self, node: ET.Element) -> tuple[ET.Element, Attachments]:
        match = re.match(r"{http://www.w3.org/1999/xhtml}(\w+)", node.tag)
        if match:
            tag = match.group(1)
            if tag in ("p", "ol", "ul", "li"):
                p = node
                node.tag = f"xhtml:{tag}"
                attachments = {}
            else:
                logger.warning(f"unsupported XHTML element: {node.tag}")
        else:
            logger.warning("unsupported object of type %s", node.tag)
            p = ET.Element("xhtml:p")
            p.text = f"UNSUPPORTED OBJECT OF TYPE {node.tag}"
            attachments = {}
        return p, attachments

    def parse_flat_children(self, children: list[ET.Element]) -> tuple[list[ET.Element], Attachments]:
        result_children: list[ET.Element] = []
        attachments: Attachments = {}
        for child in children:
            c, a = self.parse_leaf_block(child)
            result_children.append(c)
            attachments.update(a)
        return result_children, attachments

    def parse_requirement(self, requirement: ET.Element) -> tuple[Requirement, Attachments]:
        attachments = {}
        text: list[ET.Element] = []
        notes: list[InfoItem] = []
        ref_id = requirement.attrib["id"]
        for child in requirement:
            if child.tag == "note":
                child_text, a = self.parse_flat_children([c for c in child])
                notes.append(InfoItem(
                    ref_id=self.make_id(f"{ref_id}_note{len(notes)}"),
                    title=f"note {len(notes)+1}",
                    text=child_text,
                    is_note=True,
                    has_stable_id=True,
                ))
            else:
                c, a = self.parse_leaf_block(child)
                text.append(c)
            attachments.update(a)

        keyword = requirement.attrib["keyword"]
        category = requirement.attrib["category"]
        assert keyword in ("shall", "should", "may")
        assert category in ("technical", "process", "documentation", "other")

        return Requirement(
            ref_id=self.make_id(ref_id),
            title=requirement.attrib["title"],
            keyword=keyword,
            category=category,
            role=requirement.attrib["role"],
            notes=notes,
            text=text,
        ), attachments

    def get_absolute_attachment_path(self, input_file: Path, base_dir: Path|None, images_dir: Path|None) -> Path:
        absolute_file, reason = self.get_absolute_attachment_path_inner(input_file, base_dir, images_dir)
        logger.debug("attachment %s can be found at %s (%s)", input_file, absolute_file, reason)
        return absolute_file

    def get_absolute_attachment_path_inner(self, input_file: Path, base_dir: Path|None, images_dir: Path) -> tuple[Path, str]:
        if input_file.is_absolute():
            return input_file, "input_file is absolute"
        if images_dir: # image is generated
            # if images_dir is set, it points to the parent of the file, not to the parent of the src path!
            file_name = images_dir / input_file.name
            if file_name.is_absolute():
                return file_name, "images_dir is absolute"
            else:
                return self.find_relative_in_source_or_generated(file_name), "images_dir is relative"
        if base_dir:
            file_name = base_dir / input_file
            if file_name.is_absolute():
                return file_name, "base_dir is absolute"
            else:
                return self.find_relative_in_source_or_generated(file_name), "base_dir is relative"
        else:
            return self.find_relative_in_source_or_generated(input_file), "no subdirs set"

    def find_relative_in_source_or_generated(self, relative_file) -> Path:
        assert not relative_file.is_absolute()
        absolute_source = (self.source_base / relative_file).absolute()
        absolute_generated = (self.generated_base / relative_file).absolute()
        assert absolute_source.is_absolute()
        assert absolute_generated.is_absolute()
        if absolute_source.exists() and absolute_generated.exists() and absolute_source != absolute_generated:
            raise RuntimeError(f"Relative file {relative_file} is ambiguous: both {absolute_source} and {absolute_generated} exist")
        result = absolute_source if absolute_source.exists() else (absolute_generated if absolute_generated.exists() else None)
        if not result:
            raise RuntimeError(f"Neither {absolute_source} nor {absolute_generated} exist")
        return result


    def parse_image(self, node) -> tuple[InfoItem, dict[str, Path]]:
        relative_file = path_or_none(node.attrib["src"])
        assert relative_file, "src attribute is required"
        absolute_file: Path = self.get_absolute_attachment_path(relative_file, path_or_none(node.attrib["dir"]), path_or_none(node.attrib["imagesdir"]))
        has_stable_id = bool(node.attrib["id"])
        if has_stable_id:
            figure_id = node.attrib["id"]
        else:
            with open(absolute_file, "rb", buffering=0) as f:
                figure_id = hashlib.file_digest(f, "sha256").hexdigest()
        local_file = f"{figure_id}.png"
        attachments: dict[str, Path]  = {local_file: absolute_file}
        t = ET.Element("xhtml:object", attrib={"data": local_file, "type": "image/png"})
        item = InfoItem(
            is_note=False,
            ref_id=self.make_id(figure_id),
            title=figure_id,
            text=[t],
            has_stable_id=has_stable_id,
        )
        return item, attachments

    def parse_table(self, node) -> tuple[InfoItem, dict[str, Path]]:
        has_stable_id = bool(node.attrib["id"])
        table_id = node.attrib["id"] if has_stable_id else random_id()
        item = InfoItem(
            is_note=False,
            ref_id=self.make_id(table_id),
            title=table_id,
            text=[child for child in node],
            has_stable_id=has_stable_id,
        )
        return item, {}

    def parse(self, filename: Path) -> tuple[Document, dict[str, Path]]:
        root = ET.parse(filename)
        self.parent_map = {c: p for p in root.iter() for c in p}
        root, attachments = self.parse_document(root.getroot())
        return root, attachments

    def get_heading_id(self, node: ET.Element) -> str:
        this_index = node.attrib.get("index", "unknown")
        parent_index = self.get_heading_id(self.parent_map[node]) if node in self.parent_map else "root"
        return f"{parent_index}_{this_index}"

    def validate_json(self, document: Document, json_file: Path):
        with open(json_file, "r") as f:
            json_data = json.load(f)
        expected_ids = sorted([self.make_id(f"r{n}") for n in json_data["requirements"]["numbers"]])
        found_requirements = list(
            item for child in document.children for item in get_all_items(child) if isinstance(item, Requirement))
        found_ids = sorted([r.ref_id for r in found_requirements])
        if expected_ids != found_ids:
            raise RuntimeError(
                f"expected requirements in JSON file do not match asciidoc input:\nJSON:     {expected_ids}\nASCIIDOC: {found_ids}")


def parse_xml(filename: Path, id_prefix: str, source_base: Path, generated_base: Path, json_file: Path | None) -> tuple[Document, dict[str, Path]]:
    parser = _Parser(id_prefix, source_base, generated_base)
    document, attachments = parser.parse(filename)
    logger.debug("attachments:")
    for key, value in attachments.items():
        logger.debug("  %s -> %s", key, value)
    if json_file:
        parser.validate_json(document, json_file)
    else:
        logger.warning("no JSON file specified, no cross-check performed")
    return document, attachments

def parse_adoc(filename: Path, tmp_dir: Path, enable_plantuml: bool, json_file: Path | None)-> tuple[Document, dict[str, Path]]:
    ruby_helper = Path(__file__).parent / "reqif.rb"
    commands = (
            ["asciidoctor", ] +
            (["-r", "asciidoctor-diagram"] if enable_plantuml else []) +
            ["-r", ruby_helper,
             "--backend", "plainxml",
             "--trace",
             "--destination-dir", tmp_dir,
             f"--attribute=imagesoutdir={tmp_dir/'myimagesoutdir'}",
             f"--attribute=diagram-autoimagesdir",
             filename
             ])
    try:
        subprocess.run(commands, check=True, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        e.add_note(e.stderr)
        raise
    xml_export = tmp_dir / filename.with_suffix(".xml").name
    id_prefix = filename.stem
    document, attachments = parse_xml(xml_export, id_prefix, filename.parent, tmp_dir, json_file)

    return document, attachments
