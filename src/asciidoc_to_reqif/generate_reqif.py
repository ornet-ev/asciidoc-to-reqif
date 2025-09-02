import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import logging
import zipfile

from .model import Requirement, Document, WorkItem, Heading, InfoItem, ContentWorkItem, get_all_items

ET.register_namespace("rf", "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd")
ET.register_namespace("", "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd")
ET.register_namespace("xhtml", "http://www.w3.org/1999/xhtml")

ns = {
    "": "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
    "rf": "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

logger = logging.getLogger(__name__)


"""
def type_ref_name(wi: WorkItem) -> str:
    if isinstance(wi, Requirement):
        return {
        "technical": "technical_requirement",
        "process": "process_requirement",
            "documentation": "documentation_requirement",
            "other": "other_requirement",
        }[wi.category]
    if isinstance(InfoItem):
        return "info_item"
    if isinstance(Heading):
        return "heading_item"
    raise NotImplementedError()
"""


def make_wi(objects: ET.Element, wi: WorkItem, date):
    logger.debug("making WI: %s", wi.ref_id)
    spec_object = ET.SubElement(objects, "SPEC-OBJECT", {"IDENTIFIER": wi.ref_id, "LAST-CHANGE": date})
    spec_type = ET.SubElement(spec_object, "TYPE")
    type_ref = ET.SubElement(spec_type, "SPEC-OBJECT-TYPE-REF")
    if isinstance(wi, Requirement):
        type_ref.text = "requirement"
    elif isinstance(wi, InfoItem):
        type_ref.text = "note_item" if wi.is_note else "info_item"
    elif isinstance(wi, Heading):
        type_ref.text = "heading_item"
    else:
        raise NotImplementedError()


    values = ET.SubElement(spec_object, "VALUES")

    if isinstance(wi, ContentWorkItem):
        title = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING", attrib={"THE-VALUE": wi.title})
        title_def = ET.SubElement(title, "DEFINITION")
        title_def_ref = ET.SubElement(title_def, "ATTRIBUTE-DEFINITION-STRING-REF")
        title_def_ref.text = type_ref.text + "_title"

        text = ET.SubElement(values, "ATTRIBUTE-VALUE-XHTML")
        text_def = ET.SubElement(text, "DEFINITION")
        text_def_ref = ET.SubElement(text_def, "ATTRIBUTE-DEFINITION-XHTML-REF")
        text_def_ref.text = type_ref.text + "_text"
        text_value = ET.SubElement(text, "THE-VALUE")
        content = ET.SubElement(text_value, "{http://www.w3.org/1999/xhtml}div")
        logger.debug("wi.text=%s", wi.text)
        content.extend(wi.text)

    if isinstance(wi, Heading):
        text = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING", attrib={"THE-VALUE": wi.title})
        text_def = ET.SubElement(text, "DEFINITION")
        text_def_ref = ET.SubElement(text_def, "ATTRIBUTE-DEFINITION-STRING-REF")
        text_def_ref.text = "heading_title"

def instantiate_wi(parent: ET.Element, wi: WorkItem, date, filter_role: str | None, show_freetext: bool):
    if isinstance(wi, Heading):
        instantiate_heading(parent=parent, heading=wi, date=date, filter_role=filter_role, show_freetext=show_freetext)
    elif isinstance(wi, Requirement):
        instantiate_requirement(parent=parent, requirement=wi, date=date, filter_role=filter_role)
    elif isinstance(wi, InfoItem):
        if show_freetext or wi.has_stable_id:
            instantiate_freestanding_info(parent=parent, info=wi, date=date, filter_role=filter_role)
    else:
        raise NotImplementedError()


def instantiate_heading(parent: ET.Element, heading: Heading, date, filter_role: str | None, show_freetext: bool):
    logger.debug("instantiate heading %s: %s", heading.ref_id, heading.title)
    container = ET.SubElement(parent, "SPEC-HIERARCHY",
                              attrib={"IDENTIFIER": f"requirements_{filter_role}_{heading.ref_id}",
                                      "LAST-CHANGE": date})
    heading_object = ET.SubElement(container, "OBJECT")
    ref = ET.SubElement(heading_object, "SPEC-OBJECT-REF")
    ref.text = heading.ref_id

    if heading.children:
        children_container = ET.SubElement(container, "CHILDREN")
        for child_wi in heading.children:
            instantiate_wi(children_container, child_wi, date, filter_role, show_freetext=show_freetext)


def instantiate_requirement(parent: ET.Element, requirement: Requirement, date, filter_role: str | None):
    logger.debug("instantiate requirement %s: %s", requirement.ref_id, requirement.title)
    if filter_role and requirement.role != filter_role:
        return
    instantiation_id = f"requirements_{filter_role}_{requirement.ref_id}"
    container = ET.SubElement(parent, "SPEC-HIERARCHY", attrib={"IDENTIFIER": instantiation_id, "LAST-CHANGE": date})
    requirement_object = ET.SubElement(container, "OBJECT")
    ref = ET.SubElement(requirement_object, "SPEC-OBJECT-REF")
    ref.text = requirement.ref_id

    if requirement.notes:
        children_container = ET.SubElement(container, "CHILDREN")
        for note in requirement.notes:
            instantiate_note(children_container, note, instantiation_id, date)


def instantiate_note(parent: ET.Element, note: InfoItem, id_base: str, date):
    logger.debug("instantiate note %s", note.ref_id)
    container = ET.SubElement(parent, "SPEC-HIERARCHY",
                              attrib={"IDENTIFIER": f"{id_base}_{note.ref_id}", "LAST-CHANGE": date})
    requirement_object = ET.SubElement(container, "OBJECT")
    ref = ET.SubElement(requirement_object, "SPEC-OBJECT-REF")
    ref.text = note.ref_id
    # no children


def instantiate_freestanding_info(parent: ET.Element, info: InfoItem, date, filter_role: str | None = None):
    if filter_role:
        return
    logger.debug("instantiate freestanding info item %s", info.ref_id)
    container = ET.SubElement(parent, "SPEC-HIERARCHY",
                              attrib={"IDENTIFIER": f"requirements_{filter_role}_{info.ref_id}", "LAST-CHANGE": date})
    requirement_object = ET.SubElement(container, "OBJECT")
    ref = ET.SubElement(requirement_object, "SPEC-OBJECT-REF")
    ref.text = info.ref_id
    # no children

def add_enum(datatypes: ET.Element, name:str, values: list[str], date):
    data_def = ET.SubElement(datatypes, "DATATYPE-DEFINITION-ENUMERATION", attrib={
        "IDENTIFIER": name,
        "LAST-CHANGE": date})

    value_defs = ET.SubElement(data_def, "SPECIFIED-VALUES")
    for i, value in enumerate(values):
        enum_element = ET.SubElement(value_defs, "ENUM-VALUE", attrib={
            "IDENTIFIER": f"{name}_{value}",
            "LAST-CHANGE": date
        })
        properties = ET.SubElement(enum_element, "PROPERTIES")
        ET.SubElement(properties, "EMBEDDED-VALUE", attrib={"KEY": str(i), "OTHER-CONTENT": ""})

def build(base_file: Path | None, out_file: Path, document: Document, document_title: str, commit_hash: str):
    logger.debug(document)
    if base_file is None:
        base_file = Path(__file__).parent / "base.xml"
    root = ET.parse(base_file)
    objects = root.find(".//SPEC-OBJECTS", ns)
    documents = root.find(".//SPECIFICATIONS", ns)
    header = root.find(".//REQ-IF-HEADER", ns)

    # header
    assert objects is not None
    assert documents is not None
    assert header is not None
    creation_time = header.find(".//CREATION-TIME", ns)
    date = datetime.datetime.now().isoformat(timespec="seconds")
    creation_time.text = date
    title = ET.SubElement(header, "TITLE")
    title.text = document_title
    header.attrib["IDENTIFIER"] = f"ASCIIDOC_EXPORT_{commit_hash}"

    flat_items = list(i for child in document.children for i in get_all_items(child))
    for wi in flat_items:
        make_wi(objects, wi, date)
    known_roles = set((wi.role for wi in flat_items if isinstance(wi, Requirement)))

    # roles enum
    datatypes = root.find(".//DATATYPES", ns)
    assert datatypes is not None
    add_enum(datatypes, "enum_role", list(known_roles), date)


    make_document(documents, document, f"{document.name}_full", f"{document.name} - full", date, None, True)
    make_document(documents, document, f"{document.name}", f"{document.name} - requirements", date, None, False)
    for role in known_roles:
        make_document(documents, document, f"{document.name}_{role}", f"{document.name} - {role} requirements", date, role, False)
    root.write(out_file, xml_declaration=True, method="xml", encoding="UTF-8")

def make_document(documents_element: ET.Element, document: Document, identifier: str, long_name: str, date: str, filter_role: str|None, show_freetext: bool):
    req_document = ET.SubElement(documents_element, "SPECIFICATION",
                                 attrib={"IDENTIFIER": f"{identifier}_full", "LAST-CHANGE": date,
                                         "LONG-NAME": long_name})
    document_type = ET.SubElement(req_document, "TYPE")
    document_type_ref = ET.SubElement(document_type, "SPECIFICATION-TYPE-REF")
    document_type_ref.text = "requirementdoc"
    children = ET.SubElement(req_document, "CHILDREN")
    for wi in document.children:
        instantiate_wi(children, wi, date, filter_role=filter_role, show_freetext=show_freetext)


def package(reqif_file: Path, out_file: Path, other_files: dict[str, Path]):
    with zipfile.ZipFile(out_file, "w") as zf:

        with zf.open("main.reqif", "w") as dst:
            with open(reqif_file, "rb") as src:
                dst.write(src.read())

        for local_name, absolute_name in other_files.items():
            with zf.open(local_name, "w") as dst:
                with open(absolute_name, "rb") as src:
                    dst.write(src.read())

