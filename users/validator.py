import re
from django.core.exceptions import ValidationError

class ExtraPasswordValidator:
    def validate(self, password):
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')

        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')

        # Check for at least one digit
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')

        # Check for at least one special character
        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError('Password must contain at least one special character.')

        return password

    def get_help_text(self):
        return """Your password must contain at least one uppercase letter, one lowercase letter,
            one numerical digit, and one special character."""