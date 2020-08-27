enclosed_alp = [
    '\u249C', '\u249D', '\u249E', '\u249F', '\u24A0', '\u24A1',
    '\u24A2', '\u24A3', '\u24A4', '\u24A5', '\u24A6', '\u24A7',
    '\u24A8', '\u24A9', '\u24AA', '\u24AB', '\u24AC', '\u24AD',
    '\u24AE', '\u24AF', '\u24B0', '\u24B1', '\u24B2', '\u24B3',
    '\u24B4', '\u24B5'
]


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

    def assign(self):
        to_return = enclosed_alp[self.symbol_index]
        self.symbol_index += 1
        if self.symbol_index >= len(enclosed_alp):
            self.symbol_index = 0
        return to_return

    def cur_symbol(self):
        return enclosed_alp[self.symbol_index]

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
