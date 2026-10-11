from datetime import datetime
from src.database import db


class AliceConversation(db.Model):
    """Persisted ALICE conversation per user + session (replaces HRMS JSON files)."""

    __tablename__ = 'alice_conversation'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)
    messages_json = db.Column(db.Text, nullable=True)  # JSON array of {role, content, ...}
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'session_id', name='uq_alice_user_session'),
    )

    def __repr__(self):
        return f'AliceConversation {self.id} user={self.user_id} session={self.session_id}'
