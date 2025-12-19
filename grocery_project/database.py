import psycopg2
from psycopg2.extras import RealDictCursor


import psycopg2
from psycopg2.extras import RealDictCursor # Обязательно импортируйте это!

def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="grocery_db",
        user="postgres",
        password="123123",
        # Этот параметр заставляет базу возвращать словари вместо кортежей
        cursor_factory=RealDictCursor
    )
    return conn


def execute_query(query, params=None, fetch=False):
    """Универсальная функция для выполнения запросов"""
    conn = get_db_connection()
    if conn is None:
        return None

    # RealDictCursor позволяет получать данные в виде словаря {'column': value}
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params)

    result = None
    if fetch:
        result = cur.fetchall()

    conn.commit()
    cur.close()
    conn.close()
    return result