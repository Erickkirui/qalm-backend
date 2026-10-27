
from datetime import datetime, timezone

from flask import request
from flask_restful import Resource
from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app import db
from Server.Models.Users import Users
from Server.Models.Journal import Journal
from Server.Utils.auth import check_role


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_current_user():
    """Get the active authenticated user."""
    identity = get_jwt_identity()

    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None

    user = db.session.get(Users, user_id)

    if user is None or user.status != "active":
        return None

    return user


def validate_journal_data(data, creating=False):
    """Validate journal fields before creating or updating."""
    if not isinstance(data, dict):
        raise ValueError("A valid JSON object is required.")

    allowed_fields = {
        "title",
        "content",
        "mood",
        "tags",
        "status",
        "is_shared_with_therapist",
    }

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        raise ValueError(
            "Unsupported fields: " + ", ".join(sorted(unknown_fields))
        )

    if creating and not data.get("content", "").strip():
        raise ValueError("Journal content is required.")

    result = dict(data)

    if "content" in result:
        content = result["content"]

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Journal content is required.")

        result["content"] = content.strip()

    if "title" in result:
        title = result["title"]

        if title is not None and not isinstance(title, str):
            raise ValueError("title must be a string.")

        result["title"] = title.strip() or None if title is not None else None

    if "mood" in result:
        mood = result["mood"]

        allowed_moods = {
            "very_sad",
            "sad",
            "neutral",
            "good",
            "very_good",
            "anxious",
            "angry",
            "stressed",
            "calm",
            "happy",
        }

        if mood is not None and mood not in allowed_moods:
            raise ValueError(
                "Invalid mood. Allowed moods: "
                + ", ".join(sorted(allowed_moods))
            )

    if "tags" in result:
        tags = result["tags"]

        if not isinstance(tags, list):
            raise ValueError("tags must be a list.")

        if not all(
            isinstance(tag, str) and tag.strip()
            for tag in tags
        ):
            raise ValueError("Every tag must be a non-empty string.")

        result["tags"] = list(
            dict.fromkeys(tag.strip().lower() for tag in tags)
        )

    if "status" in result:
        if result["status"] not in ("draft", "completed"):
            raise ValueError("status must be draft or completed.")

    if "is_shared_with_therapist" in result:
        if not isinstance(result["is_shared_with_therapist"], bool):
            raise ValueError(
                "is_shared_with_therapist must be true or false."
            )

    return result


# ---------------------------------------------------------
# Create Journal Entry
# POST /api/journals
# Authenticated user
# ---------------------------------------------------------

class CreateJournal(Resource):

    @jwt_required()
    def post(self):
        try:
            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            data = request.get_json(silent=True)

            if not isinstance(data, dict):
                return {"message": "A valid JSON object is required."}, 400

            journal_data = validate_journal_data(data, creating=True)

            journal = Journal(
                user_id=user.id,
                **journal_data,
            )

            db.session.add(journal)
            db.session.commit()

            return {
                "message": "Journal entry created successfully.",
                "journal": journal.to_dict(),
            }, 201

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except AssertionError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500


# ---------------------------------------------------------
# Get Own Journals
# GET /api/journals
# Authenticated user
# ---------------------------------------------------------

class GetMyJournals(Resource):

    @jwt_required()
    def get(self):
        try:
            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            try:
                page = int(request.args.get("page", 1))
                limit = int(request.args.get("limit", 10))
            except (ValueError, TypeError):
                return {
                    "message": "page and limit must be whole numbers."
                }, 400

            if page < 1 or limit < 1 or limit > 100:
                return {
                    "message": (
                        "page must be positive and limit must be "
                        "between 1 and 100."
                    )
                }, 400

            query = Journal.query.filter_by(user_id=user.id)

            # Search title and content.
            search = request.args.get("search", "").strip()

            if search:
                term = f"%{search}%"
                query = query.filter(
                    or_(
                        Journal.title.ilike(term),
                        Journal.content.ilike(term),
                    )
                )

            # Filter by mood.
            mood = request.args.get("mood", "").strip().lower()

            if mood:
                query = query.filter(Journal.mood == mood)

            # Filter by status.
            status = request.args.get("status", "").strip().lower()

            if status:
                if status not in ("draft", "completed"):
                    return {
                        "message": "status must be draft or completed."
                    }, 400

                query = query.filter(Journal.status == status)

            # Filter by tag.
            tag = request.args.get("tag", "").strip().lower()

            if tag:
                # Works with the JSON representation used by this model.
                query = query.filter(
                    Journal.tags.cast(db.String).ilike(f'%"{tag}"%')
                )

            # Filter sharing preference.
            shared = request.args.get("is_shared_with_therapist")

            if shared is not None:
                shared_value = shared.strip().lower()

                if shared_value not in ("true", "false"):
                    return {
                        "message": (
                            "is_shared_with_therapist must be true or false."
                        )
                    }, 400

                query = query.filter(
                    Journal.is_shared_with_therapist
                    == (shared_value == "true")
                )

            query = query.order_by(
                Journal.updated_at.desc(),
                Journal.id.desc(),
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
                "journals": [
                    journal.to_dict()
                    for journal in pagination.items
                ],
            }, 200

        except SQLAlchemyError:
            return {"message": "A database error occurred."}, 500


# ---------------------------------------------------------
# Get, Update or Delete One Journal
# /api/journals/<journal_id>
# Authenticated owner only
# ---------------------------------------------------------

class JournalResource(Resource):

    @jwt_required()
    def get(self, journal_id):
        user = get_current_user()

        if user is None:
            return {"message": "Active user account not found."}, 401

        journal = db.session.get(Journal, journal_id)

        if journal is None or journal.user_id != user.id:
            return {"message": "Journal entry not found."}, 404

        return {"journal": journal.to_dict()}, 200

    @jwt_required()
    def patch(self, journal_id):
        try:
            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            journal = db.session.get(Journal, journal_id)

            if journal is None or journal.user_id != user.id:
                return {"message": "Journal entry not found."}, 404

            data = request.get_json(silent=True)

            if not isinstance(data, dict) or not data:
                return {
                    "message": "Provide journal fields to update."
                }, 400

            journal_data = validate_journal_data(data)

            for field, value in journal_data.items():
                setattr(journal, field, value)

            journal.updated_at = datetime.now(timezone.utc)

            db.session.commit()

            return {
                "message": "Journal entry updated successfully.",
                "journal": journal.to_dict(),
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

    @jwt_required()
    def delete(self, journal_id):
        try:
            user = get_current_user()

            if user is None:
                return {"message": "Active user account not found."}, 401

            journal = db.session.get(Journal, journal_id)

            if journal is None or journal.user_id != user.id:
                return {"message": "Journal entry not found."}, 404

            db.session.delete(journal)
            db.session.commit()

            return {
                "message": "Journal entry deleted successfully."
            }, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500
