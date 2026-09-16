# dita_validation

Modul C aus dem modularisierten DITA-Dokumentenmanagement
(Konfigurationsprotokoll v16, Abschnitt 7). Prüft DITA-Content (Topics,
Maps) gegen die passenden DTDs sowie gegen die verbindlichen
Datei-Konventionen (DOCTYPE-Version, `xml:lang`) – kundenneutral,
einmalig/global, für jedes Produkt verbindlich (kein `vars.USE_MODULE_X`
nötig, anders als bei den optionalen Modulen E/F/G/H).

## Wofür dieses Repo zuständig ist – und wofür nicht

- **Zuständig:** DTD-Konformität und Referenz-Integrität von `.dita`-/
  `.ditamap`-Dateien (Einzeldatei-Prüfung, optional ergänzt um eine
  transitive Root-Map-Prüfung), Konventionsprüfung (DOCTYPE „1.3",
  `xml:lang`).
- **Nicht zuständig:** `.tbx` (Modul F), `valuelists.xml`/
  `design-values.xml` (Module E/G/H) – Domäneneigene Dateiformate prüft
  das jeweils zuständige Modul selbst. Linkprüfung (Modul D),
  Metadaten-Schematron (Modul E), PDF-/HTML-Publikation (Module G/H).

## Struktur

```
dita_validation/
├── README.md                            ← diese Datei
├── OPEN_ISSUES.md                       ← echte offene Punkte, keine geloesten Design-Fragen
├── .gitignore
├── .github/actions/validate/
│   ├── action.yml                       ← Composite Action, von A/B aufgerufen
│   └── validate_dita.py                 ← Dateisuche, DTD-/Referenzpruefung via DITA-OT, Konventionspruefung
└── tests/                                ← manueller Selbsttest, kein CI-Job
    ├── valid/                            ← je ein valides Beispiel pro Typ
    └── invalid/                          ← isoliert fehlerhafte Gegenstuecke
```

## Aufruf aus A oder B

```yaml
- uses: actions/checkout@v4
- uses: <org>/dita_validation/.github/actions/validate@v1.0.0
  with:
    pfad: .
    root: docs/project_content.ditamap   # bei B allein: reuse/reusables.ditamap
```

Die Versionsnummer (`@v1.0.0`) wird von der aufrufenden Pipeline explizit
eingetragen – nie automatisch auf den neuesten Stand aktualisiert
(Konfigurationsprotokoll Abschnitt 6). `actions/checkout` ist notwendig:
Die Composite Action checkt das aufrufende Repo nicht automatisch aus.

## Wichtige praktische Hinweise

**Zwei Prüfmodi, keiner ersetzt den anderen.** Die Einzeldatei-Schleife
läuft immer und ist repo-topologie-unabhängig (funktioniert gegen A
allein, A+B, B allein, ohne vorher zu wissen, welche Datei „die" Root
ist). Der optionale `root`-Parameter ergänzt eine transitive Prüfung ab
einer Root-Map – deckt zusätzlich Fehler ab, die nur bei vollständiger
Schlüsselraum-Auflösung sichtbar werden (z. B. `keyref`-Ziele, die
standalone nur als Info `I`, nicht als Fehler gemeldet werden).

**DITA-OTs Exit-Code ist unzuverlässig.** Real mit DITA-OT 4.4.0
verifiziert: Bei echten DTD-Fehlern (Schweregrad `E`) meldet DITA-OT
trotzdem „BUILD SUCCESSFUL" und liefert Exit-Code 0. Auswertung erfolgt
stattdessen über das Message-ID-Muster `\[[A-Z]{4}\d{3}[EFW]\]` im
Log-Text – gilt für beide Prüfmodi gleichermaßen.

**Kein `lxml`, keine externen Python-Abhängigkeiten.** Die
Konventionsprüfung nutzt `xml.dom.minidom` aus der Standardbibliothek.
`lxml.etree.DTD` wäre für die DTD-Konformität selbst ohnehin ungeeignet:
real getestet, bricht an den echten DITA-1.3-DTDs mit „Maximum entity
amplification factor exceeded" ab (libxml2-Schutz gegen XML-Bomben,
ausgelöst durch die verschachtelte Parameter-Entity-Struktur der
offiziellen DTDs selbst).

**DITA-OT wird von diesem Modul unabhängig bereitgestellt**, kein
gemeinsames Setup-Modul mit D–H (bewusste Architekturentscheidung,
Konfigurationsprotokoll Abschnitt 4). Gecacht über `actions/cache`
(Schlüssel `dita-ot-4.4.0`), nur falls nicht bereits über PATH
verfügbar.

**Einmaliger manueller Schritt, falls dieses Repo privat ist:** Unter
„Settings → Actions → General → Access" muss der Zugriff für A/B
freigegeben werden (Details in `OPEN_ISSUES.md`).

**Vor produktivem Einsatz noch zu erledigen** (Details in
`OPEN_ISSUES.md`): Verifikation unter Python 3.14 (entwickelt/getestet
mit 3.12), sowie der komplette repo-übergreifende Aufruf aus einem
echten A- oder B-Repo.

## Tests lokal ausführen

Von der Repo-Wurzel aus, keine Installation nötig:
```
python .github\actions\validate\validate_dita.py --input tests\valid      (Exit-Code 0 erwartet)
python .github\actions\validate\validate_dita.py --input tests\invalid    (Exit-Code 1 erwartet)
```

Bewusst ein manueller Schritt, kein automatisierter CI-Job – vermeidet
zwei `.yml`-Dateien mit unklarem Verhältnis zueinander (eine für den
eigentlichen Aufruf durch A/B, eine nur für den Selbsttest).
