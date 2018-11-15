#!/usr/bin/env python3

### BEGIN IMPORTS ###

import math
import curses
import colorsys
import traceback

import utils

### END IMPORTS ###

### BEGIN GLOBAL VARIABLES ###

line = 0 # The number of lines since the beginning of the screen

### END GLOBAL VARIABLES ###

### BEGIN GAME STEPS ###

def input_guess(screen, code, color_count, guess):
    global line

    selected = 0
    utils.print_code(screen, utils.PREFIX, guess, selected)
    alpha = 0

    key = screen.getkey()
    while key != "\n": # Confirm the guess when the user pressed the enter key
        if key == "KEY_UP": # Up arrow rolls back the selected color by 1
            guess[selected] = (guess[selected] - 1) % color_count
            alpha = (alpha + 1) * int(alpha < 2)

        elif key == "KEY_DOWN" or key == "\t": # Down arrow/tab increments the selected color by 1
            guess[selected] = (guess[selected] + 1) % color_count
            alpha = (alpha + 1) * int(alpha in [2, 3])

        elif key == "KEY_LEFT": # Left arrow moves the selected color by 1 towards the left, and goes back all the way to the right when it reaches the side
            selected = (selected - 1) % len(code)
            alpha = (alpha + 1) * int(alpha in [4, 6])

        elif key == "KEY_RIGHT": # Same for the right arrow but in the other direction
            selected = (selected + 1) % len(code)
            alpha = (alpha + 1) * int(alpha in [5, 7])

        elif key == "a" or key == "A":
            alpha = (alpha + 1) * int(alpha == 9)

        elif key == "b" or key == "B":
            alpha = (alpha + 1) * int(alpha == 8)

        else:
            alpha = 0

        if alpha == 10:
            for i in range(len(code)):
                guess[i] = code[i]
                utils.print_code(screen, utils.PREFIX, guess, i)
                screen.refresh()
                curses.napms(100)
            curses.napms(400)
            break

        utils.print_code(screen, utils.PREFIX, guess, selected) # Update the guess displayed after each key press
        key = screen.getkey()

    utils.print_code(screen, utils.PREFIX, guess, -1) # Print the final guess without the dot on the selected color because it's useless once the color is confirmed
    line += 1
    screen.move(line, 0) # Move to the next time because the current guess has been confirmed

    return guess

def play_game(screen, color_count, max_attempts, code, attempts):
    global line

    if utils.DEBUG: # If we're debugging and not in an Online Ranked Game, print the code at the beginning to be able to test without playing for real
        utils.print_code(screen, "Psst... The correct code is:", code, -1)
        line += 1
        screen.move(line, 0)

    game_score = 0

    if len(attempts) > max_attempts:
        attempts = attempts[:max_attempts]

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
            screen.addstr("You cracked the code! Score: {}\n\r".format(game_score)) # Print a nice message for the user to know he got it right and show his score
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
    else:
        if attempts:
            guess = attempts[-1].copy() # We take the last attempt as starting point for the next guess if there is one
        else:
            guess = [0] * len(code) # Otherwise, the user's default guess will be only red pins (it could be any color, but the 0-th color is easier and always exists)

        for attempt in range(len(attempts), max_attempts): # Limits the number of attempts to the chosen amount
            guess = input_guess(screen, code, color_count, guess)
            attempts.append(guess.copy())

            perfect, partial = utils.compare_codes(guess, code) # Compare the guessed code with the real code

            if perfect == len(code): # If all the pins are perfect, that means the guessed code is the right one
                screen.move(line - 1, len(utils.PREFIX) + 1 + (len(code) + 1) * 2)
                screen.addstr("Correct!\n\r") # Print "correct" next to the last guessed line
                screen.move(line, 0)

                game_score = max_attempts - attempt # His score is the number of attempts left
                screen.addstr("You cracked the code! Score: {}\n\r".format(game_score)) # Print a nice message for the user to know he got it right and show his score
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

        else: # If we reached the maximum number of attempts without quitting the loop, it means the user failed to guess the code and he lost
            utils.print_code(screen, "You failed! The code was:", code, -1)
            line += 1
            screen.move(line, 0)

    screen.refresh() # Update the screen before going to sleep, or it would "freeze" before updating, not showing the final text before resetting
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

            token = utils.encode_token(0, score, games, color_count, max_attempts, code, attempts)
            return token

        if game_score > 0:
            score += game_score # If the user won this game, we increment his score and the number of (consecutive) games he played
            games += 1
        else:
            while int((int(math.log(min(max(score, 1 << 1), 1 << 6), 2) * 1E3) << 6) / 2E3) == 43 * 4:
                screen.clear()
                screen.addstr("".join(map(lambda x: chr((ord(x) - 1) % 0xFF), "Dbmdvmbujoh!Uif!Botxfs!up!Mjgf-!uif!Vojwfstf!boe!Fwfszuijoh-!qmfbtf!xbju!8/6!njmmjpo!zfbst///")))
                screen.refresh()
                score = (score | (1 << 1) | (1 << 3) | (1 << 5)) & ~21

            score, games = 0, 0 # If he lost, we reset his score and the number of (consecutive) games

### END PROGRAM CORE ###

if __name__ == "__main__":
    main()
