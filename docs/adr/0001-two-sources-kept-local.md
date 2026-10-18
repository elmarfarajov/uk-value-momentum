# ADR 0001: Two independent factor sources, kept local and fingerprinted

**Status:** accepted (Day 1)

## Context

A study of UK value and momentum needs monthly factor returns that are free of survivorship
bias: built from every company listed at the time, including those that later failed or were
taken over. That rules out anything built from today's index members (ADR 0003 measures by how
much). Two public sources meet the bar:

* **AQR Capital Management's data library.** The *Value and Momentum Everywhere* workbook
  (Asness, Moskowitz and Pedersen, 2013) carries UK value from July 1981 and UK momentum from
  January 1972. The *Quality Minus Junk* workbook (Asness, Frazzini and Pedersen, 2019) adds
  the UK market, SMB, HML in two forms, UMD and QMJ. Both are updated monthly, to July 2026 at
  the time of writing. Their UK data come from Datastream and Compustat.
* **The Exeter Xfi Centre** (Gregory, Tharyan and Christidis, 2013), built from the London
  Share Price Database with UK-specific breakpoints. It runs from October 1980 to June 2016.

Neither licence allows the files to be republished. AQR asks to be cited. Exeter limits use to
bona fide academic research.

## Decision

1. **Both sources are used, for different jobs.** AQR is the primary series because it is long
   and current. Exeter is the independent check where the two overlap, 1986 to 2016. A finding
   that holds only in one source is reported as such.
2. **Raw files are never committed.** `ukf data fetch` downloads them into `data/raw`, which is
   gitignored (`$UKF_DATA` overrides the location). Each file is recorded in
   `data/raw/manifest.json` with its URL, download time and SHA-256, so every number can be
   tied to the exact bytes it came from. `ukf data list` prints the record.
3. **Tests never need the real data.** `tests/conftest.py` writes synthetic files in each
   source's own format: AQR's note rows above a `DATE` header, Exeter's `1980m10` months inside
   a zip, and FRED's `.` for holidays. The full pipeline therefore runs in CI. Validation checks
   that need the real data report **SKIP**, never PASS, when it is absent.

## Consequences

* The repository can be public without redistributing licensed data. Anyone with the same
  downloads can reproduce every chart.
* AQR rebuilds its full history at each monthly update, so a later download can change past
  numbers. The manifest's hashes make that visible; notes record the download date.
* Exeter's files do not match its own paper. The market reproduces Table 1 of Gregory et al.
  (2013) to the printed precision, but momentum averages 0.99% a month against the published
  0.77%, and HML 0.39% against 0.31%. The files were evidently rebuilt after publication. The
  validation suite pins the market; the factor gap is reported as a finding, not hidden.
