"""
Exports this port's simplified AnnotationObject overlay (app.models) as XML
matching LEADTOOLS' own <Annotations>/<Container>/<Object> .ann schema (built
against a real sample of that format), instead of this port's own simplified
JSON (see Factory/DownloadAnnotations). Every node present in that sample is
always emitted -- for fields this port has no equivalent data for (Hyperlink,
Password, GroupName, UserId, ...) the node is still created, just empty,
rather than omitted, so the document stays structurally identical to what a
real LEADTOOLS-produced .ann file looks like.

Coordinate scale: the reference sample's page size is 6120x7920 units for a
Letter-size (8.5in x 11in) page at CalibrationUnit=Inch -- exactly 720
units/inch, i.e. 10x PyMuPDF's 72-points/inch space. All page and annotation
geometry below is this port's PDF-point value * LEAD_UNITS_PER_POINT. This is
inferred from that one sample, not from a LEADTOOLS spec, so treat it as a
documented assumption, not a guarantee, for page sizes/units outside it.

Fields with no equivalent in AnnotationObject (Guid aside) are emitted empty
rather than invented. Guid is the one exception: a real GUID is structurally
required, so one is derived deterministically from
(document_id, page, index) via uuid5, so re-exporting the same document
produces the same Guids without needing to persist one on AnnotationObject.
"""
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from app.models import AnnotationObject

LEAD_UNITS_PER_POINT = 10
_GUID_NAMESPACE = uuid.UUID("6f6e6f6e-6f6e-6f6e-6f6e-6f6e6f6e6f6e")

_OBJECT_TYPES = {
    "rect": "Leadtools.Annotations.Engine.AnnRectangleObject",
    "text": "Leadtools.Annotations.Engine.AnnTextObject",
}


def _num(value) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _el(parent, tag: str, text: Optional[str] = None):
    node = ET.SubElement(parent, tag)
    if text is not None:
        node.text = text
    return node


def _point(parent, tag: str, x: float, y: float):
    node = _el(parent, tag)
    _el(node, "X", _num(x))
    _el(node, "Y", _num(y))
    return node


def _on_load(parent):
    node = _el(parent, "OnLoad")
    _el(node, "RotateAngle", "0")
    _el(node, "ScaleX", "1")
    _el(node, "ScaleY", "1")
    _point(node, "Offset", 0, 0)
    return node


def _solid_color(parent, tag: str, color: str):
    # <tag><SolidColorBrush><Color>...</Color></SolidColorBrush></tag> --
    # used for Object/Fill and Label/Foreground. Not to be confused with
    # _stroke's Stroke/SelectionStroke, which wrap an extra <Fill> around
    # the SolidColorBrush (see that function).
    node = _el(parent, tag)
    brush = _el(node, "SolidColorBrush")
    _el(brush, "Color", color)
    return node


def _stroke(parent, tag: str, color: str, thickness: float, alignment: str):
    node = _el(parent, tag)
    brush = _el(_el(node, "Fill"), "SolidColorBrush")
    _el(brush, "Color", color)
    _el(node, "Thickness", _num(thickness))
    _el(node, "MiterLimit", "0")
    _el(node, "DashCap", "Flat")
    _el(node, "StartLineCap", "Round")
    _el(node, "EndLineCap", "Round")
    _el(node, "LineJoin", "Round")
    _el(node, "DashOffset", "0")
    _el(node, "Dashes")
    _el(node, "StrokeAlignment", alignment)
    return node


def _font(parent, tag: str, size: float):
    node = _el(parent, tag)
    _el(node, "FamilyName", "Arial")
    _el(node, "Size", _num(size))
    _el(node, "Stretch", "Normal")
    _el(node, "Weight", "Normal")
    _el(node, "Style", "Normal")
    _el(node, "TextDecoration", "0")
    return node


def _object_guid(document_id: str, page: int, index: int) -> str:
    return str(uuid.uuid5(_GUID_NAMESPACE, f"{document_id}:{page}:{index}"))


def _build_object(parent, document_id: str, page: int, index: int, ann: AnnotationObject):
    obj = _el(parent, "Object")
    _el(obj, "ObjectType", _OBJECT_TYPES.get(ann.type, _OBJECT_TYPES["rect"]))
    _el(obj, "AssemblyName")
    _on_load(obj)
    _el(obj, "Guid", _object_guid(document_id, page, index))
    _el(obj, "IsVisible", "true")
    _el(obj, "IsSelected", "false")
    _el(obj, "IsLocked", "false")
    _el(obj, "Password")
    _el(obj, "GroupName")
    _el(obj, "Hyperlink")
    _el(obj, "FixedStateOperations", "0")
    _el(obj, "RotateGripper", "375")

    x0, y0 = ann.x * LEAD_UNITS_PER_POINT, ann.y * LEAD_UNITS_PER_POINT
    x1 = (ann.x + ann.width) * LEAD_UNITS_PER_POINT
    y1 = (ann.y + ann.height) * LEAD_UNITS_PER_POINT
    _point(obj, "RotateCenter", (x0 + x1) / 2, (y0 + y1) / 2)

    points = _el(obj, "Points")
    for px, py in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        _point(points, "Point", px, py)

    _solid_color(obj, "Fill", "transparent")

    labels = _el(obj, "Labels")
    label = _el(labels, "Label")
    _el(label, "Key", "AnnObjectName")
    _el(label, "IsVisible", "false")
    _el(label, "LabelRestriction", "0")
    _el(label, "Text", ann.text or "")
    _point(label, "OriginalPosition", x0, y0)
    _point(label, "Offset", 0, 0)
    _el(label, "Background")
    _solid_color(label, "Foreground", "red")
    _font(label, "Font", 11)
    _el(label, "OffsetHeight", "true")
    _el(label, "LabelPositionMode", "0")

    _stroke(obj, "Stroke", ann.color or "red", 1, "Inset")
    _stroke(obj, "SelectionStroke", "Blue", 4, "Center")
    _font(obj, "Font", 12)

    _el(obj, "ObjectId", "-3")
    _el(obj, "ObjectTag")

    metadata = _el(obj, "Metadata")
    for key, value in (
        ("Subject", ""),
        ("Author", ""),
        ("Modified", ""),
        ("Title", ""),
        ("Content", ann.value or ""),
        ("Created", ""),
    ):
        item = _el(metadata, "Item")
        _el(item, "Key", key)
        _el(item, "Value", value)

    _el(obj, "Reviews")
    _el(obj, "UserId")
    _el(obj, "LayerId")
    _el(obj, "Opacity", "1")
    _el(obj, "BorderStyle", "0")
    _el(obj, "StartDrawingAngle", "0")
    return obj


def build_annotations_xml(
    pdf_path: Path, document_id: str, annotations_by_page: Dict[int, List[AnnotationObject]]
) -> bytes:
    """Returns a full <Annotations> document, one <Container> per page in the
    document (not just pages that have annotations -- matching the reference
    sample, which includes an empty Container for every page)."""
    root = ET.Element("Annotations")
    _el(root, "Version", "1")

    doc = fitz.open(str(pdf_path))
    try:
        for page_number in range(1, doc.page_count + 1):
            page = doc[page_number - 1]
            container = _el(root, "Container")
            _el(container, "PageNumber", str(page_number))
            size = _el(container, "Size")
            _el(size, "Width", _num(page.rect.width * LEAD_UNITS_PER_POINT))
            _el(size, "Height", _num(page.rect.height * LEAD_UNITS_PER_POINT))
            _point(container, "Offset", 0, 0)
            _el(container, "CalibrationScale", "1")
            _el(container, "IsVisible", "true")
            _el(container, "IsEnabled", "true")
            _el(container, "ViewPerspective", "1")
            _el(container, "RotateAngle", "0")
            _el(container, "UserData")
            _el(container, "CalibrationUnit", "Inch")

            objects = _el(container, "Objects")
            _on_load(objects)
            for index, ann in enumerate(annotations_by_page.get(page_number, [])):
                _build_object(objects, document_id, page_number, index, ann)
    finally:
        doc.close()

    ET.indent(root, space="    ")
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")
