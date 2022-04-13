import threading
import random
import base64
import lorawan
import struct
from sys import stdout
from lorawan import DeviceSession, DeviceInfo, CLASS_A, CLASS_B, CLASS_C
from util import *
from handlers import deviceTypes
from flask import Flask, request

def device_from_row(row):
    if row is None:
        return None

    device = DeviceInfo()
    device.devEUI = row["deveui"]
    device.appEUI = row["appeui"]
    device.appKey = row["appkey"]
    device.cflist = find_device_cflist(row["id"])
    if row["device_class"] == 0:
        device.devClass = CLASS_A
    elif row["device_class"] == 1:
        device.devClass = CLASS_B
    else:
        device.devClass = CLASS_C
    stdout.flush()
    return device

def session_from_row(row):
    if row is None:
        return None

    session = DeviceSession()
    session.networkId = row['networkId']
    session.deviceAddr = row['deviceAddr']
    session.nOnce = row['nOnce'] or 0
    session.devNOnce = row['devNOnce'] or 0
    session.fNwkSIntKey = row['fNwkSIntKey']
    session.sNwkSIntKey = row['sNwkSIntKey']
    session.nwkSEncKey = row['nwkSEncKey']
    session.appSKey = row['appSKey']
    session.lastAccessTime = row['lastAccessTime']
    session.fCntUp = row['fCntUp'] or 0
    session.fCntDown = row['fCntDown'] or 0
    session.rxDelay1 = row['rxDelay1'] or 5
    session.joinAckDelay1 = row['joinAckDelay1'] or 5
    session.rx2Channel = row['rx2Channel'] or 0
    session.rx2Datarate = row['rx2Datarate'] or 0
    stdout.flush()
    return session

def create_new_session(row):
    sess = DeviceSession()
    sess.deviceAddr = random.randint(0, 0x00ffffff)
    sess.rxDelay1 	   = 5
    sess.joinAckDelay1 = 5
    sess.rx2Channel  = 0
    sess.rx2Datarate = lorawan.DR0
    sess.devNOnce    = 0
        

def ndpd_get_device_info(devEUI, appEUI):
    result = []
    rows = find_device(devEUI, appEUI)
    print("Getting device info {}:{}".format(devEUI, appEUI))
    
    for row in rows:
        device = device_from_row(row)
        device.session = session_from_row(find_device_session(row["id"]))
        if device.session is None:
            device.session = create_new_session(row);
        result.append(device)

    stdout.flush()
    return result

def ndpd_get_device_session(deviceAddr, networkAddr):
    result = []
    rows = find_session(networkAddr, deviceAddr)
    print("Getting session info {}:{}".format(deviceAddr, networkAddr))

    for row in rows:
        session = session_from_row(row)
        session.device = device_from_row(find_device_id(row["device_id"]))
        result.append(session)

    stdout.flush()
    return result

def ndpd_save_device_session(session):
    print("Saving device session: {}".format(session.__dict__))
    row = row_from_session(session)
    save_session(**row)
    stdout.flush()
    pass

def ndpd_process_data(session, port, data):
    print('Got data from device {} : {}'.format(session.device.devEUI, session.device.appEUI))

    rows = find_device(session.device.devEUI, session.device.appEUI)

    if len(rows) == 0:
        print('Device not found')

    for row in rows:
        handler = deviceTypes.get(session.device.appEUI, {}).get('get', None)
        if handler is not None:
            print('Calling handler {}'.format(handler))
            handler(session, port, data)
        else:
            print('Handler for appEUI {} not found'.format(session.device.appEUI))

        send_data = find_send_data(row['id'])

        if send_data is not None:
            lorawan.send(session.networkId, session.deviceAddr, send_data['port'], bytearray(send_data['data']), send_data['confirmation'])

    stdout.flush()


###############################################################################################
#    Flask app to access lorawan device sending functions                                     #
###############################################################################################

app = Flask(__name__)

@app.route("/send", methods=["POST", "GET"])
def send_device_data():
    print("Data: {}".format(request.data))
    args = request.get_json(force=True)
    signalName = args.get('signal', '0:0')
    dev, signal = signalName.split(':')
    base64_data = args.get('data', None)

    if base64_data is not None:
        base64_bytes = base64_data.encode('ascii')
        data = bytearray(base64.b64decode(base64_bytes))
        print('Got data for device {} : {}: {}'.format(dev, signal, base64_bytes))
    else:
        value = args.get('value', 0)
        data = struct.pack('f', value)
        print('Got value for device {} : {}: {}'.format(dev, signal, value))
    print("Type: {}".format(type(data)))

    row = find_device_id(dev)

    print('Found {} device'.format(row))
    if row is not None:
        session = session_from_row(find_device_session(row["id"]))
        signal = find_signal_by_id(row, signal)

        if signal is None:
            return "{}:{}\n".format(dev, signal), 404

        device = device_from_row(row)

        print('Device: {}'.format(device))
        handler = deviceTypes.get(device.appEUI, {'set': None}).get('set', None)
        if handler is not None:
            handler(session, signal, data)

        stdout.flush()
        return "{}:{}\n".format(device.devEUI, device.appEUI), 200

    stdout.flush()
    return "{}:{}\n".format(dev, signal), 404

def run_flask():
    try:
        kwargs = {'debug': True, 'use_reloader': False, 'port': 4000, 'host': 'localhost'}
        app.run(**kwargs)
    except Exception as e:
        print("Flask error: {}".format(e))
        pass

t1 = threading.Thread(target=run_flask, daemon=True)
t1.start()

print("Config module imported!")

