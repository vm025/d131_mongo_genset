
uv add streamlit  pymongo  tzdata


a) settings in UI:
Radio buttons: each now has a fixed width, set by RADIO_WIDTH_PX = 300.
Submit button: it now has a fixed width, set by SUBMIT_WIDTH_PX = 240

b) db settings:
 --network access:  allow the reqd IP addresses.
DB_NAME = "genset_db"
COLLECTION_NAME = "operation_logs"

-- to  create the db: go to "Data Explorer", connect to the cluster, & then create 
  this db & its collection.

