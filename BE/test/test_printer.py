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


class _FakeCell:
    def __init__(self, row, column):
        self.Row = row
        self.Column = column


class _FakeRange:
    def __init__(self, first, last):
        self.Address = (
            f"$A${first.Row}:${_col_letter(last.Column)}${last.Row}")


def _col_letter(index):
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


class _FakeCells:
    """Enough of Range.Cells/Range.Find for _last_content_cell."""

    def __init__(self, sheet):
        self.sheet = sheet

    def __call__(self, row, column):
        return _FakeCell(row, column)

    def Find(self, **kwargs):
        return _FakeCell(self.sheet.last_row, self.sheet.last_col)


class _FakePages:
    def __init__(self, setup):
        self._setup = setup

    @property
    def Count(self):
        return self._setup.page_count()


class _FakePageSetup:
    """
    Models the one behaviour that matters: whether Excel honours the request.

    ``honors_fit`` False is the real failure this guards — Excel accepts
    Zoom/FitToPages without complaint and paginates as if they were never
    set, which is how cash sheets reached the printer cut off.
    """

    def __init__(self, fits_at=45, honors_fit=True):
        self.PrintArea = "$A$1:$W$62"
        self.FitToPagesWide = None
        self.FitToPagesTall = None
        self.fits_at = fits_at          # largest zoom that still prints as one
        self.honors_fit = honors_fit
        self.Pages = _FakePages(self)
        self.zoom_history = []
        self._zoom = 100

    @property
    def Zoom(self):
        return self._zoom

    @Zoom.setter
    def Zoom(self, value):
        self._zoom = value
        self.zoom_history.append(value)

    def page_count(self):
        if self._zoom is False:
            return 1 if self.honors_fit else 4
        return 1 if self._zoom <= self.fits_at else 4


class _FakeTracker:
    def __init__(self):
        self.warnings = []
        self.details = []

    def warning(self, message):
        self.warnings.append(message)

    def detail(self, message):
        self.details.append(message)

    def log(self, message):
        pass


class _FakeSheet:
    def __init__(self, name, workbook=None, fits_at=45, honors_fit=True,
                 last_row=84, last_col=23):
        self.Name = name
        self.workbook = workbook
        self.print_calls = []
        self.PageSetup = _FakePageSetup(fits_at, honors_fit)
        self.reset_breaks = 0
        self.last_row = last_row
        self.last_col = last_col
        self.Cells = _FakeCells(self)

    def Range(self, first, last):
        return _FakeRange(first, last)

    def ResetAllPageBreaks(self):
        self.reset_breaks += 1

    def Copy(self, Before=None, After=None):
        if After is None:
            excel = self.workbook.application
            destination = _FakeWorkbook((), application=excel)
            excel.Workbooks.added.append(destination)
            excel.ActiveWorkbook = destination
            destination.Worksheets.items.append(
                _FakeSheet(f"{self.Name} copy", destination,
                           fits_at=self.PageSetup.fits_at,
                           honors_fit=self.PageSetup.honors_fit))
            return
        destination = After.workbook
        destination.Worksheets.items.append(
            _FakeSheet(f"{self.Name} copy", destination,
                       fits_at=self.PageSetup.fits_at,
                       honors_fit=self.PageSetup.honors_fit))

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

    def test_duplex_redoes_the_page_setup_on_the_staged_copies(self):
        """
        The copy in the batch workbook is what prints, so it gets the print
        area and the one-page scaling in its own right.
        """
        excel = _FakeExcel()
        printer = ExcelPrinter(settings={"duplex": True})
        source = _FakeSheet(
            "Monday", _FakeWorkbook(("Monday",), application=excel))
        printer._expand_print_area(source)

        printer._start_duplex_batch(excel)
        printer._print_sheets(None, [source], fit_one_page=True)

        copy = excel.Workbooks.added[0].Worksheets.items[0]
        self.assertEqual(copy.PageSetup.PrintArea, "$A$1:$W$84")
        self.assertIs(copy.PageSetup.Zoom, False)
        self.assertEqual(copy.PageSetup.FitToPagesWide, 1)
        self.assertEqual(copy.PageSetup.FitToPagesTall, 1)
        self.assertEqual(copy.reset_breaks, 1)
        printer._close_duplex_batch()

    def test_duplex_leaves_report_scaling_alone(self):
        """Reports print at 100% on purpose; only cash sheets are refitted."""
        excel = _FakeExcel()
        printer = ExcelPrinter(settings={"duplex": True})
        report = _FakeSheet(
            "Financials", _FakeWorkbook(("Financials",), application=excel))

        printer._start_duplex_batch(excel)
        printer._print_sheet(report)

        copy = excel.Workbooks.added[0].Worksheets.items[0]
        self.assertEqual(copy.PageSetup.Zoom, 100)
        self.assertIsNone(copy.PageSetup.FitToPagesWide)
        printer._close_duplex_batch()

    def test_keeps_excels_own_fit_when_excel_honours_it(self):
        tracker = _FakeTracker()
        printer = ExcelPrinter(tracker=tracker)
        sheet = _FakeSheet("Monday", honors_fit=True)

        printer._fit_to_one_page(sheet)

        self.assertEqual(sheet.PageSetup.zoom_history, [False])
        self.assertEqual(tracker.warnings, [])

    def test_falls_back_to_an_explicit_zoom_when_excel_ignores_the_fit(self):
        """
        The failure this whole path exists for: Excel accepts Zoom/FitToPages
        without complaint and paginates as if they were never set.
        """
        tracker = _FakeTracker()
        printer = ExcelPrinter(tracker=tracker)
        sheet = _FakeSheet("Monday", fits_at=42, honors_fit=False)

        printer._fit_to_one_page(sheet)

        # the largest whole percent that still prints as one page
        self.assertEqual(sheet.PageSetup.Zoom, 42)
        self.assertEqual(sheet.PageSetup.page_count(), 1)
        self.assertEqual(tracker.warnings, [])
        self.assertTrue(
            any("printed at 42%" in d for d in tracker.details),
            tracker.details)

    def test_warns_when_nothing_fits_even_at_the_floor(self):
        tracker = _FakeTracker()
        printer = ExcelPrinter(tracker=tracker)
        sheet = _FakeSheet("Monday", fits_at=5, honors_fit=False)

        printer._fit_to_one_page(sheet)

        self.assertEqual(len(tracker.warnings), 1)
        self.assertIn("will not fit on one page", tracker.warnings[0])

    def test_shrink_never_probes_below_excels_floor(self):
        printer = ExcelPrinter(tracker=_FakeTracker())
        sheet = _FakeSheet("Monday", fits_at=5, honors_fit=False)

        printer._fit_to_one_page(sheet)

        probes = [z for z in sheet.PageSetup.zoom_history if z is not False]
        self.assertTrue(probes)
        self.assertGreaterEqual(min(probes), 10)

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
