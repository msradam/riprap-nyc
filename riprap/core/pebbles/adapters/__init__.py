"""Adapters — concrete fetchers keyed by short name in pebble manifests.

Each adapter is a Pebble subclass that knows how to fetch one *class* of
source (HTTP live, baked GeoJSON, model endpoint, ...). The manifest's
`adapter:` field is a short name resolved here in ADAPTERS.
"""
from __future__ import annotations

from riprap.core.pebbles.adapters.baked_vector import BakedVectorPebble
from riprap.core.pebbles.adapters.ckan_records import CKANRecordsPebble
from riprap.core.pebbles.adapters.csv_points import CSVPointsPebble
from riprap.core.pebbles.adapters.local_corpus_with_ner import LocalCorpusWithNERPebble
from riprap.core.pebbles.adapters.python_call import PythonCallPebble
from riprap.core.pebbles.adapters.rest_json import RestJSONPebble
from riprap.core.pebbles.adapters.socrata_records import SocrataRecordsPebble

ADAPTERS: dict[str, type] = {
    "baked_vector": BakedVectorPebble,
    "ckan_records": CKANRecordsPebble,
    "csv_points": CSVPointsPebble,
    "local_corpus_with_ner": LocalCorpusWithNERPebble,
    "python_call": PythonCallPebble,
    "rest_json": RestJSONPebble,
    "socrata_records": SocrataRecordsPebble,
}

__all__ = [
    "ADAPTERS",
    "BakedVectorPebble",
    "CKANRecordsPebble",
    "CSVPointsPebble",
    "LocalCorpusWithNERPebble",
    "PythonCallPebble",
    "RestJSONPebble",
    "SocrataRecordsPebble",
]
