from datetime import datetime
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
        lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False);


def electro_read(session, port, data):
    rows = find_device(session.device.devEUI, session.device.appEUI)

    print('Got electricity meter data for device {}:{}'.format(session.device.devEUI, session.device.appEUI))
    print('Packet type: {}, port: {}'.format(data[0], port))
    if port == 2:
        print('Port matches')
        datatype = data[0]
        if datatype == 4:
            try:
                print('Data type matches')
                utc_ts = int.from_bytes(bytes(data[5:9]), byteorder='little')
                #WtH = int.from_bytes(bytes(data[10:14]), byteorder='little')
                WtH = int.from_bytes(bytes(data[10:14]), byteorder='big')

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
    if port == 4 and datatype == 255:
        dt = datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)
        now_ts = utc_time.timestamp()

        utc_ts = int.from_bytes(data[2:6], 'little')
        diff = now_ts - utc_ts

        if abs(diff) > 50:
            send_data = bytearray([255])
            send_data.extend(diff.to_bytes(8, byteorder = 'little'))
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


def relay_read(session, port, data):
    print('Got relay data')
    rows = find_device(session.device.devEUI, session.device.appEUI)
    if port == 2 and data[0] == 5:
        inputN = data[3]
        for row in rows:
            if inputN == 1:
                save_device_reading(row, 'relay1', data[4])
            elif inputN == 2:
                save_device_reading(row, 'relay2', data[4])
    if port == 2 and data[0] == 1:
        input1 = int.from_bytes(bytes(data[5:9]), byteorder='little')
        input2 = int.from_bytes(bytes(data[9:13]), byteorder='little')
        for row in rows:
            save_device_reading(row, 'input1', input1)
            save_device_reading(row, 'input2', input2)


def relay_write(session, signal, data):
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


def run_delayed(fun, delay):
    time.sleep(delay)
    fun()

def valve_read(session, port, data):
    print('Got valve packet type {}'.format(data[0]))
    if port == 2 and data[0] == 5 and data[3] == 2:
        update_control(session, 'state', data[4])
    elif port == 2 and data[0] == 2 and data[8] == 1:
        t1 = threading.Thread(target=lambda : run_delayed(lambda : disable_valve(session), 10), daemon=True)
        t1.start()
    elif port == 2 and data[0] == 2 and data[8] == 0:
        t2 = threading.Thread(target=lambda : run_delayed(lambda : enable_valve(session), 10), daemon=True)
        t1.start()


def enable_valve(session):
    send_data = bytearray([4, 1])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)
    print("Sleeping 4 seconds")
    time.sleep(4)
    send_data = bytearray([3, 2, 0])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def disable_valve(session):
    send_data = bytearray([4, 2])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)
    print("Sleeping 4 seconds")
    time.sleep(4)
    send_data = bytearray([3, 1, 0])
    lorawan.send(session.networkId, session.deviceAddr, 2, send_data, False)


def valve_write(session, signal, data):
    port = 2
    data = struct.unpack('f', data)[0]
    print('Sending valve data: {}'.format(data))
    if data == 1:
        t1 = threading.Thread(target=lambda : enable_valve(session), daemon=True)
        t1.start()
    else:
        t1 = threading.Thread(target=lambda : disable_valve(session), daemon=True)
        t1.start()


deviceTypes = {
    '7665676153564531': {'get': water_meter,  'set': None}, # Водосчётчики
    '5345454220312020': {'get': electro_read, 'set': electro_write}, # Электросчётчик
    '7665676173693132': {'get': relay_read,   'set': relay_write},
    #'Счётчик ГВ'     : {'get': water_meter,  'set': None},
    #'Нагрузка1'      : {'get': relay_read,   'set': relay_write},
    #'Нагрузка2'      : {'get': relay_read,   'set': relay_write},
    #'Вентиль ХВ'     : {'get': valve_read,   'set': valve_write},
    #'Вентиль ГВ'     : {'get': valve_read,   'set': valve_write},
}

