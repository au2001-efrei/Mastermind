#!/usr/bin/env python3

import time
import random
import itertools
import threading

import utils

def generate_codes(code_length=4, color_count=6):
    if code_length > 0:
        for i in range(color_count):
            for subcode in generate_codes(code_length=code_length - 1, color_count=color_count):
                yield [i] + subcode
    else:
        yield []

def input_guess(code_length, color_count, possibilities):
    if len(possibilities) == color_count ** code_length:
        guess = [0] * ((code_length + 1) // 2) + [1] * (code_length // 2)
    else:
        guess = random.choice(possibilities)

    possibilities.remove(guess)
    return guess

def benchmark(code, color_count=6, max_attempts=12):
    possibilities = list(map(list, itertools.product(range(color_count), repeat=len(code))))

    for i in range(max_attempts):
        attempt = input_guess(len(code), color_count, possibilities)
        perfect, partial = utils.compare_codes(attempt, code)

        if perfect == len(code):
            return i
        else:
            possibilities = list(filter(lambda possibility: utils.compare_codes(attempt, possibility) == (perfect, partial), possibilities))

    return max_attempts

def main():
    def worker(status):
        while status["running"]:
            for code in generate_codes():
                score = benchmark(code) + 1

                status["total"] += score
                status["games"] += 1

                if status["mini"] is None or score < status["mini"]:
                    status["mini"] = score

                if status["maxi"] is None or score > status["maxi"]:
                    status["maxi"] = score

                if not status["running"]:
                    break
            else:
                status["iteration"] += 1

    worker.running = True

    status = {
        "running": True,
        "iteration": 0,
        "games": 0,
        "total": 0,
        "mini": None,
        "maxi": None
    }

    threads = []
    for i in range(1):
        thread = threading.Thread(target=worker, args=[status])
        thread.start()
        threads.append(thread)

    try:
        start = time.time()
        previous = status["iteration"]
        time.sleep(1)
        while True:
            if status["iteration"] > previous:
                print("*** Iteration %d" % status["iteration"])
                print("Total: %d attempts on %d games" % (status["total"], status["games"]))
                print("Average: %d / %d = %f" % (status["total"], status["games"], status["total"] / status["games"]))
                print("Minimum: %d - Maximum: %d" % (status["mini"], status["maxi"]))
                print("Speed: %f games/second" % (status["games"] / (time.time() - start)))
                print()
                previous = status["iteration"]
            else:
                time.sleep(5)
    except KeyboardInterrupt:
        status["running"] = False
        for thread in threads:
            thread.join()

if __name__ == "__main__":
    main()
