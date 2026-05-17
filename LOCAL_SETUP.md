# Lokales Setup auf diesem Mac

## Bereits eingerichtet
- Python-Umgebung: `.venv`
- Abhängigkeiten: installiert
- Microsoft-Anmeldung: erfolgreich getestet
- Lokale Konfiguration: `.env.local`

## Sicherer Start
```bash
source .venv/bin/activate
export OUTLOOK_SORTER_CLIENT_ID="$(grep '^OUTLOOK_SORTER_CLIENT_ID=' .env.local | cut -d= -f2-)"
python main.py preview
```

`preview` ist der sichere Modus und verändert keine Mails.

