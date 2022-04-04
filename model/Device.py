import datetime
from model.Meta import meta
from sqlalchemy import Table, Text, Column, Float, BigInteger, Integer, String, MetaData, Sequence, ForeignKey, DateTime

device_type = Table(
  'signalogic_devicetype', meta, 
  Column('id', Integer), 
  Column('name', String(256)), 
  Column('description', Text), 
)

service_type = Table(
  'signalogic_servicetype', meta, 
  Column('id', Integer), 
  Column('name', String(256)), 
  Column('description', Text), 
)

device = Table(
  'signalogic_device', meta, 
  Column('id', Integer, primary_key = True), 
  Column('deveui', String(128)), 
  Column('appeui', String(128)), 
  Column('appkey', String(128)), 
  Column('user_id', Integer), 
  Column('device_class', Integer), 
  Column('name', String(256)), 
  Column('alias', String(256)), 
)

device_signal = Table(
  'signalogic_devicesignal', meta, 
  Column('id', Integer, primary_key = True), 
  Column('device_type_id', Integer, ForeignKey("signalogic_devicetype.id"), nullable=False), 
  Column('service_type_id', Integer, ForeignKey("signalogic_servicetype.id"), nullable=False), 
  Column('name', String(256)), 
  Column('alias', String(256)), 
  Column('unit', String(64)), 
)

signal = Table(
  'signalogic_signal', meta, 
  Column('id', String(256), primary_key = True), 
  Column('device_id', Integer, ForeignKey("signalogic_device.id"), nullable=False), 
  Column('device_signal_id', Integer, ForeignKey("signalogic_devicesignal.id"), nullable=False), 
  Column('service_type_id', Integer, ForeignKey("signalogic_servicetype.id"), nullable=False), 
  Column('name', String(256)), 
  Column('alias', String(256)), 
  Column('unit', String(64)), 
)

device_reading = Table(
  'signalogic_devicereading', meta, 
  Column('id', Integer, primary_key = True), 
  Column('device_signal_id', Integer, ForeignKey("signalogic_devicesignal.id"), nullable=False), 
  Column('device_id', Integer, ForeignKey("signalogic_device.id"), nullable=False), 
  Column('value', Float), 
  Column('reading_date', DateTime, default=datetime.datetime.utcnow), 
)

device_cflist = Table(
  'signalogic_devicecflist', meta, 
  Column('id', Integer, primary_key = True), 
  Column('device_id', Integer, ForeignKey("signalogic_device.id"), nullable=False), 
  Column('channel',  Integer),
)

device_session = Table(
  'signalogic_devicesession', meta, 
  Column('id', Integer, primary_key = True), 
  Column('device_id', Integer, ForeignKey("signalogic_device.id"), nullable=False), 
  Column("networkId",  Integer),
  Column("deviceAddr", Integer),
  Column("nOnce", Integer),
  Column("devNOnce", Integer),
  Column("fNwkSIntKey", String(128)),
  Column("sNwkSIntKey", String(128)),
  Column("nwkSEncKey", String(128)),
  Column("appSKey", String(128)),
  Column("lastAccessTime", BigInteger),
  Column("fCntUp", BigInteger),
  Column("fCntDown", BigInteger),
  Column("rxDelay1", Integer),
  Column("joinAckDelay1", Integer),
  Column("rx2Channel", Integer),
  Column("rx2Datarate", Integer),
)
