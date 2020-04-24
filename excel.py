# coding=utf-8
"""The excel persistence module"""
from datetime import date
import os.path
import sys
import xlwings as xl

from data import Player, Team


def _is_player_sheet(sheet):
    """Return whether the specified sheet is a player sheet"""
    return sheet["A1"].value == "Dátum"


def _update_value_next_to_named_range(cell, name, value):
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


class Excel:
    """Excel-based HT database management"""

    def __init__(self, file):
        if not os.path.isfile(file):
            raise ValueError("Cannot find '{}'".format(file))
        self._file = file
        self._workbook = None
        self._player_sheets = {}
        self._monitored_players_names = []

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

        return self._monitored_players_names

    def update_team(self, team: Team):
        """Find the right place in the spreadsheet and update it with team's
        info"""
        team_sheet = self._workbook.sheets["Csapat"]
        range_size = 50
        updated_total = False
        updated_board_reserves = False
        for row in range(1, range_size):
            for col in range(1, range_size):
                cell = team_sheet.range((row, col))

                updated = _update_value_next_to_named_range(cell, "Összesen",
                                                            team.finance.total)
                updated_total = updated_total or updated

                updated = _update_value_next_to_named_range(cell, "Az igazgatóság tartaléka",
                                                            team.finance.board_reserves)
                updated_board_reserves = updated_board_reserves or updated

                if updated_total and updated_board_reserves:
                    break  # we've updated everything we wanted
        team_sheet["A1"].value = date.today()

    def update_player(self, player: Player):
        """Store the `player`'s updated info on his tab in the spreadsheet"""
        sheet = self._player_sheets[player.name]
        last_cell_with_value = sheet["A:A"].end("down")
        today = date.today().strftime("%d/%m/%Y")
        if last_cell_with_value.value == today:
            new_row = last_cell_with_value.row
            new_row = sheet.range("{row}:{row}".format(row=new_row))
        else:
            old_row = last_cell_with_value.row
            old_row = sheet.range("{row}:{row}".format(row=old_row))
            new_row = last_cell_with_value.row + 1
            new_row = sheet.range("{row}:{row}".format(row=new_row))
            old_row.copy(destination=new_row)
            new_row[0].value = today
        new_row[2].value = player.age.years
        new_row[3].value = player.age.days
        new_row[5].value = player.tsi
        is_ntp = player.ntp_status.is_national_team_player
        new_row[6].value = "IGEN!!!" if is_ntp else "Nem"
        new_row[7].value = player.sell_base_price
