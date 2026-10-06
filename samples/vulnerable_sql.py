def get_user_profile(user_id):
    # Vulnerable to SQL Injection
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()
