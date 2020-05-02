# coding=utf-8
"""The excel persistence module"""
from datetime import date, datetime
import os.path
import sys
import xlwings as xl

from data import Player, Team


def _is_player_sheet(sheet):
    """Return whether the specified sheet is a player sheet"""
    return sheet["A1"].value == "Dátum"


def _update_value_next_to_named_cell(cell, name, value):
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


def _cell_by_row_and_header(sheet, row_number, header_name):
    """Find and return a cell based on its `header_name` and `row_number`"""
    headers = sheet["1:1"]
    column_number = None
    for header in headers:
        if header.value is None:
            break
        if header.value == header_name:
            column_number = header.column
            break
    if column_number is None:
        raise RuntimeError("Failed to find '{}' in '{}'!".format(header_name, headers))

    return sheet.range(row_number, column_number)


def _update_row_based_on_map(sheet, row_number, header_value_map):
    """Update a row in the sheet based on the provided mapping"""
    for (header, value) in header_value_map.items():
        _cell_by_row_and_header(sheet, row_number, header).value = value


class Excel:
    """Excel-based HT database management"""

    def __init__(self, file):
        if not os.path.isfile(file):
            raise ValueError("Cannot find '{}'".format(file))
        self._file = file
        self._workbook = None
        self._player_sheets = {}
        self._monitored_players_names = []
        self._today = date.today()

    def __enter__(self):
        """Open self._file
        If any step fail, an exception is raised so if we managed to enter,
        the file is ready to read/write.
        In case of an exception, __exit__ will run, so don't worry.
        """
        try:
            self._workbook = xl.Book(self._file)
            print("Opened '{}'".format(self._file))
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Save the workbook to file, if there was no exception
        When __exit__ returns True, any exception passed to it is swallowed.
        When __exit__ returns False, the exception is re-raised.
        """
        if exc_type is None:
            if self._workbook is not None:
                print("Saving '{}'...".format(self._file))
                self._workbook.save()
            success = True
        else:
            print("One or more exceptions have invalidated the update!")
            success = False

        return success

    def monitored_players_names(self):
        """Return the list of the monitored players' names"""
        print("excel -> player list... ", end="")
        for sheet in self._workbook.sheets:
            if _is_player_sheet(sheet):
                sold_player_marker = '$'
                new_player_marker = '@'
                player_is_active = not any(
                    marker in sheet.name
                    for marker in (sold_player_marker, new_player_marker)
                )
                if player_is_active:
                    self._player_sheets[sheet.name] = sheet
                    self._monitored_players_names.append(sheet.name)
        print("done")
        return self._monitored_players_names

    def update_team(self, team: Team):
        """Find the right place in the spreadsheet and update it with team's
        info"""
        print("Team -> excel... ", end="")
        team_sheet = self._workbook.sheets["Csapat"]
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
        print("done")

    def update_player(self, player: Player):
        """Store the `player`'s updated info on his tab in the spreadsheet"""
        print("Player -> excel... ", end="")
        sheet = self._player_sheets[player.name]

        last_cell_with_value = sheet["A:A"].end("down")
        date_of_last_update = last_cell_with_value.options(dates=date).value
        row_number = last_cell_with_value.row

        if date_of_last_update is None:
            raise RuntimeError("Failed to find the date of last update on row {}"
                               .format(row_number))
        if not isinstance(date_of_last_update, date):
            if isinstance(date_of_last_update, str):
                date_value = datetime.strptime(date_of_last_update, "%d/%m/%Y")
                date_of_last_update = date_value
            else:
                raise ValueError("Expected date and not '{}'".format(type(date_of_last_update)))

        if date_of_last_update == self._today:
            current_row = sheet.range("{row}:{row}".format(row=row_number))
        else:
            old_row = sheet.range("{row}:{row}".format(row=row_number))
            current_row = row_number + 1
            current_row = sheet.range("{row}:{row}".format(row=current_row))
            old_row.copy(destination=current_row)
            current_row[0].value = self._today

        is_ntp = player.ntp_status.is_national_team_player
        header_value_map = {
            "Kor (év)": player.age.years,
            "Kor (nap)": player.age.days,
            "TSI": player.tsi,
            "Válogatott?": "IGEN!!!" if is_ntp else "Nem",
            "Eladási alapár": player.sell_base_price,
        }

        row_number = current_row.row
        _update_row_based_on_map(sheet, row_number, header_value_map)
        print("done")
