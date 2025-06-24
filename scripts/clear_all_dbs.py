import psycopg2

ARK_CONN_STR = "postgresql://postgres:KUrBZASRsVpSqBSWpXeqWZvFudDsLMEp@mainline.proxy.rlwy.net:50842/railway"
USER_CONN_STR = "postgresql://postgres:jvTSAaPPRetcBWADiXAJmtKILCTUuNuZ@nozomi.proxy.rlwy.net:34043/railway"
AUTH_CONN_STR = "postgresql://postgres:SnXjWvCWbNndmBhCTrlHkpSmkHAMcnJH@yamanote.proxy.rlwy.net:32243/railway"

CV_DB_URL = "postgresql://postgres:oYoFOWMUQpxMHGvkudKmrFMEPXisPAtG@yamabiko.proxy.rlwy.net:39356/railway"

cv_tables = [
    "applications",
    "cvs",
    "experiences",
    "education",
    "skills",
    "languages",
    "projects",
    "certifications",
    "references"
]

def clear_ark_db():
    try:
        conn = psycopg2.connect(ARK_CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        print("[Ark DB] Connected.")
        cur.execute("DELETE FROM cv_tasks;")
        cur.execute("DELETE FROM user_arc_data;")
        print("[Ark DB] Cleared cv_tasks and user_arc_data.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Ark DB] Error: {e}")

def clear_user_db():
    try:
        conn = psycopg2.connect(USER_CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        print("[User DB] Connected.")
        cur.execute("DELETE FROM users;")
        print("[User DB] Cleared users table.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[User DB] Error: {e}")

def clear_auth_db():
    try:
        conn = psycopg2.connect(AUTH_CONN_STR)
        conn.autocommit = True
        cur = conn.cursor()
        print("[Auth DB] Connected.")
        cur.execute("DELETE FROM users;")
        print("[Auth DB] Cleared users table.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Auth DB] Error: {e}")

def clear_cv_db():
    print("[CV DB] Connecting...")
    conn = psycopg2.connect(CV_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        for table in cv_tables:
            try:
                cur.execute(f'TRUNCATE TABLE {table} CASCADE;')
                print(f"[CV DB] Cleared {table} table.")
            except Exception as e:
                print(f"[CV DB] Error clearing {table}: {e}")
    finally:
        cur.close()
        conn.close()
        print("[CV DB] Done.")

def main():
    print("Clearing all main tables in Ark, User, and Auth DBs...")
    clear_ark_db()
    clear_user_db()
    clear_auth_db()
    clear_cv_db()
    print("All done.")

if __name__ == "__main__":
    main() 