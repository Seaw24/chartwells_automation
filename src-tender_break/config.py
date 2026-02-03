# config.py

# Maps keywords found in filenames to the official names in the Breakdown sheet
"""Settings: 
{
  "filepath" : [{"Location name 1 in Breakdown sheet" : "What to look for in casheet"}},
    ...         {"Location name 2 in Breakdown sheet" : "What to look for in casheet"}] 
  }
  """

FILENAME_TO_MASTER_NAME = {
    "beanyard": [{"beanyard": "TOTALS"}],
    "crimson corner": [{"crimson corner": "TOTALS"}],
    "unionshakesmart": [{"union shake smart": "TOTALS"}],
    "gardner": [{"gardner": "TOTALS"}],
    "honors": [{"honors": "TOTALS"}],
    "heritage": [{"phc": ["Heritage 1", "Heritage 2"]}],
    "kv": [{"kahlert": "TOTALS"}],
    "shake smart ": [{"student life center": "TOTALS"}],
    "epicenter": [{"epicenter": "TOTALS"}],
    "cv casheet": [{"crimson view": "TOTALS"}],
    "lassonde": [{"lassonde": "TOTALS"}],
    "satellite": [{"einsteins": "TOTALS"}],
    "hecs": [{"hive": "Hive Tavlo"}, {"quartzdyne": "Quartz Café"}],
    "hub": [{"city's edge": "TOTALS"}],
    "crss": [{"seagull sunrise": "TOTALS"}],
    "csfs": [{"union food court": "TOTALS"}],
    "shake smart": [{"student life center": "TOTALS"}],
}

# Starting column of each location in the tender breakdown sheet
LOCATION_START_COL = {
    "phc": 2,
    "crimson view": 14,
    "einsteins": 26,
    "hive": 38,
    "union food court": 50,
    "honors": 62,
    "gardner": 74,
    "crimson corner": 86,
    "lassonde": 98,
    "beanyard": 110,
    "student life center": 122,
    "kahlert": 134,
    "union shake smart": 146,
    "epicenter": 158,
    "quartzdyne": 170,
    "seagull sunrise": 182,
    "city's edge": 194
}
# Directory paths for cash sheets and master file
DIRECTORY_PATHS = {
    "casheets_dir": "cash sheets",
    "master_path": "Tender Breakdown.xlsx"
}

# Data/Col in the cash sheet that needs to be filled to the tender breakdown
IMPORTANT_CASHEET_DATA_COL = [3, 4, 6, 7, 8, 11, 13, 16, 17, 18, 19]
