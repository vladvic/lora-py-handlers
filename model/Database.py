from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine import Engine
from sqlalchemy import event
from model.Meta import meta

#engine = create_engine('sqlite:///db/logibot.db', echo=True)
engine = create_engine('mysql+mysqlconnector://communal:communal@localhost/communal1', echo=False, pool_size=10, max_overflow=20)
session = scoped_session(sessionmaker(autocommit=False, autoflush=True, bind=engine))

@event.listens_for(engine, "connect")
def config_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('SET sql_mode="STRICT_TRANS_TABLES"')
    cursor.close()
    pass

meta.create_all(engine)

