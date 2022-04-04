from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

meta = MetaData()
Base = declarative_base(metadata=meta)

