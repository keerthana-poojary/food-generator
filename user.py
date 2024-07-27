import sqlite3

conn=sqlite3.connect('subbi.db')

cat=conn.cursor()

sql="create table bekk(kaal varchar(100),kay int)"

cat.execute(sql)