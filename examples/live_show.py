"""show() in a loop updates one panel in place.

Calling consolekit.show() again with the same title swaps what the panel
shows instead of rebuilding it, so a loop can report progress smoothly.
This one hunts for primes and shows what it has found so far.
"""
import time

import consolekit

LIMIT = 20000
REPORT_EVERY = 1000


def is_prime(number):
    return number > 1 and all(number % divisor for divisor in range(2, int(number ** 0.5) + 1))


def report(checked, primes, seconds):
    return '\n'.join([
        'Checked up to %d of %d' % (checked, LIMIT),
        'Primes found: %d' % len(primes),
        'Largest so far: %d' % primes[-1],
        'Latest: ' + ', '.join(str(prime) for prime in primes[-5:]),
        '',
        '%.1f seconds' % seconds,
    ])


primes = []
started = time.time()
for number in range(2, LIMIT + 1):
    if is_prime(number):
        primes.append(number)
    if number % REPORT_EVERY == 0:
        consolekit.show(report(number, primes, time.time() - started),
                        title='Primes', icon='🔍', height=220)
        time.sleep(0.15)     # slow enough to watch it update

consolekit.show(report(LIMIT, primes, time.time() - started) + '\nDone.', title='Primes')