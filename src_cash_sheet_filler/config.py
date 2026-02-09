import sys
from pathlib import Path

# This code block makes your paths work in both
# normal mode (python src/main.py) and as an .exe

if getattr(sys, 'frozen', False):
    # If it is running as a bundled .exe:
    # BASE_DIR is the folder containing main.exe
    # (e.g., C:\...\Auto-fill casheet)
    BASE_DIR = Path(sys.executable).parent
else:
    # If it is running as a normal .py script:
    # BASE_DIR is the folder *above* the src folder
    # (e.g., C:\...\Auto-fill casheet)
    BASE_DIR = Path(__file__).parent.parent

# 4. Define your folders relative to the project root
REPORTS_FOLDER = BASE_DIR / "reports"
CASH_SHEET_FOLDER = BASE_DIR / "casheet"


REPORTS_CASHSHEET_MAP = {
    "Crimson Corner 1-1": ('Crimson Corner', "Crimson Corner"),
    "Gardner Food Court 1-1": ('gardner', "Register 1"),
    "Gardner Food Court 4-1": ('gardner', "Register 4"),
    "Honors Market 1-1": ('Honors', "Honors"),
    "Kahlert 1-1": ('KV', "Urban Bites 1"),
    "Kahlert 2-1": ('KV', "Urban Bites 2"),
    "Shake Smart 1-1": ('Shake Smart', "Life Center"),
    "The Bean Yard": ('Beanyard', "BeanYard"),
    "Thirst 1-1": ('Crimson Corner', "Thirst"),
    "Union Shake Smart 1-1": ('UnionShakeSmart', "U.S.S."),
    "Café Epicenter Market Kiosks": ("Epicenter", "Epicenter Market"),
    "Café Epicenter ordering Kiosk": ("Epicenter", "Epicenter Order"),
    "City Edge Cafe": ('HUB', "City's Edge 3"),
    "Crimson View": ("cv casheet", "Register 1"),
    "Einstein Bros. Bagels": ("Satellite", "Einsteins 1"),
    "Hive Express": ("HECS", "Hive Tavlo"),
    "Quartzdyne Cafe": ("HECS", "Quartz Café"),
    "Lassonde Market Kiosks": ("Lassonde", "Tavlo Market"),
    "Lassonde ordering Kiosk": ("Lassonde", "Tavlo Ordering"),
    "Seagull Sunrise at Lund Commons": ("CRSS", "Seagull Sunrise"),
    "Union Food Court": ("csfs", "foodcourt 1")

}

FILL_COL_MAP = {
    "date": 21,
    "count": 1,
    "location": 2,
    "total_sales": 3,
    "contract_card": 4,
    "flex": 6,
    "transfer": 7,
    "coupons": 8,
    "ucash": 11,
    "chartwellsDCB": 12,
    "dining_dollars": 13,
    "ushop": 14,
    "amex": 16,
    "discover": 17,
    "mc": 18,
    "visa": 19,
    "tax": 3
}

CHECKING_COL_MAP = {
    "cash overings": 8,
    "adj cash sales": 9,
    "cash sales": 18,
    "cash for deposit": 19,
    "over": 20
}

INFOR_TENDERS = {
    'AT Contract Card': 'contract_card',
    'AT Flex Dollars': 'flex',
    'AT Meal Transfer': 'transfer',
    'AT Meals': 'transfer',
    'AT ToGoBox Checkout': 'transfer',
    'AT ToGoBox Return': 'transfer',
    'AT Guest Pass': 'transfer',
    "ChartwellsDCB": "chartwellsDCB",
    "UShop": "ushop",
    'Coupons': 'coupons',
    'AT UCash': 'ucash',
    'AT Dining Dollars': 'dining_dollars',
    'Amex': 'amex',
    'Discover': 'discover',
    'Mastercard': 'mc',
    'Visa': 'visa',
}


TAVLO_TENDERS = {
    'Contract Card': 'contract_card',
    'Flex': 'flex',
    "Flex UID": "flex",
    'Transfer Meal': 'transfer',
    'Meal Transfer': 'transfer',
    "Meal Transfer UID": "transfer",
    'Coupons': 'coupons',
    'UCash': 'ucash',
    'UShop': 'ushop',
    "ChartwellsDCB": 'chartwellsDCB',
    'Dining Dollars': 'dining_dollars',
    'AMEX': 'amex',
    'Discover': 'discover',
    'DCVR': 'discover',
    'M/C': 'mc',
    'VISA': 'visa'
}


CASHEET_TENDERS = {
    'contract_card': 0.0,
    'flex': 0.0,
    'transfer': 0.0,
    'coupons': 0.0,
    'ucash': 0.0,
    'ushop': 0.0,
    "chartwellsDCB": 0.0,
    'dining_dollars': 0.0,
    'amex': 0.0,
    'discover': 0.0,
    'mc': 0.0,
    'visa': 0.0
}
