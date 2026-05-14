import datetime
import sqlalchemy
from data.db_session import SqlAlchemyBase


class Message(SqlAlchemyBase):
    __tablename__ = "messages"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    uuid = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    sender_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"), nullable=False
    )
    recipient_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"), nullable=False
    )
    content = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    is_read = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)
    delivered_at = sqlalchemy.Column(sqlalchemy.DateTime)
    read_at = sqlalchemy.Column(sqlalchemy.DateTime)
