#!/usr/bin/env python3
"""
validate_dita.py - Modul C (dita_validation)

Prueft DITA-Content (Topics, Maps) gegen die passenden DTDs sowie gegen
die verbindlichen Datei-Konventionen aus dem Konfigurationsprotokoll
(Abschnitt 4): DOCTYPE-Public-ID mit Versionsangabe "1.3", xml:lang auf
dem Wurzelelement.

Zustaendigkeit (Protokoll Abschnitt 4/7):
  - NUR DITA-Content (.dita/.ditamap) gegen Standard-OASIS-DTDs.
  - NICHT zustaendig fuer .tbx (Modul F) oder valuelists.xml/
    design-values.xml (Module E/G/H) - diese Dateiendungen werden von
    der Dateisuche gar nicht erst erfasst.

Drei Pruefmechanismen (der dritte optional, ergaenzend):
  1. DTD-Konformitaet + Referenz-Integritaet je Einzeldatei (mapref/
     keyref/conref): Aufruf von DITA-OT (`dita -v -i ... -f dita -o ...`),
     Log-Text gegen das dokumentierte Message-ID-Muster ausgewertet:
       [PPPPnnnS]  P=Praefix (4 Grossbuchstaben), n=Nummer (3 Ziffern),
                   S=Schweregrad (E/F/W/I)
     E/F blockieren, W warnt, I wird ignoriert.
  2. Konventionspruefung (DOCTYPE "1.3", xml:lang): einfaches,
     nicht-validierendes XML-Parsen ueber die Python-Standardbibliothek
     (xml.dom.minidom) - kein DTD-Laden, keine externe Abhaengigkeit
     noetig. (lxml.etree.DTD wurde fuer die DTD-Konformitaet selbst
     bewusst NICHT verwendet - die echten DITA-1.3-DTDs loesen libxml2s
     Amplification-Schutz aus, siehe OPEN_ISSUES.md. Da DITA-OT dieselbe
     Pruefung zuverlaessig ohne dieses Problem leistet und fuer die
     Konventionspruefung die Standardbibliothek ausreicht, ist dieses
     Skript ohne externe Python-Abhaengigkeiten lauffaehig.)
  3. Optionale transitive Root-Pruefung (--root): validiert die gesamte
     mapref-Kette einer Root-Map in einem Rutsch. Root ist konfigurierbar
     (Planungs-Chat-Rueckmeldung): docs/project_content.ditamap bei A
     allein/A+B, reuse/reusables.ditamap bei B allein. Faengt zusaetzlich
     Referenz-/Keyref-Fehler ab, die bei Einzeldatei-Pruefung mangels
     vollstaendigem Keyspace-Kontext nur als Info statt Fehler gemeldet
     wuerden (real verifiziert). Ergaenzt, ersetzt NICHT die
     Einzeldatei-Schleife (Schritt 1) - diese bleibt in allen
     Konstellationen zusaetzlich bestehen (repo-topologie-unabhaengig,
     faengt auch verwaiste, nicht in der Root-Map verankerte Dateien ab).

Aufruf:
    python validate_dita.py --input <repo1> [<repo2> ...] [--dita-ot <pfad-zur-dita.bat>] [--root <root-map>]

Exit-Code:
    0  - keine Fehler (E/F). Warnungen (W) moeglich, blockieren nicht.
    1  - mindestens ein Fehler (E/F) oder Konventionsverstoss gefunden.
    2  - Aufruffehler (z.B. DITA-OT nicht gefunden, Pfad existiert nicht).
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import xml.dom.minidom
from xml.parsers.expat import ExpatError

# --- Konstanten --------------------------------------------------------

# Dokumentierte DITA-OT-Message-ID-Konvention: 4 Grossbuchstaben-Praefix,
# 3-stellige Nummer, Schweregrad-Buchstabe (I/W/E/F).
MESSAGE_MUSTER = re.compile(r"\[([A-Z]{4}\d{3})([EFW])\]")

GEFORDERTE_VERSION = "1.3"

# Bekannter Windows-Installationspfad (siehe Projektwissen). Wird nur
# als Fallback genutzt, wenn "dita"/"dita.bat" nicht ueber PATH
# gefunden wird oder --dita-ot nicht gesetzt ist.
DITA_OT_FALLBACK_WINDOWS = r"C:\Program Files\dita-ot\dita-ot-4.4\bin\dita.bat"


# --- Datenklassen (einfach gehalten, keine externen Abhaengigkeiten) ---

class Befund:
    def __init__(self, datei, kategorie, schweregrad, meldung):
        self.datei = datei
        self.kategorie = kategorie      # "DTD/Referenz" oder "Konvention"
        self.schweregrad = schweregrad  # "FEHLER" oder "WARNUNG"
        self.meldung = meldung

    def __str__(self):
        return f"[{self.schweregrad}] {self.datei} ({self.kategorie}): {self.meldung}"


# --- Schritt 1: Dateien finden -----------------------------------------

def find_dita_files(wurzelpfade):
    """
    Sucht rekursiv nach .dita- und .ditamap-Dateien unterhalb der
    uebergebenen Wurzelpfade. Keine Ordnerannahmen (wichtig, da B als
    Submodul in A eingebunden sein kann - siehe Chatverlauf). .git wird
    ausgeschlossen.
    """
    gefunden = []
    for wurzel in wurzelpfade:
        wurzel = Path(wurzel)
        if not wurzel.exists():
            raise FileNotFoundError(f"Pfad existiert nicht: {wurzel}")
        for muster in ("*.dita", "*.ditamap"):
            for datei in wurzel.rglob(muster):
                if ".git" in datei.parts:
                    continue
                gefunden.append(datei)
    # Duplikate entfernen (falls sich uebergebene Pfade ueberschneiden),
    # Reihenfolge stabil halten.
    gesehen = set()
    eindeutig = []
    for datei in gefunden:
        auf = datei.resolve()
        if auf not in gesehen:
            gesehen.add(auf)
            eindeutig.append(datei)
    return eindeutig


# --- Schritt 2: DTD-Konformitaet + Referenz-Integritaet (DITA-OT) ------

def dita_ot_ausfuehrbare_finden(explizit_angegeben):
    if explizit_angegeben:
        pfad = Path(explizit_angegeben)
        if pfad.exists():
            return str(pfad)
        raise FileNotFoundError(f"--dita-ot Pfad nicht gefunden: {pfad}")

    for name in ("dita", "dita.bat"):
        gefunden = shutil.which(name)
        if gefunden:
            return gefunden

    fallback = Path(DITA_OT_FALLBACK_WINDOWS)
    if fallback.exists():
        return str(fallback)

    raise FileNotFoundError(
        "DITA-OT nicht gefunden (weder ueber PATH noch am bekannten "
        f"Fallback-Pfad '{DITA_OT_FALLBACK_WINDOWS}'). Bitte --dita-ot "
        "explizit angeben."
    )


def check_dtd(datei, dita_ot_pfad, temp_basis):
    """
    Ruft DITA-OT fuer eine einzelne Datei auf und wertet den Log-Text
    nach dem dokumentierten Message-ID-Muster aus. Gibt eine Liste von
    Befund-Objekten zurueck (leer = keine Beanstandung).
    """
    befunde = []
    ausgabe_ordner = Path(temp_basis) / f"out_{abs(hash(str(datei)))}"

    try:
        ergebnis = subprocess.run(
            [dita_ot_pfad, "-v", "-i", str(datei), "-f", "dita",
             "-o", str(ausgabe_ordner)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        befunde.append(Befund(datei, "DTD/Referenz", "FEHLER",
                               "DITA-OT-Aufruf nach 120s abgebrochen (Timeout)."))
        return befunde

    log_text = (ergebnis.stdout or "") + (ergebnis.stderr or "")
    treffer = MESSAGE_MUSTER.findall(log_text)

    for message_id, schwere in treffer:
        voller_code = f"[{message_id}{schwere}]"
        # zugehoerige Zeile fuer Kontext im Log suchen (erste passende Zeile)
        kontext = next(
            (zeile.strip() for zeile in log_text.splitlines() if voller_code in zeile),
            voller_code,
        )
        if schwere in ("E", "F"):
            befunde.append(Befund(datei, "DTD/Referenz", "FEHLER", kontext))
        elif schwere == "W":
            befunde.append(Befund(datei, "DTD/Referenz", "WARNUNG", kontext))
        # "I" (Info) wird bewusst ignoriert

    return befunde


def check_transitive(root_datei, dita_ot_pfad, temp_basis):
    """
    Ergaenzende, optionale Pruefung: transitive Validierung ueber die
    gesamte mapref-Kette einer Root-Map (Abschnitt 7/Planungs-Chat-
    Rueckmeldung: docs/project_content.ditamap bei A allein/A+B,
    reuse/reusables.ditamap bei B allein).

    Ersetzt NICHT die Einzeldatei-Schleife (check_dtd), ergaenzt sie:
    faengt zusaetzlich Referenz-/Keyref-Fehler ab, die bei
    Einzeldatei-Pruefung mangels vollstaendigem Keyspace-Kontext nur als
    Info statt Fehler gemeldet wuerden (real verifiziert, siehe
    OPEN_ISSUES.md). Nutzt dieselbe Log-Text-Auswertung wie check_dtd -
    auch der transitive DITA-OT-Lauf liefert bei E-Befunden weiterhin
    Exit-Code 0 (real bestaetigt), der Exit-Code allein ist also auch
    hier kein verlaesslicher Indikator.
    """
    befunde = []
    ausgabe_ordner = Path(temp_basis) / "transitiv_out"

    try:
        ergebnis = subprocess.run(
            [dita_ot_pfad, "-v", "-i", str(root_datei), "-f", "dita",
             "-o", str(ausgabe_ordner)],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        befunde.append(Befund(root_datei, "Transitiv", "FEHLER",
                               "DITA-OT-Aufruf (transitiv) nach 180s abgebrochen (Timeout)."))
        return befunde

    log_text = (ergebnis.stdout or "") + (ergebnis.stderr or "")
    treffer = MESSAGE_MUSTER.findall(log_text)

    for message_id, schwere in treffer:
        voller_code = f"[{message_id}{schwere}]"
        kontext = next(
            (zeile.strip() for zeile in log_text.splitlines() if voller_code in zeile),
            voller_code,
        )
        if schwere in ("E", "F"):
            befunde.append(Befund(root_datei, "Transitiv", "FEHLER", kontext))
        elif schwere == "W":
            befunde.append(Befund(root_datei, "Transitiv", "WARNUNG", kontext))
        # "I" (Info) wird bewusst ignoriert

    return befunde

def check_doctype_version(datei):
    """Prueft, ob die DOCTYPE-Public-ID die Versionsangabe '1.3' enthaelt."""
    try:
        dok = xml.dom.minidom.parse(str(datei))
    except ExpatError as e:
        return [Befund(datei, "Konvention", "FEHLER",
                        f"Datei nicht als XML lesbar: {e}")]

    doctype = dok.doctype
    public_id = doctype.publicId if doctype else None
    if not public_id:
        return [Befund(datei, "Konvention", "FEHLER",
                        "Kein DOCTYPE mit Public-ID gefunden.")]
    if GEFORDERTE_VERSION not in public_id:
        return [Befund(datei, "Konvention", "FEHLER",
                        f"DOCTYPE-Public-ID ohne Versionsangabe '{GEFORDERTE_VERSION}': "
                        f"'{public_id}'")]
    return []


def check_xml_lang(datei):
    """Prueft, ob xml:lang am Wurzelelement gesetzt ist."""
    try:
        dok = xml.dom.minidom.parse(str(datei))
    except ExpatError:
        return []  # bereits von check_doctype_version gemeldet

    wurzel = dok.documentElement
    lang = wurzel.getAttribute("xml:lang")
    if not lang:
        return [Befund(datei, "Konvention", "FEHLER",
                        "xml:lang fehlt am Wurzelelement.")]
    return []


# --- Orchestrierung ------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Modul C - DTD- und Konventionspruefung fuer DITA-Content."
    )
    parser.add_argument("--input", nargs="+", required=True,
                         help="Ein oder mehrere Repo-Wurzelpfade (A allein, A+B, oder B allein).")
    parser.add_argument("--dita-ot", default=None,
                         help="Expliziter Pfad zu dita/dita.bat. Sonst: PATH, dann bekannter Fallback.")
    parser.add_argument("--root", default=None,
                         help="Optional: Pfad zu einer Root-Map fuer zusaetzliche transitive "
                              "Pruefung (z.B. docs/project_content.ditamap bei A allein/A+B, "
                              "reuse/reusables.ditamap bei B allein). Ergaenzt, ersetzt nicht "
                              "die Einzeldatei-Schleife.")
    args = parser.parse_args()

    try:
        dita_ot_pfad = dita_ot_ausfuehrbare_finden(args.dita_ot)
    except FileNotFoundError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2

    try:
        dateien = find_dita_files(args.input)
    except FileNotFoundError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2

    if not dateien:
        print("Keine .dita/.ditamap-Dateien gefunden.")
        return 0

    alle_befunde = []
    with tempfile.TemporaryDirectory(prefix="dita_validation_") as temp_basis:
        for datei in dateien:
            alle_befunde.extend(check_dtd(datei, dita_ot_pfad, temp_basis))
            alle_befunde.extend(check_doctype_version(datei))
            alle_befunde.extend(check_xml_lang(datei))

        if args.root:
            root_pfad = Path(args.root)
            if not root_pfad.exists():
                print(f"FEHLER: --root Pfad nicht gefunden: {root_pfad}", file=sys.stderr)
                return 2
            alle_befunde.extend(check_transitive(root_pfad, dita_ot_pfad, temp_basis))

    fehler = [b for b in alle_befunde if b.schweregrad == "FEHLER"]
    warnungen = [b for b in alle_befunde if b.schweregrad == "WARNUNG"]

    print(f"\nGeprueft: {len(dateien)} Datei(en)")
    print(f"Fehler:   {len(fehler)}")
    print(f"Warnungen: {len(warnungen)}\n")

    for b in fehler + warnungen:
        print(b)

    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
