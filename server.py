#!/usr/bin/env python3

import os
import re
import json
import time
import queue
import errno
import base64
import socket
import threading
import traceback
import itertools

import utils

THREAD_COUNT = 16
PER_THREAD = 8
MAX_CLIENTS = THREAD_COUNT * PER_THREAD * 2

USERNAME_CHARACTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-°()[]{}*$€£%!?¡¿&@#/+=÷:;.…,<>§\"' àâæáäãåāçćčéèêëęėēîïìíįīñńôœöòóõōûùüúūÿÀÂÆÁÄÃÅĀÇĆČÉÈÊËĘĖĒÎÏÌÍĮĪÑŃÔŒÖÒÓÕŌÛÙÜÚŪŸ")

def run_thread(pending_clients, user_list, scoreboard):
    thread = threading.current_thread()
    clients = []
    while thread.running:
        try:
            while len(clients) < PER_THREAD:
                conn, address = pending_clients.get(False)
                conn.settimeout(0)
                data = {
                    "status": 300,
                    "inputs": []
                }
                clients.append((conn, address, data))
                print("Client {}:{} connected on thread #{}.".format(*address, thread.ident))
        except queue.Empty:
            pass

        for conn, address, data in clients:
            if not tick_client(conn, address, data, user_list, scoreboard):
                clients.remove((conn, address, data))

        time.sleep(0.1)

    for conn, address, data in clients:
        conn.close()
        user_list[address[0]]["connected"] = False
        clients.remove((conn, address, data))

def tick_client(conn, address, data, user_list, scoreboard):
    try:
        buff = data["inputs"].pop(0) if data["inputs"] else utils.receive_packet(conn)

        if buff:
            if data["status"] == 200:
                game = user_list[address[0]]["game"]

                guess = [0xFFFF] * len(game["code"])
                for i in range(len(game["code"])):
                    guess[i] = int.from_bytes(buff[2 * i:2 * (i + 1)], "big")

                perfect, partial = utils.compare_codes(guess, game["code"])

                if game["color_count"] == 6 and len(game["code"]) == 4 and guess == [0, 1, 0, 0]:
                    utils.send_packet(conn, (418).to_bytes(2, "big"))

                utils.send_packet(conn, perfect.to_bytes(2, "big") + partial.to_bytes(2, "big"))

                if perfect == len(game["code"]):
                    game["score"] += game["max_attempts"] - len(game["attempts"])
                    game["games"] += 1
                    game["code"] = utils.generate_code(len(game["code"]), game["color_count"])
                    game["attempts"] = []

                    if utils.DEBUG:
                        print("Client {}:{} won a game on thread #{}.".format(*address, thread.ident))
                else:
                    game["attempts"].append(guess)
                    if len(game["attempts"]) >= game["max_attempts"]:
                        token = utils.encode_token(game["gamemode"], game["score"], game["games"], game["color_count"], game["max_attempts"], game["code"], game["attempts"])
                        utils.send_packet(conn, token.encode("utf8"))

                        total_attempts = (game["max_attempts"] + 1) * game["games"] - game["score"]
                        normalized_score = game["score"]
                        normalized_score *= game["color_count"] ** len(game["code"]) / 1000
                        normalized_score /= 1.2 ** game["max_attempts"] / 10
                        normalized_score = int(normalized_score)

                        entry = (address[0], user_list[address[0]]["username"], game["score"], game["games"], total_attempts, normalized_score, game["color_count"], len(game["code"]), game["max_attempts"], time.time())
                        for i, other in enumerate(scoreboard):
                            if other[5] < entry[5] or (other[5] == entry[5] and other[3] < entry[3] or (other[3] == entry[3] and other[4] > entry[4])):
                                scoreboard.insert(i, entry)
                                break
                        else:
                            scoreboard.append(entry)

                        del user_list[address[0]]["game"]
                        user_list[address[0]]["connected"] = False
                        data["status"] = 204
                        utils.send_packet(conn, data["status"].to_bytes(2, "big"))

                        if utils.DEBUG:
                            print("Client {}:{} lost a game on thread #{}.".format(*address, thread.ident))

            elif address[0] in user_list and "connected" in user_list[address[0]] and user_list[address[0]]["connected"]:
                data["status"] = 409
                utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                conn.close()

                if utils.DEBUG:
                    print("Client {}:{} forcefully disconnected from thread #{}.".format(*address, thread.ident))

                return False

            elif data["status"] == 204:
                token = buff.decode("utf8")
                if re.match(r"^SB:\d+ \d+$", token):
                    page_size, offset = map(int, token[3:].split())
                    answer_bytes = bytes()

                    if len(scoreboard) >= offset:
                        for entry in scoreboard[offset:min(offset + page_size, len(scoreboard))]:
                            username = entry[1].encode("utf8")

                            if 6 + len(answer_bytes) + len(username) + 6 > 65535:
                                break

                            answer_bytes += (min(len(username), 0xFFFF) & 0xFFFF).to_bytes(2, "big")
                            answer_bytes += username

                            answer_bytes += (min(entry[5], 0xFFFF) & 0xFFFF).to_bytes(2, "big")
                            answer_bytes += (min(entry[3], 0xFFFF) & 0xFFFF).to_bytes(2, "big")
                            answer_bytes += (min(entry[4], 0xFFFF) & 0xFFFF).to_bytes(2, "big")

                            answer_bytes += (min(entry[4], 0xFFFF) & 0xFFFF).to_bytes(2, "big")
                            answer_bytes += (min(entry[5], 0xFFFF) & 0xFFFF).to_bytes(2, "big")
                            answer_bytes += (min(entry[6], 0xFFFF) & 0xFFFF).to_bytes(2, "big")

                            answer_bytes += (min(int(entry[8] * 1000), 2**64-1) & 2**64-1).to_bytes(8, "big")

                    utils.send_packet(conn, answer_bytes)
                else:
                    gamemode, score, games, color_count, max_attempts, code, attempts = utils.decode_token(token)

                    score, games = 0, 0
                    code = utils.generate_code(len(code), color_count)

                    user_list[address[0]]["connected"] = True
                    game = {
                        "gamemode": gamemode,
                        "score": score,
                        "games": games,
                        "color_count": color_count,
                        "max_attempts": max_attempts,
                        "code": code,
                        "attempts": []
                    }
                    user_list[address[0]]["game"] = game

                    if len(attempts) > max_attempts:
                        attempts = attempts[:max_attempts]

                    for attempt in attempts:
                        attempt_bytes = bytes()

                        if len(attempt) > len(code):
                            attempt = attempt[:len(code)]
                        elif len(attempt) < len(code):
                            attempt += [0] * (len(code) - len(attempt))

                        for color in attempt:
                            attempt_bytes += (min(color, 0xFFFF) & 0xFFFF).to_bytes(2, "big")

                        data["inputs"].append(attempt_bytes)

                        if attempt == code:
                            break

                    data["status"] = 200
                    utils.send_packet(conn, data["status"].to_bytes(2, "big"))

                    fake_code = [0xFFFF] * len(game["code"])
                    fake_token = utils.encode_token(game["gamemode"], game["score"], game["games"], game["color_count"], game["max_attempts"], fake_code, attempts)
                    utils.send_packet(conn, fake_token.encode("utf8"))

                    if utils.DEBUG:
                        print("Client {}:{} started a new game on thread #{}.".format(*address, thread.ident))

            elif data["status"] == 401 or data["status"] == 403:
                username = buff.decode("utf8")

                if buff == b"\x36\x39":
                    for chars in itertools.product(*[[b"\x4e",b"\x6e",b"\xc3\xb1",b"\xc5\x84",b"\xc3\x91",b"\xc5\x83"],[b"\x69",b"\x49",b"\xc3\xae",b"\xc3\xaf",b"\xc3\xac",b"\xc3\xad",b"\xc4\xaf",b"\xc4\xab",b"\xc3\x8e",b"\xc3\x8f",b"\xc3\x8c",b"\xc3\x8d",b"\xc4\xae",b"\xc4\xaa"],[b"\x63",b"\x43",b"\xc3\xa7",b"\xc4\x87",b"\xc4\x8d",b"\xc3\x87",b"\xc4\x86",b"\xc4\x8c"],[b"\x65",b"\x45",b"\xc3\xa9",b"\xc3\xa8",b"\xc3\xaa",b"\xc3\xab",b"\xc4\x99",b"\xc4\x97",b"\xc4\x93",b"\xc3\x89",b"\xc3\x88",b"\xc3\x8a",b"\xc3\x8b",b"\xc4\x98",b"\xc4\x96",b"\xc4\x92"]]):
                        username = "".join(map(lambda x: x.decode("utf8"), chars))
                        for other_address in user_list:
                            if username == user_list[other_address]["username"]:
                                data["status"] = 403
                                utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                                break
                        else:
                            break
                    else:
                        username = ""

                if 3 <= len(username) <= 32 and set(username) <= USERNAME_CHARACTERS:
                    for other_address in user_list:
                        if username == user_list[other_address]["username"]:
                            data["status"] = 403
                            utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                            break
                    else:
                        user_list[address[0]] = {
                            "username": username
                        }
                        data["status"] = 204
                        utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                else:
                    data["status"] = 403
                    utils.send_packet(conn, data["status"].to_bytes(2, "big"))

            elif data["status"] == 300:
                if buff.decode("utf8") == "OK":
                    if address[0] in user_list:
                        if not "connected" in user_list[address[0]] or not user_list[address[0]]["connected"]:
                            if "game" in user_list[address[0]] and user_list[address[0]]["game"] is not None:
                                game = user_list[address[0]]["game"]
                                user_list[address[0]]["connected"] = True

                                attempts = game["attempts"]
                                game["attempts"] = []

                                if len(attempts) > game["max_attempts"]:
                                    attempts = attempts[:game["max_attempts"]]

                                for attempt in attempts:
                                    attempt_bytes = bytes()

                                    if len(attempt) > len(game["code"]):
                                        attempt = attempt[:len(game["code"])]
                                    elif len(attempt) < len(game["code"]):
                                        attempt += [0] * (len(game["code"]) - len(attempt))

                                    for color in attempt:
                                        attempt_bytes += (min(color, 0xFFFF) & 0xFFFF).to_bytes(2, "big")

                                    data["inputs"].append(attempt_bytes)

                                    if attempt == game["code"]:
                                        break

                                data["status"] = 200
                                utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                                utils.send_packet(conn, user_list[address[0]]["username"].encode("utf8"))

                                fake_code = [0xFFFF] * len(game["code"])
                                fake_token = utils.encode_token(game["gamemode"], game["score"], game["games"], game["color_count"], game["max_attempts"], fake_code, attempts)
                                utils.send_packet(conn, fake_token.encode("utf8"))

                                if utils.DEBUG:
                                    print("Client {}:{} resumed a game on thread #{}.".format(*address, thread.ident))
                            else:
                                data["status"] = 204
                                utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                                utils.send_packet(conn, user_list[address[0]]["username"].encode("utf8"))
                        else:
                            data["status"] = 409
                            utils.send_packet(conn, data["status"].to_bytes(2, "big"))
                            conn.close()

                            if utils.DEBUG:
                                print("Client {}:{} forcefully disconnected from thread #{}.".format(*address, thread.ident))

                            return False
                    else:
                        data["status"] = 401
                        utils.send_packet(conn, data["status"].to_bytes(2, "big"))

            return True
    except socket.error as e:
        if hasattr(e, "skipped_data"):
            data = e.skipped_data
            if data.decode("utf8").startswith("GET "):
                data += conn.recv(65536 - len(e.skipped_data))
                if re.match(r"^GET .*? HTTP/\d+(?:\.\d+)*\r\n", data.decode("utf8")):
                    conn.send(base64.b64decode("SFRUUC8xLjEgMjAwIE9LDQpDb250ZW50LVR5cGU6aW1hZ2UvZ2lmDQpDb25uZWN0aW9uOmNsb3NlZA0KDQpHSUY4OWEQAA4A8gAA/wEqFf5J4esIoOc5K+7IycenAAAAAAAAIfkECQQAAAAh/hlPcHRpbWl6ZWQgdXNpbmcgZXpnaWYuY29tACH/C05FVFNDQVBFMi4wAwEAAAAh/wt4bXAgZGF0YXhtcP8/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG10YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS4zLWMwMTEgNjYuMTQ1NjYxLCAyMDEyLzAyLzA2LTE0OjU2OjI3ICAgICAgICAiPjxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53Lm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZjphYm91dD0iIiD/eG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1uczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzAubS40MTUgMjAxMi8wMy8wNToyMTowMDowMCkgIChNYWNpbnRvc2gpIiB4bXBNTTpJbnN0YWNlSUQ9/yJ4bXAuaWlkOjNFMDkxQkU1N0I3NTExRTE5QkY3ODJBQjU0NUZGMkI2IiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOjNFMDkxQkU2N0I3NTExRTE5QkY3ODJBQjU0NUZGMkI2Ij4gPG1wTU06RGVyaXZlZEZyb20gc3RSZWY6aW5zdGFuY2VJRD0ieG1wLmlpZDozRTA5MUJFMzdCNzUxMUUxOUJGNzgyQUI1NDVGRjJCNiIgc3RSZWY6ZG9jdW1lbnRJRD0ieG1wLmRpZDozRTA5MUJFNDdCNzUxMUUxOUY3ODJBQjU0NUZGMkI2Ii8+IDwvcmRmOkRlc2Nyaf9wdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFrZXQgZW5kPSJyIj8+Af/+/fz7+vn49/b19PPy8fDv7u3s6+rp6Ofm5eTj4uHg397d3Nva2djX1tXU09LR0M/OzczLysnIx8bFxMPCwcC/vr28u7q5uLe2tbSzsrGwr66trKupqKempaSjoqGgn56dnJuamZiXlpWUk5KRkI+OjYyLiomIh4aFhIOCgYB/fn18e3p5eHd2dXRzcnFwb25tbGtqaWhnZmVkY2JhYF9eXVxbWllYV1ZVVFNSUVBPTk1MS0pJSEdGRURDQkFAPz49PDs6OTg3NjU0MzIyMTAvLi0sKyopKCcmJSQjIiEgHx4dHBsaGRgXFhUUExIREA8ODQwLCgkIBwYFBAMCAQAALAAAAAAQAA4AAAM7CLoM1I08EMKAKsgtMdVcB1XhNpYcM5DopAgryGkqXIF3I+yxVF2LwW4IiwEBKyGRWFAIlUviK0oFJAAAIfkECQQAAAAsAAAAAA8ADgCCAAAAKv4jqvgVGUf7ENfjsaXCAAAAAAAAAz8IukvEjIwBHClQuSKHy5UzeRO2cOJkUY2Vjkzgjmosz96zBLdrMQVez2JSCI5HIa9YQCKVAWPAmVQaqVWhIAEAIfkECQQAAAAsAQAAAA8ADgCCAAAAD/9BLDf5BdTlRu6/nbKwAAAAAAAAAzsIuiO1sBUhmoCMao3B+BsXhVtkkRQDopfyrSRDEDAIFUH+vg+U/7oBoacA5miDXC9pnAUIOQXUSA0AEgAh+QQJBAAAACwAAAAAEAAOAIIAAABMOfbGGvIG2udG7r9D338AAAAAAAADQgi6EPxACBUCgdSKsCeulSR6DCiaDxGGIwkMIDdWzACbUljbcfzYvN6FUbARgLwhkVAoHJE2YrMIHTAXzGbV5gQkAAAh+QQJBAAAACwAAAEADwANAIIAAAA5PfjdCN/WaMAEy/fgWIMAAAAAAAADOQi6MvugFTBEg9RW7WAIVjNsXmiGDxiORWGlqlaQyxef8L2mBGFbn46iR7TZCAti0RhAApQ9ZhOZAAAh+QQJBAAAACwAAAEADgANAIIAAADtR3H+EzBJLffbI9LJx6cAAAAAAAADOAi6EMUrBEXIhFYGISSuXLddFBFyGmmJZ7dUUuuW2ekBxFCtnUVQg2AmsHsogkjh7phsIgHOKCABACH5BAkEAAAALAAAAQANAA0AggAAAPk0O/q5BN0a2nVK7wAAAAAAAAAAAAMtCLrcHuGJCSEbNcx5M9UL5mlCBIjQRiko+bFtZg5xxhJ0PJwD4eO5He/nCwISACH5BAkEAAAALAAAAQAPAA0AggAAAPY8Q+DbBvG9CvIL08nHpwAAAAAAAAM7CLoswu2BMESBqhYnKg4UJ0JgJZpMwJnjErKtAoaik87s4MlEr1cDygUgCPR6s9nQeGyCHkVQ8ygFJAAAIfkECQQAAAAsAAABABAADQCCAAAA/SgnN/4K190Gu+EazqatAAAAAAAAAzsIugxTjREBByEwDlummJGzeRTYjML3TdliXWRKNMEbX/T2ysTADIEa7ML5BYM6XQt4bCIVOqdUJJ0CEgAh+QQFBAAAACwAAAAAEAAOAIIAAAD+QwQm/hsI/l3D2R1G7r8AAAAAAAADPwi63K5lifHULFjgSrT4Q+gQHTiAEUN+aDE1pRZmAhyH4WfH7KuSvE5KQQoEgEjComhsIlPIphFJJBylThIgAQA7"))
                    conn.close()

                    if utils.DEBUG:
                        print("Client {}:{} disconnected from thread #{}.".format(*address, thread.ident))

                    return False

        if e.errno == errno.EWOULDBLOCK:
            return True
        elif utils.DEBUG:
            traceback.print_exc()
        else:
            print(e)
    except Exception as e:
        if utils.DEBUG:
            traceback.print_exc()
        else:
            print(e)
        pass

    conn.close()

    if address[0] in user_list and "connected" in user_list[address[0]] and user_list[address[0]]["connected"]:
        user_list[address[0]]["connected"] = False

    if utils.DEBUG:
        print("Client {}:{} disconnected from thread #{}.".format(*address, thread.ident))

    return False

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(("0.0.0.0", utils.SERVER_PORT))
server_socket.listen(MAX_CLIENTS)

pending_clients = queue.Queue(maxsize=MAX_CLIENTS)

if os.path.isfile("user_list.json"):
    with open("user_list.json", "r") as file:
        user_list = json.load(file)
else:
    user_list = {}

if os.path.isfile("scoreboard.csv"):
    scoreboard = []
    with open("scoreboard.csv", "r") as file:
        for line in file.readlines():
            try:
                entry = list(map(lambda x: x.replace("„", ","), line.split(",")))
                entry[2:9] = map(int, entry[2:9])
                entry[9] = float(entry[9])
                scoreboard.append(entry)
            except:
                pass
else:
    scoreboard = []

threads = []
for i in range(THREAD_COUNT):
    thread = threading.Thread(target=run_thread, args=[pending_clients, user_list, scoreboard])
    thread.running = True
    thread.start()
    threads.append(thread)

try:
    while True:
        conn, address = server_socket.accept()
        pending_clients.put((conn, address))
except:
    for thread in threads:
        thread.running = False

    for thread in threads:
        thread.join()

server_socket.close()

with open("user_list.json", "w") as file:
    json.dump(user_list, file)

with open("scoreboard.csv", "w") as file:
    file.write("id,username,score,games,total attempts,normalized score,color count,code length,maximum attempts,timestamp\n")
    for entry in scoreboard:
        file.write(",".join(map(lambda x: str(x).replace(",", "„"), entry)) + "\n")
