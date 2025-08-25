from dataclasses import dataclass, field

import typing
import xml.etree.ElementTree as ET


@dataclass
class WorkItem:
    ref_id: str
    title: str


@dataclass
class ContentWorkItem(WorkItem):
    text: list[ET.Element]


@dataclass
class Heading(WorkItem):
    children: list[WorkItem] = field(default_factory=list)


@dataclass
class Document:
    ref_id: str
    name: str
    children: list[WorkItem] = field(default_factory=list)


@dataclass
class InfoItem(ContentWorkItem):
    is_note: bool = False


@dataclass
class Requirement(ContentWorkItem):
    keyword: typing.Literal["shall", "should", "may"]
    category: typing.Literal["technical", "process", "documentation", "other"]
    role: str
    notes: list[InfoItem] = field(default_factory=list)


def get_all_items(wi: WorkItem):
    yield wi

    if isinstance(wi, Document):
        for child in wi.children:
            yield from get_all_items(child)

    if isinstance(wi, Heading):
        for child in wi.children:
            yield from get_all_items(child)

    if isinstance(wi, Requirement):
        for note in wi.notes:
            yield from get_all_items(note)
