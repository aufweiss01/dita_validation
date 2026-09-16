# Offene Punkte - Modul C

## GitHub-Repo-Sichtbarkeit von dita_validation
Ist das Repo privat, muss unter Settings > Actions > General > Access
der Zugriff fuer A/B einmalig manuell freigegeben werden. Noch nicht
durchgefuehrt.

## End-to-End-Test mit echtem Content steht noch aus
Der repo-uebergreifende Aufruf aus A ist im Pilot real gelaufen
(16.9.2026). v1.0.0 hat dabei aber die eigenen Dateien von DITA-OT
im Arbeitsordner mitgeprueft (korrigiert in v1.0.1). Ein sauberer
Durchlauf gegen echten A- und B-Content mit v1.0.1 steht noch aus.

## Python 3.14 noch nicht real verifiziert
validate_dita.py wurde mit Python 3.12 entwickelt und getestet
(Sandbox-Einschraenkung), action.yml pinnt aber verbindlich Python 3.14.
Vor produktivem Einsatz mit 3.14 real gegenpruefen.
