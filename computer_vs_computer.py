#!/usr/bin/env python3

### BEGIN IMPORTS ###

import re
import sys
import zlib
import base64
import curses
import random
import socket
import colorsys
import traceback
import itertools

import utils

### END IMPORTS ###

### BEGIN GLOBAL VARIABLES ###

line = 0 # The number of lines since the beginning of the screen

### END GLOBAL VARIABLES ###

### BEGIN GAME STEPS ###

def input_guess(screen, code_length, color_count, possibilities):
    global line

    screen.refresh()
    if not utils.DEBUG:
        curses.napms(250)

    # TODO: Animation?

    if len(possibilities) == color_count ** code_length:
        guess = [0] * ((code_length + 1) // 2) + [1] * (code_length // 2)
    else:
        guess = random.choice(possibilities)

    possibilities.remove(guess)

    utils.print_code(screen, utils.PREFIX, guess, -1)
    line += 1
    screen.move(line, 0)

    return guess

def play_game(screen, color_count, max_attempts, code, attempts):
    global line

    utils.print_code(screen, "The computer will try to guess the following code:", code, -1)
    line += 1
    screen.move(line, 0)

    game_score = 0

    if len(attempts) > max_attempts:
        attempts = attempts[:max_attempts]

    screen.refresh()
    possibilities = list(map(list, itertools.product(range(color_count), repeat=len(code))))
    total_possibilities = len(possibilities)

    for i, attempt in enumerate(attempts):
        utils.print_code(screen, utils.PREFIX, attempt, -1)
        line += 1
        screen.move(line, 0)

        perfect, partial = utils.compare_codes(attempt, code) # Compare the current attempt with the real code

        if perfect == len(code): # If all the pins are perfect, that means the guessed code was the right one
            screen.move(line - 1, len(utils.PREFIX) + 1 + (len(code) + 1) * 2)
            screen.addstr("Correct!\n\r") # Print "correct" next to the last guessed line
            screen.move(line, 0)

            game_score = max_attempts - i # His score is the number of attempts left
            screen.addstr("The computer cracked the code! Score: {}\n\r".format(game_score)) # Print a nice message for the user to know he got it right and show his score
            line += 1
            break
        else:
            # Show the perfect and partial pins next to the guess
            offset = len(utils.PREFIX) + 1 + (len(code) + 1) * 2
            screen.addstr(line - 1, offset, "Result:")
            offset += len("Result:") + 1
            for i in range(perfect + partial):
                attr = curses.color_pair(2 if i < perfect else 1)
                screen.addstr(line - 1, offset + i * 2, " ", attr)
            screen.move(line, 0)

            screen.refresh()
            # Remove all the remaining possibilities that don't match the new conditions
            possibilities = list(filter(lambda possibility: utils.compare_codes(attempt, possibility) == (perfect, partial), possibilities))
    else:
        for attempt in range(len(attempts), max_attempts): # Limits the number of attempts to the chosen amount
            guess = input_guess(screen, len(code), color_count, possibilities)
            attempts.append(guess.copy())

            perfect, partial = utils.compare_codes(guess, code) # Compare the current attempt with the real code

            if perfect == len(code): # If all the pins are perfect, that means the guessed code is the right one
                screen.move(line - 1, len(utils.PREFIX) + 1 + (len(code) + 1) * 2)
                screen.addstr("Correct!\n\r") # Print "correct" next to the last guessed line
                screen.move(line, 0)

                game_score = max_attempts - attempt # His score is the number of attempts left
                screen.addstr("The computer cracked the code! Score: {}\n\r".format(game_score)) # Print a nice message for the user to know he got it right and show his score
                line += 1
                break
            else:
                # Show the perfect and partial pins next to the guess
                offset = len(utils.PREFIX) + 1 + (len(code) + 1) * 2
                screen.addstr(line - 1, offset, "Result:")
                offset += len("Result:") + 1
                for i in range(perfect + partial):
                    attr = curses.color_pair(2 if i < perfect else 1)
                    screen.addstr(line - 1, offset + i * 2, " ", attr)
                screen.move(line, 0)
                screen.refresh()
                # Remove all the remaining possibilities that don't match the new conditions
                possibilities = list(filter(lambda possibility: utils.compare_codes(guess, possibility) == (perfect, partial), possibilities))

        else: # If we reached the maximum number of attempts without quitting the loop, it means the user failed to guess the code and he lost
            screen.addstr("The computer failed! Progress: {}%".format(100 - int(len(possibilities) / total_possibilities * 100)))
            line += 1
            screen.move(line, 0)

    screen.refresh() # Update the screen before going to sleep, or it would "freeze" before updating, not showing the final text before resetting
    if not utils.DEBUG:
        curses.napms(3000)

    return game_score

### END GAME STEPS ###

### BEGIN PROGRAM CORE ###

def main(screen=None, color_count=None, max_attempts=None, score=0, games=0, code=None, attempts=None):
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

    code_length = len(code) if code is not None else utils.DEFAULT_CODE_LENGTH

    if color_count is None or color_count <= 0:
        color_count = utils.DEFAULT_COLOR_COUNT

    if max_attempts is None or max_attempts <= 0:
        max_attempts = utils.DEFAULT_MAX_ATTEMPTS

    curses.init_pair(0, -1, utils.find_nearest_color(0, 0, 0))
    curses.init_pair(1, -1, utils.find_nearest_color(1, 1, 1))
    for color in range(2, color_count + 2): # Initialize all the colors we will need, generating them around the color wheel
        # Each color is uniformly spread around the color spectrum, keeping its saturation and value to the max (excludes black and white)
        h, s, v = (color - 2) / color_count, 1.0, 1.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v) # Convert the color from HSV (easier to generate) to RGB (easier to manipulate)

        # Because we can't use custom colors in most terminals, we find the closest available one and pair it to the color's id with a white foreground
        curses.init_pair(color, -1, utils.find_nearest_color(r, g, b))

    global line

    while True: # Play an infinite number of games until the user quits the program (with Ctrl+C)
        screen.clear()
        line = 0

        try:
            if code is None:
                code = utils.generate_code(code_length, color_count) # Generate a random code to "play against the computer"
            if attempts is None:
                attempts = []

            game_score = play_game(screen, color_count, max_attempts, code, attempts)
            code, attempts = None, None # Reset the code and the attempts to make the next game independent
        except KeyboardInterrupt:
            screen.move(line, 0)
            screen.clrtoeol() # Clear the current line, just in case some text was there

            if games > 0:
                screen.addstr("Average score: {}\n\r".format(score / games))
                screen.refresh()
                curses.napms(3000)

            token = utils.encode_token(2, score, games, color_count, max_attempts, code, attempts)
            return token

        if game_score > 0:
            score += game_score # If the computer won this game, we increment his score and the number of (consecutive) games he played
            games += 1

        if game_score <= 0:
            score, games = 0, 0 # If he lost, we reset his score and the number of (consecutive) games

### END PROGRAM CORE ###

if __name__ == "__main__":
    main()
