# Fehlerbehebung (Troubleshooting)

In diesem Dokument findest du Lösungen für die häufigsten Probleme mit der
IDM Heatpump Integration und der zugrundeliegenden Bibliothek.

---

## "Cancel send, because not connected!" / pymodbus-Log-Flut

### Symptom

Im Home Assistant Log erscheinen wiederholt Einträge der Art:

```
Logger: pymodbus.logging
Cancel send, because not connected!
>>>>> recv: 0xb 0x4 0x4 ... extra data:
>>>>> send: 0xb 0x4 0x0 0xec 0x0 0x2 0xb0 0x94
No response received after 3 retries, continue with next request
```

### Ursache

Die TCP-Verbindung zwischen Home Assistant und dem IDM Navigator bricht
während des Betriebs ab. pymodbus protokolliert jeden einzelnen Modbus-Frame
(`>>>>> send/recv`) auf DEBUG-Ebene sowie Verbindungsabbrüche auf ERROR-Ebene.
Bei instabilen Verbindungen füllt das das Log schnell.

Die Bibliothek fängt Verbindungsabbrüche ab und baut die Verbindung automatisch
wieder auf — die Warnungen sind also erst einmal kosmetisch, können aber auf
ein echtes Netzwerkproblem hinweisen.

### Abhilfe

**1. pymodbus-Logging ruhiger stellen**

```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: info
    pymodbus.logging: warning   # unterdrückt die ">>>>> send/recv" Flut
```

Alternativ kann die Bibliothek das auch für Konsumenten übernehmen:

```python
from idm_heatpump import quiet_pymodbus_logging
quiet_pymodbus_logging("WARNING")
```

**2. Netzwerk prüfen**

| Mögliche Ursache | Prüfung |
|-----------------|---------|
| Andere Modbus-Clients (App, ioBroker, zweite HA-Instanz) greifen gleichzeitig zu | Alle anderen Clients stoppen; IDM Navigator akzeptiert oft nur eine TCP-Verbindung |
| WLAN-Verbindung des Navigators | Testweise LAN verwenden |
| Router/Firewall schneidet idle TCP-Verbindungen ab | Timeout-Einstellungen des Routers prüfen |
| Modbus-Server des Navigators stürzt intern ab | Navigator neu starten, Firmware-Update prüfen |

**3. Konsolenauswahl**: Ab Bibliotheksversion 0.6.0 (siehe CHANGELOG) verwendet
`IdmModbusClient` pymodbus-interne Retries nicht mehr doppelt zur
eigenen Retry-Logik. Falls eine ältere Version eingesetzt wird, hilft ein
Update der Bibliothek.

---

## "Register X has failed N times. Marking as permanently failed."

Ein einzelnes Register hat mehrfach hintereinander fehlschlagen gelesen zu
werden. Das ist normal für optionale Register, die auf der vorhandenen Hardware
nicht existieren (z. B. `firmware_version` auf einzelnen Navigator-10-Firmwares).

Falls ein eigentlich verfügbares Register fälschlicherweise als permanent
fehlschlagend markiert wurde, kann der Zustand mit
`client.reset_failed_registers()` zurückgesetzt werden. In Home Assistant hilft
ein Neuladen der Integration.

---

## Beispiel-Automatisierungen

Hier findest du zusätzlich praktische Beispiele für den Einsatz der IDM Heatpump Integration, insbesondere wie man Werte über Automatisierungen schreiben kann.

---

## Werte schreiben per Automatisierung (Übersicht)

In Home Assistant werden schreibbare Werte der Wärmepumpe als **Entitäten** dargestellt. Um diese Werte in Automatisierungen zu ändern, verwendest du nicht `idm_heatpump.write_register`, sondern die Standard-Dienste von Home Assistant:

- Für Temperaturen, Heizkurven oder Sollwerte (Typ `number`): Dienst `number.set_value`
- Für Betriebsmodi (Typ `select`): Dienst `select.select_option`
- Für Schalter (Typ `switch`): Dienst `switch.turn_on` oder `switch.turn_off`

**Alternative (Fortgeschritten):** Wenn ein Register nicht als Entität existiert, kannst du den Dienst `idm_heatpump.write_register` verwenden (siehe [Services Referenz](Services)).

Hier sind einige konkrete Anwendungsfälle:

---

## Urlaubsmodus automatisch aktivieren

Schaltet die Wärmepumpe in den Urlaubsmodus wenn du das Haus verlässt:

```yaml
automation:
  - alias: "Wärmepumpe: Urlaubsmodus bei Abwesenheit"
    trigger:
      - platform: state
        entity_id: person.ich
        to: "not_home"
        for:
          hours: 2
    action:
      - service: idm_heatpump.set_system_mode
        data:
          mode: "urlaub"
```

---

## Normalbetrieb bei Heimkehr

```yaml
automation:
  - alias: "Wärmepumpe: Automatik bei Heimkehr"
    trigger:
      - platform: state
        entity_id: person.ich
        to: "home"
    action:
      - service: idm_heatpump.set_system_mode
        data:
          mode: "automatik"
```

---

## Benachrichtigung bei Störung

Sendet eine Push-Benachrichtigung wenn eine Störung auftritt:

```yaml
automation:
  - alias: "Wärmepumpe: Störungsbenachrichtigung"
    trigger:
      - platform: state
        entity_id: binary_sensor.idm_heatpump_stoerung
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Wärmepumpe Störung"
          message: >
            IDM Störung aktiv. Fehlercode: {{ states('sensor.idm_heatpump_fehlercode') }}
```

---

## Warmwasser-Boost bei PV-Überschuss

Erhöht die Warmwasser-Solltemperatur wenn PV-Überschuss vorhanden ist:

```yaml
automation:
  - alias: "Wärmepumpe: WW-Boost bei PV-Überschuss"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        above: 2.0
        for:
          minutes: 15
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_warmwasser_solltemperatur
        data:
          value: 60
  - alias: "Wärmepumpe: WW-Boost beenden"
    trigger:
      - platform: numeric_state
        entity_id: sensor.idm_heatpump_pv_surplus
        below: 0.5
        for:
          minutes: 10
    action:
      - service: number.set_value
        target:
          entity_id: number.idm_heatpump_warmwasser_solltemperatur
        data:
          value: 48
```

---

## Heizkreis-Modus per Zeitplan

Wechselt den Heizkreis A täglich nach Zeitplan:

```yaml
automation:
  - alias: "Wärmepumpe: Heizkreis A – Zeitprogramm"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_betriebsart_hk_a
        data:
          option: "Eco"
  - alias: "Wärmepumpe: Heizkreis A – Normalbetrieb"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.idm_heatpump_betriebsart_hk_a
        data:
          option: "Normal"
```

---

## Energie-Dashboard

Für ein Energie-Dashboard in Home Assistant:

```yaml
# Tägliche Heizenergie (in configuration.yaml oder helpers)
sensor:
  - platform: integration
    source: sensor.idm_heatpump_aktuelle_leistung_heizen
    name: Tagesenergie Heizen
    unit_prefix: k
    round: 2
```

---

## Smart-Grid-Steuerung

Reagiert auf Smart-Grid-Status der Wärmepumpe:

```yaml
automation:
  - alias: "SmartGrid: Wärmepumpe Status auslesen"
    trigger:
      - platform: state
        entity_id: sensor.idm_heatpump_smart_grid_status
    action:
      - service: notify.persistent_notification
        data:
          title: "Smart Grid Status"
          message: "Aktueller Smart-Grid-Status: {{ states('sensor.idm_heatpump_smart_grid_status') }}"
```

---

## Fehler quittieren (manuell via Button-Helper)

```yaml
# button-helper in configuration.yaml
button:
  - platform: template
    buttons:
      idm_acknowledge_errors:
        friendly_name: "IDM Störungen quittieren"
        press:
          service: idm_heatpump.acknowledge_errors
```
