from sqlalchemy import create_engine, text

CONN_STR = "postgresql://postgres:KUrBZASRsVpSqBSWpXeqWZvFudDsLMEp@mainline.proxy.rlwy.net:50842/railway"
engine = create_engine(CONN_STR)

with engine.begin() as conn:
    conn.execute(text('DELETE FROM cv_tasks'))
    conn.execute(text('DELETE FROM user_arc_data'))
    print('Cleared cv_tasks and user_arc_data tables.') 