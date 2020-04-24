# coding=utf-8
"""Automate my hattrick player status monitoring"""
import argparse

from excel import Excel
from hattrick import Hattrick


PARSER = argparse.ArgumentParser(
    description="Let me help you with that repetitive stuff..."
)
PARSER.add_argument("spreadsheet", help="the spreadsheet to be used as our database")
ARGS = PARSER.parse_args()

with Hattrick() as ht, Excel(ARGS.spreadsheet) as xl:
    TEAM = ht.download_team()
    print(TEAM)
    xl.update_team(TEAM)

    PLAYERS_LIST_PAGE = ht.download_player_list_page()  # only download once
    for name in xl.monitored_players_names():
        player = ht.download_player_by_name(name, PLAYERS_LIST_PAGE)
        print(player)
        xl.update_player(player)
