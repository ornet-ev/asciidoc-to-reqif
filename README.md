# Asciidoc to ReqIF

This folder contains the tooling to convert asciidoc to [ReqIF](https://www.omg.org/spec/ReqIF/20110401/reqif.xsd) format.

## Features

### Supported features
* Plain text
* Cross-references
* lists (ordered/unordered)
* images
* tables
* Requirements with role-tags
* Notes to requirements


### Hard limitations
These limitations are inherent in the process, and will probably never be solved:
* It is not possible to link to glossary items using text anchors.
  This is due to the fact that ReqIF does not support linking in text to other spec items.
  Some tools like Polarion allow using HTML-anchors. However, this would require knowledge of the URL of the item to be linked, but this URL is different for each ALM instance and may not even be defined prior to import.

## Output formats
It generates a single file with different variants.
Depending on your ALM-tool, importing multiple documents may fail.
Instead, you should choose a specific document or set of documents to import, or you will end up with redundant information and multiple instances of the same object.

### Full document
This document contains all text, including informative items and notes.
Asciidoc with git cannot reliably assign identifiers to objects.
Therefore, all objects which are not explicitly tagged with an ID will not have stable ReqIF identifiers.
If you import this document regularly, all non-requirement objects will appear as deleted/rejected and new objects will appear.
This document is therefore not recommended for continuous importing of draft documents.

### Requirements document
This document contains all requirements and their notes, but no freetext info items.
This document is suitable for continuous importing of draft documents.
This is the document to choose if you want to make sure you have all requirements for traceability, but don't care about the explanations around the text.

### Role-based requirements documents
For each role defined in asciidoc, there is one document which includes all requirements for this role and their notes.
This document is suitable for continuous importing of draft documents.
This is the document to choose if you only want to implement one role.

## Prerequisites
The following is required to run this tool:
1. `asciidoctor`
2. a python3 interpreter (3.12 works, earlier versions might)

### Optional
1. ruby gems `asciidoctor-diagram asciidoctor-diagram-plantuml`. If you don't need PlantUML, use the `--no-plantuml` parameter.

## Installation

    python3 -m venv /path/to/env
    source /path/to/env/bin/activate
    python -m pip install -e /path/to/repo/asciidoc_to_reqif

## Usage

    asciidoc-to-reqif /path/to/source.adoc /path/to/output.reqifz

Use `--help` to get more options.


## Contributing
Install development-dependencies and run pytest:

    python -m pip install -e '/path/to/repo/asciidoc_to_reqif[dev]'
    pytest /path/to/repo/asciidoc_to_reqif

## Technical details
This backend consists of two parts:
* A ruby-script to be used as an asciidoctor-backend which generates an intermediate xml representation.
* A python package which converts the intermediate xml to ReqIF format
The python package wraps the calls to asciidoctor for ease of use.
