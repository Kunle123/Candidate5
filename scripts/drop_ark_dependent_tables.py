import psycopg2

ARK_CONN_STR = "postgresql://postgres:KUrBZASRsVpSqBSWpXeqWZvFudDsLMEp@mainline.proxy.rlwy.net:50842/railway"

def drop_dependent_tables():
    conn = psycopg2.connect(ARK_CONN_STR)
    conn.autocommit = True
    cur = conn.cursor()
    tables = [
        "ai_extraction_logs",
        "cv_tasks",
        "user_arc_data"
    ]
    for table in tables:
        try:
            cur.execute(f'DROP TABLE IF EXISTS {table} CASCADE;')
            print(f"Dropped {table} table.")
        except Exception as e:
            print(f"Error dropping {table}: {e}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    drop_dependent_tables() 