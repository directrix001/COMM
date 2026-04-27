"""
utils/constants.py
──────────────────
Shared constants used across tabs and utilities.
"""

import calendar

FULL_TO_ABBR = {m: calendar.month_abbr[i] for i, m in enumerate(calendar.month_name) if m}
ABBR_SET = set(calendar.month_abbr[1:])
MONTH_HEADER_REGEX = r"\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"

MONTH_TO_FYNUM = {
    "Apr": 1,  "May": 2,  "Jun": 3,  "Jul": 4,
    "Aug": 5,  "Sep": 6,  "Oct": 7,  "Nov": 8,
    "Dec": 9,  "Jan": 10, "Feb": 11, "Mar": 12,
}

FY_NAMES = [
    "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "January", "February", "March",
]

FY_MONTH_OPTIONS = [f"{str(i+1).zfill(2)} - {FY_NAMES[i]}" for i in range(12)]

PREF_GROUP_ORDER = [
    "OH/LC", "CostCat description", "Division_Desc",
    "Function_Desc", "Departement_desc", "Entity_desc",
]

MAPPING_PATH = "backend/mapping.xlsx"

HEADER_H = 64
FOOTER_H = 50
