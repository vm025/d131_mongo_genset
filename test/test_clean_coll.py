import streamlit as st
from pymongo import MongoClient

# 1. Retrieve connection string from .streamlit/secrets.toml
# Your secrets.toml should look like this:
# [mongo]
# connection_string = "mongodb+srv://<username>:<password>@cluster.xxxx.mongodb.net/"
mongo_uri = st.secrets["mongo"]["connection_string"]

# 2. Establish connection to the MongoDB cluster
client = MongoClient(mongo_uri)

# 3. Target your specific database and collection
DB_NAME = "genset_db"
COLLECTION_NAME = "operation_logs"

db = client[DB_NAME]
collection = db[COLLECTION_NAME]

def clear_operation_logs():
    try:
        # Option A: Deletes all documents but KEEPS the collection & indexes intact
        result = collection.delete_many({})
        print(f"Successfully cleared data! Deleted {result.deleted_count} logs.")
        
        # Option B: Uncomment the line below if you want a complete, fast wipeout 
        # (Note: This drops indexes, so you will need to re-create them next time you write)
        # collection.drop()
        
    except Exception as e:
        print(f"An error occurred while deleting data: {e}")
    finally:
        # Always close the connection pool when done
        client.close()


if __name__ == "__main__":
    clear_operation_logs()
