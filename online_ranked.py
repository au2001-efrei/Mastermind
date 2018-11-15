#!/usr/bin/env python3

### BEGIN IMPORTS ###

import curses
import socket
import colorsys
import traceback

import utils

### END IMPORTS ###

### BEGIN GLOBAL VARIABLES ###

score, games = 0, 0
line = 0 # The number of lines since the beginning of the screen

client_socket = None # TODO: Implement a packet exchange on top of the TCP socket

### END GLOBAL VARIABLES ###

### BEGIN GAME STEPS ###

def input_guess(screen, code_length, color_count, guess):
    global line

    selected = 0
    utils.print_code(screen, utils.PREFIX, guess, selected)

    key = screen.getkey()
    while key != "\n": # Confirm the guess when the user pressed the enter key
        if key == "KEY_UP": # Up arrow rolls back the selected color by 1
            guess[selected] = (guess[selected] - 1) % color_count

        elif key == "KEY_DOWN" or key == "\t": # Down arrow/tab increments the selected color by 1
            guess[selected] = (guess[selected] + 1) % color_count

        elif key == "KEY_LEFT": # Left arrow moves the selected color by 1 towards the left, and goes back all the way to the right when it reaches the side
            selected = (selected - 1) % code_length

        elif key == "KEY_RIGHT": # Same for the right arrow but in the other direction
            selected = (selected + 1) % code_length

        utils.print_code(screen, utils.PREFIX, guess, selected) # Update the guess displayed after each key press
        key = screen.getkey()

    utils.print_code(screen, utils.PREFIX, guess, -1) # Print the final guess without the dot on the selected color because it's useless once the color is confirmed
    line += 1
    screen.move(line, 0) # Move to the next time because the current guess has been confirmed

    return guess

def play_game(screen, color_count, max_attempts, code, attempts):
    global line, client_socket

    score = 0

    if len(attempts) > max_attempts:
        attempts = attempts[:max_attempts]

    for i, attempt in enumerate(attempts):
        utils.print_code(screen, utils.PREFIX, attempt, -1)
        line += 1
        screen.move(line, 0)

        answer_bytes = utils.receive_packet(client_socket) # We read the server's answer for the current attempt and find the corresponding perfect and partial pin counts
        if len(answer_bytes) == 2 and int.from_bytes(answer_bytes, "big") == 418:
            answer_bytes = utils.receive_packet(client_socket)

        perfect = int.from_bytes(answer_bytes[:2], "big")
        partial = int.from_bytes(answer_bytes[2:4], "big")

        if perfect == len(code): # If all the pins are perfect, that means the guessed code was the right one
            screen.move(line - 1, len(utils.PREFIX) + 1 + (len(code) + 1) * 2)
            screen.addstr("Correct!\n\r") # Print "correct" next to the last guessed line
            screen.move(line, 0)

            score = max_attempts - i # His score is the number of attempts left
            screen.addstr("You cracked the code! Score: {}\n\r".format(score)) # Print a nice message for the user to know he got it right and show his score
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
            guess = input_guess(screen, len(code), color_count, guess)
            attempts.append(guess.copy())

            guess_bytes = bytes() # While in an Online Ranked Game, instead of comparing the codes locally, we send the guess to the server

            # If guess is not the same size as code, cut it off or append zeros
            if len(guess) > len(code):
                guess = guess[:len(code)]
            elif len(guess) < len(code):
                guess += [0] * (len(code) - len(guess))

            for color in guess:
                # Encode guess' colors on 16 bits (max. 65535 colors)
                guess_bytes += (min(color, 0xFFFF) & 0xFFFF).to_bytes(2, "big")

            utils.send_packet(client_socket, guess_bytes)

            answer_bytes = utils.receive_packet(client_socket) # We then read the server's answer and find the corresponding perfect and partial pin counts
            if len(answer_bytes) == 2 and int.from_bytes(answer_bytes, "big") == 418:
                answer_bytes = utils.receive_packet(client_socket)

            perfect = int.from_bytes(answer_bytes[:2], "big")
            partial = int.from_bytes(answer_bytes[2:4], "big")

            if perfect == len(code): # If all the pins are perfect, that means the guessed code is the right one
                screen.move(line - 1, len(utils.PREFIX) + 1 + (len(code) + 1) * 2)
                screen.addstr("Correct!\n\r") # Print "correct" next to the last guessed line
                screen.move(line, 0)

                score = max_attempts - attempt # His score is the number of attempts left
                screen.addstr("You cracked the code! Score: {}\n\r".format(score)) # Print a nice message for the user to know he got it right and show his score
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
            token = utils.receive_packet(client_socket).decode("utf8")
            _, _, _, _, _, code, _ = utils.decode_token(token) # Retrieve the real code from the server once the player lost

            utils.print_code(screen, "You failed! The code was:", code, -1)
            line += 1
            screen.move(line, 0)

    screen.refresh() # Update the screen before going to sleep, or it would "freeze" before updating, not showing the final text before resetting
    curses.napms(3000)

    return score

def get_scoreboard(page_size, offset):
    global client_socket

    utils.send_packet(client_socket, "SB:{} {}".format(page_size, offset).encode("utf8"))
    answer_bytes = utils.receive_packet(client_socket)

    scoreboard = []

    j = 0
    for i in range(page_size):
        if len(answer_bytes) < j + 2:
            break

        username_length = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2

        if len(answer_bytes) < j + username_length + 20:
            break

        username = answer_bytes[j:j+username_length].decode("utf8")
        j += username_length

        normalized_score = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2
        games = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2
        total_attempts = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2

        color_count = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2
        code_length = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2
        max_attempts = int.from_bytes(answer_bytes[j:j+2], "big")
        j += 2

        timestamp = int.from_bytes(answer_bytes[j:j+8], "big") / 1000
        j += 8

        scoreboard.append((username, normalized_score, games, total_attempts, color_count, code_length, max_attempts, timestamp))

    return scoreboard

def display_scoreboard(screen):
    global client_socket

    page_size, offset = 100, 0
    scoreboard = get_scoreboard(page_size, offset)

    if not scoreboard:
        return

    key = None
    screen.keypad(False)
    while key is None or (key != "\n" and ord(key) != 27):
        screen.clear()
        screen.addstr("Current scoreboard:\n\r")
        for entry in scoreboard:
            screen.addstr("{}: {}\n\r".format(entry[0], entry[1]))
        screen.addstr("Press enter or escape to start a new game.\n\r")

        screen.refresh()
        key = screen.getkey()
    screen.keypad(True)

### END GAME STEPS ###

### BEGIN PROGRAM CORE ###

def main(screen=None, color_count=None, max_attempts=None, code_length=None):
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

    if color_count is None or color_count <= 0:
        color_count = utils.DEFAULT_COLOR_COUNT

    if max_attempts is None or max_attempts <= 0:
        max_attempts = utils.DEFAULT_MAX_ATTEMPTS

    if code_length is None or code_length <= 0:
        code_length = utils.DEFAULT_CODE_LENGTH

    global score, games

    score, games = 0, 0
    code, attempts = None, None
    # Create a token containing the settings requested by the user
    token = utils.encode_token(1, score, games, color_count, max_attempts, [0xFFFF] * code_length, [])

    global client_socket, line

    username = ""

    initialized, first = False, True
    while True: # Play an infinite number of games until the user quits the program (with Ctrl+C)
        if client_socket is None: # If the client isn't connected to the server yet, connect to it
            screen.clear()
            screen.addstr("Connecting to the server, please wait...\n\r")
            screen.refresh() # Refresh the screen, because the following code could block for a few seconds

            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((utils.SERVER_HOST, utils.SERVER_PORT)) # Connect to socket server
                client_socket.settimeout(2) # Let the server 2 seconds to understand our request and answer it, or disconnect
            except socket.error as e:
                screen.clear()
                raise Exception("Failed to connect to server. Please try again later.")

            # TODO: GDPR Prompt
            utils.send_packet(client_socket, "OK".encode("utf8"))

        while not initialized: # While the game hasn't fully been created and started on the server, don't start it locally
            try:
                status = int.from_bytes(utils.receive_packet(client_socket), "big")

                if status == 401 or status == 403: # Status 401: Unknown user; Status 403: Unknown user, username provided taken
                    username = ""
                    while not username:
                        screen.clear()
                        screen.addstr("Please enter a username which will represent you in the Online Ranked Games scoreboard.\n\r")
                        screen.addstr("WARNING: This username CAN NOT BE CHANGED and will be linked to your address. It must be UNIQUE.\n\r")
                        screen.addstr("\n\r")
                        screen.addstr("Username: \n\r")
                        if status == 403:
                            screen.addstr("Invalid username. Please try again.")
                        curses.curs_set(2)
                        curses.echo()
                        username = screen.getstr(3, 10).decode("utf8")
                        curses.noecho()
                        curses.curs_set(0)

                    screen.clear()
                    screen.addstr("Registering new user, please wait...\n\r")
                    screen.refresh()

                    utils.send_packet(client_socket, username.encode("utf8"))

                elif status == 204: # Status 204: Known user, no game started
                    if not username:
                        username = utils.receive_packet(client_socket).decode("utf8")

                    if not first:
                        display_scoreboard(screen)

                    screen.clear()
                    screen.addstr("Initializing new Online Ranked Game, please wait...\n\r")
                    screen.refresh()

                    utils.send_packet(client_socket, token.encode("utf8")) # Send the token containing all the settings requested by the user to the server

                elif status == 200: # Status 200: Known user, game pending
                    if not username:
                        username = utils.receive_packet(client_socket).decode("utf8")
                    token = utils.receive_packet(client_socket).decode("utf8")
                    # Get all the required information about the game from the server
                    _, score, games, color_count, max_attempts, code, attempts = utils.decode_token(token)
                    code_length = len(code)

                    curses.init_pair(0, -1, utils.find_nearest_color(0, 0, 0))
                    curses.init_pair(1, -1, utils.find_nearest_color(1, 1, 1))
                    for color in range(2, color_count + 2): # Initialize all the colors we will need, generating them around the color wheel
                        # Each color is uniformly spread around the color spectrum, keeping its saturation and value to the max (excludes black and white)
                        h, s, v = (color - 2) / color_count, 1.0, 1.0
                        r, g, b = colorsys.hsv_to_rgb(h, s, v) # Convert the color from HSV (easier to generate) to RGB (easier to manipulate)

                        # Because we can't use custom colors in most terminals, we find the closest available one and pair it to the color's id with a white foreground
                        curses.init_pair(color, -1, utils.find_nearest_color(r, g, b))

                    initialized = True
                    break

                elif status == 409: # Status 409: Known user, game already running
                    screen.clear()
                    raise Exception("A user is already playing an Online Ranked Game from this address.")

                elif not status:
                    screen.clear()
                    raise Exception("Server disconnected unexpectedly. Please try again later.")

                else:
                    screen.clear()
                    raise Exception("Unknown status {} returned by server.".format(status))
            except socket.timeout:
                pass

        screen.clear()
        line = 0
        first = False

        try:
            if code is None:
                code = [0xFFFF] * code_length
            if attempts is None:
                attempts = []

            game_score = play_game(screen, color_count, max_attempts, code, attempts)
            code, attempts = None, None # Reset the code and the attempts to make the next game independent
        except KeyboardInterrupt:
            screen.move(line, 0)
            screen.clrtoeol() # Clear the current line, just in case some text was there

            token = utils.encode_token(1, score, games, color_count, max_attempts, code, attempts)
            return token

        if game_score > 0:
            score += game_score # If the user won this game, we increment his score and the number of (consecutive) games he played
            games += 1
        else:
            score, games = 0, 0 # If he lost, we reset his score and the number of (consecutive) games

            initialized = False

### END PROGRAM CORE ###

if __name__ == "__main__":
    main()
