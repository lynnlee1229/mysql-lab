"""Small serial specification, independent of MySQL, isolation levels and runner SQL.

This enumerates the two legal request orders. It is an oracle for THIS two-member,
fixed-roster business rule, not an implementation of a database or an SQL engine.
"""
from itertools import permutations


def serial_outcomes(initial=(1, 1)):
    assert len(initial) == 2 and all(x in (0, 1) for x in initial)
    terminal = set()
    for order in permutations(range(len(initial))):
        state = list(initial)
        for doctor in order:
            if state[doctor] and sum(state) > 1:
                state[doctor] = 0
        terminal.add(tuple(state))
    return sorted(terminal)


def assess(rows):
    assert [r['doctor_id'] for r in rows] == [1, 2]
    state = tuple(r['on_call'] for r in rows)
    assert all(type(x) is int and x in (0, 1) for x in state)
    legal = serial_outcomes()
    return {'on_call_count': sum(state), 'invariant_holds': sum(state) >= 1,
            'serially_reachable': state in legal,
            'allowed_serial_states': [list(x) for x in legal]}
