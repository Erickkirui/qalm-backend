
from datetime import datetime, timezone
from sqlalchemy.orm import validates
from app import db


class Journal(db.Model):
    __tablename__ = "journals"

    id = db.Column(db.Integer, primary_key=True)

    # Journal owner
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Entry content
    title = db.Column(
        db.String(200),
        nullable=True
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    # Optional mood tracking
    mood = db.Column(
        db.String(30),
        nullable=True
    )

    # Optional tags, e.g. stress, family, work
    tags = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # Entry status
    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft"
    )

    # Explicit permission to share entries with an authorized therapist
    is_shared_with_therapist = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Encryption metadata for application-level encrypted content
    encryption_version = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    # Timestamps
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = db.relationship(
        "Users",
        foreign_keys=[user_id],
        backref=db.backref("journal_entries", lazy=True)
    )

    # Accepted moods
    @validates("mood")
    def validate_mood(self, key, mood):
        allowed_moods = (
            "very_sad",
            "sad",
            "neutral",
            "good",
            "very_good",
            "anxious",
            "angry",
            "stressed",
            "calm",
            "happy"
        )

        if mood is not None:
            assert mood in allowed_moods, (
                f"Mood must be one of: {', '.join(allowed_moods)}."
            )

        return mood

    # Accepted statuses
    @validates("status")
    def validate_status(self, key, status):
        allowed_statuses = ("draft", "completed")

        assert status in allowed_statuses, (
            f"Status must be one of: {', '.join(allowed_statuses)}."
        )

        return status

    # Required content
    @validates("content")
    def validate_content(self, key, content):
        assert isinstance(content, str) and content.strip(), (
            "Journal content is required."
        )

        return content.strip()

    # Optional title
    @validates("title")
    def validate_title(self, key, title):
        if title is not None:
            title = title.strip()
            return title or None

        return title

    # Tags
    @validates("tags")
    def validate_tags(self, key, tags):
        assert isinstance(tags, list), (
            "Tags must be provided as a list."
        )

        assert all(
            isinstance(tag, str) and tag.strip()
            for tag in tags
        ), "Each tag must be a non-empty string."

        return list(dict.fromkeys(
            tag.strip().lower() for tag in tags
        ))

    # Sharing preference
    @validates("is_shared_with_therapist")
    def validate_sharing(self, key, shared):
        assert isinstance(shared, bool), (
            "Sharing preference must be true or false."
        )

        return shared

    # Serializer
    def to_dict(self, include_content=True):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "mood": self.mood,
            "tags": self.tags,
            "status": self.status,
            "is_shared_with_therapist": (
                self.is_shared_with_therapist
            ),
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at else None
            ),
        }

        if include_content:
            data["content"] = self.content

        return data

    def __repr__(self):
        return (
            f"Journal(id={self.id}, "
            f"user_id={self.user_id}, "
            f"status='{self.status}')"
        )
