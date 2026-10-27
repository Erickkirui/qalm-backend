
from sqlalchemy.orm import validates
import bcrypt
import re
from app import db




class Users(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(70), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.String(10),
        default="normal",
        nullable=False
    )

    status = db.Column(
        db.String(10),
        default="active",
        nullable=False
    )

    has_therapist_profile = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    @validates('name')
    def validate_name(self, key, name):
        assert name and name.strip(), "Name is required."
        return name.strip()

    @validates('email')
    def validate_email(self, key, email):
        email = email.strip().lower()
        assert '@' in email, "Email address must contain the @ symbol."
        assert '.' in email.split('@')[-1], \
            "Email address must have a valid domain name."
        return email

    @validates('username')
    def validate_username(self, key, username):
        username = username.strip()
        assert len(username) >= 8, \
            "Username must be at least 8 characters long."
        return username

    @validates('password')
    def validate_password(self, key, password):
        assert len(password) >= 8, \
            "Password must be at least 8 characters long."
        assert any(char.isupper() for char in password), \
            "Password must contain at least one capital letter."
        assert any(char.isdigit() for char in password), \
            "Password must contain at least one number."
        assert re.search(r'[!@#$%^&*()\-_=+{};:,<.>]', password), \
            "Password must contain at least one symbol."
        return password

    @validates('role')
    def validate_role(self, key, role):
        allowed_roles = ('admin', 'normal')
        assert role in allowed_roles, (
            f"Role must be one of: {', '.join(allowed_roles)}."
        )
        return role

    @validates('status')
    def validate_status(self, key, status):
        allowed_statuses = ('active', 'inactive', 'suspended')
        assert status in allowed_statuses, (
            f"Status must be one of: {', '.join(allowed_statuses)}."
        )
        return status

    def hash_password(self, password):
        # Hash the password using bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')

    def to_dict(self, include_email=False):
        """Serialize user details without exposing the password hash."""
        data = {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'role': self.role,
            'status': self.status,
            'has_therapist_profile': self.has_therapist_profile,
        }

        if include_email:
            data['email'] = self.email

        return data

    def __repr__(self):
        return (
            f"Users(id={self.id}, name='{self.name}', "
            f"username='{self.username}', email='{self.email}')"
        )
