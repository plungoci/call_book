"""Static IARU Region 1 amateur band plan reference data (160m to 70cm).

Not fetched live and not tied to any specific external source: these band
edges are the stable, widely published IARU Region 1 amateur allocations
that ANCOM's Romanian amateur radio regulation also follows. Always verify
against the current ANCOM authorization before relying on this for licensing
decisions — this is a quick reference, not a legal text.

The "shared allocation" table is general regulatory context (which primary
service, if any, shares or borders each band under the ITU Radio
Regulations) rather than an exhaustive or classified list of specific
military systems or frequencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AmateurBand:
    band: str
    frequency_range: str
    notes: str


@dataclass(frozen=True)
class SharedAllocation:
    band: str
    primary_or_shared_service: str


AMATEUR_BANDS: tuple[AmateurBand, ...] = (
    AmateurBand("160m", "1810–2000 kHz", "Secundară; unele țări limitează puterea noaptea"),
    AmateurBand("80m", "3500–3800 kHz", "Primară în Regiunea 1"),
    AmateurBand("60m", "5351.5–5366.5 kHz", "Secundară, putere max. 15 W PEP"),
    AmateurBand("40m", "7000–7200 kHz", "Primară în Regiunea 1"),
    AmateurBand("30m", "10100–10150 kHz", "Bandă WARC; numai CW/date, fără radiotelefonie"),
    AmateurBand("20m", "14000–14350 kHz", "Primară"),
    AmateurBand("17m", "18068–18168 kHz", "Bandă WARC"),
    AmateurBand("15m", "21000–21450 kHz", "Primară"),
    AmateurBand("12m", "24890–24990 kHz", "Bandă WARC"),
    AmateurBand("10m", "28000–29700 kHz", "Primară"),
    AmateurBand("6m", "50000–52000 kHz", "Secundară în Regiunea 1"),
    AmateurBand("4m", "70000–70500 kHz", "Alocare recentă; condițiile variază pe țări"),
    AmateurBand("2m", "144000–146000 kHz", "Primară"),
    AmateurBand("70cm", "430000–440000 kHz", "Secundară, partajată cu radiolocație"),
)

SHARED_ALLOCATIONS: tuple[SharedAllocation, ...] = (
    SharedAllocation("160m", "Fix / maritim mobil"),
    SharedAllocation("80m", "Fix / maritim mobil (în afara sub-benzii radioamator)"),
    SharedAllocation("60m", "Guvernamental / fix / mobil terestru"),
    SharedAllocation("40m", "Radiodifuziune (în afara Regiunii 1) / fix"),
    SharedAllocation("30m", "Fix (radioamatorul e secundar la nivel mondial)"),
    SharedAllocation("20m", "Fără partajare semnificativă"),
    SharedAllocation("17m", "Fără partajare semnificativă"),
    SharedAllocation("15m", "Fără partajare semnificativă"),
    SharedAllocation("12m", "Fără partajare semnificativă"),
    SharedAllocation("10m", "Fără partajare semnificativă"),
    SharedAllocation("6m", "Radiodifuziune TV / radiolocație (variază pe țări)"),
    SharedAllocation("4m", "Fostă utilizare guvernamentală în unele țări"),
    SharedAllocation("2m", "Fără partajare semnificativă (cu excepția sub-benzii satelit)"),
    SharedAllocation("70cm", "Radiolocație, inclusiv radar militar"),
)
