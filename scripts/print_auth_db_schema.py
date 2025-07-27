import psycopg2

CONN_STR = 'postgresql://postgres:SnXjWvCWbNndmBhCTrlHkpSmkHAMcnJH@yamanote.proxy.rlwy.net:32243/railway'

OUTPUT_FILE = 'auth_db_schema.txt'

def print_schema():
    conn = psycopg2.connect(CONN_STR)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = cur.fetchall()
    lines = []
    lines.append('Tables:')
    for t in tables:
        lines.append(f'- {t[0]}')
    lines.append('\n')
    for t in tables:
        lines.append(f'\nTable: {t[0]}')
        cur.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = %s", (t[0],))
        for r in cur.fetchall():
            lines.append(f'  {r[0]} | {r[1]} | nullable: {r[2]}')
    cur.close()
    conn.close()
    with open(OUTPUT_FILE, 'w') as f:
        f.write('\n'.join(lines))

if __name__ == '__main__':
    print_schema() 