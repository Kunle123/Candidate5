import psycopg2

# Connection string
conn_str = "postgresql://postgres:KUrBZASRsVpSqBSWpXeqWZvFudDsLMEp@mainline.proxy.rlwy.net:50842/railway"

try:
    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    cur = conn.cursor()
    print("Connected to the database.")

    # Delete all records from the relevant tables
    cur.execute("DELETE FROM user_arc_data;")
    print("Deleted all records from user_arc_data.")
    cur.execute("DELETE FROM cv_tasks;")
    print("Deleted all records from cv_tasks.")

    cur.close()
    conn.close()
    print("Connection closed.")
except Exception as e:
    print(f"Error: {e}") 