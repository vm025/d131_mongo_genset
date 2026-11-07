import streamlit as st
from pymongo import MongoClient

import os
import threading
import time




# 1. Retrieve connection string from .streamlit/secrets.toml
# Your secrets.toml should look like this:
# [mongo]
# connection_string = "mongodb+srv://<username>:<password>@cluster.xxxx.mongodb.net/"
mongo_uri = st.secrets["mongo"]["connection_string"]

# 2. Establish connection to the MongoDB cluster
client = MongoClient(mongo_uri)
print(client , "\n\n")

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


## --------  did not work. ----------------------------------------------------

# # Set shutdown duration in seconds (e.g., 5 minutes = 300 seconds)
# SHUTDOWN_DELAY = 40


# def auto_shutdown():
#   time.sleep(SHUTDOWN_DELAY)
#   os._exit(0)


# # Ensure the timer thread only starts once per session
# if "shutdown_started" not in st.session_state:
#   st.session_state["shutdown_started"] = True
#   threading.Thread(target=auto_shutdown, daemon=True).start() # starts the shutdown.

# # st.title("Auto-Shutdown Streamlit App")
# st.write(
#     f"This application will automatically shut down after"
#     f" {SHUTDOWN_DELAY // 60} minutes of running."
# )

## ----------------------------------------------

if __name__ == "__main__":
    clear_operation_logs()



