# -*- coding: utf-8 -*-
"""删除截图用的演示数据库。"""
import os

import pymysql

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root",
    password=os.environ["DEMO_DB_PASSWORD"], charset="utf8mb4",
)
with conn.cursor() as cur:
    cur.execute("DROP DATABASE IF EXISTS `message-classify-demo`")
conn.commit()
conn.close()
print("demo db dropped")
