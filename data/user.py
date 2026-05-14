import datetime
import sqlalchemy
from .db_session import SqlAlchemyBase

from sqlalchemy import orm


class User(SqlAlchemyBase):
    __tablename__ = "users"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    uuid = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    phone = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    full_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)
    last_seen = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)

    sent_messages = orm.relationship(
        "Message", foreign_keys="Message.sender_id", backref="sender"
    )
    received_messages = orm.relationship(
        "Message", foreign_keys="Message.recipient_id", backref="recipient"
    )
