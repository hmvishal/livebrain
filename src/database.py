import sqlite3
from sqlite3 import Error
import os

# Define the path for the database file (in the root directory)
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot.db')

def create_connection():
    """ create a database connection to the SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        return conn
    except Error as e:
        print(e)
    return conn

def create_table(conn, create_table_sql):
    """ create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)

def setup_database():
    """ create the necessary tables for the bot """

    sql_create_clients_table = """
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL UNIQUE,
        subscription_status TEXT NOT NULL DEFAULT 'inactive',
        subscription_expiry_date TIMESTAMP,
        payment_gateway_config TEXT
    );
    """

    sql_create_groups_table = """
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL UNIQUE,
        client_id INTEGER NOT NULL,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    );
    """

    sql_create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        subscription_status TEXT NOT NULL DEFAULT 'inactive',
        subscription_expiry_date TIMESTAMP,
        UNIQUE(telegram_id, group_id),
        FOREIGN KEY (group_id) REFERENCES groups (id)
    );
    """

    sql_create_faqs_table = """
    CREATE TABLE IF NOT EXISTS faqs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES groups (id)
    );
    """

    conn = create_connection()

    if conn is not None:
        # create tables
        create_table(conn, sql_create_clients_table)
        create_table(conn, sql_create_groups_table)
        create_table(conn, sql_create_users_table)
        create_table(conn, sql_create_faqs_table)
        conn.close()
    else:
        print("Error! cannot create the database connection.")

def get_or_create_client(telegram_id):
    """Get a client by telegram_id, or create one if they don't exist."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,))
    client = cursor.fetchone()
    if client is None:
        cursor.execute("INSERT INTO clients (telegram_id) VALUES (?)", (telegram_id,))
        conn.commit()
        cursor.execute("SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,))
        client = cursor.fetchone()
    conn.close()
    # Return client as a dictionary for easier access
    if client:
        client_dict = {
            "id": client[0],
            "telegram_id": client[1],
            "subscription_status": client[2],
            "subscription_expiry_date": client[3],
            "payment_gateway_config": client[4],
        }
        return client_dict
    return None

def update_client_subscription(client_id, expiry_date):
    """Update the subscription status and expiry date for a client."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clients SET subscription_status = ?, subscription_expiry_date = ? WHERE id = ?",
        ('active', expiry_date, client_id)
    )
    conn.commit()
    conn.close()

def get_expiring_clients(days_to_expiry=3):
    """Get clients whose subscriptions are expiring within a certain number of days."""
    conn = create_connection()
    cursor = conn.cursor()
    # Using date('now', '+X days') to find expiry dates in the future
    expiry_threshold = f"date('now', '+{days_to_expiry} days')"
    cursor.execute(
        "SELECT telegram_id, subscription_expiry_date FROM clients WHERE subscription_status = 'active' AND date(subscription_expiry_date) <= " + expiry_threshold
    )
    expiring_clients = cursor.fetchall()
    conn.close()
    return expiring_clients


def add_or_get_group(group_id, client_id):
    """Adds a new group for a client, or gets it if it already exists."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
    group = cursor.fetchone()
    if group is None:
        cursor.execute("INSERT INTO groups (group_id, client_id) VALUES (?, ?)", (group_id, client_id))
        conn.commit()
        cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
        group = cursor.fetchone()
    conn.close()
    if group:
        group_dict = {
            "id": group[0],
            "group_id": group[1],
            "client_id": group[2],
        }
        return group_dict
    return None

def add_user_to_group(user_id, group_id_db):
    """Adds a user to a group with an inactive subscription."""
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (telegram_id, group_id) VALUES (?, ?)", (user_id, group_id_db))
        conn.commit()
    except sqlite3.IntegrityError:
        # User is already in the group, which is fine.
        pass
    finally:
        conn.close()

def update_user_subscription(user_id, group_id_db, expiry_date):
    """Updates a user's subscription status and expiry date."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET subscription_status = 'active', subscription_expiry_date = ? WHERE telegram_id = ? AND group_id = ?",
        (expiry_date, user_id, group_id_db)
    )
    conn.commit()
    conn.close()

def get_user_in_group(user_id, group_id_db):
    """Gets a user's details for a specific group."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ? AND group_id = ?", (user_id, group_id_db))
    user = cursor.fetchone()
    conn.close()
    if user:
        user_dict = {
            "id": user[0],
            "telegram_id": user[1],
            "group_id": user[2],
            "subscription_status": user[3],
            "subscription_expiry_date": user[4],
        }
        return user_dict
    return None

def get_group_by_telegram_id(group_telegram_id):
    """Gets a group's details by its telegram group ID."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_telegram_id,))
    group = cursor.fetchone()
    conn.close()
    if group:
        group_dict = {
            "id": group[0],
            "group_id": group[1],
            "client_id": group[2],
        }
        return group_dict
    return None

def get_group_members(group_db_id):
    """Gets all members of a group."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, subscription_status, subscription_expiry_date FROM users WHERE group_id = ?", (group_db_id,))
    members = cursor.fetchall()
    conn.close()
    return members

def get_expired_group_members():
    """Gets all users with an expired subscription."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT u.telegram_id, g.group_id FROM users u "
        "JOIN groups g ON u.group_id = g.id "
        "WHERE u.subscription_status = 'active' AND date(u.subscription_expiry_date) < date('now')"
    )
    expired_users = cursor.fetchall()
    conn.close()
    return expired_users

def set_user_inactive(user_telegram_id, group_telegram_id):
    """Sets a user's subscription status to inactive."""
    # This function is a bit more complex as we have telegram IDs, not DB IDs.
    group = get_group_by_telegram_id(group_telegram_id)
    if not group:
        return

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET subscription_status = 'inactive' WHERE telegram_id = ? AND group_id = ?",
        (user_telegram_id, group['id'])
    )
    conn.commit()
    conn.close()

def add_faq(group_db_id, question, answer):
    """Adds a new FAQ to a group."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO faqs (group_id, question, answer) VALUES (?, ?, ?)", (group_db_id, question, answer))
    conn.commit()
    conn.close()

def delete_faq(faq_id):
    """Deletes an FAQ by its ID."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    conn.commit()
    conn.close()

def get_faqs_for_group(group_db_id):
    """Gets all FAQs for a group."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, answer FROM faqs WHERE group_id = ?", (group_db_id,))
    faqs = cursor.fetchall()
    conn.close()
    return faqs

def update_client_payment_config(client_id, config_json):
    """Updates the payment gateway configuration for a client."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clients SET payment_gateway_config = ? WHERE id = ?",
        (config_json, client_id)
    )
    conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()
