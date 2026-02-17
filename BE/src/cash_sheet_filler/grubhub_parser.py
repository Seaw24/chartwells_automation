from datetime import datetime
from .config import GRUBHUB_TENDERS, CASHEET_TENDERS


class Grubhub_parser:
    def __init__(self, xl_path):
        self.xl_path = xl_path

        # {date: { venue: { total_count , total_sales, total_tax, tenders, balance } }} before convert to general cash sheet
        self.raw_data = {}

        # After convert to general cash sheet, {date: { venue: { total_count , total_sales, total_tax, tenders, balance } }}
        self.data = {}

    def normalize_date(self, date_str):
        # Implement date normalization logic here
        # For example, convert "MM/DD/YYYY" to "YYYY-MM-DD"
        try:
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}")

    # def parse(self):
    #     # Implement parsing logic here to populate self.raw_data

    #     try:
    #         with open(self.xl_path, 'r') as f:
    #             #Retrive content from the file
    #             content = f.read()
    #             lines = content.splitlines()

    #             #Poplate self.raw_data with the content of the file
    #             for line in lines:
