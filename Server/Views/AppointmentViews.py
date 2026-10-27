from datetime import date, time, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app import db
from Server.Models.Users import Users
from Server.Models.Therapists import Therapist
from Server.Models.Appointment import Appointment
from Server.Utils.auth import check_role


ACTIVE_APPOINTMENT_STATUSES = (
    "pending",
    "confirmed",
    "rescheduled",
)

ALLOWED_SESSION_TYPES = ("online", "in_person")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_current_user():
    try:
        user_id = int(get_jwt_identity())
    except (ValueError, TypeError):
        return None

    user = db.session.get(Users, user_id)

    if not user or user.status != "active":
        return None

    return user


def parse_date(value):
    if not isinstance(value, str):
        raise ValueError("appointment_date must use YYYY-MM-DD format.")

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid appointment_date. Use YYYY-MM-DD.")


def parse_time(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must use HH:MM or HH:MM:SS format.")

    try:
        return time.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field_name}. Use HH:MM or HH:MM:SS.")


def get_therapist_for_user(user):
    return Therapist.query.filter_by(user_id=user.id).first()


def is_admin(user):
    return user.role == "admin"


def can_access_appointment(user, appointment):
    if is_admin(user):
        return True

    if appointment.client_id == user.id:
        return True

    therapist = appointment.therapist

    return therapist is not None and therapist.user_id == user.id


def appointment_response(appointment, user):
    # Private information is restricted to the client, assigned
    # therapist, and admin.
    data = appointment.to_dict(include_private=False)

    if can_access_appointment(user, appointment):
        data.update({
            "meeting_url": appointment.meeting_url,
            "reason": appointment.reason,
            "cancellation_reason": appointment.cancellation_reason,
            "cancelled_by": appointment.cancelled_by,
            "cancelled_at": (
                appointment.cancelled_at.isoformat()
                if appointment.cancelled_at else None
            ),
            "completed_at": (
                appointment.completed_at.isoformat()
                if appointment.completed_at else None
            ),
        })

    # Session notes are private to the assigned therapist and admin.
    if is_admin(user) or (
        appointment.therapist is not None
        and appointment.therapist.user_id == user.id
    ):
        data["therapist_notes"] = appointment.therapist_notes

    return data


def parse_fee(value):
    if value is None:
        return None

    try:
        fee = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("consultation_fee must be a valid number.")

    if not fee.is_finite() or fee < 0:
        raise ValueError("consultation_fee must be a non-negative number.")

    return fee


def validate_schedule(appointment_date, start_time, end_time):
    if end_time <= start_time:
        raise ValueError("Appointment end time must be after start time.")

    start_datetime = datetime.combine(appointment_date, start_time)

    if start_datetime <= datetime.now():
        raise ValueError("Appointments must be scheduled for a future time.")


def has_schedule_conflict(
    therapist_id,
    appointment_date,
    start_time,
    end_time,
    exclude_appointment_id=None,
):
    query = Appointment.query.filter(
        Appointment.therapist_id == therapist_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )

    if exclude_appointment_id is not None:
        query = query.filter(
            Appointment.id != exclude_appointment_id
        )

    return query.first() is not None


def get_appointment(appointment_id):
    return db.session.get(Appointment, appointment_id)


def validate_session_type(value):
    if value not in ALLOWED_SESSION_TYPES:
        raise ValueError("session_type must be online or in_person.")


def validate_appointment_update(data, appointment):
    allowed_fields = {
        "appointment_date",
        "start_time",
        "end_time",
        "session_type",
        "location",
        "reason",
    }

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        raise ValueError(
            "Fields cannot be updated here: "
            + ", ".join(sorted(unknown_fields))
        )

    appointment_date = appointment.appointment_date
    start_time = appointment.start_time
    end_time = appointment.end_time

    if "appointment_date" in data:
        appointment_date = parse_date(data["appointment_date"])

    if "start_time" in data:
        start_time = parse_time(data["start_time"], "start_time")

    if "end_time" in data:
        end_time = parse_time(data["end_time"], "end_time")

    if appointment_date is None or start_time is None or end_time is None:
        raise ValueError("Appointment date, start time, and end time are required.")

    validate_schedule(appointment_date, start_time, end_time)

    if "session_type" in data:
        validate_session_type(data["session_type"])

    for field in ("location", "reason"):
        if field in data and data[field] is not None:
            if not isinstance(data[field], str):
                raise ValueError(f"{field} must be a string or null.")

    return {
        "appointment_date": appointment_date,
        "start_time": start_time,
        "end_time": end_time,
    }


# ---------------------------------------------------------
# Create Appointment
# POST /api/appointments
# Client only
# ---------------------------------------------------------

class CreateAppointment(Resource):

    @jwt_required()
    def post(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        if user.role == "admin":
            return {
                "message": "Admins cannot book appointments as clients."
            }, 403

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A valid JSON body is required."}, 400

        required_fields = (
            "therapist_id",
            "appointment_date",
            "start_time",
            "end_time",
        )

        missing = [
            field for field in required_fields
            if field not in data
        ]

        if missing:
            return {
                "message": "Missing required fields.",
                "fields": missing,
            }, 400

        try:
            therapist_id = int(data["therapist_id"])
            therapist = db.session.get(Therapist, therapist_id)

            if not therapist:
                return {"message": "Therapist not found."}, 404

            if not therapist.is_bookable:
                return {
                    "message": "This therapist is not currently accepting bookings."
                }, 400

            appointment_date = parse_date(data["appointment_date"])
            start_time = parse_time(data["start_time"], "start_time")
            end_time = parse_time(data["end_time"], "end_time")

            validate_schedule(appointment_date, start_time, end_time)

            session_type = data.get("session_type", "online")
            validate_session_type(session_type)

            allowed_session_types = therapist.session_types or []

            if session_type not in allowed_session_types:
                return {
                    "message": (
                        "The therapist does not offer this session type."
                    )
                }, 400

            if has_schedule_conflict(
                therapist.id,
                appointment_date,
                start_time,
                end_time,
            ):
                return {
                    "message": "The therapist already has an appointment during this time."
                }, 409

            location = data.get("location")

            if session_type == "in_person":
                if not location:
                    location = therapist.location

                if not location:
                    return {
                        "message": "A location is required for in-person appointments."
                    }, 400

            if location is not None and not isinstance(location, str):
                return {"message": "location must be a string."}, 400

            reason = data.get("reason")

            if reason is not None and not isinstance(reason, str):
                return {"message": "reason must be a string."}, 400

            # The server determines the fee and currency.
            # Never trust payment amounts supplied by the client.
            appointment = Appointment(
                client_id=user.id,
                therapist_id=therapist.id,
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=end_time,
                session_type=session_type,
                location=location,
                reason=reason,
                status="pending",
                consultation_fee=therapist.consultation_fee,
                currency=therapist.currency or "KES",
                payment_status="unpaid",
            )

            db.session.add(appointment)
            db.session.commit()

            return {
                "message": "Appointment request created successfully.",
                "data": appointment_response(appointment, user),
            }, 201

        except (ValueError, TypeError, AssertionError) as e:
            db.session.rollback()
            return {"message": str(e)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to create appointment."}, 500


# ---------------------------------------------------------
# List My Appointments
# GET /api/appointments
# Client or therapist
# Optional filters: status, date, page, limit
# ---------------------------------------------------------

class MyAppointments(Resource):

    @jwt_required()
    def get(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)

        query = Appointment.query

        if not is_admin(user):
            therapist = get_therapist_for_user(user)

            if therapist:
                query = query.filter(
                    or_(
                        Appointment.client_id == user.id,
                        Appointment.therapist_id == therapist.id,
                    )
                )
            else:
                query = query.filter(
                    Appointment.client_id == user.id
                )

        status = request.args.get("status")

        if status:
            allowed_statuses = {
                "pending", "confirmed", "completed", "cancelled",
                "rejected", "no_show", "rescheduled",
            }

            if status not in allowed_statuses:
                return {"message": "Invalid appointment status."}, 400

            query = query.filter(Appointment.status == status)

        appointment_date = request.args.get("date")

        if appointment_date:
            try:
                query = query.filter(
                    Appointment.appointment_date == parse_date(appointment_date)
                )
            except ValueError as e:
                return {"message": str(e)}, 400

        pagination = query.order_by(
            Appointment.appointment_date.desc(),
            Appointment.start_time.desc(),
        ).paginate(
            page=page,
            per_page=limit,
            error_out=False,
        )

        return {
            "message": "Appointments retrieved successfully.",
            "data": [
                appointment_response(item, user)
                for item in pagination.items
            ],
            "pagination": {
                "page": pagination.page,
                "limit": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }, 200


# ---------------------------------------------------------
# Get, Update or Delete an Appointment
# GET    /api/appointments/<appointment_id>
# PATCH  /api/appointments/<appointment_id>
# DELETE /api/appointments/<appointment_id>
# Owner, assigned therapist, or admin
# ---------------------------------------------------------

class AppointmentResource(Resource):

    @jwt_required()
    def get(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        if not can_access_appointment(user, appointment):
            return {"message": "You cannot access this appointment."}, 403

        return {
            "message": "Appointment retrieved successfully.",
            "data": appointment_response(appointment, user),
        }, 200

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        therapist_user = (
            appointment.therapist is not None
            and appointment.therapist.user_id == user.id
        )

        client_user = appointment.client_id == user.id

        if not (is_admin(user) or therapist_user or client_user):
            return {"message": "You cannot update this appointment."}, 403

        # Scheduling changes are made through the reschedule action.
        # Clients cannot modify therapist details, fees, status, or payments.
        if therapist_user and not is_admin(user):
            return {
                "message": (
                    "Therapists should use the appointment action endpoints "
                    "to confirm, reject, complete, or update session notes."
                )
            }, 403

        if not (client_user or is_admin(user)):
            return {"message": "You cannot update this appointment."}, 403

        if appointment.status not in ("pending", "confirmed", "rescheduled"):
            return {
                "message": "This appointment can no longer be edited."
            }, 409

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return {"message": "Provide fields to update."}, 400

        try:
            schedule = validate_appointment_update(data, appointment)

            if has_schedule_conflict(
                appointment.therapist_id,
                schedule["appointment_date"],
                schedule["start_time"],
                schedule["end_time"],
                exclude_appointment_id=appointment.id,
            ):
                return {
                    "message": "The therapist already has an appointment during this time."
                }, 409

            for field, value in schedule.items():
                setattr(appointment, field, value)

            for field in ("session_type", "location", "reason"):
                if field in data:
                    setattr(appointment, field, data[field])

            # A schedule change requires the therapist to reconfirm.
            if any(
                field in data
                for field in ("appointment_date", "start_time", "end_time")
            ):
                appointment.status = "rescheduled"

            appointment.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            return {
                "message": "Appointment updated successfully.",
                "data": appointment_response(appointment, user),
            }, 200

        except (ValueError, TypeError, AssertionError) as e:
            db.session.rollback()
            return {"message": str(e)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to update appointment."}, 500

    @jwt_required()
    def delete(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        # Deleting is restricted to admins. Clients and therapists
        # should cancel appointments so the history is retained.
        if not is_admin(user):
            return {
                "message": (
                    "Appointments cannot be deleted by clients or therapists. "
                    "Use the cancellation endpoint instead."
                )
            }, 403

        try:
            db.session.delete(appointment)
            db.session.commit()

            return {
                "message": "Appointment deleted successfully."
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to delete appointment."}, 500


# ---------------------------------------------------------
# Confirm Appointment
# PATCH /api/appointments/<appointment_id>/confirm
# Assigned therapist or admin
# ---------------------------------------------------------

class ConfirmAppointment(Resource):

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        assigned_therapist = (
            appointment.therapist is not None
            and appointment.therapist.user_id == user.id
        )

        if not (assigned_therapist or is_admin(user)):
            return {
                "message": "Only the assigned therapist or an admin can confirm this appointment."
            }, 403

        if appointment.status not in ("pending", "rescheduled"):
            return {
                "message": "Only pending or rescheduled appointments can be confirmed."
            }, 409

        if not appointment.therapist.is_bookable:
            return {
                "message": "This therapist is no longer available for bookings."
            }, 409

        if has_schedule_conflict(
            appointment.therapist_id,
            appointment.appointment_date,
            appointment.start_time,
            appointment.end_time,
            exclude_appointment_id=appointment.id,
        ):
            return {
                "message": "This appointment conflicts with another booking."
            }, 409

        appointment.status = "confirmed"
        appointment.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()

            return {
                "message": "Appointment confirmed successfully.",
                "data": appointment_response(appointment, user),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to confirm appointment."}, 500


# ---------------------------------------------------------
# Reject Appointment
# PATCH /api/appointments/<appointment_id>/reject
# Assigned therapist or admin
# ---------------------------------------------------------

class RejectAppointment(Resource):

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        assigned_therapist = (
            appointment.therapist is not None
            and appointment.therapist.user_id == user.id
        )

        if not (assigned_therapist or is_admin(user)):
            return {
                "message": "Only the assigned therapist or an admin can reject this appointment."
            }, 403

        if appointment.status not in ("pending", "rescheduled"):
            return {
                "message": "Only pending or rescheduled appointments can be rejected."
            }, 409

        data = request.get_json(silent=True) or {}
        reason = data.get("reason")

        if reason is not None and not isinstance(reason, str):
            return {"message": "reason must be a string."}, 400

        appointment.status = "rejected"
        appointment.cancellation_reason = reason.strip() if reason else None
        appointment.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()

            return {
                "message": "Appointment rejected successfully.",
                "data": appointment_response(appointment, user),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to reject appointment."}, 500


# ---------------------------------------------------------
# Cancel Appointment
# PATCH /api/appointments/<appointment_id>/cancel
# Client, assigned therapist, or admin
# ---------------------------------------------------------

class CancelAppointment(Resource):

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        if not can_access_appointment(user, appointment):
            return {"message": "You cannot cancel this appointment."}, 403

        if appointment.status not in ("pending", "confirmed", "rescheduled"):
            return {
                "message": "This appointment cannot be cancelled in its current status."
            }, 409

        data = request.get_json(silent=True) or {}
        reason = data.get("reason")

        if reason is not None and not isinstance(reason, str):
            return {"message": "reason must be a string."}, 400

        appointment.status = "cancelled"
        appointment.cancelled_by = user.id
        appointment.cancellation_reason = reason.strip() if reason else None
        appointment.cancelled_at = datetime.now(timezone.utc)
        appointment.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()

            return {
                "message": "Appointment cancelled successfully.",
                "data": appointment_response(appointment, user),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to cancel appointment."}, 500


# ---------------------------------------------------------
# Complete Appointment
# PATCH /api/appointments/<appointment_id>/complete
# Assigned therapist or admin
# ---------------------------------------------------------

class CompleteAppointment(Resource):

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        assigned_therapist = (
            appointment.therapist is not None
            and appointment.therapist.user_id == user.id
        )

        if not (assigned_therapist or is_admin(user)):
            return {
                "message": "Only the assigned therapist or an admin can complete this appointment."
            }, 403

        if appointment.status != "confirmed":
            return {
                "message": "Only confirmed appointments can be completed."
            }, 409

        data = request.get_json(silent=True) or {}
        notes = data.get("therapist_notes")

        if notes is not None and not isinstance(notes, str):
            return {"message": "therapist_notes must be a string."}, 400

        appointment.status = "completed"
        appointment.completed_at = datetime.now(timezone.utc)
        appointment.updated_at = datetime.now(timezone.utc)

        if notes is not None:
            appointment.therapist_notes = notes.strip() or None

        try:
            db.session.commit()

            return {
                "message": "Appointment marked as completed.",
                "data": appointment_response(appointment, user),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to complete appointment."}, 500


# ---------------------------------------------------------
# Mark Client as No-Show
# PATCH /api/appointments/<appointment_id>/no-show
# Assigned therapist or admin
# ---------------------------------------------------------

class MarkAppointmentNoShow(Resource):

    @jwt_required()
    def patch(self, appointment_id):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        assigned_therapist = (
            appointment.therapist is not None
            and appointment.therapist.user_id == user.id
        )

        if not (assigned_therapist or is_admin(user)):
            return {
                "message": "Only the assigned therapist or an admin can mark a no-show."
            }, 403

        if appointment.status != "confirmed":
            return {
                "message": "Only confirmed appointments can be marked as no-show."
            }, 409

        # Do not permit marking a future appointment as missed.
        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.end_time,
        )

        if appointment_datetime > datetime.now():
            return {
                "message": "An appointment cannot be marked as no-show before its end time."
            }, 400

        appointment.status = "no_show"
        appointment.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()

            return {
                "message": "Appointment marked as no-show.",
                "data": appointment_response(appointment, user),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Failed to update appointment."}, 500


# ---------------------------------------------------------
# Update Appointment Payment Status
# PATCH /api/appointments/<appointment_id>/payment
# Admin only
#
# For real payments, use a verified payment-provider callback
# rather than trusting a client-supplied status.
# ---------------------------------------------------------

class UpdateAppointmentPayment(Resource):

    @check_role("admin")
    def patch(self, appointment_id):
        appointment = get_appointment(appointment_id)

        if not appointment:
            return {"message": "Appointment not found."}, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A valid JSON body is required."}, 400

        payment_status = data.get("payment_status")

        allowed_statuses = {
            "unpaid",
            "pending",
            "paid",
            "failed",
            "refunded",
            "partially_refunded",
        }

        if payment_status not in allowed_statuses:
            return {
                "message": "Invalid payment_status.",
                "allowed_values": sorted(allowed_statuses),
            }, 400

        appointment.payment_status = payment_status
        appointment.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()

            return {
                "message": "Appointment payment status updated.",
                "data": appointment.to_dict(include_private=False),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Failed to update appointment payment status."
            }, 500


# ---------------------------------------------------------
# Admin: List All Appointments
# GET /api/appointments/admin
# Admin only
# ---------------------------------------------------------

class AdminAppointments(Resource):

    @check_role("admin")
    def get(self):
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)

        query = Appointment.query

        status = request.args.get("status")

        if status:
            allowed_statuses = {
                "pending", "confirmed", "completed", "cancelled",
                "rejected", "no_show", "rescheduled",
            }

            if status not in allowed_statuses:
                return {"message": "Invalid appointment status."}, 400

            query = query.filter(Appointment.status == status)

        pagination = query.order_by(
            Appointment.appointment_date.desc(),
            Appointment.start_time.desc(),
        ).paginate(
            page=page,
            per_page=limit,
            error_out=False,
        )

        return {
            "message": "Appointments retrieved successfully.",
            "data": [
                item.to_dict(include_private=True)
                for item in pagination.items
            ],
            "pagination": {
                "page": pagination.page,
                "limit": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }, 200
