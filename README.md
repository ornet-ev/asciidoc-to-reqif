# Asciidoc to ReqIF

This folder contains the tooling to convert asciidoc to [ReqIF](https://www.omg.org/spec/ReqIF/20110401/reqif.xsd) format.

## Known limitations
Currently, the exporter only supports:
* Plain text
* Cross-references
* lists (ordered/unordered)
* Requirements with role-tags
* Notes to requirements

Currently **not** supported:
* images
* formulas
* tables
* automatically generated content like ICS-tables

## Output formats
It generates a single file with different variants.
Depending on your ALM-tool, importing all documents may fail.
Instead, you should choose a specific document or set of documents to import, or you will end up with redundant information and multiple instances of the same object.

### Full document
This document contains all text, including informative items and notes.
Asciidoc with git cannot reliably assign identifiers to objects.
Therefore, all objects which are not explicitly tagged with an ID will not have stable ReqIF identifiers.
If you import this document regularly, all non-requirement objects will appear as deleted/rejected and new objects will appear.
This document is therefore not recommended for continuous importing of draft documents.

### Role-based requirements document
For each role defined in asciidoc, there will be one ReqIF specification document which includes all requirements for this role.
This document also includes all notes which are added to a specific requirement block.


## Prerequisites
The following is required to run this tool:
1. `asciidoctor`
2. a python3 interpreter (3.12 works, earlier versions might)

## Installation

    python3 -m venv /path/to/env
    source /path/to/env/bin/activate
    python -m pip install -e /path/to/repo/asciidoc_to_reqif

## Usage

    asciidoc-to-reqif /path/to/source.adoc /path/to/output.reqifz

Use `--help` to get more options.

## Technical details
This backend consists of two parts:
. A ruby-script to be used as an asciidoctor-backend which generates an intermediate xml representation.
. A python package which converts the intermediate xml to ReqIF format
The python package wraps the calls to asciidoctor for ease of use.
