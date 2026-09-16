# Offene Punkte - Modul C

## GitHub-Repo-Sichtbarkeit von dita_validation
Ist das Repo privat, muss unter Settings > Actions > General > Access
der Zugriff fuer A/B einmalig manuell freigegeben werden. Noch nicht
durchgefuehrt.

## End-to-End-Test des repo-uebergreifenden Aufrufs steht noch aus
Der eigentliche Aufruf von A oder B aus per "uses: ^<org^>/dita_validation/
.github/actions/validate@v1.0.0" konnte bisher nicht gegen zwei echte
GitHub-Repos getestet werden. Mechanik ist nach offizieller
GitHub-Actions-Dokumentation gebaut und einzelne Bausteine (PATH-
Bereitstellung von DITA-OT, github.action_path) real verifiziert, der
komplette Ablauf aber noch nicht als Ganzes.

## Python 3.14 noch nicht real verifiziert
validate_dita.py wurde mit Python 3.12 entwickelt und getestet
(Sandbox-Einschraenkung), action.yml pinnt aber verbindlich Python 3.14.
Vor produktivem Einsatz mit 3.14 real gegenpruefen.
