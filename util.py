from datetime import datetime
import model.Device
from model.Device import device, device_reading, device_session, device_cflist, device_type, device_signal, device_sendqueue, signal
from model.Database import engine, session
from sqlalchemy.sql import select, and_
from sqlalchemy.exc import OperationalError

def exec_query(sql):
    try:
        res = session.execute(sql)
        session.commit()
    except OperationalError as e:
        session.rollback()
        print(e)
        res = session.execute(sql)
        session.commit()

    session.close()
    return res
        

def add_send_data(device_id, port, data, confirm):
    sql = device_sendqueue.select().where(device_sendqueue.c.device_id == device_id).order_by(device_sendqueue.c.id)
    sql = device_sendqueue.insert().values({'device_id': device_id,
                                            'port': port,
                                            'data': data,
                                            'confirmation': confirm})
    res = exec_query(sql)


def find_send_data(device_id):
    sql = device_sendqueue.select().where(device_sendqueue.c.device_id == device_id).order_by(device_sendqueue.c.id)
    res = exec_query(sql)

    res = list(res)

    for row in res:
        sql = device_sendqueue.delete().where(device_sendqueue.c.id == row['id'])
        exec_query(sql)
        return row

    return None


def find_device_id(device_id):
    sql = device.select().where(device.c.id == device_id)

    res = exec_query(sql)

    res = list(res)

    if len(res) == 0:
        return None

    return list(res)[0]

def find_device(devEui, appEui):
    sql = device.select().where(and_(device.c.deveui == devEui, device.c.appeui == appEui))

    res = exec_query(sql)

    res = list(res)

    return res

def find_device_cflist(device_id):
    sql = device_cflist.select().where(device_cflist.c.device_id == device_id)

    cflist = []

    res = exec_query(sql)

    for row in res:
        cflist.append(row['channel'])

    return cflist

def find_device_session(device_id):
    sql = device_session.select().where(device_session.c.device_id == device_id)

    res = exec_query(sql)

    for row in res:
        res = row
        return res

    return None

def find_session(netId, devAddr):
    sql = device_session.select().where(and_(device_session.c.networkId == netId, device_session.c.deviceAddr == devAddr))

    rows = exec_query(sql)

    res = list(rows)

    return res

def find_signal_by_id(device, sid):
    signal = model.Device.signal
    sql = signal.select().where(and_(signal.c.device_id == device['id'], signal.c.device_signal_id == sid))
    signals = exec_query(sql)
    for signal in signals:
        res = signal
        return res

    return None

def find_signal_by_name(device, name):
    signal = model.Device.signal
    sql = signal.select().where(and_(signal.c.alias.like('{}%'.format(name)), signal.c.device_id == device['id']))
    signals = exec_query(sql)
    for signal in signals:
        res = signal
        return res
    return None

def find_device_type(device):
    sql = device_type.select().where(device_type.c.id == device['device_type_id'])
    types = exec_query(sql)
    for t in types:
        print('Found type {}'.format(t))
        return t['name']

    return None

def save_device_reading(device, signal_name, value, time = None):
    if time is None:
        time = datetime.utcnow();
    signal = find_signal_by_name(device, signal_name)
    if signal is None:
        print("Signal {} not found for device {}!".format(signal_name, device))
        return
    print("Found signal {} for device {}".format(signal, device))
    sql = device_reading.insert().values({'device_signal_id': signal['device_signal_id'], 
                                          'device_id': signal['device_id'], 'value': value,
                                          'reading_date': time})
    exec_query(sql)

def update_control(sess, signal_name, value):
    print("Updating control state")
    rows = find_device(sess.device.devEUI, sess.device.appEUI)
    
    print("Found {} devices".format(len(rows)))
    for row in rows:
        signal = find_signal_by_name(row, signal_name)
        if signal is None:
            print("Signal not found!")
            continue
        flat_id = row['flat_id']
        sql = device_reading.select().where(and_(device_reading.c.flat_id == row['flat_id'], device_reading.c.device_signal_id == signal['id']))
        rows2 = list(session.execute(sql))
        numreadings = len(rows2)
        if numreadings == 0:
            print("Inserting device reading")
            sql = device_reading.insert().values({'device_signal_id': signal['id'], 'flat_id': row['flat_id'], 'value': value})
        else:
            for reading in rows2:
                print("Updating device reading {}".format(reading['id']))
                sql = device_reading.update().where(device_reading.c.id == reading['id']).values({'value': value})
        exec_query(sql)

def save_session(**row):
    if not 'device_id' in row:
        return None

    sql = device_session.select().where(device_session.c.device_id == row.get('device_id'))

    res = list(exec_query(sql))

    if bool(res):
        sql = device_session.update().where(device_session.c.id == res[0]['id']).values(row)
        exec_query(sql)
        res = res[0]['id']
    else:
        sql = device_session.insert().values(row)
        res = exec_query(sql).inserted_primary_key

    return res

def row_from_session(session):
    if session.device is None:
        return None

    row = session.__dict__
    device = row.pop('device')

    device = find_device(device.devEUI, device.appEUI)

    if len(device) > 0:
        row['device_id'] = device[0]['id']
    return row

if __name__ == "__main__":
    print(find_signal_by_name({'id': 1}, 'meter'))

