"""Taxonomy loader and accent-insensitive EN/FR query expansion."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from guideit_master.paths import get_taxonomy_dir


@dataclass(frozen=True, slots=True)
class SubcategorySpec:
    """Sub-subject category grouping playbooks inside a top-level domain."""

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Metadata describing one numbered playbook domain folder."""

    folder: str
    prefix: str
    subject: str
    description: str
    subcategories: tuple[SubcategorySpec, ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaConfig:
    """Validation rules loaded from taxonomy/schema.json."""

    required_fields: list[str]
    optional_fields: list[str]
    enums: dict[str, list[str]]
    required_sections: list[str]
    optional_sections: list[str]
    allowed_placeholder_email_domains: set[str]
    allowed_public_dns_ips: set[str]


@dataclass(frozen=True, slots=True)
class KeywordMapEntry:
    """Maps messy EN/FR user phrases to canonical tags, domains, and error codes."""

    phrases: list[str]
    tags: list[str]
    domains: list[str]
    error_codes: list[str]


@dataclass(frozen=True, slots=True)
class TaxonomyConfig:
    """Combined taxonomy configuration loaded from taxonomy/*.json."""

    domains_by_folder: dict[str, DomainSpec]
    schema: SchemaConfig
    keyword_entries: list[KeywordMapEntry]


_EN_NEG_CONTRACTION_RE = re.compile(
    r"\b(?:can|won|don|doesn|didn|isn|aren|wasn|weren|haven|hasn|hadn|couldn|wouldn|shouldn|mustn)'t\b"
)
_EN_PRON_CONTRACTION_RE = re.compile(
    r"\b(?:i'm|i've|i'll|i'd|you're|you've|you'll|you'd|he's|she's|it's|"
    r"we're|we've|we'll|we'd|they're|they've|they'll|that's|there's|what's|who's|let's)\b"
)
_EN_POSSESSIVE_RE = re.compile(r"\b([a-z0-9]+)'s\b")
_FR_ELISION_RE = re.compile(r"\b(?:l|d|n|s|j|qu|c|m|t)'([a-z0-9])")
_SEARCH_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")

# Deliberately keep "son" (French "sound"), "up", "down", "out", "off", "full",
# "slow", "lost", "work", "error", "failed", "blocked", "denied" searchable.
SEARCH_STOPWORDS: frozenset[str] = frozenset(
    {
        # English function / filler words
        "a",
        "an",
        "the",
        "and",
        "or",
        "not",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "from",
        "by",
        "as",
        "into",
        "about",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "my",
        "your",
        "our",
        "their",
        "we",
        "you",
        "they",
        "he",
        "she",
        "i",
        "me",
        "us",
        "them",
        "do",
        "does",
        "did",
        "done",
        "can",
        "cant",
        "cannot",
        "could",
        "couldnt",
        "will",
        "wont",
        "would",
        "wouldnt",
        "should",
        "shouldnt",
        "may",
        "might",
        "must",
        "have",
        "has",
        "had",
        "having",
        "get",
        "got",
        "getting",
        "keeps",
        "keep",
        "just",
        "very",
        "too",
        "so",
        "also",
        "when",
        "where",
        "why",
        "how",
        "what",
        "which",
        "who",
        "if",
        "then",
        "than",
        "but",
        "no",
        "dont",
        "doesnt",
        "didnt",
        "isnt",
        "arent",
        "wasnt",
        "werent",
        "havent",
        "hasnt",
        "able",
        "unable",
        "trying",
        "try",
        "tried",
        "need",
        "needs",
        "want",
        "wants",
        "help",
        "please",
        "issue",
        "issues",
        "problem",
        "problems",
        "working",
        # French function / filler words
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "et",
        "ou",
        "ne",
        "pas",
        "plus",
        "aucun",
        "aucune",
        "est",
        "sont",
        "etre",
        "au",
        "aux",
        "en",
        "dans",
        "sur",
        "sous",
        "pour",
        "par",
        "avec",
        "sans",
        "ce",
        "cet",
        "cette",
        "ces",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "sa",
        "ses",
        "notre",
        "nos",
        "votre",
        "vos",
        "leur",
        "leurs",
        "je",
        "tu",
        "il",
        "elle",
        "on",
        "nous",
        "vous",
        "ils",
        "elles",
        "se",
        "me",
        "te",
        "qui",
        "que",
        "quoi",
        "dont",
        "si",
        "mais",
        "comme",
        "tout",
        "tous",
        "toute",
        "toutes",
        "tres",
        "trop",
        "peut",
        "peux",
        "pouvoir",
        "impossible",
        "fonctionne",
        "marche",
        "probleme",
        "problemes",
        "arrive",
        "arriver",
        "veut",
        "veux",
        "faire",
        "fait",
    }
)


def normalize_text(text: str) -> str:
    """Lowercase text, strip Unicode diacritics, and normalize apostrophes/whitespace."""
    cleaned = text.replace("’", "'").replace("–", "-").replace("—", "-")
    decomposed = unicodedata.normalize("NFKD", cleaned)
    ascii_ish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_ish.lower().split())


def extract_search_tokens(text: str) -> list[str]:
    """Extract ordered meaningful search tokens after stripping EN/FR contractions & stop words."""
    norm = normalize_text(text)
    if not norm:
        return []
    cleaned = _EN_NEG_CONTRACTION_RE.sub(" ", norm)
    cleaned = _EN_PRON_CONTRACTION_RE.sub(" ", cleaned)
    cleaned = _EN_POSSESSIVE_RE.sub(r"\1", cleaned)
    cleaned = _FR_ELISION_RE.sub(r"\1", cleaned)

    tokens: list[str] = []
    seen: set[str] = set()
    for tok in _SEARCH_TOKEN_RE.findall(cleaned):
        if len(tok) == 1 and tok.isalpha():
            continue
        if tok in SEARCH_STOPWORDS:
            continue
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return tokens


def load_taxonomy(root_dir: Path | None = None) -> TaxonomyConfig:
    """Load domains.json, schema.json, and keyword_map.json from taxonomy/."""
    tax_dir = get_taxonomy_dir(root_dir)
    domains_raw = json.loads((tax_dir / "domains.json").read_text(encoding="utf-8"))
    schema_raw = json.loads((tax_dir / "schema.json").read_text(encoding="utf-8"))
    kw_raw = json.loads((tax_dir / "keyword_map.json").read_text(encoding="utf-8"))

    domains_by_folder: dict[str, DomainSpec] = {}
    for entry in domains_raw.get("domains", []):
        subcategories = tuple(
            SubcategorySpec(id=str(sub["id"]), label=str(sub["label"]))
            for sub in entry.get("subcategories", [])
        )
        spec = DomainSpec(
            folder=str(entry["folder"]),
            prefix=str(entry["prefix"]),
            subject=str(entry["subject"]),
            description=str(entry.get("description", "")),
            subcategories=subcategories,
        )
        domains_by_folder[spec.folder] = spec

    schema = SchemaConfig(
        required_fields=list(schema_raw.get("required_fields", [])),
        optional_fields=list(schema_raw.get("optional_fields", [])),
        enums={k: list(v) for k, v in schema_raw.get("enums", {}).items()},
        required_sections=list(schema_raw.get("required_sections", [])),
        optional_sections=list(schema_raw.get("optional_sections", [])),
        allowed_placeholder_email_domains={
            d.lower() for d in schema_raw.get("allowed_placeholder_email_domains", [])
        },
        allowed_public_dns_ips=set(schema_raw.get("allowed_public_dns_ips", [])),
    )

    keyword_entries: list[KeywordMapEntry] = []
    for entry in kw_raw.get("entries", []):
        keyword_entries.append(
            KeywordMapEntry(
                phrases=[str(p) for p in entry.get("phrases", [])],
                tags=[str(t) for t in entry.get("tags", [])],
                domains=[str(d) for d in entry.get("domains", [])],
                error_codes=[str(c) for c in entry.get("error_codes", [])],
            )
        )

    return TaxonomyConfig(
        domains_by_folder=domains_by_folder,
        schema=schema,
        keyword_entries=keyword_entries,
    )


def load_resources(root_dir: Path | None = None) -> list[dict[str, object]]:
    """Load curated external tools and websites from taxonomy/resources.json."""
    res_file = get_taxonomy_dir(root_dir) / "resources.json"
    if not res_file.is_file():
        return []
    raw = json.loads(res_file.read_text(encoding="utf-8"))
    return list(raw.get("resources", []))


def _phrase_in_query(norm_phrase: str, norm_query: str) -> bool:
    """Return True if norm_phrase appears in norm_query on token boundaries."""
    if not norm_phrase or not norm_query:
        return False
    pattern = r"(?<![a-z0-9_])" + re.escape(norm_phrase) + r"(?![a-z0-9_])"
    return re.search(pattern, norm_query) is not None


def expand_query(
    query: str,
    taxonomy: TaxonomyConfig,
) -> tuple[list[str], list[str], list[str]]:
    """Expand a raw EN/FR query into (canonical_tags, suggested_domains, error_codes)."""
    norm_query = normalize_text(query)
    if not norm_query:
        return [], [], []

    tags: list[str] = []
    domains: list[str] = []
    error_codes: list[str] = []

    for entry in taxonomy.keyword_entries:
        matched = False
        for phrase in entry.phrases:
            if _phrase_in_query(normalize_text(phrase), norm_query):
                matched = True
                break
        if not matched:
            for code in entry.error_codes:
                if _phrase_in_query(normalize_text(code), norm_query):
                    matched = True
                    break
        if matched:
            for tag in entry.tags:
                if tag not in tags:
                    tags.append(tag)
            for domain in entry.domains:
                if domain not in domains:
                    domains.append(domain)
            for code in entry.error_codes:
                if code not in error_codes:
                    error_codes.append(code)

    return tags, domains, error_codes
