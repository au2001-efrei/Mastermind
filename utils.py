#!/usr/bin/env python3

### BEGIN IMPORTS ###

import zlib
import base64
import curses
import socket
import random

### END IMPORTS ###

### BEGIN CONSTANTS ###

PREFIX = "Guess:"

DEFAULT_CODE_LENGTH = 4
DEFAULT_COLOR_COUNT = 6
DEFAULT_MAX_ATTEMPTS = 12

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 45735

HEADER = (0x1EE7).to_bytes(2, "little")
FOOTER = (0x7EE1).to_bytes(2, "little")

DEBUG = False

### END CONSTANTS ###

### BEGIN UTILS ###

def generate_code(code_length, color_count):
    # Generates a code of the right length with each color between 0 and the number of colors (excluded)
    return [random.randint(0, color_count - 1) for i in range(code_length)]

def find_nearest_color(r, g, b):
    best_color, best_error = None, 0
    for color_number in range(curses.COLORS): # Iterate through the preset colors and get their RGB values
        cr, cg, cb = curses.color_content(color_number)
        cr, cg, cb = cr / 1000, cg / 1000, cb / 1000

        error = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2 # The error is a simple Euclidean distance between the requested color and the current preset one

        if best_color is None or error < best_error: # We store the color matching best the requested RGB values
            best_error = error
            best_color = color_number

            if error == 0: # If the color is exactly the one we're looking for, we can stop here and return it right away
                break

    return best_color if best_color is not None else 0 # If a color was found, we return it, or we return 0 which is the basic black and white color

def compare_codes(guess, correct):
    guess, correct = guess.copy(), correct.copy() # Clone the lists because we are going to edit them, so we don't want to mess up the main program's lists

    perfect = 0
    for i in range(min(len(guess), len(correct))):
        if guess[i - perfect] == correct[i - perfect]: # If the guessed color is the right one
            del guess[i - perfect] # We remove that color from both lists
            del correct[i - perfect]
            perfect += 1 # And we increment the perfect color counter

    partial = 0
    for left in guess: # For each color left in the guess
        if left in correct: # If the color is also in the correct answer (it can't be at the right position, or we would have found it in the first loop)
            correct.remove(left) # We remove it from the correct list (no need to remove it in the guessed list as we're not using it further)
            partial += 1 # And we increment the partial color counter

    return perfect, partial

def encode_token(gamemode, score, games, color_count, max_attempts, code, attempts):
    token, bits = 0, 0

    # Encode gamemode on 8 bits (max. 256 gamemodes)
    token |= (min(gamemode, 0xFF) & 0xFF) << bits
    bits += 8

    # Encode score on 16 bits (max. 65535 score)
    token |= (min(score, 0xFFFF) & 0xFFFF) << bits
    bits += 16

    # Encode games on 16 bits (max. 65535 games)
    token |= (min(games, 0xFFFF) & 0xFFFF) << bits
    bits += 16

    # Encode color count on 16 bits (max. 65535 colors)
    token |= (min(color_count, 0xFFFF) & 0xFFFF) << bits
    bits += 16

    # Encode max attempts on 16 bits (max. 65535 attempts)
    token |= (min(max_attempts, 0xFFFF) & 0xFFFF) << bits
    bits += 16

    # If code is too long, cut it off to the maximum length
    if len(code) > 0xFFFF:
        code = code[:0xFFFF]

    # Encode code length on 16 bits (max. 65535 code length)
    token |= (len(code) & 0xFFFF) << bits
    bits += 16

    for color in code:
        # Encode code's colors on 16 bits (max. 65535 colors)
        token |= (min(color, 0xFFFF) & 0xFFFF) << bits
        bits += 16

    # If attempts is too long, cut it off to the maximum length
    if len(attempts) > 0xFFFF:
        attempts = attempts[:0xFFFF]

    # Encode attempt count on 16 bits (max. 65535 attempts)
    token |= (len(attempts) & 0xFFFF) << bits
    bits += 16

    for attempt in attempts:
        # If attempt is not the same size as code, cut it off or append zeros
        if len(attempt) > len(code):
            attempt = attempt[:len(code)]
        elif len(attempt) < len(code):
            attempt += [0] * (len(code) - len(attempt))

        for color in attempt:
            # Encode attempt's colors on 16 bits (max. 65535 colors)
            token |= (min(color, 0xFFFF) & 0xFFFF) << bits
            bits += 16

    # Convert the integer token to a byte array, then compress it using zlib, and encode it into Base64
    byte_array = bytes()
    while token:
        byte_array = bytes([token & 0xFF]) + byte_array
        token >>= 8
    return base64.b64encode(zlib.compress(byte_array, 9)).decode("utf8")

def decode_token(token):
    # Decode the Base64 token, then decompress it using zlib, and convert the byte array to an integer token
    byte_array = zlib.decompress(base64.b64decode(token))
    token = 0
    for i in range(len(byte_array)):
        token <<= 8
        token |= byte_array[i]

    # Decode gamemode from 8 bits (max. 256 gamemodes)
    gamemode = token & 0xFF
    token >>= 8

    # Decode score from 16 bits (max. 65535 score)
    score = token & 0xFFFF
    token >>= 16

    # Decode games from 16 bits (max. 65535 games)
    games = token & 0xFFFF
    token >>= 16

    # Decode color count from 16 bits (max. 65535 colors)
    color_count = token & 0xFFFF
    token >>= 16

    # Decode max attempts from 16 bits (max. 65535 attempts)
    max_attempts = token & 0xFFFF
    token >>= 16

    # Decode code length from 16 bits (max. 65535 code length)
    code_length = token & 0xFFFF
    token >>= 16

    code = [0] * code_length
    for i in range(code_length):
        # Decode code's colors from 16 bits (max. 65535 colors)
        code[i] = token & 0xFFFF
        token >>= 16

    # Decode attempt count from 16 bits (max. 65535 attempts)
    attempt_count = token & 0xFFFF
    token >>= 16

    attempts = [None] * attempt_count
    for i in range(attempt_count):
        attempts[i] = [0] * code_length
        for j in range(code_length):
            # Decode attempt's colors from 16 bits (max. 65535 colors)
            attempts[i][j] = token & 0xFFFF
            token >>= 16

    return gamemode, score, games, color_count, max_attempts, code, attempts

def print_code(screen, prefix, guess, selected):
    screen.addstr("\r")
    screen.clrtoeol() # Clear the current line, just in case some text was there (usually clears the previous print_code output)

    screen.addstr(prefix)

    for i, color in enumerate(guess):
        screen.addstr(" ")

        attr = curses.color_pair(color + 2) # For each color, print it in the right color
        screen.addstr("•" if i == selected else " ", attr) # Add a white dot in the middle if it's the currently selected color

def send_packet(conn, data):
    # We limit the packet length to 65536 not to overload the network and to reduce the probability of packet loss
    length = len(HEADER + data + FOOTER) + 2
    if length > 65536:
        raise socket.error("packet length was too long ({} > {})".format(length, 65536))

    # The packet contains the header, the total packet's length, the data itself, and the footer
    packet = bytes()
    packet += HEADER
    packet += length.to_bytes(2, "big")
    packet += data
    packet += FOOTER

    conn.send(packet)

def receive_packet(conn, max_tries=10):
    skipped_data = bytes()
    for i in range(max_tries):
        for i in range(len(HEADER)):
            byte = conn.recv(1) # Receive bytes one by one not to go past the HEADER if it was offset by an odd number of bytes

            if not byte: # If the client closed the connection
                error = socket.error("could not receive packet header")
                error.skipped_data = skipped_data
                raise error

            skipped_data += byte # Keep the data which is skipped not to lose any important information, just in case
            if ord(byte) != HEADER[i]:
                break
        else:
            break
    else:
        error = socket.error("could not receive packet header")
        error.skipped_data = skipped_data
        raise error

    length = int.from_bytes(conn.recv(2), "big")
    data = conn.recv(length - (len(HEADER) + 2 + len(FOOTER))) if length > 0 else bytes() # Read all the data between the length and the footer

    # Add the read length and data in case the packet is still invalid
    skipped_data += length.to_bytes(2, "big")
    skipped_data += data

    byte = conn.recv(len(FOOTER))
    skipped_data += byte

    if byte != FOOTER: # Make sure the packet ends with the footer so that we don't lose any information/skip any data
        error = socket.error("packet did not end with expected footer")
        error.skipped_data = skipped_data
        raise error

    return data

### END UTILS ###
