# Festa F310GP MQTT Addon

TP-Link Festa F310GP → MQTT Auto-Discovery für Home Assistant.

Liest per SSH CPU, Memory, Port-Status und PoE-Daten aus und publiziert sie via MQTT mit Auto-Discovery.

## Installation

1. Dieses Repo als HA Addon-Repo hinzufügen:
   Settings → Add-ons → Add-on Store → ⋮ → Repositories
   `https://github.com/<dein-user>/festa-to-mqtt`

2. Addon installieren

3. Konfiguration ausfüllen

## Konfiguration

| Feld | Beschreibung |
|---|---|
| `mqtt_host` | MQTT Broker Adresse |
| `mqtt_port` | MQTT Port (default 1883) |
| `mqtt_user` | MQTT Benutzer |
| `mqtt_password` | MQTT Passwort |
| `mqtt_prefix` | Discovery Prefix (default `homeassistant`) |
| `switch_hosts` | Kommagetrennte IPs (z.B. `192.168.1.10,192.168.1.11`) |
| `switch_users` | Kommagetrennte SSH-User (gleiche Reihenfolge) |
| `switch_passwords` | Kommagetrennte SSH-Passwörter (gleiche Reihenfolge) |
| `poll_interval` | Poll-Zyklus in Sekunden (default 60) |

> **Achtung:** Enthält ein Passwort ein Komma, muss das Trennzeichen in der `config.yaml` manuell geändert werden.

## Sensoren

**Pro Switch:**
- CPU 5s / 1m / 5m — Auslastung in %
- Memory — Auslastung in %

**Pro Port:**
- 1 Sensor mit State = Link-Status (`Up`/`Down`/`NotPresent`)
- Attributes: Speed, PoE Power/Current/Voltage/Class/Status (nur bei PoE-Ports 1–8)

## Entwicklung

```
pip install paho-mqtt paramiko
python f310gp_hass.py
```
