
from datetime import datetime, timezone

from flask import request
from flask_restful import Resource
from flask_jwt_extended import (
    get_jwt_identity,
    verify_jwt_in_request,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from Server.Models.Users import Users
from Server.Models.Therapists import Therapist
from Server.Utils.auth import check_role

from sqlalchemy import or_, cast, String



# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_current_user():
    """Return the logged-in user from the JWT, or None."""
    identity = get_jwt_identity()

    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None

    user = db.session.get(Users, user_id)

    if user is None or user.status != "active":
        return None

    return user


def parse_expiry_date(value):
    """Convert YYYY-MM-DD to a date object."""
    if value in (None, ""):
        return None

    from datetime import date

    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("license_expiry_date must use YYYY-MM-DD format.")


def validate_profile_data(data, creating=False):
    """Validate fields allowed during registration or profile updates."""
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required.")

    if creating:
        required_fields = ("professional_title", "qualification")

        for field in required_fields:
            value = data.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required.")

    allowed_fields = {
        "therapist_type",
        "organization_name",
        "registration_number",
        "professional_title",
        "profile_image_url",
        "specialization",
        "bio",
        "years_of_experience",
        "languages",
        "qualification",
        "institution",
        "certificate_urls",
        "license_number",
        "licensing_body",
        "license_country",
        "license_expiry_date",
        "license_document_url",
        "session_types",
        "session_duration",
        "consultation_fee",
        "currency",
        "location",
        "accepting_clients",
    }

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        raise ValueError(
            "Unsupported fields: " + ", ".join(sorted(unknown_fields))
        )

    result = dict(data)

    if "license_expiry_date" in result:
        result["license_expiry_date"] = parse_expiry_date(
            result["license_expiry_date"]
        )

    if "accepting_clients" in result:
        if not isinstance(result["accepting_clients"], bool):
            raise ValueError("accepting_clients must be true or false.")

    if "session_duration" in result:
        value = result["session_duration"]

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("session_duration must be a whole number.")

    if "years_of_experience" in result:
        value = result["years_of_experience"]

        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise ValueError("years_of_experience must be a whole number.")

    if "consultation_fee" in result:
        value = result["consultation_fee"]

        if value is not None:
            try:
                result["consultation_fee"] = float(value)
            except (ValueError, TypeError):
                raise ValueError("consultation_fee must be a valid number.")

    return result


def public_therapist_query():
    """Only therapists approved and listed publicly."""
    return Therapist.query.join(
        Users, Therapist.user_id == Users.id
    ).filter(
        Therapist.verification_status == "approved",
        Therapist.is_listed.is_(True),
        Users.status == "active",
    )


# ---------------------------------------------------------
# Register Therapist
# POST /api/therapists/register
# Requires JWT
# ---------------------------------------------------------

class RegisterTherapist(Resource):

    def post(self):
        try:
            verify_jwt_in_request()

            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            existing = Therapist.query.filter_by(user_id=user.id).first()

            if existing:
                return {
                    "message": "You already have a therapist profile.",
                    "therapist": existing.to_dict(include_private=True),
                }, 409

            data = request.get_json(silent=True)

            if not isinstance(data, dict):
                return {"message": "A valid JSON object is required."}, 400

            profile_data = validate_profile_data(data, creating=True)

            therapist = Therapist(
                user_id=user.id,
                verification_status="pending",
                is_listed=False,
                accepting_clients=False,
                **profile_data,
            )

            db.session.add(therapist)
            db.session.commit()

            return {
                "message": "Therapist registration submitted for admin approval.",
                "therapist": therapist.to_dict(include_private=True),
            }, 201

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except AssertionError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except IntegrityError:
            db.session.rollback()
            return {
                "message": "A therapist profile already exists for this user."
            }, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500


# ---------------------------------------------------------
# Approve, Reject or Suspend Therapist
# PATCH /api/therapists/<therapist_id>/approval
# Admin only
# ---------------------------------------------------------

class ApproveTherapist(Resource):

    @check_role("admin")
    def patch(self, therapist_id):
        therapist = db.session.get(Therapist, therapist_id)

        if therapist is None:
            return {"message": "Therapist profile not found."}, 404

        data = request.get_json(silent=True) or {}
        status = data.get("verification_status")

        allowed_statuses = ("approved", "rejected", "suspended")

        if status not in allowed_statuses:
            return {
                "message": (
                    "verification_status must be approved, rejected, "
                    "or suspended."
                )
            }, 400

        rejection_reason = data.get("rejection_reason")

        if status == "rejected":
            if not isinstance(rejection_reason, str) or not rejection_reason.strip():
                return {
                    "message": "rejection_reason is required when rejecting."
                }, 400

        try:
            admin = get_current_user()

            if admin is None:
                return {"message": "Active admin account not found."}, 401

            therapist.verification_status = status
            therapist.verified_by = admin.id
            therapist.verified_at = datetime.now(timezone.utc)

            if status == "approved":
                therapist.is_listed = True
                therapist.rejection_reason = None

            elif status == "rejected":
                therapist.is_listed = False
                therapist.accepting_clients = False
                therapist.rejection_reason = rejection_reason.strip()

            elif status == "suspended":
                therapist.is_listed = False
                therapist.accepting_clients = False
                therapist.rejection_reason = rejection_reason

            db.session.commit()

            return {
                "message": f"Therapist profile {status} successfully.",
                "therapist": therapist.to_dict(include_private=True),
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500


# ---------------------------------------------------------
# Get All Public Therapists
# GET /api/therapists
#
# No JWT: first 5 profiles only.
# JWT: pagination, with a maximum of 100 per request.
# ---------------------------------------------------------

class GetAllTherapists(Resource):
    """
    GET /api/therapists

    Public:
        - First 5 results only.
        - Search and filters are allowed.

    Authenticated:
        - Pagination and up to 100 results per request.
        - Search and filters are allowed.

    Query parameters:
        search, specialization, language, location, session_type,
        therapist_type, min_experience, max_fee, currency,
        accepting_clients, page, limit
    """

    def get(self):
        try:
            # Allow public access, but require JWT for additional results.
            verify_jwt_in_request(optional=True)

            identity = get_jwt_identity()
            user = get_current_user() if identity else None

            if identity and user is None:
                return {
                    "message": "Active user account not found."
                }, 401

            # Pagination
            try:
                page = int(request.args.get("page", 1))
                limit = int(request.args.get("limit", 5))
            except (ValueError, TypeError):
                return {
                    "message": "page and limit must be whole numbers."
                }, 400

            if page < 1 or limit < 1:
                return {
                    "message": "page and limit must be greater than zero."
                }, 400

            if limit > 100:
                return {
                    "message": "limit cannot exceed 100."
                }, 400

            # Public users can only retrieve the first five results.
            if user is None and (page != 1 or limit > 5):
                return {
                    "message": (
                        "Log in to view more therapists. "
                        "Public access is limited to the first 5 results."
                    ),
                    "login_required": True,
                }, 401

            # Only approved, listed therapists with active accounts.
            query = public_therapist_query()

            # -------------------------------------------------
            # 1. General search
            # ?search=anxiety
            # -------------------------------------------------
            search = request.args.get("search", "").strip()

            if search:
                term = f"%{search}%"

                query = query.filter(
                    or_(
                        Users.name.ilike(term),
                        Therapist.professional_title.ilike(term),
                        Therapist.organization_name.ilike(term),
                        Therapist.bio.ilike(term),
                        Therapist.qualification.ilike(term),
                        Therapist.location.ilike(term),
                        cast(Therapist.specialization, String).ilike(term),
                        cast(Therapist.languages, String).ilike(term),
                    )
                )

            # -------------------------------------------------
            # 2. Filter by specialization
            # ?specialization=Anxiety
            # -------------------------------------------------
            specialization = request.args.get(
                "specialization", ""
            ).strip()

            if specialization:
                query = query.filter(
                    cast(Therapist.specialization, String).ilike(
                        f"%{specialization}%"
                    )
                )

            # -------------------------------------------------
            # 3. Filter by language
            # ?language=Swahili
            # -------------------------------------------------
            language = request.args.get("language", "").strip()

            if language:
                query = query.filter(
                    cast(Therapist.languages, String).ilike(
                        f"%{language}%"
                    )
                )

            # -------------------------------------------------
            # 4. Filter by location
            # ?location=Nairobi
            # -------------------------------------------------
            location = request.args.get("location", "").strip()

            if location:
                query = query.filter(
                    Therapist.location.ilike(f"%{location}%")
                )

            # -------------------------------------------------
            # 5. Filter by session type
            # online or in_person
            # ?session_type=online
            # -------------------------------------------------
            session_type = request.args.get(
                "session_type", ""
            ).strip().lower()

            if session_type:
                if session_type not in ("online", "in_person"):
                    return {
                        "message": (
                            "session_type must be online or in_person."
                        )
                    }, 400

                query = query.filter(
                    cast(Therapist.session_types, String).ilike(
                        f'%"{session_type}"%'
                    )
                )

            # -------------------------------------------------
            # 6. Filter by therapist type
            # individual or organization
            # -------------------------------------------------
            therapist_type = request.args.get(
                "therapist_type", ""
            ).strip().lower()

            if therapist_type:
                if therapist_type not in ("individual", "organization"):
                    return {
                        "message": (
                            "therapist_type must be individual "
                            "or organization."
                        )
                    }, 400

                query = query.filter(
                    Therapist.therapist_type == therapist_type
                )

            # -------------------------------------------------
            # 7. Minimum years of experience
            # ?min_experience=5
            # -------------------------------------------------
            min_experience = request.args.get("min_experience")

            if min_experience is not None:
                try:
                    min_experience = int(min_experience)

                    if min_experience < 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return {
                        "message": (
                            "min_experience must be a non-negative "
                            "whole number."
                        )
                    }, 400

                query = query.filter(
                    Therapist.years_of_experience >= min_experience
                )

            # -------------------------------------------------
            # 8. Maximum consultation fee
            # ?max_fee=3000
            # -------------------------------------------------
            max_fee = request.args.get("max_fee")

            if max_fee is not None:
                try:
                    max_fee = float(max_fee)

                    if max_fee < 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return {
                        "message": "max_fee must be a non-negative number."
                    }, 400

                query = query.filter(
                    Therapist.consultation_fee <= max_fee
                )

            # -------------------------------------------------
            # 9. Filter by currency
            # ?currency=KES
            # -------------------------------------------------
            currency = request.args.get("currency", "").strip().upper()

            if currency:
                if len(currency) != 3 or not currency.isalpha():
                    return {
                        "message": (
                            "currency must be a three-letter code."
                        )
                    }, 400

                query = query.filter(
                    Therapist.currency == currency
                )

            # -------------------------------------------------
            # 10. Filter by client availability
            # ?accepting_clients=true
            # -------------------------------------------------
            accepting_clients = request.args.get("accepting_clients")

            if accepting_clients is not None:
                value = accepting_clients.strip().lower()

                if value not in ("true", "false"):
                    return {
                        "message": (
                            "accepting_clients must be true or false."
                        )
                    }, 400

                query = query.filter(
                    Therapist.accepting_clients == (value == "true")
                )

            # Stable ordering helps keep pagination consistent.
            query = query.order_by(
                Therapist.created_at.desc(),
                Therapist.id.desc(),
            )

            pagination = query.paginate(
                page=page,
                per_page=limit,
                error_out=False,
            )

            return {
                "count": len(pagination.items),
                "total": pagination.total,
                "page": page,
                "limit": limit,
                "pages": pagination.pages,
                "login_required_for_more": user is None,
                "filters": {
                    "search": search or None,
                    "specialization": specialization or None,
                    "language": language or None,
                    "location": location or None,
                    "session_type": session_type or None,
                    "therapist_type": therapist_type or None,
                    "min_experience": min_experience,
                    "max_fee": max_fee,
                    "currency": currency or None,
                    "accepting_clients": accepting_clients,
                },
                "therapists": [
                    therapist.to_dict()
                    for therapist in pagination.items
                ],
            }, 200

        except SQLAlchemyError:
            return {
                "message": "A database error occurred."
            }, 500



# ---------------------------------------------------------
# Get, Update or Delete a Therapist Profile
# GET    /api/therapists/<therapist_id>
# PATCH  /api/therapists/<therapist_id>
# DELETE /api/therapists/<therapist_id>
# ---------------------------------------------------------
class TherapistResource(Resource):

    def get(self, therapist_id):
        try:
            verify_jwt_in_request(optional=True)
            user = get_current_user() if get_jwt_identity() else None

            if get_jwt_identity() and user is None:
                return {"message": "Active user account not found."}, 401

            therapist = db.session.get(Therapist, therapist_id)

            if therapist is None:
                return {"message": "Therapist profile not found."}, 404

            is_owner = user is not None and therapist.user_id == user.id
            is_admin = user is not None and user.role == "admin"

            if not therapist.is_bookable and not (is_owner or is_admin):
                return {"message": "Therapist profile not found."}, 404

            return {
                "therapist": therapist.to_dict(
                    include_private=(is_owner or is_admin)
                )
            }, 200

        except SQLAlchemyError:
            return {"message": "A database error occurred."}, 500

    def patch(self, therapist_id):
        try:
            verify_jwt_in_request()

            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            therapist = db.session.get(Therapist, therapist_id)

            if therapist is None:
                return {"message": "Therapist profile not found."}, 404

            is_owner = therapist.user_id == user.id
            is_admin = user.role == "admin"

            if not (is_owner or is_admin):
                return {"message": "You cannot edit this profile."}, 403

            data = request.get_json(silent=True)

            if not isinstance(data, dict) or not data:
                return {"message": "Provide profile fields to update."}, 400

            # --- NEW LOGIC: Strip restricted fields ---
            # Remove fields that should never be manually updated via PATCH
            restricted_fields = {"created_at", "updated_at"}
            clean_data = {k: v for k, v in data.items() if k not in restricted_fields}

            if not clean_data:
                return {"message": "No valid fields to update."}, 400

            # Only admins can modify client acceptance.
            if "accepting_clients" in clean_data and not is_admin:
                return {
                    "message": "Only an admin can change accepting_clients."
                }, 403

            # Only admins may edit profiles that are not approved.
            if not is_admin and therapist.verification_status != "approved":
                return {
                    "message": (
                        "Your application is awaiting approval or is not "
                        "currently approved. Contact an admin for changes."
                    )
                }, 403

            # Validate the cleaned data. 
            # We are assuming validate_profile_data checks the model's @validates decorators.
            # If validate_profile_data is strict about allowed keys, you may need to 
            # update it on the backend to allow fields like "verification_status" for admins.
            profile_data = validate_profile_data(clean_data, creating=False)

            for field, value in profile_data.items():
                setattr(therapist, field, value)

            if not is_admin:
                therapist.verification_status = "pending"
                therapist.is_listed = False
                therapist.accepting_clients = False
                therapist.verified_by = None
                therapist.verified_at = None
                therapist.rejection_reason = None

            db.session.commit()

            return {
                "message": (
                    "Profile updated. Your changes require admin approval."
                    if not is_admin
                    else "Therapist profile updated successfully."
                ),
                "therapist": therapist.to_dict(include_private=True),
            }, 200

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except AssertionError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500

    @check_role("admin")
    def delete(self, therapist_id):
        try:
            therapist = db.session.get(Therapist, therapist_id)

            if therapist is None:
                return {"message": "Therapist profile not found."}, 404

            db.session.delete(therapist)
            db.session.commit()

            return {
                "message": "Therapist profile deleted successfully."
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500

# ---------------------------------------------------------
# Get, Therapist pending approval
# GET    /api/therapists/<therapist_id>

# ---------------------------------------------------------

class GetPendingTherapists(Resource):
    @check_role("admin")
    def get(self):
        try:
            page = request.args.get("page", 1, type=int)
            limit = request.args.get("limit", 20, type=int)

            page = max(page, 1)
            limit = min(max(limit, 1), 100)

            query = Therapist.query.filter_by(
                verification_status="pending"
            ).order_by(Therapist.created_at.desc())

            pagination = query.paginate(
                page=page,
                per_page=limit,
                error_out=False
            )

            therapists = [
                therapist.to_dict(include_private=True)
                for therapist in pagination.items
            ]

            return {
                "message": "Pending therapists retrieved successfully.",
                "data": therapists,
                "pagination": {
                    "page": pagination.page,
                    "limit": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev
                }
            }, 200

        except Exception as e:
            return {
                "message": "Failed to retrieve pending therapists.",
                "error": str(e)
            }, 500