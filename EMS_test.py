from flask import Flask, render_template, request, jsonify
from waitress import serve
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.datastore import ModbusSparseDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server.sync import ModbusTcpServer
import time
import struct
import json
from datetime import datetime, timezone
from threading import Thread
from paho.mqtt import client as mqtt_client
import ssl
import os
import requests
import pexpect
import logging
import statistics
import math
import yaml
import struct
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
#------------------------------------------------------------------------POMOĆNE KORISNE FUNKCIJE ZA NADOGRADNJE----------------------------------------------------------------------------

# učitavanje konfiguracijske datoteke
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)



logger = logging.getLogger(__name__)
# ------------------------------------------------ TCP SERVER -------------------------------------------------

register_range = range(40001, 40100)  # 0 to 99 (maps to 40001–40100)
register_dict = {addr: 0 for addr in register_range}
dm_datablock = ModbusSparseDataBlock(register_dict)

slave_context = ModbusSlaveContext(
    hr=dm_datablock,
    zero_mode=False    
)

server_context = ModbusServerContext(slaves=slave_context, single=True)

def start_tcp_slave_server():
    server = ModbusTcpServer(server_context, address=("0.0.0.0", 5021))  # Definicija IP adrese i porta 
    logger.info("Pokretanje Modbus TCP slave servera...")
    server.serve_forever()

def citaj_tcp_server(address, datatype="int"):
   
    try:
        if datatype == "float":
            regs = slave_context.getValues(3, address, count=2)
            if len(regs) != 2:
                return None
            packed = struct.pack('>HH', regs[0], regs[1])
            return struct.unpack('>f', packed)[0]
        elif datatype == "int":
            regs = slave_context.getValues(3, address, count=1)
            if len(regs) != 1:
                return None
            # Interpret as signed 16-bit int
            value = regs[0]
            if value > 32767:
                value -= 65536
            return value
        else:
            return None
    except Exception as e:
        logger.error(f"read_dm_register error: {e}")
        return None

def pisi_na_tcp_server(address, value, datatype="int"):
    try:
        if datatype == "float":
            value = float(value)  # Ensure value is float
            packed = struct.pack('>f', value)
            high, low = struct.unpack('>HH', packed)
            slave_context.setValues(3, address, [high, low])
        elif datatype == "int":
            value = int(value)  # Ensure value is int
            # Write as signed 16-bit int
            if value < 0:
                value = 65536 + value
            slave_context.setValues(3, address, [value])
        else:
            logger.error(f"Unsupported datatype for write: {datatype}")
    except Exception as e:
        logger.error(f"write_dm_register error: {e}")

#--------------------------------------------------------------------------------------------- KRAJ POMOĆNIH FUNKCIJA ZA NADOGRADNJU -----------------------------------------------------------------------



#--------------------------------------------------------------------------------------------- MAIN PROGRAM ------------------------------------------------------------------------------------------------

# ------------------Definiranje foldera za zapis logova---------------------
LOG_DIR = "Dnevni_logovi"
LOG_DIR_ERROR = "ERROR_LOG"
os.makedirs(LOG_DIR, exist_ok=True)  # Provjera ako folder postoji
os.makedirs(LOG_DIR_ERROR, exist_ok=True)  # Provjera ako folder postoji
LOG_FILE = os.path.join(LOG_DIR_ERROR, "logovi_error.log")

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler()  # printa i u konzolu
    ]
)

logger = logging.getLogger(__name__)


# ------------------------------------------------ Deklaracija varijabli ------------------------------------------------
register_map = {}   # mapa registara 
WRITE_REGISTERS = config.get("pisanje_u_registre", {})

# ------------------------------------------------ MODBUS DEVICES ------------------------------------------------
MODBUS_DEVICES = config["MODBUS_DEVICES"]
MODBUS_CLIENTS = {}
RTU_DELAY=0.04

def utc_now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def ensure_tcp_connected(client, client_key):
    device = MODBUS_DEVICES[client_key]

    if device["type"] != "tcp":
        return True

    try:
        # socket is None or closed
        if not client.socket or client.socket._closed:
            logger.warning(f"Reconnecting TCP Modbus {client_key}...")
            client.close()
            return client.connect()

        return True

    except Exception:
        logger.warning(f"Force reconnect TCP Modbus {client_key}")
        try:
            client.close()
        except:
            pass
        return client.connect()
    
def reset_modbus_client(client_key, client):
    try:
        client.close()
    except:
        pass

    MODBUS_CLIENTS.pop(client_key, None)



def get_modbus_client(client_key):
    if client_key not in MODBUS_DEVICES:
        return None, {"message": "Invalid client identifier!", "status": "error"}

    # reuse client if exists
    if client_key in MODBUS_CLIENTS:
        return MODBUS_CLIENTS[client_key], None

    device = MODBUS_DEVICES[client_key]

    try:
        if device["type"] == "tcp":
            client = ModbusTcpClient(
                host=device["ip"],
                port=device["port"],
                timeout=2
            )
        elif device["type"] == "rtu":
            client = ModbusSerialClient(
                method="rtu",
                port=device["port"],
                baudrate=device["baudrate"],
                parity=device["parity"],
                stopbits=device["stopbits"],
                bytesize=device["bytesize"],
                timeout=2
            )
        else:
            return None, {"message": "Unsupported device type", "status": "error"}

        if not client.connect():
            return None, {"message": "Unable to connect to Modbus device", "status": "error"}

        MODBUS_CLIENTS[client_key] = client
        logger.info(f"Modbus client '{client_key}' connected")

        return client, None

    except Exception as e:
        return None, {"message": str(e), "status": "error"}

# ------------------------------------------------ MODBUS READ/WRITE ------------------------------------------------

def read_register_internal(address, client_key="A", datatype="int32"):
  
    is_rtu = MODBUS_DEVICES[client_key]["type"] == "rtu"
    if is_rtu:
        time.sleep(RTU_DELAY)
    
    client, error = get_modbus_client(client_key)
    if error:
        return {"status": "error", "message": error["message"], "data": None}
  
    if MODBUS_DEVICES[client_key]["type"] == "tcp":
        if not ensure_tcp_connected(client, client_key):
            return {"status": "error", "message": "TCP reconnect failed", "data": None}

    try:

        slave_id = MODBUS_DEVICES[client_key]["slave_id"]

        if datatype in ["int16", "uint16"]:
            result = client.read_holding_registers(address=address, count=1, unit=slave_id)
            
            if result.isError():
                logger.error(f"Modbus error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus communication error", "data": None}
   
            raw = result.registers[0]
            if datatype == "int16" and raw > 32767:
                raw -= 65536
            value = raw

        elif datatype in ["int32", "uint32", "float32"]:
            result = client.read_holding_registers(address=address, count=2, unit=slave_id)
 
            if result.isError():
                logger.error(f"Modbus error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus communication error", "data": None}

            word_order = MODBUS_DEVICES[client_key].get("word_order", "big")

            regs = result.registers
            if word_order == "big":
                high_word, low_word = regs[0], regs[1]
            else:  # little
                high_word, low_word = regs[1], regs[0]
                
            packed = struct.pack('>HH', high_word, low_word)

            if datatype == "int32":
                value = struct.unpack('>i', packed)[0]
            elif datatype == "uint32":
                value = struct.unpack('>I', packed)[0]
            elif datatype == "float32":
                value = struct.unpack('>f', packed)[0]

        elif datatype == "float64":
            result = client.read_holding_registers(address=address, count=4, unit=slave_id)
 
            if result.isError():
                logger.error(f"Modbus error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus communication error", "data": None}
            
            word_order = MODBUS_DEVICES[client_key].get("word_order", "big")

            words = result.registers
            if word_order == "little":
                words = words[::-1]
                
            packed = struct.pack('>HHHH', words[0], words[1], words[2], words[3])
            value = struct.unpack('>d', packed)[0]

        elif datatype == "string":
            # length depends on expected string size; here assuming 2 registers = 4 chars
            result = client.read_holding_registers(address=address, count=2, unit=slave_id)
 
            if result.isError():
                logger.error(f"Modbus error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus communication error", "data": None}
            
            packed = struct.pack('>HH', result.registers[0], result.registers[1])
            value = packed.decode(errors="ignore").strip()
        
        elif datatype == "rtu0x02":
            # New FC0x02 option
            count = MODBUS_DEVICES[client_key].get("discrete_input_count", 8)
            result = client.read_discrete_inputs(address=address, count=count, unit=slave_id)

            if result.isError():
                logger.error(f"Modbus FC0x02 error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus FC0x02 read failed", "data": None}

            value = result.bits[:count]

        else:
            return {"status": "error", "message": f"Unsupported datatype: {datatype}", "data": None}

        return {"status": "success", "message": "Read OK", "data": value}

    except Exception as e:
        logger.error(f"Modbus error on {client_key}: {e}")

# Reset broken client
        try:
            client.close()
        except:
            pass
        MODBUS_CLIENTS.pop(client_key, None)
        return {"status": "error", "message": str(e), "data": None}


def write_register_internal(address, value, client_key="A", bit_size=16):
    
    is_rtu = MODBUS_DEVICES[client_key]["type"] == "rtu"
    if is_rtu:
        time.sleep(RTU_DELAY)
            
    
    client, error = get_modbus_client(client_key)
    if error:
        logger.error(f"get_modbus_client error: {error['message']}")  
        return {"status": "error", "message": error["message"]}
          
    if MODBUS_DEVICES[client_key]["type"] == "tcp":
        if not ensure_tcp_connected(client, client_key):
            return {"status": "error", "message": "TCP reconnect failed", "data": None}
    
    try:
        
        slave_id = MODBUS_DEVICES[client_key]["slave_id"]
        word_order = MODBUS_DEVICES[client_key].get("word_order", "big")

        if bit_size == 8:
            # Only lower 8 bits; must be 0-255
            if value < 0 or value > 255:
                return {"status": "error", "message": "8-bit value must be 0-255"}
            result=client.write_register(address, value, unit=slave_id)
            
            if result.isError():
                logger.error(f"Modbus write error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus write failed"}

        elif bit_size == 16:
            if value < 0:
                value = 65536 + value
            result=client.write_register(address, value, unit=slave_id)
            
            if result.isError():
                logger.error(f"Modbus write error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus write failed"}

        elif bit_size == 32:
            high_word = (value >> 16) & 0xFFFF
            low_word = value & 0xFFFF

            if word_order == "big":
                words = [high_word, low_word]
            else:
                words = [low_word, high_word]

            result = client.write_registers(address, words, unit=slave_id)
            
            if result.isError():
                logger.error(f"Modbus write error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus write failed"}

        elif bit_size == 64:
            # Split 64-bit value into four 16-bit registers
            if value < 0:
                value += 2**64
            words = [
                (value >> 48) & 0xFFFF,
                (value >> 32) & 0xFFFF,
                (value >> 16) & 0xFFFF,
                value & 0xFFFF
            ]
                
            if word_order == "little":
                words = words[::-1]
            result = client.write_registers(address, words, unit=slave_id)
            
            if result.isError():
                logger.error(f"Modbus write error on {client_key}: {result}")
                reset_modbus_client(client_key, client)
                return {"status": "error", "message": "Modbus write failed"}

        else:
            return {"status": "error", "message": f"Unsupported bit_size: {bit_size}"}

        return {"status": "success", "message": f"Wrote {value} to register {address}"}
    
    except Exception as e:
        logger.error(f"Modbus error on {client_key}: {e}")
# Reset broken client
        try:
            client.close()
        except:
            pass
        MODBUS_CLIENTS.pop(client_key, None)
        return {"status": "error", "message": str(e), "data": None}
# ---------------------------------------------------------------------------------- FLASK RUTINE -----------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('SCADA.html')

@app.route('/write', methods=['POST'])
def write_register():
    try:
        data = request.json or {}
        if "address" not in data or "value" not in data:
            return jsonify({"status": "error", "message": "'address' and 'value' required"})

        register_address = int(data.get("address"))
        register_value = int(data.get("value"))
        bit_size = int(data.get("bit_size", 16))
        client_key = data.get("client", "A")

        result = write_register_internal(register_address, register_value, client_key, bit_size)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"})

##OVo pozivam s frontenda za primanje mape registara-------------------------------------------------------------------------
@app.route('/Frontend_primi_podatke', methods=['GET'])
def Frontend_primi_podatke():
    return jsonify({k: {"value": v} for k, v in register_map.items()})

#Ovo koristim za saljnje podataka na backend s frontenda----------------------------------------------------------------------
@app.route('/Frontend_salji_podatke', methods=['POST'])
def Frontend_salji_podatke():
    podaci_s_frontenda = request.get_json()  # Primanje JSON-a s frontenda
    if podaci_s_frontenda:
    # Update REGISTER_mape
        register_map.update(podaci_s_frontenda)
    return jsonify({"status": "ok", "current_map": register_map})


# ------------------------ Set mode endpoint ------------------------
@app.route('/set_mode', methods=['POST'])
def set_mode():
    global zastavica
    data = request.get_json()
    if not data or "mode" not in data:
        return jsonify({"error": "Missing mode"}), 400

    mode_value = data["mode"]
    if mode_value not in (0, 1):
        return jsonify({"error": "Invalid mode"}), 400

    # Update the authoritative map
    zastavica=mode_value
    print(f"[INFO] Mode updated to {mode_value}")
    return jsonify({"success": True, "mode": mode_value})

@app.route('/get_mode', methods=['GET'])
def get_mode():
    mode = zastavica if 'zastavica' in globals() else 0
    return jsonify({"mode": mode})

#Pomoćna funkcija za sigurno zaokruživanje za spremanje
def safe_round(value, decimals=2):
    try:
        if value is None:
            return None
        return float(f"{float(value):.{decimals}f}")
    except Exception:
        return None

@app.route("/api/write_registers", methods=["GET"])
def get_write_registers():
    response = []

    for key, reg in WRITE_REGISTERS.items():
        response.append({
            "key": key,
            "id": reg["register_id"],
            "description": reg["description"],
            "explanation": reg.get("explanation", ""),
            "bit_size": reg["bit_size"],
            "gain": reg.get("gain", 1),
            "client": reg["client_key"]
        })

    return jsonify(response)

last_email_time = 0
EMAIL_COOLDOWN = 60  # seconds

# ---------------------------------- Rutina za slanje mail-a ---------------------------------------------------

def send_email_alert(subject, body):
    sender_email = "filip.kralj@solektra.hr"
    receiver_email = "kralj.filip007@gmail.com"
    password = "syaa vzpb pogu yseb"  # from Google

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()

        logger.info("Email poslan!")

    except Exception as e:
        logger.error(f"Email error: {e}")


# ---------------------------------- Definiranje registara i varijabli za čitanje ------------------------------------------------


probni_a_value=0
probni_b_value=0
probni_c_value=0

# -------------------------------------------------------- Spremanje u log. fajlove i slanje prema CLABU ---------------------------------------------------
def save_data(content=None):
 while True: 
    try:

        # Struktura upisa
        log_entry = {
                "Timestamp": utc_now_iso(),
                "Active power": probni_a_value,
                "Line voltage": probni_b_value,
                "SOC": probni_c_value

        }
        # Naziv datoteke definicija
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(LOG_DIR, f"{date_str}.log")

        # Spremanje u fajl
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception as e:
        logger.warning(f"Greška spremanja podataka: {e}")
    time.sleep(2)


# ------------------------------------------------------------------------------------ GLAVNI PROGRAM ----------------------------------------------------------------------

# ----------------------------------------------- Definiranje pisanja u registre ------------------------------------------------

probni_a_citanje=config["definicija_registara"]["probni_a_citanje"]
probni_b_citanje=config["definicija_registara"]["probni_b_citanje"]
probni_c_citanje=config["definicija_registara"]["probni_c_citanje"]

#-------------------------ČITANJE REGISTARA----------------------------------------
def CITANJE_REGISTARA():
    
    global probni_a_value,  probni_b_value, probni_c_value
    global last_email_time

    while True:
        try:
            # PROBNI A
            try:
                probni_a_value = read_register_internal(probni_a_citanje["register_id"], client_key=probni_a_citanje["client_key"], datatype=probni_a_citanje["datatype"]).get("data", 0)
                probni_a_value *= probni_a_citanje["gain"]
                probni_a_value = safe_round(probni_a_value)
                print(f"Vrijednost struje L1(A) {probni_a_value}")

            except Exception as e:
                probni_a_value = 0
                logger.warning("Greška čitanja podataka s probnog A registra: %s", e)

             # PROBNI B
            try:
                probni_b_value = read_register_internal(probni_b_citanje["register_id"], client_key=probni_b_citanje["client_key"], datatype=probni_b_citanje["datatype"]).get("data", 0)

                print(f"optokupler vrijednost: {probni_b_value}")
               
            
            except Exception as e:
                probni_b_value = 0
                logger.warning("Greška čitanja podataka s probnog B registra: %s", e)    
            
            #  # PROBNI C
            # try:
            #     probni_c_value = read_register_internal(probni_c_citanje["register_id"], client_key=probni_c_citanje["client_key"], datatype=probni_c_citanje["datatype"]).get("data", 0)
            #     probni_c_value *= probni_c_citanje["gain"]
            #     probni_c_value = safe_round(probni_c_value)
            # except Exception as e:
            #     probni_c_value = 0
            #     logger.warning("Greška čitanja podataka s probnog B registra: %s", e)    
        

            time.sleep(1)

        except Exception as e:
            # preostale greške u background tasku
            logger.error("Background task error: %s", e)


#----------------------------------------------------------------- Upravljanje elektranom ----------------------------------------------------------
def FRONTEND_PRIJENOS():

    
#petlja regulacije
    while True:
        try:
           
            register_map["M_probni_a"] = probni_a_value
            register_map["M_probni_b"] = probni_b_value
            register_map["M_probni_c"] = probni_c_value
        
        except Exception as e:
            logger.error(f"Problem u programu regulacije: {e}")
        time.sleep(1)     



def MQTT_indikator():
    # ===== CONFIG =====
    BROKER1 = "ba17a54308ab4625a6ac98fe3677d0ec.s1.eu.hivemq.cloud"
    PORT1 = 8883  # TLS port
    USERNAME1 = "Filip"
    PASSWORD1 = "Pinkala!23"

    CLIENT_ID1 = "SOL_IX"  # must be a string
    TOPIC1 = "Indikator_SN/SOL_IX"          # must be a string

    logger.info("Pokretanje MQTT za nadzor napona...")

    # ------------------------------------------------ CALLBACKS ------------------------------------------------
    def on_connect1(client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.is_connected_flag = True
            logger.info("MQTT za nadzor napona povezan")
        else:
            logger.error(f"MQTT za nadzor napona - greška povezivanja: {rc}")

    def on_disconnect1(client, userdata, rc):
        client.is_connected_flag = False
        if rc != 0:
            logger.warning(f"MQTT za nadzor napona - greška disconnect-a ({rc})")
        else:
            logger.info("MQTT za nadzor napona - disconnected")

    # ------------------------------------------------ CLIENT ------------------------------------------------
    client1 = mqtt_client.Client(
        client_id=CLIENT_ID1,
        protocol=mqtt_client.MQTTv311
    )

    client1.username_pw_set(USERNAME1, PASSWORD1)
    client1.tls_set()  # TLS required for HiveMQ Cloud
    client1.reconnect_delay_set(min_delay=1, max_delay=30)
    client1.is_connected_flag = False

    client1.on_connect = on_connect1
    client1.on_disconnect = on_disconnect1

    # ------------------------------------------------ CONNECT ------------------------------------------------
    while True:
        try:
            client1.connect(BROKER1, PORT1, keepalive=60)
            break
        except Exception as e:
            logger.warning(f"Greška povezivanja: {e}")
            time.sleep(5)

    client1.loop_start()

    # ------------------------------------------------ PUBLISH LOOP ------------------------------------------------
    while True:
        try:
            # wait for connection
            if not client1.is_connected_flag:
                time.sleep(1)
                continue

            data1 = {
                
                "Input 1": probni_a_value,
                "Input 2": probni_b_value,
                "Input 3" : probni_c_value
            }

            payload = json.dumps(data1)

            result = client1.publish(
                TOPIC1,
                payload,
                qos=1,
                retain=False
            )

            if result.rc != mqtt_client.MQTT_ERR_SUCCESS:
                logger.warning(f"MQTT za nadzor napona - greška rc={result.rc}")

            time.sleep(1)

        except Exception as e:
            logger.warning(f"MQTT za nadzor napona - runtime error {e}")
            time.sleep(2)

# --------------------------------------------------------------------------- MAIN dio ------------------------------------------------
if __name__ == '__main__':
    logger.info("Pokretanje MQTT servisa...")
    
    logger.info("Pokretanje pozadinskih servisa...")

    Thread(target=CITANJE_REGISTARA, daemon=True).start()
    Thread(target=FRONTEND_PRIJENOS, daemon=True).start()
    Thread(target=save_data, daemon=True).start()
    Thread(target=MQTT_indikator, daemon=True).start()

    logger.info("Pokretanje WAITRESS servisa http://0.0.0.0:5000 ...")
    try:
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except KeyboardInterrupt:
        logger.info("Server zaustavljen ručno")
    
    # Keep console open after server stops
    input("Pritisnite Enter za izlaz iz skripte...")

