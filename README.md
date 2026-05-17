# Outlook Mail-Sortierer

Ein kleiner lokaler Outlook-Mail-Sortierer für ein privates Microsoft-/Outlook-Konto.

Diese Version ist weiterhin absichtlich konservativ:

- Anmeldung per **MSAL Python** und **Device Code Flow**
- Verwendung von **Microsoft Graph v1.0**
- lokaler Token-Cache, damit du dich nicht bei jedem Start neu anmelden musst
- Lesen von Konto, Top-Level-Ordnern und den letzten 10 Inbox-Mails
- regelbasierte Ordner-Vorschläge im **Dry-Run**
- Auflösen verschachtelter Zielpfade wie `Finanzen/Rechnungen`
- Anzeige, welche Zielordner bereits existieren und welche später angelegt werden müssten
- optionaler Ordner-Anlage-Modus hinter zwei bewussten Schaltern
- optionaler Verschiebe-Modus hinter eigener bewusster Sicherung
- Dry-Run-Analyse realer Bestandsmails, um eine schlanke Ordnerstruktur vorzuschlagen
- automatische Zielordnerwahl nur aus stabilen Themen, die im eigenen Postfach belegt sind
- JSON-Protokoll pro Lauf für nachvollziehbare Entscheidungen
- leichter Langzeitspeicher, damit Themen erst über mehrere Läufe stabil werden
- **keine** Verschiebungen
- **keine** Löschungen
- **keine** serverseitigen Outlook-Regeln
- **kein** Client Secret

## Projektstruktur

```text
outlook_sorter/
├── main.py
├── auth.py
├── graph_client.py
├── folder_resolver.py
├── mailbox_analyzer.py
├── rules.py
├── config.py
├── requirements.txt
└── README.md
```

## Sicherheitsprinzip

In `config.py` ist standardmäßig gesetzt:

```python
DEFAULT_MODE = "preview"
CREATE_MISSING_FOLDERS = False
MOVE_MESSAGES = False
```

Beim normalen Start zeigt das Skript ausdrücklich:

```text
DRY RUN AKTIV - Es werden keine Mails verändert.
```

Der einfachste Aufruf bleibt sicher:

```powershell
python main.py
```

Das entspricht intern:

```powershell
python main.py preview
```

Im Modus `preview` liest das Skript nur Daten und gibt Vorschläge aus. Es verschiebt nichts, löscht nichts und legt auch keine Ordner an.

Wenn du später bewusst ausführen willst, nutzt du:

```powershell
python main.py apply
```

Aber selbst dann bleiben echte Änderungen zusätzlich geschützt:

```python
CREATE_MISSING_FOLDERS = False
MOVE_MESSAGES = False
```

Ordner werden nur erstellt, wenn `CREATE_MISSING_FOLDERS = True` gesetzt ist. Mails werden nur verschoben, wenn `MOVE_MESSAGES = True` gesetzt ist. So braucht jede echte Aktion weiterhin ein bewusstes zweites Ja.


## Voraussetzungen

Du hast bereits:

- eine App-Registrierung in Microsoft Entra
- unterstützte Kontotypen: **persönliche Microsoft-Konten**
- **öffentlicher Client / Public Client**
- aktivierte öffentliche Clientflows
- eine passende Redirect URI für Mobile/Desktop/Public Client
- delegierte Microsoft-Graph-Berechtigungen:
  - `User.Read`
  - `Mail.ReadWrite`
  - `offline_access`

Die Authority ist für dein Szenario in `config.py` bereits gesetzt auf:

```python
https://login.microsoftonline.com/consumers
```

Hinweis: `offline_access` bleibt in der App-Registrierung gesetzt, wird im Python-Code mit MSAL aber nicht ausdrücklich in `SCOPES` ergänzt, weil MSAL reservierte OpenID-Scopes selbst behandelt.

## CLIENT_ID eintragen

Du hast zwei Möglichkeiten.

### Option A: direkt in `config.py`

Öffne `config.py` und ersetze:

```python
CLIENT_ID = os.getenv("OUTLOOK_SORTER_CLIENT_ID", "HIER_DEINE_CLIENT_ID_EINTRAGEN")
```

indem du rechts deinen echten Wert einträgst, zum Beispiel:

```python
CLIENT_ID = os.getenv("OUTLOOK_SORTER_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
```

### Option B: als Umgebungsvariable

In PowerShell:

```powershell
$env:OUTLOOK_SORTER_CLIENT_ID="DEINE-CLIENT-ID"
```

Dann musst du `config.py` nicht anfassen.

## Installation unter Windows

Öffne PowerShell im Ordner, in dem `outlook_sorter` liegt, und führe aus:

```powershell
cd outlook_sorter
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Was beim ersten Start passiert

1. Das Skript startet im Dry-Run.
2. Falls noch kein gültiger Token im lokalen Cache liegt, zeigt MSAL eine URL und einen Code an.
3. Du öffnest die URL im Browser, gibst den Code ein und meldest dich mit deinem privaten Microsoft-Konto an.
4. Danach ruft das Skript:
   - `GET /me`
   - `GET /me/mailFolders`
   - bei Bedarf `GET /me/mailFolders/{id}/childFolders`
   - `GET /me/mailFolders/inbox/messages?$top=10`
5. Für jede Mail wird ein Zielordner vorgeschlagen.
6. Anschließend prüft das Skript rein lesend, ob diese Zielpfade schon existieren.

## Start-Regeln

- Absender oder Betreff enthält `Amazon`, `eBay`, `PayPal`, `Klarna`
  - Ziel: `Finanzen/Bestellungen`
- Betreff enthält `Rechnung`, `Invoice`, `Beleg`, `Zahlungsbestätigung`
  - Ziel: `Finanzen/Rechnungen`
- Absender oder Betreff enthält `Framer`, `OpenAI`, `Microsoft`, `GitHub`
  - Ziel: `WorldofWorkflow/Tools`
- Betreff enthält `Impressum`, `Datenschutz`, `AGB`, `Vertrag`
  - Ziel: `WorldofWorkflow/Rechtliches`
- Mail-Vorschau enthält `unsubscribe` oder `abmelden`
  - Ziel: `Newsletter`
- sonst
  - Ziel: `Unsortiert prüfen`

Die Regeln werden in dieser Reihenfolge geprüft. Die erste passende Regel gewinnt.

## Lokaler Token-Cache

Nach erfolgreicher Anmeldung speichert das Skript einen lokalen Cache in:

```text
.token_cache.json
```

Dadurch ist normalerweise keine erneute Anmeldung bei jedem Start nötig.

Wichtig:

- diese Datei enthält sensible Authentifizierungsdaten
- gib sie nicht weiter
- committe sie nicht in ein öffentliches Repository

## Was Version 2 zusätzlich kann

Nach der Kategorisierung prüft das Skript die Zielordner rein lesend:

- existiert der komplette Pfad bereits?
- existiert nur der obere Teil?
- welche Teilstrecke fehlt noch?

Beispiel:

```text
Ordner-Check im Dry-Run
- OK: Newsletter existiert bereits (2 vorgeschlagene Mail(s)).
- FEHLT TEILWEISE: Finanzen/Rechnungen (vorhanden: Finanzen; später anzulegen: Rechnungen; 1 vorgeschlagene Mail(s)).
- FEHLT: WorldofWorkflow/Tools (später anzulegen: WorldofWorkflow/Tools; 3 vorgeschlagene Mail(s)).
```

## Was Version 3 zusätzlich kann

Version 3 enthält einen echten Ordner-Anlagepfad, aber standardmäßig bleibt er ausgeschaltet.

Wenn du im `preview`-Modus läufst, zeigt das Skript nur:

```text
Ordner-Anlage
- Deaktiviert, weil Modus = preview.
```

Wenn du irgendwann bewusst Ordner erstellen willst, setzt du in `config.py`:

```python
CREATE_MISSING_FOLDERS = True
```

Dann erstellt das Skript nur die tatsächlich fehlenden Teilstücke, zum Beispiel:

```text
Ordner-Anlage
- Angelegt: Finanzen
- Angelegt: Finanzen/Rechnungen
```

Vorher prüft es weiterhin, welche Ordner schon existieren, damit keine unnötigen Duplikate entstehen.

Seit Version 7 gilt zusätzlich: Neue Ordner dürfen nur für Themen entstehen, die deine Analyse bereits als stabil erkannt hat. Ein einmaliger Sonderfall reicht nicht.

## Was Version 4 zusätzlich kann

Nach der Ordnerprüfung erzeugt das Skript jetzt zusätzlich einen Verschiebe-Plan:

```text
Verschiebe-Plan
- [1] würde verschoben nach Finanzen/Rechnungen: Ihre Rechnung
- [2] NICHT verschiebbar, Ziel fehlt (WorldofWorkflow/Tools): Produktupdate
```

Im Standardzustand bleibt die echte Bewegung aus:

```text
Mail-Verschiebung
- Deaktiviert, weil Modus = preview.
```

Wenn du später bewusst echte Moves erlauben willst, setzt du:

```python
MOVE_MESSAGES = True
```

Dann werden nur Mails verschoben, deren Zielordner tatsächlich aufgelöst ist. Fehlt ein Zielordner noch, bleibt die Mail unangetastet.

## Was Version 5 zusätzlich kann

Version 5 schaut sich im Dry-Run eine größere aktuelle Stichprobe deiner vorhandenen Mails an und leitet daraus **breite, wiederkehrende Themen** ab.

Der Gedanke ist bewusst privat-postfach-tauglich:

- keine neuen Ordner wegen einer einzelnen Sondermail
- lieber wenige stabile Themen als viele winzige Absenderordner
- vorhandene Mails dienen als Evidenz dafür, welche Struktur sich wirklich lohnt

Die Standardwerte stehen in `config.py`:

```python
ANALYSIS_MESSAGE_LIMIT = 200
MIN_MESSAGES_PER_TOPIC = 5
```

Das heißt: Das Skript betrachtet bis zu 200 aktuelle Mails und empfiehlt ein Thema erst dann als sinnvolle Ordneridee, wenn es mindestens 5-mal im Bestand vorkommt.

Beispiel:

```text
Postfach-Analyse im Dry-Run
- Analysiert: 200 aktuelle Mail(s) (Themen-Schwelle: mindestens 5).
- Empfohlene kompakte Struktur aus wiederkehrenden Mustern:
  • Finanzen/Rechnungen (18 Mail(s), 6 Absender; Beispiele: billing@example.com, ...)
  • Newsletter (14 Mail(s), 9 Absender; Beispiele: ...)
- Bewusst nicht einsortiert: 121 Mail(s), damit Einzelthemen nicht sofort neue Ordner erzeugen.
```

Diese Analyse verändert nichts. Sie ist dafür da, dass die spätere Automatik **aus deinem echten Postfach wächst**, statt eine künstliche Riesenstruktur zu erzwingen.

## Was Version 6 zusätzlich kann

Version 6 verbindet Analyse und Sortierung:

- Nur Themen, die im eigenen Bestand stabil genug waren, dürfen automatisch als Zielordner für neue Mails verwendet werden.
- Wenn eine neue Mail zwar zu einem bekannten Muster passen könnte, dieses Thema in deinem Postfach aber noch nicht stabil genug ist, landet sie zunächst in `Unsortiert prüfen`.
- Dadurch entsteht nicht für jeden neuen Sonderfall sofort ein frischer Ordner.

Das ist der bewusst private, schlanke Workflow:

```text
neue Mail
   ↓
passt zu stabilem Thema aus deinem Bestand?
   ├─ ja  → passenden Ordner nutzen
   └─ nein → Unsortiert prüfen
```

So lernt das System aus deinem echten Leben, bleibt aber zurückhaltend genug, um die Struktur nicht aufzublähen.

## Was Version 7 zusätzlich kann

Version 7 koppelt die Ordneranlage an dieselbe Stabilitätslogik:

- stabiles Thema, Zielordner fehlt → darf später angelegt werden
- noch instabiles Thema, Zielordner fehlt → wird nicht angelegt

Beispiel:

```text
Keine anlagefähigen fehlenden Zielordner.
- Nicht angelegt, weil Thema noch nicht stabil genug ist: Reisen
```

Damit bleibt die Ordnerstruktur auch dann beherrschbar, wenn im Alltag immer wieder neue Einzelfälle auftauchen.

## Was Version 8 zusätzlich kann

Version 8 vereinfacht die Bedienung:

- `python main.py` oder `python main.py preview`
  - nur lesen, analysieren, vorschlagen
- `python main.py apply`
  - bewusster Ausführungsmodus, aber weiterhin mit separaten Sicherungen für Ordneranlage und Verschieben

Damit musst du im Alltag nicht mehr über mehrere Sicherheitszustände nachdenken. Der Standard bleibt ungefährlich; echte Änderungen verlangen weiterhin klare Absicht.

## Was Version 9 zusätzlich kann

Version 9 schreibt nach jedem Lauf ein kleines JSON-Protokoll nach:

```text
logs/run_YYYYMMDD_HHMMSS.json
```

Darin stehen unter anderem:

- welche stabilen Themen erkannt wurden
- welche Inbox-Mail welchem Zielordner zugeordnet wurde
- welche Zielordner existieren oder fehlen
- welche Ordner bewusst nicht angelegt wurden
- welche Ordner oder Mails tatsächlich verändert wurden, falls du später `apply` aktiv nutzt

Das macht den Sortierer vertrauenswürdiger: Entscheidungen bleiben sichtbar, ohne dass du dir im Alltag mehr Arbeit auflädst.

## Was Version 10 zusätzlich kann

Version 10 merkt sich wiederkehrende Themen über mehrere Läufe hinweg in:

```text
topic_memory.json
```

Ein Thema gilt standardmäßig erst dann als **langfristig stabil**, wenn:

```python
MIN_RUNS_FOR_STABLE_TOPIC = 2
MIN_TOTAL_MESSAGES_FOR_STABLE_TOPIC = 10
```

Das bedeutet:

- Ein Thema, das nur in einem einzigen Lauf auffällig war, wird noch nicht sofort zur festen Struktur.
- Erst wenn es wiederkehrt und genug Gesamtgewicht bekommt, darf es automatisch als Zielordner genutzt oder später angelegt werden.

Das ist bewusst träger als eine reine Momentaufnahme — und genau deshalb besser für ein privates Postfach, dessen Ordnung nicht bei jeder kleinen Welle umgebaut werden soll.

## Was Version 11 zusätzlich kann

Version 11 lässt alte Themen langsam wieder aus der aktiven Automatik herausfallen, wenn sie über mehrere Läufe nicht mehr auftauchen.

Der Standardwert ist:

```python
MAX_RUNS_SINCE_LAST_SEEN_FOR_STABLE_TOPIC = 3
```

Das bedeutet:

- Ein Thema bleibt nicht für immer automatisch aktiv, nur weil es früher einmal wichtig war.
- Wenn es mehrere Läufe lang nicht mehr auftaucht, wird es nicht weiter als automatisches Ziel genutzt.
- Bestehende Ordner oder alte Mails werden dabei **nie** gelöscht oder verändert.

Das System vergisst also sanft auf Entscheidungsebene, nicht destruktiv im Postfach selbst.

## Was Version 12 zusätzlich kann

Version 12 ergänzt eine kleine Qualitätsprüfung: Ein Thema soll nicht nur häufig sein, sondern auch von mehr als einem Absender getragen werden.

Standardmäßig gilt:

```python
MIN_UNIQUE_SENDERS_FOR_STABLE_TOPIC = 2
```

Damit wird ein Thema erst dann automatisch aktiv, wenn es:

- oft genug vorkam
- über mehrere Läufe wiederkehrte
- nicht zu lange verschwunden war
- und von mindestens zwei verschiedenen Absendern getragen wird

Das schützt davor, dass ein einzelner sehr aktiver Sender die Ordnerstruktur überproportional bestimmt.

## Was Version 13 zusätzlich kann

Version 13 passt die Automatik an den natürlichen Workflow eines privaten Postfachs an:

- Unklare Mails bleiben im `Posteingang`, statt in einen zusätzlichen Prüf-Ordner verschoben zu werden.
- Sehr starke Themen dürfen schon im ersten Lauf aktiv werden, wenn sie klar genug belegt sind.

Standardmäßig gilt:

```python
STRONG_TOPIC_MESSAGE_THRESHOLD = 20
STRONG_TOPIC_UNIQUE_SENDERS_THRESHOLD = 5
```

So wird ein Thema wie `Finanzen/Bestellungen` schon früh nutzbar, wenn es eindeutig genug ist. Schwächere Themen müssen sich weiterhin über mehrere Läufe bewähren.

## Was Version 14 zusätzlich kann

Version 14 behandelt den `Posteingang` nicht mehr wie einen Zielordner, sondern wie eine bewusste **Nicht-Aktion**:

- unklare Mails bleiben sichtbar im Posteingang
- sie werden nicht unnötig „in denselben Ordner verschoben“
- im Plan erscheint klar: `bleibt im Posteingang`

Das macht die Ausgabe ehrlicher und den späteren Apply-Modus sauberer.

## Was noch bewusst fehlt

Diese Version löscht weiterhin keine Mails, erstellt keine serverseitigen Regeln und führt keine KI-Kategorisierung aus. Sie bleibt bewusst deterministisch und nachvollziehbar.

Für eine spätere Version bietet sich an:

1. neue Ordner automatisch nur dann zulassen, wenn ein Thema über längere Zeit stabil bleibt
2. optional ein kleines Protokoll speichern, damit jede Entscheidung nachvollziehbar bleibt
3. die Themenlogik später bei Bedarf behutsam verfeinern

## Beispielausgabe

```text
Outlook Mail-Sortierer - Version 14
DRY RUN AKTIV - Es werden keine Mails verändert.

Login erfolgreich.

Konto-Test
Name: Max Mustermann
Mailadresse: max@example.com

Top-Level-Mailordner
- Posteingang (gesamt: 42, ungelesen: 3)

Posteingang - letzte 1 Mail(s)

[1]
Absender: PayPal <service@paypal.de>
Betreff: Ihre Zahlungsbestätigung
Empfangen: 17.05.2026 10:31
Vorschau: Vielen Dank für Ihre Zahlung ...
Vorschlag: Finanzen/Bestellungen

Fertig. Es wurden keine Mails verschoben, gelöscht oder verändert.
```

## Nächster sinnvoller Ausbauschritt

Wenn dir diese Richtung gefällt, wäre der nächste starke Schritt der **erste echte Apply-Lauf nur für Ordneranlage**:

- fehlende stabile Zielordner anlegen
- noch keine Mails verschieben
- danach in einem weiteren Preview prüfen, ob der Move-Plan sauber aussieht

## Cloud-Betrieb mit Azure Functions

Für den automatischen Cloud-Betrieb wurden zusätzlich ergänzt:

```text
function_app.py
cloud_runner.py
state_store.py
host.json
```

Die Cloud-Version verwendet:

- `OUTLOOK_SORTER_CLIENT_ID`
- `OUTLOOK_SORTER_AUTHORITY`
- `OUTLOOK_SORTER_STATE_CONTAINER`
- `OUTLOOK_SORTER_SCHEDULE`
- `CREATE_MISSING_FOLDERS`
- `MOVE_MESSAGES`

als App-Einstellungen in Azure.

Der Azure-Function-Trigger läuft nach Zeitplan. Für alle 10 Minuten:

```text
0 */10 * * * *
```

Der Zustand liegt in Blob Storage:

```text
token_cache.json
topic_memory.json
logs/run_....json
```

### Einmalige Vorbereitung vor dem ersten Cloud-Lauf

1. Lokal erfolgreich per Device Code Flow anmelden.
2. Die lokale Datei `.token_cache.json` aus dem Projektordner in den Blob-Container hochladen als:

```text
token_cache.json
```

3. Die lokale Datei `topic_memory.json` ebenfalls in denselben Blob-Container hochladen.

Die Cloud-Funktion kann sich nicht interaktiv anmelden. Sie nutzt deshalb denselben gespeicherten MSAL-Cache weiter und erneuert Tokens still im Hintergrund, solange das möglich ist.

### Deployment

Für die Veröffentlichung wird die Function App aus dem Projektordner deployt. Der typische Befehl lautet:

```powershell
func azure functionapp publish <FUNCTION_APP_NAME> --python --build remote
```

Vor dem Deployment müssen Azure Functions Core Tools installiert sein.

## Einmalige Bestandsbereinigung (Backfill)

Der normale Dauerbetrieb prüft bewusst nur eine kleine Zahl neuer Inbox-Mails. Für den bereits vorhandenen Bestand gibt es separat:

```powershell
python main.py backfill-preview
python main.py backfill-apply
```

Standardmäßig betrachtet der Backfill:

```python
BACKFILL_MESSAGE_LIMIT = 200
```

Empfohlener Ablauf:

1. zuerst:
   ```powershell
   python main.py backfill-preview
   ```
2. Vorschläge prüfen
3. nur wenn das Bild gut aussieht:
   ```powershell
   python main.py backfill-apply
   ```

Der Backfill ist absichtlich **separat** vom Cloud-Automatismus. So wird alter Bestand kontrolliert aufgeräumt, während der laufende Dienst danach wieder klein und ruhig bleibt.


## Was Version 15 zus?tzlich kann

Version 15 bremst die Entstehung neuer Ordner noch etwas st?rker:

- Ein Thema darf weiterhin erst stabil genug sein, bevor es automatisch genutzt wird.
- Zus?tzlich wird ein **neuer** Ordner erst angelegt, wenn im aktuellen Lauf mindestens zwei Mails wirklich dorthin m?chten.
- Dadurch erzeugt eine einzelne Randmail keinen frischen Ordner mehr, selbst wenn das Thema historisch schon einmal vorkam.

Standardm??ig gilt:

```python
MIN_TARGET_MESSAGES_TO_CREATE_FOLDER = 2
```

Das h?lt die Struktur klein, ohne sinnvolle Sammelordner wie `Newsletter` zu verhindern.
