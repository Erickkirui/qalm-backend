
from datetime import datetime, timezone
from sqlalchemy.orm import validates
from app import db


class TherapistMatchPreference(db.Model):
    __tablename__ = "therapist_match_preferences"

    id = db.Column(db.Integer, primary_key=True)

    # User requesting therapist recommendations
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Location preferences
    country = db.Column(
        db.String(100),
        nullable=False,
        default="Kenya"
    )

    county = db.Column(
        db.String(100),
        nullable=True
    )

    town = db.Column(
        db.String(100),
        nullable=True
    )

    preferred_location = db.Column(
        db.String(255),
        nullable=True
    )

    # Accepted location types
    location_type = db.Column(
        db.String(20),
        nullable=False,
        default="any"
    )

    # Areas where the user needs help
    help_areas = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # Preferred session type
    session_types = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: ["online"]
    )

    # Optional preferences
    preferred_languages = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    min_experience_years = db.Column(
        db.Integer,
        nullable=True
    )

    max_consultation_fee = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    currency = db.Column(
        db.String(3),
        nullable=False,
        default="KES"
    )

    # Whether the user wants recommendations
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
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

    # Accepted location types
    @validates("location_type")
    def validate_location_type(self, key, location_type):
        allowed_types = (
            "online",
            "in_person",
            "both",
            "any"
        )

        assert location_type in allowed_types, (
            f"Location type must be one of: {', '.join(allowed_types)}."
        )

        return location_type

    # Required country
    @validates("country")
    def validate_country(self, key, country):
        assert country and country.strip(), (
            "Country is required."
        )

        return country.strip()

    # Areas where help is needed
    @validates("help_areas")
    def validate_help_areas(self, key, areas):
        assert isinstance(areas, list) and len(areas) > 0, (
            "Select at least one area where you need help."
        )

        assert all(
            isinstance(area, str) and area.strip()
            for area in areas
        ), "Each help area must be a non-empty string."

        cleaned_areas = [
            area.strip().lower()
            for area in areas
        ]

        assert len(cleaned_areas) == len(set(cleaned_areas)), (
            "Help areas cannot contain duplicates."
        )

        return cleaned_areas

    # Preferred session types
    @validates("session_types")
    def validate_session_types(self, key, types):
        allowed_types = ("online", "in_person")

        assert isinstance(types, list) and len(types) > 0, (
            "Select at least one session type."
        )

        assert all(
            isinstance(item, str) and item in allowed_types
            for item in types
        ), f"Session types must be: {', '.join(allowed_types)}."

        assert len(types) == len(set(types)), (
            "Session types cannot contain duplicates."
        )

        return types

    # Preferred languages
    @validates("preferred_languages")
    def validate_preferred_languages(self, key, languages):
        assert isinstance(languages, list), (
            "Preferred languages must be provided as a list."
        )

        assert all(
            isinstance(language, str) and language.strip()
            for language in languages
        ), "Each language must be a non-empty string."

        return [language.strip() for language in languages]

    # Minimum therapist experience
    @validates("min_experience_years")
    def validate_min_experience_years(self, key, years):
        assert (
            years is None
            or (
                isinstance(years, int)
                and not isinstance(years, bool)
                and years >= 0
            )
        ), "Minimum experience must be a non-negative whole number."

        return years

    # Maximum consultation fee
    @validates("max_consultation_fee")
    def validate_max_consultation_fee(self, key, fee):
        assert fee is None or fee >= 0, (
            "Maximum consultation fee cannot be negative."
        )

        return fee

    # Currency
    @validates("currency")
    def validate_currency(self, key, currency):
        assert isinstance(currency, str), (
            "Currency must be a three-letter code, e.g. KES."
        )

        currency = currency.strip().upper()

        assert len(currency) == 3 and currency.isalpha(), (
            "Currency must be a three-letter code, e.g. KES."
        )

        return currency

    # Relationships
    user = db.relationship(
        "Users",
        foreign_keys=[user_id],
        backref=db.backref(
            "therapist_match_preference",
            uselist=False
        )
    )

    # Serializer
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "country": self.country,
            "county": self.county,
            "town": self.town,
            "preferred_location": self.preferred_location,
            "location_type": self.location_type,
            "help_areas": self.help_areas,
            "session_types": self.session_types,
            "preferred_languages": self.preferred_languages,
            "min_experience_years": self.min_experience_years,
            "max_consultation_fee": (
                str(self.max_consultation_fee)
                if self.max_consultation_fee is not None
                else None
            ),
            "currency": self.currency,
            "is_listed": self.is_listed,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at else None
            ),
        }

    def __repr__(self):
        return (
            f"TherapistMatchPreference("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"is_active={self.is_active})"
        )
