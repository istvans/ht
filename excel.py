# coding=utf-8
"""The excel persistence module"""
from abc import abstractmethod
from collections import namedtuple
import contextlib
from datetime import date, datetime
import os.path
import re
import sys
from typing import Any, Dict, List
import xlwings as xl
from xlwings.utils import rgb_to_int

from overrides import overrides

from data import Player, Team


CellType = xl.Range
RangeType = xl.Range
RowType = xl.Range
ColumnType = xl.Range
SheetType = xl.Sheet
SheetsType = List[SheetType]

FIRST_CELL = "A1"
FIRST_ROW = "1:1"
FIRST_DATA_ROW = "2:2"
FIRST_COLUMN = "A:A"

SOLD_PLAYER_MARKER = '$'
NEW_PLAYER_MARKER = '@'
NEXT_PLAYER_NAME_ATTRIBUTE = "next_player_name"


def _is_player_sheet(sheet: SheetType):
    """Return whether the specified sheet is a player sheet"""
    return sheet[FIRST_CELL].value == "Dátum"


def _update_value_next_to_named_cell(cell: CellType, name: str, value: Any):
    """Update the value of the cell on the right side of the named cell
    iff the cell is indeed the named cell.
    """
    if cell.value == name:
        next_cell = cell.offset(row_offset=0, column_offset=1)
        next_cell.value = value
        found = True
    else:
        found = False
    return found


def _find_cell_by_name(cells: RangeType, value: str, num_empty_cells_means_eor=3):
    """Return the cell if it was found in the range, or None
    The range is ended if there are `num_empty_cells_means_eor` consecutive empty
    cells in it
    """
    named_cell = None
    none_counter = 0
    for cell in cells:
        if cell.value is None:
            none_counter += 1
        else:
            none_counter = 0
            if cell.value == value:
                named_cell = cell
                break
        if none_counter == num_empty_cells_means_eor:
            break
    return named_cell


def _cell_by_row_and_header(sheet: SheetType, row_number: int, header_name: str):
    """Find and return a cell based on its `header_name` and `row_number`"""
    headers = sheet[FIRST_ROW]
    header = _find_cell_by_name(headers, header_name)
    if header is None:
        raise RuntimeError("Failed to find '{}' in '{}'!".format(header_name, headers))
    return sheet.range(row_number, header.column)


def _cell_by_column_and_header(sheet: SheetType, column_number: int, header_name: str):
    """Find and return a cell based on its `header_name` and `column_number`"""
    headers = sheet[FIRST_COLUMN]
    header = _find_cell_by_name(headers, header_name)
    if header is None:
        raise RuntimeError("Failed to find '{}' in '{}'!".format(header_name, headers))
    return sheet.range(header.row, column_number)


class ValueAndFormat:  # pylint: disable=too-few-public-methods
    """Store a value and allow custom cell formatting via inheritance"""

    def __init__(self, value):
        self.value = value

    @abstractmethod
    def format_cell_win32(self, cell: CellType):
        """The abstract cell formatter function
        WARNING: this makes the script Windows dependent!
        """


class NtpValueAndFormat(ValueAndFormat):  # pylint: disable=too-few-public-methods
    """National Team Player formatter"""

    def __init__(self):
        super(NtpValueAndFormat, self).__init__("IGEN!!!")

    @overrides
    def format_cell_win32(self, cell: CellType):
        """Apply the emblematic NTP formatting to the cell
        WARNING: this makes the script Windows dependent!
        """
        cell.api.Font.Bold = True
        nice_green = (0, 176, 80)
        cell.api.Font.Color = rgb_to_int(nice_green)


class ValueWithNormalFormat(ValueAndFormat):  # pylint: disable=too-few-public-methods
    """Normal format with no special colour or font or anything"""

    def __init__(self, value):
        super(ValueWithNormalFormat, self).__init__(value)

    @overrides
    def format_cell_win32(self, cell: CellType):
        """(Re-)set the format to the normal
        WARNING: this makes the script Windows dependent!
        """
        cell.api.Font.Bold = False
        black = (0, 0, 0)
        cell.api.Font.Color = rgb_to_int(black)


def _set_and_maybe_format_cell(cell: CellType, generic_value):
    """Set the `cell`'s value and also format it if `generic_value` is of type ValueAndFormat"""
    if isinstance(generic_value, ValueAndFormat):
        cell.value = generic_value.value
        generic_value.format_cell_win32(cell)
    else:
        cell.value = generic_value


def _update_row_based_on_map(sheet: SheetType, row_number: int, header_value_map: Dict) -> None:
    """Update a row in the sheet based on the provided mapping"""
    for (header, value) in header_value_map.items():
        cell = _cell_by_row_and_header(sheet, row_number, header)
        _set_and_maybe_format_cell(cell, value)


def _update_column_based_on_map(sheet: SheetType, column_number: int, header_value_map: Dict):
    """Update a column in the sheet based on the provided mapping"""
    for (header, value) in header_value_map.items():
        cell = _cell_by_column_and_header(sheet, column_number, header)
        _set_and_maybe_format_cell(cell, value)


def _update_player(player: Player, sheet: SheetType, row_number: int) -> None:
    """Update the `player`'s info in the given `sheet` on the specified `row`"""
    is_ntp = player.ntp_status.is_national_team_player
    header_value_map = {
        "Kor (év)": player.age.years,
        "Kor (nap)": player.age.days,
        "TSI": player.tsi,
        "Válogatott?": NtpValueAndFormat() if is_ntp else ValueWithNormalFormat("Nem"),
        "Forma": str(player.form),
        "Erőnlét": str(player.stamina),
        "Eladási alapár": player.sell_base_price,
    }
    _update_row_based_on_map(sheet, row_number, header_value_map)


def _date_with_row(last_cell_with_value: CellType):
    """Return a DateWithRow with "date" and "row" fields"""
    date_of_last_update = last_cell_with_value.options(dates=date).value
    row_number = last_cell_with_value.row
    return namedtuple("DateWithRow", "date row")(date_of_last_update, row_number)


def _check_and_try_fixing_date_of_last_update(last_cell_with_value: CellType) -> date:
    """Check if it's sensible and convert to date if it's a string
    If it does not make sense (e.g. the value is None) -> RuntimeError
    If it's neither a date nor a string -> ValueError
    """
    last_update = _date_with_row(last_cell_with_value)
    if last_update.date is None:
        raise RuntimeError("Failed to find the date of last update on row {}"
                           .format(last_update.row))

    if isinstance(last_update.date, date):
        date_value = last_update.date
    else:
        if isinstance(last_update.date, str):
            date_value = datetime.strptime(last_update.date, "%d/%m/%Y")
        else:
            raise ValueError("Expected date and not '{}'".format(type(last_update.date)))

    return date_value


def _get_row_by_number(sheet: SheetType, row_number: int) -> RowType:
    """Return the row (aka range) of the sheet for row_number:row_number"""
    return sheet.range("{row}:{row}".format(row=row_number))


def _get_column_by_number(sheet: SheetType, column_number: int) -> ColumnType:
    """Return the column (aka range) of the sheet for column_number:column_number"""
    column_index = column_number - 1
    _ensure_valid_index(column_index)
    return sheet[:, column_index]


def _get_todays_row(sheet: SheetType, last_cell_with_value: CellType, today: date) -> RowType:
    """Get today's row which we might need to create as a copy of the previous
    or just return it if it exists already.
    """
    date_of_last_update = last_cell_with_value.options(dates=date).value
    row_number = last_cell_with_value.row
    if date_of_last_update == today:
        todays_row = _get_row_by_number(sheet, row_number)
    else:
        previous_row = _get_row_by_number(sheet, row_number)
        this_row = previous_row.row + 1
        todays_row = _get_row_by_number(sheet, this_row)
        previous_row.copy(destination=todays_row)
        todays_row[0].value = today
    return todays_row


@contextlib.contextmanager
def _run_if_not_read_only(read_only: bool):
    """Only yield if we are not in `read_only` mode"""
    if read_only:
        print("skipped (read-only mode)")
    else:
        yield
        print("done")


def _is_formula_cell(cell: CellType) -> bool:
    """Return whether the specified cell contains a formula"""
    return bool(re.search("^=", cell.formula))


def _update_central_player_sheet(player: Player, sheet: SheetType) -> None:
    """Find the player in the sheet and update its second column or add to the
    left of its next player sheet (or MAYDO just to the beginning if that's missing)
    and update its first column
    """
    header_value_map = {
        "Kor (év)": player.age.years,
        "Kor (nap)": player.age.days,
        "TSI": player.tsi,
        "Csillagok": player.extra.stars,
        "Játékszervezés": player.extra.skillz.playmaking,
        "Szélsőjáték": player.extra.skillz.winger,
        "Átadás": player.extra.skillz.passing,
        "Gólszerzés": player.extra.skillz.scoring,
    }

    headers = sheet[FIRST_ROW]
    name = player.name
    cell = _find_cell_by_name(headers, name)
    reserve_price_header = "Kikiáltási ár"
    if cell is None:
        next_player_name = getattr(player, NEXT_PLAYER_NAME_ATTRIBUTE, "Dunno")
        if next_player_name == "Dunno":
            raise ValueError("Failed to find '{}' in '{}'!".format(name, headers))
        if next_player_name is None:  # the first player ever
            raise NotImplementedError("Add manually")  # MAYDO automate when everything else works
        # there is at least one more player
        cell = _find_cell_by_name(headers, next_player_name)
        if cell is None:
            raise ValueError("Failed to find '{}' in '{}'!".format(next_player_name, headers))
        next_player_range = _get_column_by_number(sheet, cell.column)
        next_player_range = next_player_range.resize(column_size=2)
        next_player_range.insert()
        new_player_range = _get_column_by_number(sheet, next_player_range.column - 2)
        new_player_range = new_player_range.resize(column_size=2)
        next_player_range.copy(new_player_range)
        for maybe_outdated_cell in new_player_range:
            if _is_formula_cell(maybe_outdated_cell):
                break
            maybe_outdated_cell.value = None
        update_column = new_player_range.column
        header_value_map.update({
            "Név": player.name,
            "Forrás": player.extra.source.value,
            "Spec": player.extra.skillz.speciality.value,
            reserve_price_header: player.extra.reserve_price,
            "Végső ár": player.extra.buy_price,
            "Érkezés -> Távozás": player.extra.arrival,
        })
    else:
        update_column = cell.column + 1
        header_value_map.update({
            reserve_price_header: player.sell_base_price,
        })
    _update_column_based_on_map(sheet, update_column, header_value_map)


def _sheets_of_sheet(sheet: SheetType) -> SheetsType:
    """Return the sheets that this sheet is part of"""
    return sheet.book.sheets


def _ensure_valid_index(index: int):
    """Raise IndexError if the index is smaller than zero"""
    if index < 0:
        raise IndexError("'{}' supposed to be 1-based...")


def _sheet_index(sheet: SheetType) -> int:
    """Return the zero-based sheet index"""
    zero_based_index = sheet.index - 1
    _ensure_valid_index(zero_based_index)
    return zero_based_index


def _offset_sheet(sheet: SheetType, offset: int) -> SheetType:
    """Return the sheet on the offset or None if there's no sheet there"""
    try:
        zero_based_index = _sheet_index(sheet)
        requested_sheet = _sheets_of_sheet(sheet)[zero_based_index + offset]
    except IndexError:
        requested_sheet = None
    return requested_sheet


def _copy_sheet_win32(
        source: SheetType, before_this_sheet: SheetType, name: str) -> SheetType:
    """Create a copy of a sheet before another sheet
    WARNING: this makes the script Windows dependent!
    """
    source.api.Copy(Before=before_this_sheet.api)
    new_sheet = _offset_sheet(before_this_sheet, offset=-1)
    new_sheet.name = name
    return new_sheet


def _find_sheet_by_regex(regex: str, sheets: SheetsType) -> SheetType:
    """Find a sheet by the regex searched in sheet names or return None"""
    found_sheet = None
    for sheet in sheets:
        if re.search(regex, sheet.name):
            found_sheet = sheet
            break
    return found_sheet


def _player_name_to_the_right(sheet: SheetType) -> str:
    """Return the player's name arrived before this player or None
    Players are stored in arrival order
    """
    next_sheet = _offset_sheet(sheet, offset=1)
    raw_player_name = next_sheet.name
    if SOLD_PLAYER_MARKER in raw_player_name:
        player_name = raw_player_name.replace(SOLD_PLAYER_MARKER, "")
    elif NEW_PLAYER_MARKER in raw_player_name:
        player_name = None
    else:
        player_name = raw_player_name
    return player_name


class Excel:
    """Excel-based HT persistence layer"""

    CENTRAL_PLAYER_SHEET = "Nevelde"

    def __init__(self, file: str, read_only: bool):
        if not os.path.isfile(file):
            raise ValueError("Cannot find '{}'".format(file))
        self._file = file
        self._read_only = read_only
        self._workbook = None
        self._central_player_sheet = None
        self._player_sheets = {}
        self._monitored_players_names = []
        self._today = date.today()

    def __enter__(self):
        """Open self._file
        If any step fail, an exception is raised so if we managed to enter,
        the file is ready to read/write (or just read in read-only mode).
        In case of an exception, __exit__ will run, so don't worry.
        """
        try:
            self._workbook = xl.Book(self._file, read_only=self._read_only)
            print("Opened '{}' (read-only mode: {})".format(self._file, self._read_only))
            self._central_player_sheet = self._sheets()[self.CENTRAL_PLAYER_SHEET]
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Save the workbook to file, if there was no exception, and we are not in read-only mode
        When __exit__ returns True, any exception passed to it is swallowed.
        When __exit__ returns False, the exception is re-raised.
        """
        there_was_no_exception = exc_type is None

        if self._read_only:
            print("Nothing to save as we're in read-only mode. Bye!")
        else:
            if there_was_no_exception:
                if self._workbook is not None:
                    print("Saving '{}'...".format(self._file))
            else:
                print("One or more exceptions have invalidated the update!")

        success = there_was_no_exception

        return success

    def _sheets(self) -> SheetsType:
        """Return the list of existing sheets"""
        if self._workbook is None:
            raise RuntimeError("Tried accessing sheets when we don't even have a workbook!")
        return self._workbook.sheets

    def monitored_players_names(self) -> List[str]:
        """Return the list of the monitored players' names (read-only operation)"""
        print("excel -> player list... ", end="")

        for sheet in self._sheets():
            if _is_player_sheet(sheet):
                player_is_active = not any(
                    marker in sheet.name
                    for marker in (SOLD_PLAYER_MARKER, NEW_PLAYER_MARKER)
                )
                if player_is_active:
                    self._player_sheets[sheet.name] = sheet
                    self._monitored_players_names.append(sheet.name)

        print("done")
        return self._monitored_players_names

    def update_team(self, team: Team) -> None:
        """Find the right place in the spreadsheet and update it with team's
        info (unless we're in read-only mode)"""
        print("Team -> excel... ", end="")

        with _run_if_not_read_only(self._read_only):
            team_sheet = self._sheets()["Csapat"]
            range_size = 50
            updated_total = False
            updated_board_reserves = False
            for row in range(1, range_size):
                for col in range(1, range_size):
                    cell = team_sheet.range((row, col))

                    updated = _update_value_next_to_named_cell(cell, "Összesen",
                                                               team.finance.total)
                    updated_total = updated_total or updated

                    updated = _update_value_next_to_named_cell(cell, "Az igazgatóság tartaléka",
                                                               team.finance.board_reserves)
                    updated_board_reserves = updated_board_reserves or updated

                    if updated_total and updated_board_reserves:
                        break  # we've updated everything we wanted
            team_sheet["A1"].value = self._today

    def update_player(self, player: Player) -> None:
        """Store the `player`'s updated info on his tab in the spreadsheet
        (unless we're in read-only mode)
        """
        print("### Update '{}' -> excel... ".format(player.name), end="")

        with _run_if_not_read_only(self._read_only):
            sheet = self._player_sheets[player.name]

            last_cell_with_value = sheet["A:A"].end("down")

            _check_and_try_fixing_date_of_last_update(last_cell_with_value)

            todays_row = _get_todays_row(sheet, last_cell_with_value, self._today)

            _update_player(player, sheet, todays_row.row)

            _update_central_player_sheet(player, self._central_player_sheet)

    def add_player(self, player: Player) -> None:
        """Add a new player to excel (unless we're in read-only mode)"""
        print("### Add '{}' -> excel... ".format(player.name), end="")

        with _run_if_not_read_only(self._read_only):
            name = player.name
            player_sheet = None
            for sheet in self._sheets():
                if name == sheet.name:
                    player_sheet = sheet
                    break

            if player_sheet is None:
                latest_player_sheet = _offset_sheet(self._central_player_sheet, offset=1)
                new_player_sheet = _find_sheet_by_regex(NEW_PLAYER_MARKER, self._sheets())
                player_sheet = _copy_sheet_win32(new_player_sheet, latest_player_sheet, name)
                arrival_row = player_sheet[FIRST_DATA_ROW]
                row_number = arrival_row.row
                header_value_map = {
                    "Dátum": player.extra.arrival,
                    "Vételi ár": player.extra.buy_price,
                }
                _update_row_based_on_map(player_sheet, row_number, header_value_map)
                _update_player(player, player_sheet, row_number)  # to fill in the common columns

            next_player_name = _player_name_to_the_right(player_sheet)
            setattr(player, NEXT_PLAYER_NAME_ATTRIBUTE, next_player_name)
            _update_central_player_sheet(player, self._central_player_sheet)
