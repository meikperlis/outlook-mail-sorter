# Projektgedächtnis – Outlook-Mail-Sortierer

## 1. Ziel des Projekts

Ein lokaler und später cloudbasierter Outlook-Mail-Sortierer für ein privates Microsoft-/Outlook-Konto.

Er soll neue E-Mails regelmäßig prüfen, passende Zielordner vorschlagen bzw. nutzen, fehlende sinnvolle Ordner kontrolliert anlegen und Mails automatisch verschieben — ohne Ordnerwildwuchs und ohne Blackbox-KI.

- Repository: `meikperlis/outlook-mail-sorter`

## 2. Wichtige Architektur- und Produktentscheidungen

- Python statt einer komplexeren Plattform
- Microsoft Graph v1.0 für Mailzugriff
- MSAL Python + Device Code Flow
- Kein Client Secret, da privates Konto / Public Client
- Authority für private Konten:
  - `https://login.microsoftonline.com/consumers`
- Erst vollständig im Dry-Run, dann schrittweise echte Aktionen
- Keine serverseitigen Outlook-Regeln
- Keine Löschungen
- Unklare Mails bleiben im Posteingang, statt in einen künstlichen Prüf-Ordner verschoben zu werden
- Die Ordnerstruktur soll aus echten wiederkehrenden Mustern wachsen, nicht aus Einzelfällen
- Neue Ordner nur bei stabilen Themen und zusätzlich nur dann, wenn im aktuellen Lauf mindestens 2 Mails wirklich dorthin möchten
- Lokale Preview und dauerhafter Cloud-Betrieb sind bewusst getrennt:
  - lokal für Entwicklung, Prüfung und Backfill
  - Azure Function für laufende Automatik

## 3. Was bereits umgesetzt ist

### Lokal

- Login-Test per Device Code Flow
- Konto-Test über `GET /me`
- Top-Level-Mailordner auslesen
- Inbox lesen
- regelbasierte Kategorisierung
- verschachtelte Ordnerauflösung
- Dry-Run / Apply-Modus
- JSON-Protokolle pro Lauf
- Backfill-Modus für Altbestand
- Langzeit-Themen-Gedächtnis (`topic_memory`)
- Themen-Stabilität über:
  - Häufigkeit
  - mehrere Läufe
  - mehrere Absender
  - kontrolliertes Veralten
- Vorsichtige Nachschärfung der Regeln:
  - `order` entfernt als zu breites Signal
  - `konto` entfernt als zu breites Signal
  - stärkere Sicherheitsmuster ergänzt
  - Body-Preview bei den meisten Kategorien nicht mehr als Hauptsignal

### Cloud

- Azure-Abonnement eingerichtet
- Ressourcengruppe:
  - `rg-outlook-sorter`
- Storage Account:
  - `stoutlooksortermeik`
- Blob-Container:
  - `outlook-sorter-state`
- Function App:
  - `func-outlook-sorter-meik`
- Timer Trigger aktiv
- Cloud-State in Blob Storage:
  - `token_cache.json`
  - `topic_memory.json`
  - `logs/...`
- Deployment erfolgreich abgeschlossen
- Hintergrunddienst läuft automatisch

### Bestandsbereinigung

- erster Backfill: 40 Mails verschoben
- zweiter Backfill: 1 weitere Mail verschoben
- restlicher Bestand bewusst nicht weiter automatisch einsortiert, weil er nicht robust genug klassifizierbar war

### GitHub

- privates Repository erstellt und hochgeladen
- sensible Dateien ausgeschlossen:
  - Token-Caches
  - Logs
  - echtes `topic_memory.json`
  - lokale Settings

## 4. Aktueller technischer Stand

### Code-Version

- aktuelle lokale Version: Version 15

### Wichtige Dateien

- `main.py`
- `auth.py`
- `graph_client.py`
- `rules.py`
- `mailbox_analyzer.py`
- `topic_memory.py`
- `folder_resolver.py`
- `run_logger.py`
- `state_store.py`
- `cloud_runner.py`
- `function_app.py`
- `config.py`

### Wichtige Modi

- `preview`
- `apply`
- `backfill-preview`
- `backfill-apply`

### Wichtige Konfiguration

```python
MESSAGE_LIMIT = 10
BACKFILL_MESSAGE_LIMIT = 200
ANALYSIS_MESSAGE_LIMIT = 200
MIN_MESSAGES_PER_TOPIC = 5
MIN_RUNS_FOR_STABLE_TOPIC = 2
MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC = 10
MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC = 2
STRONG_TOPIC_MESSAGE_THRESHOLD = 20
STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD = 5
MIN_TARGET_MESSAGES_TO_CREATE_FOLDER = 2
```

### Aktive stabile Zielstruktur

- `Finanzen/Bestellungen`
- `Finanzen/Rechnungen`
- `Dokumente/Rechtliches`
- `Konten & Sicherheit`
- `Newsletter`

### Cloud-App-Settings

- `OUTLOOK_SORTER_CLIENT_ID`
- `OUTLOOK_SORTER_AUTHORITY`
- `OUTLOOK_SORTER_STATE_CONTAINER`
- `OUTLOOK_SORTER_SCHEDULE`
- `CREATE_MISSING_FOLDERS`
- `MOVE_MESSAGES`

### Timer

- aktuell alle 10 Minuten:
  - `0 */10 * * * *`

## 5. Offene Punkte

- Keine offene Kernfunktion mehr für den privaten Produktivbetrieb
- `Tools & Dienste` wird erkannt, aber bewusst noch nicht angelegt, da derzeit zu wenig echte Zielmails vorhanden sind
- README ist funktional, aber noch lang und eher entwicklungsnah; für ein öffentliches Portfolio wäre später eine schlankere, polierte Fassung sinnvoll

### Optional

- bessere Tests
- feinere Themenregeln
- öffentlichkeitsfähige Demo-Daten
- GitHub-Repo später ggf. öffentlich machen
- Firmenvariante separat designen

## 6. Nächste sinnvolle Schritte

1. Cloud-Dienst einige Tage beobachten
2. Prüfen, ob neue Mails sauber einsortiert werden
3. Bei Fehlklassifikationen nur gezielt nachschärfen, nicht das System unnötig aufblasen
4. Bei Bedarf:
   - kleine Test-Suite ergänzen
   - README vereinfachen
   - portfolio-taugliche Projektseite bauen
5. Für Firmenkontext später separat planen:
   - Exchange Online
   - Application Permissions
   - Admin Consent
   - Zugriffsbeschränkung auf bestimmte Postfächer
   - Shared Mailboxes / Team-Postfächer

## 7. Besondere Sicherheits- oder Betriebsdetails

- Niemals Token-Dateien committen
- Niemals öffentlich hochladen:
  - `.token_cache.json`
  - `token_cache.json`
  - `logs/`
  - `topic_memory.json`
  - `local.settings.json`
- `.gitignore` ist entsprechend vorbereitet
- In GitHub liegen nur:
  - Code
  - README
  - sichere Beispielkonfigurationen
- Lokale echte Schreibvorgänge erfordern:
  - `CREATE_MISSING_FOLDERS=true`
  - `MOVE_MESSAGES=true`
- Standardmäßig bleibt das System defensiv
- Die Cloud-Funktion arbeitet nicht interaktiv; sie nutzt den in Blob Storage hinterlegten Token-Cache
- Wenn sich Anmeldedaten ungültig machen oder Microsoft eine erneute Zustimmung verlangt, muss lokal erneut per Device Code Flow angemeldet und der neue Token-Cache wieder hochgeladen werden
- Es werden keine Mails gelöscht
- Es werden keine Outlook-Regeln serverseitig erstellt

## Produktgrundsatz

> Lieber eine Mail zu wenig automatisch einsortieren als eine falsche Mail unsichtbar machen.
