installation:    uv add streamlit  pymongo  tzdata


a) settings in UI: both gensets included.


b) db settings:
 --network access:  allow the reqd IP addresses.
DB_NAME = "genset_db"
COLLECTION_NAME = "ops_logs"

-- to  create the db: go to "Data Explorer", connect to the cluster, & then create 
  this db & its collection.

