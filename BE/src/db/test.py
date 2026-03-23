import psycopg2
conn = psycopg2.connect(
    host="aws-1-us-east-1.pooler.supabase.com",
    port=6543,
    user="postgres.rfnllnvvsgkduknhinuo",
    password="@xENi5BzYdBgNfC",
    dbname="postgres",
)
print("Connected!")
conn.close()
