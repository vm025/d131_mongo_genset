"""Central, easily-editable configuration (single place to tweak behaviour)."""

# ---- Database -------------------------------------------------------------
USE_DB = True                      # False -> no DB connection; demo data is used
MONGO_HOST = "cluster0.hte6gm5.mongodb.net"
DB_NAME = "genset_db"
COLLECTION_NAME = "ops_logs"

# Field names inside each document of the collection
FIELD_SL_NO = "sl_no"
FIELD_GENSET = "genset_name"
FIELD_STATUS = "status"             # "on" / "off"
FIELD_TIMESTAMP = "timestamp"

# True  -> timestamps are stored as naive datetimes holding IST wall-clock time
# False -> timestamps are stored the usual Mongo way (UTC) and converted to IST
STORED_AS_IST_WALL_CLOCK = True

# True  -> timestamps are ISO-8601 strings, e.g. "2026-11-07T18:48:28+05:30"
# False -> timestamps are real BSON datetimes
TIMESTAMP_IS_STRING = True

GENSETS = ("ABC", "DEF")
TIMEZONE = "Asia/Kolkata"

# ---- Look & feel ----------------------------------------------------------
BODY_BG_COLOR = "#EEF0C8"           # light greenish-orange
TITLE_COLOR = "#B8860B"             # dark golden
BUTTON_BG = "#2E4A3F"               # dark button background
BUTTON_FG = "#FFFFFF"               # white button labels
CARD_BG = "#FBFAF0"
GENSET_COLORS = {"ABC": "#2F6F5E", "DEF": "#D9822B"}
