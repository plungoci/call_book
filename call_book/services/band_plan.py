"""ANCOM amateur radio band plan reference data (160m to 70cm).

Sourced from ANCOM's amateur radio frequency allocation table (as provided
by the user, matching the public band plan also mirrored at
https://yo3ram.ro/benzi-si-frecvente-ham-radio/), not fetched live. Always
verify against the current ANCOM authorization before relying on this for
licensing decisions — this is a quick reference, not a legal text.

Each segment's "allocation_status" is ANCOM's own usage-status code:
  - "NG"    — neguvernamental: exclusively amateur use in this segment.
  - "G"     — guvernamental: also allocated to a governmental service.
  - "G(A)"  — guvernamental, categorie A (see the ANCOM regulation for the
              precise definition; not assumed/expanded here).
A segment can carry more than one code (e.g. "G(A)/G/NG") when several
services share it. Every segment listed here includes "NG" — ANCOM's
amateur table only lists spectrum amateurs may use, some of it shared with
government use rather than exclusive. This is not an exhaustive or
classified list of specific military systems or frequencies, only ANCOM's
published sharing status per segment.

Footnote markers (*, **, (1), (2), (3)) are preserved verbatim from the
source table; their explanatory text is not reproduced here — see the
ANCOM regulation for what each one means.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BandSegment:
    band: str
    frequency_range: str
    allocation_status: str
    band_status: str

    @property
    def is_shared_with_government(self) -> bool:
        return self.allocation_status != "NG"


AMATEUR_SEGMENTS: tuple[BandSegment, ...] = (
    BandSegment("160m", "1.81–1.83 MHz", "G(A)/G/NG", "Primară"),
    BandSegment("160m", "1.83–1.85 MHz", "NG", "Primară"),
    BandSegment("160m", "1.85–2 MHz", "G(A)/NG", "Secundară"),
    BandSegment("80m", "3.5–3.8 MHz", "G(A)/G/NG", "Primară"),
    BandSegment("60m**", "5.3515–5.3665 MHz", "G(A)/G/NG", "Secundară"),
    BandSegment("40m", "7–7.1 MHz", "NG", "Primară"),
    BandSegment("40m", "7.1–7.2 MHz", "NG", "Primară"),
    BandSegment("30m", "10.1–10.15 MHz", "G(A)/NG", "Secundară"),
    BandSegment("20m", "14–14.25 MHz", "NG", "Primară"),
    BandSegment("20m", "14.25–14.35 MHz", "NG", "Primară"),
    BandSegment("17m", "18.068–18.168 MHz", "NG", "Primară"),
    BandSegment("15m", "21–21.45 MHz", "NG", "Primară"),
    BandSegment("12m", "24.89–24.99 MHz", "NG", "Primară"),
    BandSegment("10m", "28–29.7 MHz", "NG", "Primară"),
    BandSegment("6m", "50–52 MHz", "G(A)/NG", "Secundară"),
    BandSegment("4m", "70–70.3 MHz(2)", "G(A)/NG", "Secundară"),
    BandSegment("2m", "144–144.4 MHz", "NG", "Primară"),
    BandSegment("2m", "144.4–146 MHz", "NG", "Primară"),
    BandSegment("70cm", "431.2–432 MHz", "NG", "Primară"),
    BandSegment("70cm", "432–432.3 MHz", "NG", "Primară"),
    BandSegment("70cm", "432.3–433.05 MHz", "NG", "Primară"),
    BandSegment("70cm", "433.05–434.79 MHz", "NG", "Primară"),
    BandSegment("70cm", "434.79–438 MHz", "G(A)/NG", "Primară"),
    BandSegment("70cm", "438–440 MHz", "NG", "Primară"),
)

SHARED_SEGMENTS: tuple[BandSegment, ...] = tuple(
    segment for segment in AMATEUR_SEGMENTS if segment.is_shared_with_government
)
