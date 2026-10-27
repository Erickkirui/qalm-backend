
from datetime import datetime, timezone
from sqlalchemy.orm import validates
from app import db


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    # Client booking the appointment
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Therapist being booked
    therapist_id = db.Column(
        db.Integer,
        db.ForeignKey("therapists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Appointment schedule
    appointment_date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    start_time = db.Column(
        db.Time,
        nullable=False
    )

    end_time = db.Column(
        db.Time,
        nullable=False
    )

    # Session details
    session_type = db.Column(
        db.String(20),
        nullable=False,
        default="online"
    )

    location = db.Column(
        db.String(255),
        nullable=True
    )

    meeting_url = db.Column(
        db.String(500),
        nullable=True
    )

    # Reason for seeking an appointment
    reason = db.Column(
        db.Text,
        nullable=True
    )

    # Booking status
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True
    )

    # Payment details
    consultation_fee = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    currency = db.Column(
        db.String(3),
        nullable=False,
        default="KES"
    )

    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="unpaid"
    )

    # Cancellation details
    cancelled_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    cancellation_reason = db.Column(
        db.Text,
        nullable=True
    )

    cancelled_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # Session outcome
    therapist_notes = db.Column(
        db.Text,
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime(timezone=True),
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

    # Relationships
    client = db.relationship(
        "Users",
        foreign_keys=[client_id],
        backref=db.backref("client_appointments", lazy=True)
    )

    therapist = db.relationship(
        "Therapist",
        foreign_keys=[therapist_id],
        backref=db.backref("appointments", lazy=True)
    )

    canceller = db.relationship(
        "Users",
        foreign_keys=[cancelled_by]
    )

    # Accepted appointment statuses
    @validates("status")
    def validate_status(self, key, status):
        allowed_statuses = (
            "pending",
            "confirmed",
            "completed",
            "cancelled",
            "rejected",
            "no_show",
            "rescheduled"
        )

        assert status in allowed_statuses, (
            f"Appointment status must be one of: "
            f"{', '.join(allowed_statuses)}."
        )

        return status

    # Accepted session types
    @validates("session_type")
    def validate_session_type(self, key, session_type):
        allowed_types = ("online", "in_person")

        assert session_type in allowed_types, (
            f"Session type must be one of: {', '.join(allowed_types)}."
        )

        return session_type

    # Accepted payment statuses
    @validates("payment_status")
    def validate_payment_status(self, key, payment_status):
        allowed_statuses = (
            "unpaid",
            "pending",
            "paid",
            "failed",
            "refunded",
            "partially_refunded"
        )

        assert payment_status in allowed_statuses, (
            f"Payment status must be one of: "
            f"{', '.join(allowed_statuses)}."
        )

        return payment_status

    # Consultation fee
    @validates("consultation_fee")
    def validate_consultation_fee(self, key, fee):
        assert fee is None or fee >= 0, (
            "Consultation fee cannot be negative."
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

    # Required appointment date
    @validates("appointment_date")
    def validate_appointment_date(self, key, appointment_date):
        assert appointment_date is not None, (
            "Appointment date is required."
        )

        return appointment_date

    # Session time validation
    @validates("end_time")
    def validate_end_time(self, key, end_time):
        start_time = getattr(self, "start_time", None)

        if start_time is not None:
            assert end_time > start_time, (
                "Appointment end time must be after start time."
            )

        return end_time

    @validates("start_time")
    def validate_start_time(self, key, start_time):
        end_time = getattr(self, "end_time", None)

        if end_time is not None:
            assert end_time > start_time, (
                "Appointment end time must be after start time."
            )

        return start_time

    # Optional text fields
    @validates("reason")
    def validate_reason(self, key, reason):
        if reason is not None:
            reason = reason.strip()
            return reason or None

        return reason

    @validates("cancellation_reason")
    def validate_cancellation_reason(self, key, reason):
        if reason is not None:
            reason = reason.strip()
            return reason or None

        return reason

    # Booking eligibility
    @property
    def can_be_booked(self):
        return (
            self.therapist is not None
            and self.therapist.is_bookable
        )

    # Serializer
    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "client_id": self.client_id,
            "therapist_id": self.therapist_id,
            "appointment_date": (
                self.appointment_date.isoformat()
                if self.appointment_date else None
            ),
            "start_time": (
                self.start_time.isoformat()
                if self.start_time else None
            ),
            "end_time": (
                self.end_time.isoformat()
                if self.end_time else None
            ),
            "session_type": self.session_type,
            "location": self.location,
            "status": self.status,
            "consultation_fee": (
                str(self.consultation_fee)
                if self.consultation_fee is not None
                else None
            ),
            "currency": self.currency,
            "payment_status": self.payment_status,
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
                "meeting_url": self.meeting_url,
                "reason": self.reason,
                "cancelled_by": self.cancelled_by,
                "cancellation_reason": self.cancellation_reason,
                "cancelled_at": (
                    self.cancelled_at.isoformat()
                    if self.cancelled_at else None
                ),
                "therapist_notes": self.therapist_notes,
                "completed_at": (
                    self.completed_at.isoformat()
                    if self.completed_at else None
                ),
            })

        return data

    def __repr__(self):
        return (
            f"Appointment(id={self.id}, "
            f"client_id={self.client_id}, "
            f"therapist_id={self.therapist_id}, "
            f"status='{self.status}')"
        )
