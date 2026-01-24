#run if cant login due to MFA issues

import sqlite3

# Connect to your database
conn = sqlite3.connect('plantations.db')
cursor = conn.cursor()

# Reset MFA for ALL users (or specify a username: WHERE username='admin')
cursor.execute("UPDATE users SET mfa_secret = NULL")
conn.commit()

print("SUCCESS: MFA has been disabled for all users. You can login now.")
conn.close()