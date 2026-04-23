"""
Module D: Template Registry Loader
Loads registered templates from per-template manifest JSON folders.
Maintains a lightweight in-memory index of all known templates.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import json

from .config import TEMPLATES_DIR, ErrorCode
from .pdf_inspector import PDFInspectionResult


class TemplateRegistryError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass
class FingerprintStore:
    metadata: dict = field(default_factory=dict)
    acroform: dict = field(default_factory=dict)
    page_signature: dict = field(default_factory=dict)
    anchor_text: dict = field(default_factory=dict)
    visual_anchor: dict = field(default_factory=dict)


@dataclass
class SchemaRef:
    schema_path: str = ""
    blank_pdf_path: str = ""
    assets: dict = field(default_factory=dict)


@dataclass
class RuntimeHints:
    default_input_mode: str = "mixed"  # typed | handwritten | mixed
    primary_language: str = "en"
    alignment_mode: str = "strict"     # strict | normal | relaxed
    unknown_field_policy: str = "review"  # review | fallback | fail
    preferred_extractors: list = field(default_factory=list)


@dataclass
class TemplateRecord:
    template_id: str
    template_family: str
    template_version: str
    display_name: str
    status: str  # active | deprecated | draft
    fingerprints: FingerprintStore
    schema_ref: SchemaRef
    runtime_hints: RuntimeHints
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateRecord":
        fp_data = data.get("fingerprints", {})
        fingerprints = FingerprintStore(
            metadata=fp_data.get("metadata", {}),
            acroform=fp_data.get("acroform", {}),
            page_signature=fp_data.get("page_signature", {}),
            anchor_text=fp_data.get("anchor_text", {}),
            visual_anchor=fp_data.get("visual_anchor", {}),
        )

        schema_data = data.get("schema_ref", {})
        schema_ref = SchemaRef(
            schema_path=schema_data.get("schema_path", ""),
            blank_pdf_path=schema_data.get("blank_pdf_path", ""),
            assets=schema_data.get("assets", {}),
        )

        hints_data = data.get("runtime_hints", {})
        runtime_hints = RuntimeHints(
            default_input_mode=hints_data.get("default_input_mode", "mixed"),
            primary_language=hints_data.get("primary_language", "en"),
            alignment_mode=hints_data.get("alignment_mode", "strict"),
            unknown_field_policy=hints_data.get("unknown_field_policy", "review"),
            preferred_extractors=hints_data.get("preferred_extractors", []),
        )

        return cls(
            template_id=data.get("template_id", ""),
            template_family=data.get("template_family", ""),
            template_version=data.get("template_version", ""),
            display_name=data.get("display_name", ""),
            status=data.get("status", "draft"),
            fingerprints=fingerprints,
            schema_ref=schema_ref,
            runtime_hints=runtime_hints,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class TemplateSchema:
    """Loaded template field schema — used at runtime for extraction."""
    template_id: str
    fields: list[dict]  # list of field definitions

    @classmethod
    def from_json_file(cls, path: str) -> "TemplateSchema":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            template_id=data.get("template_id", ""),
            fields=data.get("fields", []),
        )


class TemplateRegistry:
    """
    Loads and caches template manifests from the templates directory.
    Each template lives in its own folder with a manifest.json file.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self._cache: dict[str, TemplateRecord] = {}
        self._loaded = False

    def load_all(self) -> None:
        """Scan templates_dir and load all active template manifests."""
        if not self.templates_dir.exists():
            return

        for entry in self.templates_dir.iterdir():
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                record = TemplateRecord.from_dict(data)
                if record.status == "active":
                    self._cache[record.template_id] = record
            except Exception:
                # Skip invalid manifests — log in production
                pass

        self._loaded = True

    def get(self, template_id: str) -> Optional[TemplateRecord]:
        """Return a template record by ID, loading if needed."""
        if not self._loaded:
            self.load_all()
        return self._cache.get(template_id)

    def get_manifest(self, template_id: str) -> dict:
        """
        Return a template manifest dict for use in Gemma review payloads.

        Returns an empty dict if the template is not found.
        """
        record = self.get(template_id)
        if not record:
            return {}
        return {
            "template_id": record.template_id,
            "template_family": record.template_family,
            "display_name": record.display_name,
            "template_version": record.template_version,
            "runtime_hints": {
                "default_input_mode": record.runtime_hints.default_input_mode,
                "primary_language": record.runtime_hints.primary_language,
                "alignment_mode": record.runtime_hints.alignment_mode,
                "unknown_field_policy": record.runtime_hints.unknown_field_policy,
                "preferred_extractors": record.runtime_hints.preferred_extractors,
            },
        }

    def list_active(self) -> list[TemplateRecord]:
        """Return all active template records."""
        if not self._loaded:
            self.load_all()
        return list(self._cache.values())

    def load_schema(self, template_id: str) -> Optional[TemplateSchema]:
        """Load and return the field schema for a given template."""
        record = self.get(template_id)
        if not record:
            return None

        schema_path = self.templates_dir / template_id / record.schema_ref.schema_path.split("/")[-1]
        if not schema_path.exists():
            # Try relative to template folder
            schema_path = self.templates_dir / template_id / "schema.json"

        if not schema_path.exists():
            raise TemplateRegistryError(
                ErrorCode.TEMPLATE_SCHEMA_LOAD_FAILED,
                f"Schema file not found for template {template_id}: {schema_path}",
                retryable=False,
            )

        return TemplateSchema.from_json_file(str(schema_path))

    def reload(self) -> None:
        """Clear cache and re-scan templates directory."""
        self._cache.clear()
        self._loaded = False
        self.load_all()
