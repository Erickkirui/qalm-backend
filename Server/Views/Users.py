
from flask_restful import Resource
from flask import request
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import bcrypt
from Server.Utils.auth import check_role
from app import db
from Server.Models.Users import Users


def get_current_user():
    identity = get_jwt_identity()

    try:
        return db.session.get(Users, int(identity))
    except (ValueError, TypeError):
        return None


def is_admin(user):
    return user is not None and user.role == "admin"


class AddUser(Resource):
    # Public registration endpoint
    def post(self):
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A valid JSON object is required."}, 400

        name = data.get("name")
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not all([name, username, email, password]):
            return {
                "message": "Name, username, email, and password are required."
            }, 400

        try:
            username = username.strip()
            email = email.strip().lower()

            if Users.query.filter_by(username=username).first():
                return {"message": "Username already exists."}, 409

            if Users.query.filter_by(email=email).first():
                return {"message": "Email already exists."}, 409

            new_user = Users(
                name=name,
                username=username,
                email=email,
                role="normal",
                status="active",
                has_therapist_profile=False
            )

            new_user.password = new_user.hash_password(password)

            db.session.add(new_user)
            db.session.commit()

            return {
                "message": "User created successfully.",
                "user": new_user.to_dict(include_email=True)
            }, 201

        except (AssertionError, ValueError, TypeError, AttributeError) as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except IntegrityError:
            db.session.rollback()
            return {"message": "Username or email already exists."}, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500


class Login(Resource):
    # Public login endpoint
    def post(self):
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A valid JSON object is required."}, 400

        username_or_email = data.get("username") or data.get("email")
        password = data.get("password")

        if not username_or_email or not password:
            return {
                "message": "Username/email and password are required."
            }, 400

        identifier = username_or_email.strip()

        user = Users.query.filter(
            db.or_(
                Users.username == identifier,
                Users.email == identifier.lower()
            )
        ).first()

        if not user or not bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8")
        ):
            return {"message": "Invalid credentials."}, 401

        if user.status != "active":
            return {"message": "Your account is not active."}, 403

        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role}
        )

        return {
            "message": "Login successful.",
            "access_token": access_token,
            "token_type": "Bearer",
            "user": user.to_dict(include_email=True)
        }, 200



class GetAllUsers(Resource):

    @check_role("admin")
    def get(self):
        try:
            users = Users.query.order_by(Users.id.desc()).all()

            return {
                "count": len(users),
                "users": [
                    user.to_dict(include_email=True)
                    for user in users
                ]
            }, 200

        except SQLAlchemyError:
            return {"message": "A database error occurred."}, 500



class UserResource(Resource):
    @jwt_required()
    def get(self, user_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User account not found."}, 401

        if current_user.id != user_id and not is_admin(current_user):
            return {"message": "You cannot access this user's account."}, 403

        user = db.session.get(Users, user_id)

        if not user:
            return {"message": "User not found."}, 404

        return {"user": user.to_dict(include_email=True)}, 200

    @jwt_required()
    def patch(self, user_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User account not found."}, 401

        if current_user.id != user_id and not is_admin(current_user):
            return {"message": "You cannot update this user's account."}, 403

        user = db.session.get(Users, user_id)

        if not user:
            return {"message": "User not found."}, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "A valid JSON object is required."}, 400

        allowed_fields = {"name", "username", "email", "password"}
        unexpected_fields = set(data.keys()) - allowed_fields

        if unexpected_fields:
            return {
                "message": "Unsupported fields provided.",
                "fields": sorted(unexpected_fields)
            }, 400

        try:
            if "name" in data:
                user.name = data["name"]

            if "username" in data:
                username = data["username"].strip()

                existing = Users.query.filter(
                    Users.username == username,
                    Users.id != user.id
                ).first()

                if existing:
                    return {"message": "Username already exists."}, 409

                user.username = username

            if "email" in data:
                email = data["email"].strip().lower()

                existing = Users.query.filter(
                    Users.email == email,
                    Users.id != user.id
                ).first()

                if existing:
                    return {"message": "Email already exists."}, 409

                user.email = email

            if "password" in data:
                user.password = user.hash_password(data["password"])

            db.session.commit()

            return {
                "message": "User updated successfully.",
                "user": user.to_dict(include_email=True)
            }, 200

        except (AssertionError, ValueError, TypeError, AttributeError) as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except IntegrityError:
            db.session.rollback()
            return {"message": "Username or email already exists."}, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "A database error occurred."}, 500

    @jwt_required()
    def delete(self, user_id):
        current_user = get_current_user()

        if not is_admin(current_user):
            return {"message": "Admin access required."}, 403

        user = db.session.get(Users, user_id)

        if not user:
            return {"message": "User not found."}, 404

        try:
            db.session.delete(user)
            db.session.commit()

            return {"message": "User deleted successfully."}, 200

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": (
                    "Unable to delete this user. "
                    "They may have related records."
                )
            }, 500
