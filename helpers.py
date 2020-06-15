def color(string, color):
    """Return a new string that is the input string with the specified color."""
    colors = {
        "red": '\033[91m',
        "green": '\033[92m',
        "blue": '\033[94m',
        "yellow": '\033[93m',
        "grey": '\033[90m',
    }
    endc = '\033[0m'
    assert(color in colors)
    return colors[color] + string + endc


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
