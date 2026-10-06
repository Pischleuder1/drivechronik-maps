# DriveChronik – Offline-Karten und Routingpakete

Dieses öffentliche Repository ist die zentrale Quelle für optionale **PMTiles-Karten** und **Valhalla-Routingdaten** von DriveChronik-Dash.

## Für Nutzer

Die App benötigt für Tesla-Livedaten keine Offline-Pakete. Für die vollständige Offline-Navigation eines Landes werden **beide Komponenten** benötigt:

- **PMTiles**: Offline-Kartendarstellung.
- **Valhalla**: Offline-Routenberechnung, Abbiegehinweise und Neuberechnungen.

Die Pakete sind unabhängig wählbar und werden nur bei Bedarf geladen.

## Katalog

Die App liest [`catalog.json`](catalog.json) vom Standardbranch über eine HTTPS-Adresse. **Nur tatsächlich veröffentlichte, vollständig hochgeladene, geprüfte Pakete dürfen darin erscheinen.** Ein Land darf auch nur PMTiles oder nur Routing anbieten. Leerer Katalog = keine Downloads verfügbar. Der Kartenmanager zeigt zusätzlich bereits lokal installierte Dateien, auch wenn diese noch nicht im GitHub-Katalog stehen.

Jeder Eintrag unter `packages` hat dieses Format (Beispiel – **nicht veröffentlicht**):

```json
{
  "schemaVersion": 1,
  "packages": [
    {
      "id": "de-map",
      "country": "de",
      "countryName": "Deutschland",
      "kind": "map",
      "version": "2026-10",
      "sizeBytes": 3120205459,
      "sha256": "ea1a2fec47d8fccf0cb8d6c35f0f2eab644fb366eb9222ea763ec20efb8b9dcc",
      "fileName": "germany.pmtiles",
      "parts": [
        {"name": "germany.pmtiles.part01", "sizeBytes": 0, "sha256": "EINTRAGEN", "url": "https://github.com/OWNER/REPO/releases/download/TAG/germany.pmtiles.part01"}
      ]
    }
  ]
}
```

Die Beispielwerte der einzelnen Dateiteile, URLs und Checksummen müssen **vor einer Veröffentlichung mit echten, verifizierten Werten** ersetzt werden. Dateiteile bleiben unter dem GitHub-Release-Limit von 2 GiB.

**Sichere Installation:** HTTPS, ausreichend freier Speicher, temporäre Downloads, SHA-256 pro Dateiteil und Gesamtdatei, erst nach vollständiger Prüfung aktivieren. Vorhandene Pakete niemals während eines unvollständigen Downloads überschreiben; abgebrochene Downloads müssen wiederaufnehmbar sein. Keine unbestätigten Download-URLs verwenden.

**Veröffentlichungsablauf:** Pakete lokal erzeugen → teilen → Prüfsummen erzeugen → Release-Assets hochladen → Dateien und URLs verifizieren → **erst danach** den Katalog aktualisieren.

© OpenMapTiles © OpenStreetMap contributors; die jeweiligen Datenquellen, Lizenzen und Attributionsbedingungen der erstellten Karten müssen in der App eingehalten werden.
