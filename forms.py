from wtforms import Form, StringField, PasswordField, SelectField, TextAreaField, validators

class LoginForm(Form):
    username = StringField('Username', [validators.DataRequired()])
    password = PasswordField('Password', [validators.DataRequired()])
    mfa_token = StringField('MFA Token')

class FarmForm(Form):
    number = StringField('Serial Number', [
        validators.DataRequired(),
        # We keep the Serial regex, but we will add a button to auto-fill it correctly
        validators.Regexp(r'^[A-Z]{2,4}-\d{3,6}$', message="Format: XXXX-000 (e.g., AGRI-105)")
    ])
    name = StringField('Farm Name', [
        validators.DataRequired(),
        validators.Length(min=3, max=30)
    ])
 
    date_created = StringField('Date Created', [validators.DataRequired()])

class IncidentForm(Form):
    issue = StringField('Issue Title', [
        validators.DataRequired(),
        validators.Length(min=3, max=50)
    ])
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