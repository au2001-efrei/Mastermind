#!/usr/bin/env python3

### BEGIN IMPORTS ###

import re
import sys
import curses
import traceback

import utils
import singleplayer
import online_ranked
import computer_vs_computer

### END IMPORTS ###

### BEGIN GAME STEPS ###

def select_gamemode(screen):
    def print_menu(selected, code_length, color_count, max_attempts):
        screen.clear() # Clear the screen, just in case some text was there (usually clears the previous print_menu output)

        screen.addstr("Welcome to Mastermind! Please select a gamemode:\n\r") # Print an introductory text

        screen.addstr("•" if selected == 0 else " ") # Add a white dot on the left if "Local Singleplayer" is the currently selected gamemode
        screen.addstr(" Local Singleplayer\n\r")

        screen.addstr("•" if selected == 1 else " ") # Add a white dot on the left if "Online Ranked Game" is the currently selected gamemode
        screen.addstr(" Online Ranked Game\n\r")

        screen.addstr("•" if selected == 2 else " ") # Add a white dot on the left if "Automatic Computer vs Computer" is the currently selected gamemode
        screen.addstr(" Automatic Computer vs Computer\n\r")

        screen.addstr("\n\r")
        screen.addstr("You can also customize the following settings:\n\r") # Skip a line and print some text before the settings

        code_length_str = str(code_length).center(len(str(0xFFFF))) # Convert the code length to a string and center it with spaces (max. 65,536 code length)
        screen.addstr(("< {} >" if selected == 3 else "  {}  ").format(code_length_str)) # Add left and right arrows if the code length is the currently selected setting
        screen.addstr(" Code Length\n\r")

        color_count_str = str(color_count).center(len(str(0xFFFF))) # Convert the color count to a string and center it with spaces (max. 65,536 colors)
        screen.addstr(("< {} >" if selected == 4 else "  {}  ").format(color_count_str)) # Add left and right arrows if the color count is the currently selected setting
        screen.addstr(" Number of Colors\n\r")

        max_attempts_str = str(max_attempts).center(len(str(0xFFFF))) # Convert the max attempts to a string and center it with spaces (max. 65,536 attempts)
        screen.addstr(("< {} >" if selected == 5 else "  {}  ").format(max_attempts_str)) # Add left and right arrows if the max attempts is the currently selected setting
        screen.addstr(" Maximum Attempts\n\r")

    selected = 0
    code_length, color_count, max_attempts = utils.DEFAULT_CODE_LENGTH, utils.DEFAULT_COLOR_COUNT, utils.DEFAULT_MAX_ATTEMPTS
    print_menu(selected, code_length, color_count, max_attempts)

    key = screen.getkey()
    while key != "\n" or not 0 <= selected <= 2: # Select the gamemode when the user pressed the enter key while on a valid gamemode (not a setting)
        if key == "KEY_UP": # Up arrow moves the selected gamemode/setting by 1 towards the top
            selected = (selected - 1) % 6

        elif key == "KEY_DOWN" or key == "\n" or key == "\t": # Down arrow/return/tab moves the selected gamemode/setting by 1 towards the bottom
            selected = (selected + 1) % 6

        elif key == "KEY_LEFT" and 3 <= selected <= 5: # Left arrow rolls back the selected setting by 1
            if selected == 3:
                code_length = (code_length - 1) % (2 ** 16) # (max. 65,536 code length)
            elif selected == 4:
                color_count = (color_count - 1) % (2 ** 16) # (max. 65,536 colors)
            elif selected == 5:
                max_attempts = (max_attempts - 1) % (2 ** 16) # (max. 65,536 attempts)

        elif key == "KEY_RIGHT" and 3 <= selected <= 5: # Right arrow increments the selected setting by 1
            if selected == 3:
                code_length = (code_length + 1) % (2 ** 16) # (max. 65,536 code length)
            elif selected == 4:
                color_count = (color_count + 1) % (2 ** 16) # (max. 65,536 colors)
            elif selected == 5:
                max_attempts = (max_attempts + 1) % (2 ** 16) # (max. 65,536 attempts)

        print_menu(selected, code_length, color_count, max_attempts) # Update the menu after each key press
        key = screen.getkey()

    screen.clear() # Clear the menu after selecting a gamemode and before entering the game

    return selected, code_length, color_count, max_attempts

### END GAME STEPS ###

### BEGIN PROGRAM CORE ###

def main(screen=None):
    if screen is None:
        try:
            token = curses.wrapper(main) # Use curses to handle user input, screen clearing and simplify other display management tools

            if token is not None: # If the game has been interrupted and a token to resume was generated, show a message to inform the user
                print("This game has been interrupted. To resume, copy paste this token:", token)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            if utils.DEBUG:
                traceback.print_exc()
            else:
                print("Oops! An error occured:", e)
        return

    curses.start_color() # Enable curses' colors
    curses.use_default_colors()
    curses.curs_set(0) # Hide the cursor as we will use a custom way to show the selected color

    if len(sys.argv) > 1 and re.match("^[A-Za-z0-9+/]*=*$", sys.argv[1]): # If a (seemingly) valid token was provided, resume this game rather than starting a new one
        token = sys.argv[1]
        if len(token) % 4 > 0:
            token += "=" * (4 - len(token) % 4) # Fix Base64 padding by adding equal signs at the end of the token

        gamemode, score, games, color_count, max_attempts, code, attempts = utils.decode_token(token) # Get all the required information about the pending game from the token
        code_length = len(code)
    else:
        gamemode, code_length, color_count, max_attempts = select_gamemode(screen)
        score, games = 0, 0
        code, attempts = None, None

    if gamemode == 0:
        if code is None:
            code = utils.generate_code(code_length, color_count) # Generate a random code to "play against the computer"

        return singleplayer.main(screen, color_count, max_attempts, score, games, code, attempts)
    elif gamemode == 1:
        return online_ranked.main(screen, color_count, max_attempts, code_length)
    elif gamemode == 2:
        if code is None:
            code = utils.generate_code(code_length, color_count) # Generate a random code for the computer to guess

        return computer_vs_computer.main(screen, color_count, max_attempts, score, games, code, attempts)
    else:
        raise Exception("Unknown gamemode selected: {}".format(gamemode))

### END PROGRAM CORE ###

if __name__ == "__main__":
    main()
