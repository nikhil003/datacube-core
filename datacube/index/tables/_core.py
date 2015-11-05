# coding=utf-8
"""
Module
"""
from __future__ import absolute_import

from sqlalchemy import MetaData
from sqlalchemy.schema import CreateSchema

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
SCHEMA_NAME = 'agdc'
metadata = MetaData(naming_convention=convention, schema=SCHEMA_NAME)


def ensure_db(connection, engine):
    if not engine.dialect.has_schema(connection, SCHEMA_NAME):
        engine.execute(CreateSchema(SCHEMA_NAME))
        metadata.create_all(engine)
