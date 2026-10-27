from datetime import datetime, timezone

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from app import db
from Server.Models.Users import Users
from Server.Models.TherapistMatchPreference import TherapistMatchPreference


# ---------------------------------------------------------
# Helper: Get current authenticated user
# ---------------------------------------------------------

def get_current_user():
    identity = get_jwt_identity()

    try:
        user_id = int(identity)
    except (ValueError, TypeError):
        return None

    user = db.session.get(Users, user_id)

    if not user or user.status != "active":
        return None

    return user


# ---------------------------------------------------------
# Validate therapist matching preferences
# ---------------------------------------------------------

def validate_preference_data(data, creating=False):
    if not isinstance(data, dict):
        return "Request body must be a valid JSON object."

    allowed_fields = {
        "country",
        "county",
        "town",
        "preferred_location",
        "location_type",
        "help_areas",
        "session_types",
        "preferred_languages",
        "min_experience_years",
        "max_consultation_fee",
        "currency",
        "is_active",
    }

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return (
            "Unknown field(s): "
            + ", ".join(sorted(unknown_fields))
        )

    if creating and not data.get("help_areas"):
        return "Select at least one area where you need help."

    if "country" in data:
        country = data["country"]

        if not isinstance(country, str) or not country.strip():
            return "Country must be a non-empty string."

    if "location_type" in data:
        if data["location_type"] not in (
            "online", "in_person", "both", "any"
        ):
            return (
                "location_type must be online, in_person, "
                "both, or any."
            )

    if "help_areas" in data:
        areas = data["help_areas"]

        if not isinstance(areas, list) or not areas:
            return "Select at least one area where you need help."

        if not all(
            isinstance(area, str) and area.strip()
            for area in areas
        ):
            return "Each help area must be a non-empty string."

        cleaned = [area.strip().lower() for area in areas]

        if len(cleaned) != len(set(cleaned)):
            return "Help areas cannot contain duplicates."

    if "session_types" in data:
        session_types = data["session_types"]

        if not isinstance(session_types, list) or not session_types:
            return "Select at least one session type."

        allowed_types = {"online", "in_person"}

        if not all(
            isinstance(item, str) and item in allowed_types
            for item in session_types
        ):
            return "Session types must be online or in_person."

        if len(session_types) != len(set(session_types)):
            return "Session types cannot contain duplicates."

    if "preferred_languages" in data:
        languages = data["preferred_languages"]

        if not isinstance(languages, list):
            return "Preferred languages must be provided as a list."

        if not all(
            isinstance(language, str) and language.strip()
            for language in languages
        ):
            return "Each preferred language must be a non-empty string."

    if "min_experience_years" in data:
        years = data["min_experience_years"]

        if years is not None and (
            not isinstance(years, int)
            or isinstance(years, bool)
            or years < 0
        ):
            return "Minimum experience must be a non-negative whole number."

    if "max_consultation_fee" in data:
        fee = data["max_consultation_fee"]

        if fee is not None:
            try:
                fee = float(fee)
            except (TypeError, ValueError):
                return "Maximum consultation fee must be a valid number."

            if fee < 0:
                return "Maximum consultation fee cannot be negative."

    if "currency" in data:
        currency = data["currency"]

        if not isinstance(currency, str):
            return "Currency must be a three-letter code, e.g. KES."

        currency = currency.strip()

        if len(currency) != 3 or not currency.isalpha():
            return "Currency must be a three-letter code, e.g. KES."

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return "is_active must be true or false."

    for field in (
        "county", "town", "preferred_location"
    ):
        if field in data and data[field] is not None:
            if not isinstance(data[field], str):
                return f"{field} must be a string or null."

    return None


# ---------------------------------------------------------
# Create or Get My Therapist Matching Preferences
# POST /api/therapist-match-preferences
# GET  /api/therapist-match-preferences
# Authenticated users
# ---------------------------------------------------------

class TherapistMatchPreferenceResource(Resource):

    @jwt_required()
    def post(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "Request body must be a valid JSON object."}, 400

        existing = TherapistMatchPreference.query.filter_by(
            user_id=user.id
        ).first()

        if existing:
            return {
                "message": (
                    "Therapist matching preferences already exist. "
                    "Use PATCH to update them."
                ),
                "data": existing.to_dict()
            }, 409

        error = validate_preference_data(data, creating=True)

        if error:
            return {"message": error}, 400

        try:
            preference = TherapistMatchPreference(
                user_id=user.id,
                country=data.get("country", "Kenya"),
                county=data.get("county"),
                town=data.get("town"),
                preferred_location=data.get("preferred_location"),
                location_type=data.get("location_type", "any"),
                help_areas=data.get("help_areas"),
                session_types=data.get("session_types", ["online"]),
                preferred_languages=data.get("preferred_languages", []),
                min_experience_years=data.get("min_experience_years"),
                max_consultation_fee=data.get("max_consultation_fee"),
                currency=data.get("currency", "KES"),
                is_active=data.get("is_active", True),
            )

            db.session.add(preference)
            db.session.commit()

            return {
                "message": "Therapist matching preferences created successfully.",
                "data": preference.to_dict()
            }, 201

        except (AssertionError, ValueError, TypeError) as e:
            db.session.rollback()
            return {"message": str(e)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Failed to save therapist matching preferences."
            }, 500

    @jwt_required()
    def get(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        preference = TherapistMatchPreference.query.filter_by(
            user_id=user.id
        ).first()

        if not preference:
            return {
                "message": "You have not configured therapist matching preferences.",
                "data": None
            }, 404

        return {
            "message": "Therapist matching preferences retrieved successfully.",
            "data": preference.to_dict()
        }, 200

    # ---------------------------------------------------------
    # Update My Therapist Matching Preferences
    # PATCH /api/therapist-match-preferences
    # Authenticated users
    # ---------------------------------------------------------

    @jwt_required()
    def patch(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        preference = TherapistMatchPreference.query.filter_by(
            user_id=user.id
        ).first()

        if not preference:
            return {
                "message": "Create your therapist matching preferences first."
            }, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return {
                "message": "Provide at least one field to update."
            }, 400

        error = validate_preference_data(data)

        if error:
            return {"message": error}, 400

        try:
            for field, value in data.items():
                setattr(preference, field, value)

            preference.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            return {
                "message": "Therapist matching preferences updated successfully.",
                "data": preference.to_dict()
            }, 200

        except (AssertionError, ValueError, TypeError) as e:
            db.session.rollback()
            return {"message": str(e)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Failed to update therapist matching preferences."
            }, 500

    # ---------------------------------------------------------
    # Delete My Therapist Matching Preferences
    # DELETE /api/therapist-match-preferences
    # Authenticated users
    # ---------------------------------------------------------

    @jwt_required()
    def delete(self):
        user = get_current_user()

        if not user:
            return {"message": "Active user account not found."}, 401

        preference = TherapistMatchPreference.query.filter_by(
            user_id=user.id
        ).first()

        if not preference:
            return {
                "message": "Therapist matching preferences not found."
            }, 404

        try:
            db.session.delete(preference)
            db.session.commit()

            return {
                "message": "Therapist matching preferences deleted successfully."
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Failed to delete therapist matching preferences."
            }, 500
