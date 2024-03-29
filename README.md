# Mastermind

This was originally a school project carried out during the first year at [Efrei Paris](https://www.efrei.fr).\
The goal was to recreate the [Mastermind](https://en.wikipedia.org/wiki/Mastermind_(board_game)) board game in Python.\
User-interface was unrestricted. This implementation is command-line only, specifically using [ncurses](https://invisible-island.net/ncurses/).\
It has been greatly improved from the initial requested specifications. Some improvements are details under [Features](#features).

## Features

- Play locally against the computer
  - Interrupt games and resume them using a token; can be on the same computer or a different one
- Play online and save your record on a scoreboard
  - Enter a unique username to identify yourself
  - Custom game protocol implemented over TCP
  - Interrupt games and resume them automatically (based on IP address)
- Make the computer play automatically with an A.I.
  - Tool to benchmark the computer: ~4.63 tries on average, 8 maximum (4 pins and 6 colors)
- Several easter eggs hidden around the program

## Installation

- You will need to have Python 3.7.0 or later installed
- You will need to have the [curses](https://docs.python.org/3/library/curses.html) module installed

## Running

All the following commands assume your current working directory is the folder containing this README file.
To do that, run `cd path/to/folder`.

- To start the main program and obtain the menu, run `python3 mastermind.py`.
- To interrupt a game while it is running and get a token to resume it later, press `Ctrl + C`.
- To resume a pending game, run `python3 mastermind.py TOKEN` replacing `TOKEN` with the token obtained in the previous session.
- To instantly start a Singleplayer game without going through the menu, run `python3 singleplayer.py`.
- To instantly start an Online Ranked game without going through the menu, run `python3 online_ranked.py`.
- To instantly start a Computer vs Computer game without going through the menu, run `python3 computer_vs_computer.py`.

To play an Online Ranked game, you have to start the server first.
To do that, run `python3 server.py`.

If you run the server on a different machine, you have to edit the `utils.py` file on the Client machine to specify the IP address of the machine runnning it.

## TODO

- Add comments to `server.py`
- 5 more eastereggs
- Multiplayer gamemode (rotating player)
- Player vs. Player (local + online)
- Auto-discover servers/oponnents on the network or with a QR code and UPnP
- LAN/Online PvP tournaments
- Blockchain implementation rather than a centralized server!
- Real AI, using deep learning?
