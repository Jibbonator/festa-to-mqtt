#!/usr/bin/env python3
import json, os, sys, time, signal, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("f310gp")

_opt_file = "/data/options.json"
_options = {}
try:
    with open(_opt_file) as f:
        _options = json.load(f)
        log.info("Loaded config from %s", _opt_file)
except (FileNotFoundError, json.JSONDecodeError):
    pass

def _cfg(key, default=""):
    val = os.environ.get(key.upper())
    if val:
        return val
    return str(_options.get(key, default))

MQTT_HOST  = _cfg("mqtt_host", "homeassistant.local")
MQTT_PORT  = int(_cfg("mqtt_port", "1883"))
MQTT_USER  = _cfg("mqtt_user")
MQTT_PASS  = _cfg("mqtt_password", _cfg("mqtt_pass", ""))
MQTT_PREFIX = _cfg("mqtt_prefix", "homeassistant")
POLL_INTERVAL = int(_cfg("poll_interval", "60"))

_switch_hosts_str     = _cfg("switch_hosts")
_switch_users_str     = _cfg("switch_users")
_switch_passwords_str = _cfg("switch_passwords")

SWITCH_HOSTS     = [h.strip() for h in _switch_hosts_str.split(",") if h.strip()]
SWITCH_USERS     = [u.strip() for u in _switch_users_str.split(",") if u.strip()]
SWITCH_PASSWORDS = [p.strip() for p in _switch_passwords_str.split(",") if p.strip()]

if not SWITCH_HOSTS:
    log.error("No switches configured – set SWITCH_HOSTS")
    sys.exit(1)

if not (len(SWITCH_HOSTS) == len(SWITCH_USERS) == len(SWITCH_PASSWORDS)):
    log.error("SWITCH_HOSTS / USERS / PASSWORDS count mismatch")
    sys.exit(1)

SWITCHES = list(zip(SWITCH_HOSTS, SWITCH_USERS, SWITCH_PASSWORDS))


def device_id(host):
    return f"f310gp_{host.replace('.', '_')}"


def mqtt_connect():
    import paho.mqtt.client as mqtt
    client = mqtt.Client(client_id=f"f310gp_{int(time.time())}")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    return client


def disco_topic(sensor_key):
    return f"{MQTT_PREFIX}/sensor/{sensor_key}/config"


def state_topic(sensor_key):
    return f"{MQTT_PREFIX}/sensor/{sensor_key}/state"


def attr_topic(sensor_key):
    return f"{MQTT_PREFIX}/sensor/{sensor_key}/attributes"


def publish_discovery(mqtt):
    mqtt._seen_ports = set()
    mqtt._devices = {}

    for host, user, pwd in SWITCHES:
        did = device_id(host)
        dev = {
            "identifiers": [did],
            "name": f"F310GP {host}",
            "manufacturer": "TP-Link",
            "model": "Festa F310GP",
        }
        mqtt._devices[did] = dev

        for skey_suffix, name, unit, icon in [
            ("cpu_5s",  "CPU 5s",  "%",           "mdi:cpu-64-bit"),
            ("cpu_1m",  "CPU 1m",  "%",           "mdi:cpu-64-bit"),
            ("cpu_5m",  "CPU 5m",  "%",           "mdi:cpu-64-bit"),
            ("memory",  "Memory",  "%",           "mdi:memory"),
        ]:
            skey = f"{did}_{skey_suffix}"
            payload = {
                "name": f"{dev['name']} {name}",
                "state_topic": state_topic(skey),
                "unit_of_measurement": unit,
                "icon": icon,
                "device": dev,
                "unique_id": skey,
            }
            mqtt.publish(disco_topic(skey), json.dumps(payload), retain=True)
            log.info("Discovery: %s", skey)


def publish_port_disco(mqtt, host, port_key):
    did = device_id(host)
    skey = f"{did}_port_{port_key}"
    if skey in mqtt._seen_ports:
        return
    mqtt._seen_ports.add(skey)
    dev = mqtt._devices[did]
    payload = {
        "name": f"{dev['name']} Port {port_key}",
        "state_topic": state_topic(skey),
        "json_attributes_topic": attr_topic(skey),
        "icon": "mdi:ethernet",
        "device": dev,
        "unique_id": skey,
    }
    mqtt.publish(disco_topic(skey), json.dumps(payload), retain=True)
    log.info("Discovery: port %s", skey)


def get_data(host, user, password):
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password,
                look_for_keys=False, allow_agent=False, timeout=15, banner_timeout=15)
    chan = ssh.invoke_shell()
    chan.settimeout(8)

    def cmd(c, wait=1.5):
        chan.send(c + "\r")
        time.sleep(wait)
        data = b""
        while chan.recv_ready():
            data += chan.recv(8192)
            time.sleep(0.1)
        return data.decode("utf-8", errors="replace")

    time.sleep(2)
    chan.recv(8192)
    cmd("enable")
    cmd("terminal length 0", 0.5)

    result = {}

    out = cmd("show cpu")
    for line in out.split("\n"):
        if "%" in line and "|" in line:
            try:
                pct = [x.rstrip("%") for x in line.split() if "%" in x]
                result["cpu_5s"] = int(pct[0])
                result["cpu_1m"] = int(pct[1])
                result["cpu_5m"] = int(pct[2])
            except:
                pass

    out = cmd("show memory")
    for line in out.split("\n"):
        if "%" in line:
            try:
                result["memory"] = int(line.strip().split()[-1].rstrip("%"))
            except:
                pass

    out = cmd("show interface status")
    ports = {}
    for line in out.split("\n")[3:]:
        parts = line.split()
        if len(parts) >= 4 and "/" in parts[0]:
            key = parts[0].replace("/", "_")
            ports[key] = {"status": parts[1], "speed": parts[2]}
    result["ports"] = ports

    out = cmd("show power inline information interface")
    poe = {}
    for line in out.split("\n")[3:]:
        parts = line.split()
        if len(parts) < 5 or "/" not in parts[0]:
            continue
        key = parts[0].replace("/", "_")
        try:
            pw, cur, vol = float(parts[1]), int(parts[2]), float(parts[3])
            if parts[4] == "Class":
                pd_class = f"Class_{parts[5]}"
                status = parts[6] if len(parts) > 6 else "?"
            else:
                pd_class = parts[4]
                status = parts[5] if len(parts) > 5 else "?"
            poe[key] = {
                "power": pw, "current": cur, "voltage": vol,
                "pd_class": pd_class, "status": status,
            }
        except:
            pass
    result["poe"] = poe

    chan.close()
    ssh.close()
    return result


def publish_state(mqtt, host, data):
    did = device_id(host)

    for key in ("cpu_5s", "cpu_1m", "cpu_5m", "memory"):
        if key in data:
            skey = f"{did}_{key}"
            mqtt.publish(state_topic(skey), str(data[key]), retain=True)

    for port_key, info in data.get("ports", {}).items():
        skey = f"{did}_port_{port_key}"
        publish_port_disco(mqtt, host, port_key)

        mqtt.publish(state_topic(skey), info.get("status", "?"), retain=True)

        attrs = {"speed": info.get("speed", "?")}
        poe_data = data.get("poe", {}).get(port_key)
        if poe_data:
            attrs["poe_power_w"] = poe_data["power"]
            attrs["poe_current_ma"] = poe_data["current"]
            attrs["poe_voltage_v"] = poe_data["voltage"]
            attrs["poe_class"] = poe_data["pd_class"]
            attrs["poe_status"] = poe_data["status"]

        mqtt.publish(attr_topic(skey), json.dumps(attrs), retain=True)


running = True


def handle_sig(*_):
    global running
    running = False


def main():
    global running
    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt not installed. Run: pip install paho-mqtt")
        sys.exit(1)

    log.info("F310GP monitor starting – %d switch(es)", len(SWITCHES))
    log.info("MQTT broker: %s:%s", MQTT_HOST, MQTT_PORT)

    mqttc = mqtt_connect()
    publish_discovery(mqttc)

    while running:
        for host, user, pwd in SWITCHES:
            if not running:
                break
            try:
                data = get_data(host, user, pwd)
                log.info("[%s] cpu=%s mem=%s ports=%d poe=%d",
                         host, data.get("cpu_5s"), data.get("memory"),
                         len(data.get("ports", {})), len(data.get("poe", {})))
                publish_state(mqttc, host, data)
            except Exception as e:
                log.error("[%s] Poll failed: %s", host, e)

        for _ in range(POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    log.info("Shutting down")
    mqttc.loop_stop()
    mqttc.disconnect()


if __name__ == "__main__":
    main()
