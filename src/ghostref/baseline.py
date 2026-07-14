"""Baseline support: adopt ghostref on a legacy tree without fixing it first.

A baseline file records a stable fingerprint per existing finding. Later
scans filter findings whose fingerprint is baselined, so CI only fails on
*new* ghosts. Fingerprints deliberately exclude line numbers — moving a
lying comment should not resurrect it — and use paths relative to the scan
root so the file is portable between machines.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence, Set

from ghostref.resolve import Finding

BASELINE_VERSION = 1


def _relative(file: str, root: Path) -> str:
    try:
        return Path(file).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(file).as_posix()


def fingerprint(finding: Finding, root: Path) -> str:
    """Stable identity of a finding: path (relative), token, and kind."""
    payload = "|".join((_relative(finding.file, root), finding.token, finding.kind))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class Baseline:
    """A set of accepted fingerprints, loadable from / dumpable to JSON."""

    fingerprints: Set[str] = field(default_factory=set)

    @classmethod
    def from_findings(cls, findings: Sequence[Finding], root: Path) -> "Baseline":
        return cls({fingerprint(finding, root) for finding in findings})

    @classmethod
    def load(cls, path: Path) -> "Baseline":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != BASELINE_VERSION:
            raise ValueError(
                f"{path}: not a ghostref baseline (expected version {BASELINE_VERSION})"
            )
        entries = data.get("entries", [])
        return cls({entry["fingerprint"] for entry in entries})

    def dump(self, findings: Sequence[Finding], root: Path) -> str:
        """Serialize *findings* as baseline JSON (sorted, diff-friendly)."""
        entries = [
            {
                "fingerprint": fingerprint(finding, root),
                "file": _relative(finding.file, root),
                "token": finding.token,
                "kind": finding.kind,
            }
            for finding in findings
        ]
        entries.sort(key=lambda entry: (entry["file"], entry["token"], entry["kind"]))
        unique = []
        seen = set()
        for entry in entries:
            if entry["fingerprint"] not in seen:
                seen.add(entry["fingerprint"])
                unique.append(entry)
        return json.dumps(
            {"version": BASELINE_VERSION, "entries": unique},
            indent=2,
            sort_keys=True,
        ) + "\n"

    def filter(self, findings: Sequence[Finding], root: Path) -> List[Finding]:
        """Findings not covered by this baseline, order preserved."""
        return [
            finding
            for finding in findings
            if fingerprint(finding, root) not in self.fingerprints
        ]
