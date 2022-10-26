from datetime import datetime, timezone
import threading
import time
import lorawan
import struct
from util import *

def electro_write(session, signal, data):
    if signal['alias'][:9] == 'meter':
        addr = session.deviceAddr.to_bytes(4, byteorder='little')
        send_data = list([5])
        send_data.extend(list(addr))
        send_data.append(0)
        send_data.extend(int(time.time()).to_bytes(4, byteorder='little'))
        send_data.extend([0, 1])
        print("Sending data: {}".format(send_data))
        send_data = bytearray(send_data)
        lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def electro_read(session, port, data, data_mapping = {"ts": 5, "wth": 13}):
    rows = find_device(session.device.devEUI, session.device.appEUI)

    print('Got electricity meter data for device {}:{}'.format(session.device.devEUI, session.device.appEUI))
    print('Packet type: {}, port: {}'.format(data[0], port))
    if port == 2:
        print('Port matches')
        datatype = data[0]
        if datatype == 4:
            try:
                print('Data type matches')
                utc_ts_bytes = data[data_mapping["ts"]:data_mapping["ts"]+4]
                WtH_bytes = data[data_mapping["wth"]:data_mapping["wth"]+4]
                utc_ts = int.from_bytes(bytes(utc_ts_bytes), byteorder='little')
                WtH = int.from_bytes(bytes(WtH_bytes), byteorder='little')

                print('Adding device reading: {}: {}'.format(utc_ts, WtH / 1000))
                for row in rows:
                    save_device_reading(row, 'meter', WtH / 1000, datetime.fromtimestamp(utc_ts))
            except Exception as e:
                print(e)


def water_meter(session, port, data):
    datatype = data[0]
    
    print('Got water meter data on port {}'.format(port))
    if port == 2 and datatype == 1:
        temp = data[2] # Water temp
        magnetic = data[3] # Magnetic field indicator
        blocked = data[4] # Digital display is locked
        utc_ts = int.from_bytes(data[5:9], 'little')
        leakage = data[9] # Leakage indicator
        outburst = data[10] # Leakage indicator
        cubic_meters = int.from_bytes(data[11:15], 'little')
        rows = find_device(session.device.devEUI, session.device.appEUI)

        for row in rows:
            print('Adding device reading: {}'.format(cubic_meters / 10000))
            save_device_reading(row, 'meter', cubic_meters / 10000, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, 'leak', leakage, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, 'burst', outburst, datetime.fromtimestamp(utc_ts))

        dt = datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)
        now_ts = int(utc_time.timestamp())
        diff = now_ts - utc_ts

        if abs(diff) > (60 * 60 * 24):
            send_data = bytearray([255])
            send_data.extend(diff.to_bytes(8, byteorder = 'little', signed=True))
            print("Time correction packet: {}".format(send_data))
            lorawan.send(session.networkId, session.deviceAddr, 4, send_data, False)
    if port == 4 and datatype == 255:
        dt = datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)
        now_ts = int(utc_time.timestamp())

        utc_ts = int.from_bytes(data[1:5], 'little')
        diff = now_ts - utc_ts

        if abs(diff) < (60 * 60 * 24) and abs(diff) > 50:
            send_data = bytearray([255])
            send_data.extend(diff.to_bytes(8, byteorder = 'little', signed=True))
            print("Time correction packet: {}".format(send_data))
            lorawan.send(session.networkId, session.deviceAddr, 4, send_data, False)


def enable_relay(session):
    send_data = bytearray([3, 1, 0])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)
    print("Sleeping 4 seconds")
    time.sleep(4)
    send_data = bytearray([3, 2, 0])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def disable_relay(session):
    send_data = bytearray([4, 2])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)
    print("Sleeping 4 seconds")
    time.sleep(4)
    send_data = bytearray([4, 1])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def si12_read(session, port, data):
    print('Got relay data')
    rows = find_device(session.device.devEUI, session.device.appEUI)
    if port == 2 and data[0] == 5:
        inputN = data[3]
        utc_ts = int.from_bytes(data[4:8], 'little')
        for row in rows:
            if inputN == 1:
                save_device_reading(row, 'relay1', data[4])
            elif inputN == 2:
                save_device_reading(row, 'relay2', data[4])
    if port == 2 and data[0] == 1:
        input1 = int.from_bytes(bytes(data[5:9]), byteorder='little')
        input2 = int.from_bytes(bytes(data[9:13]), byteorder='little')
        utc_ts = int.from_bytes(data[3:7], 'little')
        config = data[2]
        input1type = 'input'
        input2type = 'input'
        if config & 0x10:
            input1type = 'alarm'
        if config & 0x20:
            input2type = 'alarm'
        for row in rows:
            save_device_reading(row, input1type+'1', input1, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, input2type+'2', input2, datetime.fromtimestamp(utc_ts))
    if port == 2 and data[0] == 2:
        inputN = data[3]
        utc_ts = int.from_bytes(data[4:8], 'little')

        for row in rows:
            if row['alias'][-5:] == 'valve':
                save_device_reading(row, "alarm{}".format(inputN), 1, datetime.fromtimestamp(utc_ts))
                relay1 = load_last_device_reading(row, 'relay1')
                relay2 = load_last_device_reading(row, 'relay2')
                if relay2 > 0 or relay1 < 1:
                    print("Locking valve {}".format(row['alias']))
                    t1 = threading.Thread(target=lambda : run_delayed(lambda : disable_valve(session), 2), daemon=True)
                    t1.start()
    if port == 2 and data[0] == 6:
        utc_ts = int.from_bytes(data[1:5], 'little')
        inputs = int.from_bytes(data[5:7], 'little')
        outputs = int.from_bytes(data[7:9], 'little')
        output1 = outputs & 0x01
        output2 = outputs & 0x02
        input1 = int.from_bytes(data[9:13], 'little')
        input2 = int.from_bytes(data[13:17], 'little')
        input1type = 'input'
        input2type = 'input'
        if input1 == -1:
            input1 = inputs & 0x01
            input1type = 'alarm'
        if input2 == -1:
            input2 = inputs & 0x02
            input2type = 'alarm'
        for row in rows:
            save_device_reading(row, input1type+'1', input1, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, input2type+'2', input2, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, 'relay1', output1, datetime.fromtimestamp(utc_ts))
            save_device_reading(row, 'relay2', output2, datetime.fromtimestamp(utc_ts))
        

def si12_write(session, signal, data):
    port = 2
    if signal['alias'] == 'relay1' or signal['alias'] == 'relay2':
        print('Sending relay data to input {}: {}'.format(signal['alias'], data))
        data = struct.unpack('f', data)[0]
        print('Sending value {} to input {}'.format(data, signal['alias']))
        nInput = 1

        if signal['alias'] == 'relay2':
            nInput = 2

        if data < 0.5:
            send_data = bytearray([4, nInput])
        else:
            send_data = bytearray([3, nInput, 0])

        lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def tp11_read(session, port, data):
    print('Got TP-11 data')
    rows = find_device(session.device.devEUI, session.device.appEUI)
    if port == 2 and data[0] == 1:
        utc_ts = int.from_bytes(data[3:7], 'little')
        reason = data[12]
        value = data[13]
        relay1 = 1 if (value & 0x08) > 0 else 0
        relay2 = 1 if (value & 0x10) > 0 else 0
        print("Relay1: {}; Relay2: {}".format(relay1, relay2))
        for row in rows:
            print("REASON: {}; VALUE: {}".format(reason, value))
            if load_last_device_reading(row, 'relay1') != relay1:
                save_device_reading(row, 'relay1', relay1)
            if load_last_device_reading(row, 'relay2') != relay2:
                save_device_reading(row, 'relay2', relay2)
            if reason == 1:
                value = value & 0x02
            if reason == 2:
                value = value & 0x04
            if (reason == 1 or reason == 2) and value != 0:
                save_device_reading(row, "alarm".format(reason), 1, datetime.fromtimestamp(utc_ts))
                if relay2 > 0 or relay1 < 1:
                    print("Locking valve {}".format(row['alias']))
                    t1 = threading.Thread(target=lambda : run_delayed(lambda : disable_valve(session), 2), daemon=True)
                    t1.start()
    if port == 2 and data[0] == 5:
        inputN = data[2]
        utc_ts = int.from_bytes(data[3:7], 'little')
        for row in rows:
            if inputN == 1:
                save_device_reading(row, 'relay1', data[3])
            elif inputN == 2:
                save_device_reading(row, 'relay2', data[3])


def pulsar_read(session, port, data):
    print("Got PULSAR data: {}".format(data))
    pass


def pulsar_write(session, signal, data):
    pass


def run_delayed(fun, delay):
    time.sleep(delay)
    fun()


def wait_and_send(session, send_data):
    dt = datetime.now()
    utc_time = dt.replace()
    now_ts = int(utc_time.timestamp() * 1000000)
    diff = now_ts - session.lastAccessTime
    if diff > 2000000:
        lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)
        return True
    return False

def disable_valve(session):
    devices = find_device(session.device.devEUI, session.device.appEUI)
    for device in devices:
        retry = 5
        send_data = bytearray([4, 2])
        print("relay2 value: {}".format(load_last_device_reading(device, 'relay2')))
        while retry > 0 and load_last_device_reading(device, 'relay2') > 0:
            if not wait_and_send(session, send_data):
                time.sleep(1)
                continue
            print("Sleeping 5 seconds")
            time.sleep(4)
            retry = retry - 1
        retry = 5
        send_data = bytearray([3, 1, 0])
        print("relay1 value: {}".format(load_last_device_reading(device, 'relay1')))
        while retry > 0 and load_last_device_reading(device, 'relay1') < 1:
            if not wait_and_send(session, send_data):
                time.sleep(1)
                continue
            print("Sleeping 5 seconds")
            time.sleep(4)
            retry = retry - 1


deviceTypes = {
    '7665676153564531': {'get': water_meter,  'set': None}, # Водосчётчики
    '5345454220312020': {'get': electro_read, 'set': electro_write}, # Электросчётчик
    '5350625a49503237': {'get': lambda a, b, c : electro_read(a, b, c, {"ts": 5, "wth": 13}), 
                         'set': electro_write}, # Электросчётчик, другая ревизия
    '7665676173693132': {'get': si12_read,   'set': si12_write}, # SI-12
    '3033676174703131': {'get': tp11_read,    'set': si12_write}, # TP-11
    '13a4c6518d60477f': {'get': pulsar_read,    'set': pulsar_write}, # Pulsar flow meters
}

