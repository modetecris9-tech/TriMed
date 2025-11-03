import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',         # usuário MySQL
            password='',         # senha MySQL
            database='trimed_db'
        )
        return conn
    except Error as e:
        print("Erro ao conectar ao MySQL:", e)
        return None
