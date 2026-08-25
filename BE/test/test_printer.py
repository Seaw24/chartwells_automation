import sys
import types
import unittest
from unittest import mock

from BE.src.printer import ExcelPrinter, PrinterError


class _FakeWorksheets:
    def __init__(self, workbook, names):
        self.workbook = workbook
        self.items = [_FakeSheet(name, workbook) for name in names]

    @property
    def Count(self):
        return len(self.items)

    def __call__(self, one_based_index):
        return self.items[one_based_index - 1]


class _FakeSheet:
    def __init__(self, name, workbook=None):
        self.Name = name
        self.workbook = workbook
        self.print_calls = []

    def Copy(self, Before=None, After=None):
        if After is None:
            excel = self.workbook.application
            destination = _FakeWorkbook((), application=excel)
            excel.Workbooks.added.append(destination)
            excel.ActiveWorkbook = destination
            destination.Worksheets.items.append(
                _FakeSheet(f"{self.Name} copy", destination))
            return
        destination = After.workbook
        destination.Worksheets.items.append(
            _FakeSheet(f"{self.Name} copy", destination))

    def Delete(self):
        self.workbook.Worksheets.items.remove(self)

    def PrintOut(self, **kwargs):
        self.print_calls.append(kwargs)


class _FakeWorkbook:
    def __init__(self, names=("Sheet1",), application=None):
        self.application = application
        self.Worksheets = _FakeWorksheets(self, names)
        self.print_calls = []
        self.close_calls = []
        self.activate_calls = 0

    def PrintOut(self, **kwargs):
        self.print_calls.append(kwargs)

    def Close(self, **kwargs):
        self.close_calls.append(kwargs)

    def Activate(self):
        self.activate_calls += 1


class _FakeWorkbooks:
    def __init__(self, excel):
        self.excel = excel
        self.added = []

    def Add(self):
        workbook = _FakeWorkbook(application=self.excel)
        self.added.append(workbook)
        return workbook


class _FakeExcel:
    def __init__(self):
        self.ActiveWorkbook = None
        self.Workbooks = _FakeWorkbooks(self)


class PrinterTests(unittest.TestCase):
    def test_duplex_stages_sheets_from_different_workbooks_in_one_job(self):
        excel = _FakeExcel()
        printer = ExcelPrinter(settings={
            "duplex": True,
            "copies": 2,
            "collate": True,
        })
        printer._excel_active_printer = "Office Printer on Ne01:"

        first = _FakeSheet(
            "Monday", _FakeWorkbook(("Monday",), application=excel))
        second = _FakeSheet(
            "Tuesday", _FakeWorkbook(("Tuesday",), application=excel))

        printer._start_duplex_batch(excel)
        printer._print_sheet(first)
        printer._print_sheets(None, [second])
        printer._finish_duplex_batch()

        batch = excel.Workbooks.added[0]
        self.assertEqual(
            [sheet.Name for sheet in batch.Worksheets.items],
            ["Monday copy", "Tuesday copy"],
        )
        self.assertEqual(first.print_calls, [])
        self.assertEqual(second.print_calls, [])
        self.assertEqual(batch.print_calls, [{
            "Copies": 2,
            "Collate": True,
            "ActivePrinter": "Office Printer on Ne01:",
        }])
        printer._close_duplex_batch()
        self.assertEqual(batch.close_calls, [{"SaveChanges": False}])
        self.assertIsNone(printer._duplex_batch_workbook)

    def test_driver_devmode_allocates_private_driver_bytes(self):
        seed = types.SimpleNamespace(Fields=0, Duplex=1, Color=2)

        class FakeDevMode:
            Size = 120

            def __init__(self, driver_extra=0):
                self.driver_extra = driver_extra
                self.Fields = 0
                self.Duplex = 1
                self.Color = 2

        calls = []

        class FakeWin32Print:
            @staticmethod
            def GetPrinter(handle, level):
                return {"pDevMode": seed if level == 9 else None}

            @staticmethod
            def DocumentProperties(hwnd, handle, name, output, input_, flags):
                calls.append((output, input_, flags))
                if output is None:
                    return 168
                return 1

        modules = {
            "pywintypes": types.SimpleNamespace(DEVMODEType=FakeDevMode),
            "win32con": types.SimpleNamespace(
                DM_IN_BUFFER=8,
                DM_OUT_BUFFER=2,
            ),
        }
        with mock.patch.dict(sys.modules, modules):
            result = ExcelPrinter._read_driver_devmode(
                FakeWin32Print, "handle", "Office Printer")

        self.assertIsInstance(result, FakeDevMode)
        self.assertEqual(result.driver_extra, 48)
        self.assertEqual(calls[1], (result, seed, 10))

    def test_duplex_stops_before_printing_when_driver_reports_no_support(self):
        devmode = types.SimpleNamespace(Fields=0, Duplex=1, Color=2)
        fake_win32print = types.SimpleNamespace(
            ClosePrinter=lambda handle: None,
        )
        fake_win32con = types.SimpleNamespace(
            DMDUP_VERTICAL=2,
            DMDUP_SIMPLEX=1,
            DM_DUPLEX=0x1000,
        )
        printer = ExcelPrinter(settings={"duplex": True})

        with (
            mock.patch.dict(sys.modules, {
                "win32con": fake_win32con,
                "win32print": fake_win32print,
            }),
            mock.patch.object(
                printer, "_get_effective_windows_printer_name",
                return_value="Office Printer"),
            mock.patch.object(
                printer, "_open_windows_printer", return_value="handle"),
            mock.patch.object(
                printer, "_read_driver_devmode", return_value=devmode),
            mock.patch.object(
                printer, "_printer_supports_duplex", return_value=False),
        ):
            with self.assertRaisesRegex(
                    PrinterError, "automatic double-sided printing is not supported"):
                printer._apply_windows_driver_print_settings()

    def test_duplex_stops_when_driver_silently_discards_setting(self):
        devmode = types.SimpleNamespace(Fields=0, Duplex=1, Color=2)
        fake_win32print = types.SimpleNamespace(
            ClosePrinter=lambda handle: None,
        )
        fake_win32con = types.SimpleNamespace(
            DMDUP_VERTICAL=2,
            DMDUP_SIMPLEX=1,
            DM_DUPLEX=0x1000,
            DMCOLOR_MONOCHROME=1,
            DMCOLOR_COLOR=2,
            DM_COLOR=0x800,
        )
        printer = ExcelPrinter(settings={"duplex": True})

        with (
            mock.patch.dict(sys.modules, {
                "win32con": fake_win32con,
                "win32print": fake_win32print,
            }),
            mock.patch.object(
                printer, "_get_effective_windows_printer_name",
                return_value="Office Printer"),
            mock.patch.object(
                printer, "_open_windows_printer", return_value="handle"),
            mock.patch.object(
                printer, "_read_driver_devmode", return_value=devmode),
            mock.patch.object(
                printer, "_printer_supports_duplex", return_value=True),
            mock.patch.object(printer, "_validate_devmode"),
            mock.patch.object(printer, "_write_driver_devmode"),
            mock.patch.object(
                printer, "_read_back_devmode", return_value={"Duplex": 1}),
        ):
            with self.assertRaisesRegex(PrinterError, "did not retain"):
                printer._apply_windows_driver_print_settings()


if __name__ == "__main__":
    unittest.main()
