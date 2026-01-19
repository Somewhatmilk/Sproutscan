# --- START OF FILE forms.py ---
from wtforms import Form, StringField, PasswordField, SelectField, TextAreaField, validators

class LoginForm(Form):
    username = StringField('Username', [validators.DataRequired()])
    password = PasswordField('Password', [validators.DataRequired()])
    mfa_token = StringField('MFA Token')

class FarmForm(Form):
    number = StringField('Serial Number', [
        validators.DataRequired(message="Serial Number is required."),
        validators.Length(min=3, max=20, message="Serial must be between 3-20 chars.")
    ])
    name = StringField('Farm Name', [
        validators.DataRequired(message="Farm Name is required.")
    ])
    date_created = StringField('Date Created', [
        validators.DataRequired(),
        validators.Regexp(r'\d{2}/\d{2}/\d{4}', message="Format must be DD/MM/YYYY")
    ])

# Adapted from SproutScan's "CreateUserForm", but for Farm Incidents
class IncidentForm(Form):
    issue = StringField('Issue Title', [
        validators.DataRequired(),
        validators.Length(min=3, max=50)
    ])
    # The SproutScan feature adaptation:
    category = SelectField('Category', choices=[
        ('Pest', 'Pest Infestation'),
        ('Hardware', 'Sensor/Drone Failure'),
        ('Irrigation', 'Water/Irrigation Issue'),
        ('Network', 'Connectivity Loss'),
        ('Other', 'General Observation')
    ])
    severity = SelectField('Severity', choices=[
        ('Low', 'Low - Monitor'),
        ('Medium', 'Medium - Intervention'),
        ('High', 'High - Immediate Danger')
    ])
    remarks = TextAreaField('Remarks', [validators.Optional()])