enclosed_alp = [
    '\u249C', '\u249D', '\u249E', '\u249F', '\u24A0', '\u24A1',
    '\u24A2', '\u24A3', '\u24A4', '\u24A5', '\u24A6', '\u24A7',
    '\u24A8', '\u24A9', '\u24AA', '\u24AB', '\u24AC', '\u24AD',
    '\u24AE', '\u24AF', '\u24B0', '\u24B1', '\u24B2', '\u24B3',
    '\u24B4', '\u24B5'
]
greek_alp = [
    '\u03b1', '\u03b2', '\u03b3', '\u03b4', '\u03b5', '\u03b6',
    '\u03b7', '\u03b8', '\u03b9', '\u03ba', '\u03bb', '\u03bc',
    '\u03bd', '\u03be', '\u03bf', '\u03c0', '\u03c1', '\u03c3',
    '\u03c4', '\u03c5', '\u03c6', '\u03c7', '\u03c8', '\u03c9']


def color(string, color):
    """Return a new string that is the input string with the specified color."""
    colors = {
        "red": '\033[91m',
        "green": '\033[92m',
        "yellow": '\033[93m',
        "blue": '\033[94m',
        "purple": '\033[95m',
        "grey": '\033[90m',
    }
    endc = '\033[0m'
    assert(color in colors)
    return colors[color] + string + endc


class SymbolAssigner(object):
    def __init__(self):
        self.symbol_index = 0
        self.alp = greek_alp

    def assign(self):
        to_return = self.alp[self.symbol_index]
        self.symbol_index += 1
        if self.symbol_index >= len(self.alp):
            self.symbol_index = 0
        return to_return

    def cur_symbol(self):
        return self.alp[self.symbol_index]

    def reset(self):
        self.symbol_index = 0


node_symbol_assigner = SymbolAssigner()


class IDAssigner(object):
    def __init__(self):
        self.ID = 0

    def assign(self):
        to_return = self.ID
        self.ID += 1
        return to_return

    def reset(self):
        self.ID = 0


frame_id_assigner = IDAssigner()


class InvalidActionError(Exception):
    pass


class ActionParseError(Exception):
    pass


class Action(object):
    """
    Stores an action and the worker(s) involved in the action. E.g. spawn,
    steal, sync, splitter push, splitter pop, etc.
    """
    def __init__(self, action_type, **kwargs):
        self.type = action_type
        for key, val in kwargs.items():
            setattr(self, key, val)
