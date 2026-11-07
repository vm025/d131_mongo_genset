============== genset ops ===================

installation:    uv add streamlit  pymongo  tzdata


a) settings in UI: both gensets included.


b) db settings:
 --network access:  allow the reqd IP addresses.
DB_NAME = "genset_db"
COLLECTION_NAME = "ops_logs"

-- to  create the db: go to "Data Explorer", connect to the cluster, & then create 
  this db & its collection.

========= graph ================================

uv add pandas plotly


### File	 &   Responsibility:

* config.py: 	All settings in one place: USE_DB (default False), DB_NAME, COLLECTION_NAME, 
  field names, the body background colour, title colour and button colours.
* repository.py	An abstract EventRepository with a MongoDB version and a demo-data version. 
   Mongo is only touched when USE_DB = True.
* processor.py	Pure logic that turns events into runs, then into per-day figures, with no I/O.
* service.py	Ties the repository and processor together.
* charts.py	Builds the stacked bar and stacked line charts.
* app.py	The Streamlit interface and styling.


--Timestamp storage: STORED_AS_IST_WALL_CLOCK = True assumes timestamps are stored as naive 
 datetimes holding IST clock time.
--The demo data comes from DemoEventRepository in genset/repository.py. 
   It is used whenever USE_DB = False, and nothing connects to Mongo in that mode.