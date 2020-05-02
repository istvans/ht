# coding=utf-8
"""Automate my hattrick player status monitoring"""
import argparse
import sys
import traceback

from excel import Excel
from hattrick import Hattrick


def main():
    """parse args and perform the automation"""
    parser = argparse.ArgumentParser(
        description="Let me help you with that repetitive stuff..."
    )
    parser.add_argument("-s", "--spreadsheet", help="the spreadsheet to be used as our database")
    parser.add_argument("-u", "--user", required=False, help="the hattrick user")
    parser.add_argument("-p", "--password", required=False, help="the hattrick password")
    parser.add_argument("-P", "--pause", required=False, help="pause the script at the end",
                        action='store_true')
    parser.add_argument("-c", "--currency", required=False, help="the currency HT uses",
                        default="eFt")
    args = parser.parse_args()

    try:
        ht = Hattrick(args.currency, args.user, args.password)  # pylint: disable=invalid-name
        xl = Excel(args.spreadsheet)  # pylint: disable=invalid-name
        with ht, xl:
            team = ht.download_team()
            print(team)
            xl.update_team(team)

            players_list_page = ht.download_player_list_page()  # only download once
            for name in xl.monitored_players_names():
                player = ht.download_player_by_name(name, players_list_page)
                print(player)
                xl.update_player(player)
    finally:
        if args.pause:
            (exc_type, exc, trace) = sys.exc_info()
            if exc is not None:
                traceback.print_exception(exc_type, exc, trace)
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()
