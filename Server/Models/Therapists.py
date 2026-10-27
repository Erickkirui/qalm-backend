
from datetime import datetime, timezone
from sqlalchemy.orm import validates
from app import db


class Therapist(db.Model):
    __tablename__ = "therapists"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Therapist type
    therapist_type = db.Column(
        db.String(20),
        nullable=False,
        default="individual"
    )

    organization_name = db.Column(
        db.String(200),
        nullable=True
    )

    registration_number = db.Column(
        db.String(100),
        nullable=True
    )

    # Profile
    professional_title = db.Column(
        db.String(100),
        nullable=False
    )

    profile_image_url = db.Column(
        db.String(500),
        nullable=True
    )

    specialization = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    bio = db.Column(db.Text, nullable=True)

    years_of_experience = db.Column(
        db.Integer,
        nullable=True
    )

    languages = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # Qualifications
    qualification = db.Column(
        db.String(255),
        nullable=False
    )

    institution = db.Column(
        db.String(255),
        nullable=True
    )

    certificate_urls = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # Licensing
    license_number = db.Column(
        db.String(100),
        nullable=True
    )

    licensing_body = db.Column(
        db.String(200),
        nullable=True
    )

    license_country = db.Column(
        db.String(100),
        nullable=False,
        default="Kenya"
    )

    license_expiry_date = db.Column(
        db.Date,
        nullable=True
    )

    license_document_url = db.Column(
        db.String(500),
        nullable=True
    )

    # Services
    session_types = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: ["online"]
    )

    session_duration = db.Column(
        db.Integer,
        nullable=False,
        default=50
    )

    consultation_fee = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    currency = db.Column(
        db.String(3),
        nullable=False,
        default="KES"
    )

    location = db.Column(
        db.String(255),
        nullable=True
    )

    accepting_clients = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    is_listed = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Approval
    verification_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    verified_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    verified_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    rejection_reason = db.Column(
        db.Text,
        nullable=True
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

    # Accepted therapist types
    @validates("therapist_type")
    def validate_therapist_type(self, key, therapist_type):
        allowed_types = ("individual", "organization")

        assert therapist_type in allowed_types, (
            f"Therapist type must be one of: {', '.join(allowed_types)}."
        )

        return therapist_type

    @validates("organization_name")
    def validate_organization_name(self, key, name):
        if name is not None:
            name = name.strip() or None

        if self.therapist_type == "organization":
            assert name, (
                "Organization name is required for an organization."
            )

        return name

    @validates("registration_number")
    def validate_registration_number(self, key, number):
        if number is not None:
            number = number.strip()
            return number or None

        return number

    # Accepted verification statuses
    @validates("verification_status")
    def validate_verification_status(self, key, status):
        allowed_statuses = (
            "pending",
            "approved",
            "rejected",
            "suspended"
        )

        assert status in allowed_statuses, (
            f"Verification status must be one of: {', '.join(allowed_statuses)}."
        )

        return status

    # Professional title
    @validates("professional_title")
    def validate_professional_title(self, key, title):
        assert title and title.strip(), (
            "Professional title is required."
        )

        return title.strip()

    # Qualifications
    @validates("qualification")
    def validate_qualification(self, key, qualification):
        assert qualification and qualification.strip(), (
            "Professional qualification is required."
        )

        return qualification.strip()

    @validates("years_of_experience")
    def validate_experience(self, key, years):
        assert (
            years is None
            or (
                isinstance(years, int)
                and not isinstance(years, bool)
                and years >= 0
            )
        ), "Years of experience must be a non-negative whole number."

        return years

    # Session settings
    @validates("session_types")
    def validate_session_types(self, key, types):
        allowed_types = ("online", "in_person")

        assert isinstance(types, list) and len(types) > 0, (
            "At least one session type is required."
        )

        assert all(
            isinstance(item, str) and item in allowed_types
            for item in types
        ), f"Session types must be: {', '.join(allowed_types)}."

        assert len(types) == len(set(types)), (
            "Session types cannot contain duplicates."
        )

        return types

    @validates("session_duration")
    def validate_session_duration(self, key, duration):
        assert (
            isinstance(duration, int)
            and not isinstance(duration, bool)
            and duration > 0
        ), "Session duration must be a positive whole number."

        return duration

    @validates("consultation_fee")
    def validate_consultation_fee(self, key, fee):
        assert fee is None or fee >= 0, (
            "Consultation fee cannot be negative."
        )

        return fee

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

    # Specializations
    @validates("specialization")
    def validate_specialization(self, key, specializations):
        assert isinstance(specializations, list), (
            "Specializations must be provided as a list."
        )

        assert all(
            isinstance(item, str) and item.strip()
            for item in specializations
        ), "Each specialization must be a non-empty string."

        return [item.strip() for item in specializations]

    # Languages
    @validates("languages")
    def validate_languages(self, key, languages):
        assert isinstance(languages, list), (
            "Languages must be provided as a list."
        )

        assert all(
            isinstance(item, str) and item.strip()
            for item in languages
        ), "Each language must be a non-empty string."

        return [item.strip() for item in languages]

    # Certificate document URLs
    @validates("certificate_urls")
    def validate_certificate_urls(self, key, urls):
        assert isinstance(urls, list), (
            "Certificate URLs must be provided as a list."
        )

        assert all(
            isinstance(url, str) and url.strip()
            for url in urls
        ), "Each certificate URL must be a non-empty string."

        return [url.strip() for url in urls]

    # Image and document URLs
    @validates("profile_image_url")
    def validate_profile_image_url(self, key, url):
        if url is not None:
            url = url.strip()
            return url or None

        return url

    @validates("license_document_url")
    def validate_license_document_url(self, key, url):
        if url is not None:
            url = url.strip()
            return url or None

        return url

    # Licensing details
    @validates("license_number")
    def validate_license_number(self, key, number):
        if number is not None:
            number = number.strip()
            return number or None

        return number

    @validates("licensing_body")
    def validate_licensing_body(self, key, body):
        if body is not None:
            body = body.strip()
            return body or None

        return body

    @validates("license_country")
    def validate_license_country(self, key, country):
        assert country and country.strip(), (
            "License country is required."
        )

        return country.strip()

    # Relationships
    user = db.relationship(
        "Users",
        foreign_keys=[user_id],
        backref=db.backref(
            "therapist_profile",
            uselist=False
        )
    )

    verifier = db.relationship(
        "Users",
        foreign_keys=[verified_by]
    )

    # Booking eligibility
    @property
    def is_bookable(self):
        return (
            self.verification_status == "approved"
            and self.is_listed
            and self.accepting_clients
            and self.user is not None
            and self.user.status == "active"
        )

    # Serializer
    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "therapist_type": self.therapist_type,
            "organization_name": self.organization_name,
            "professional_title": self.professional_title,
            "profile_image_url": self.profile_image_url,
            "specialization": self.specialization,
            "bio": self.bio,
            "years_of_experience": self.years_of_experience,
            "languages": self.languages,
            "qualification": self.qualification,
            "institution": self.institution,
            "certificate_urls": self.certificate_urls,
            "session_types": self.session_types,
            "session_duration": self.session_duration,
            "consultation_fee": (
                str(self.consultation_fee)
                if self.consultation_fee is not None
                else None
            ),
            "currency": self.currency,
            "location": self.location,
            "accepting_clients": self.accepting_clients,
            "is_listed": self.is_listed,
            "is_bookable": self.is_bookable,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at else None
            ),
        }

        if include_private:
            data.update({
                "registration_number": self.registration_number,
                "license_number": self.license_number,
                "licensing_body": self.licensing_body,
                "license_country": self.license_country,
                "license_document_url": self.license_document_url,
                "license_expiry_date": (
                    self.license_expiry_date.isoformat()
                    if self.license_expiry_date else None
                ),
                "verification_status": self.verification_status,
                "verified_by": self.verified_by,
                "verified_at": (
                    self.verified_at.isoformat()
                    if self.verified_at else None
                ),
                "rejection_reason": self.rejection_reason,
            })

        return data

    def __repr__(self):
        return (
            f"Therapist(id={self.id}, "
            f"user_id={self.user_id}, "
            f"therapist_type='{self.therapist_type}', "
            f"verification_status='{self.verification_status}')"
        )
