#####
#
# Additional options for inputs:
#
# push (worker index) (splitter name)
# set (worker index) (splitter name) (splitter value)
# pop (worker index) (splitter name)
# access (worker index) (splitter_name)
#
#####


from copy import copy

from helpers import (
    color, frame_id_assigner, InvalidActionError, ActionParseError, Action
)
import base_runtime_simulator as base


def parse_action(s):
    """Parse string s, return an Action object, including new splitter actions."""
    try:  # see if s is a splitter action first
        s_comp = s.split()
        action_type = s_comp[0]
        if action_type == "push":
            action = Action(action_type, worker_index=int(s_comp[1]),
                            splitter_name=s_comp[2])
        elif action_type == "set":
            action = Action(action_type, worker_index=int(s_comp[1]),
                            splitter_name=s_comp[2], splitter_value=s_comp[3])
        elif action_type == "pop":
            action = Action(action_type, worker_index=int(s_comp[1]),
                            splitter_name=s_comp[2])
        elif action_type == "access":
            action = Action(action_type, worker_index=int(s_comp[1]),
                            splitter_name=s_comp[2])
        else:
            action = base.parse_action(s)
        return action
    except Exception:
        raise ActionParseError()


class RTS(base.RTS):
    def __init__(self, num_workers):
        frame_id_assigner.reset()
        self.num_workers = num_workers
        # Initialize blank workers
        self.workers = []
        for i in range(self.num_workers):
            self.workers.append(Worker(i))  # NOTE: override to use new Worker class
        # One worker starts with initial frame
        self.initial_frame = Frame("initial")
        init_worker = self.workers[0]
        self.initial_frame.worker = init_worker
        # That worker starts with a basic hypermap with default values
        initial_hmap = HMap(None)
        x_init_view = View("init-val")
        y_init_view = View("init-val")
        initial_hmap.top_map = {"x": x_init_view, "y": y_init_view}
        initial_hmap.base_map = {"x": x_init_view, "y": y_init_view}
        init_worker.deque.push(Stacklet(self.initial_frame))
        init_worker.hmap_deque.append(initial_hmap)
        # Keep track of all actions, for restoring
        self.actions = []

    def do_action(self, action):
        if action.type == "push":
            worker = self.workers[action.worker_index]
            worker.push(action.splitter_name)
            self.actions.append(action)
        elif action.type == "set":
            worker = self.workers[action.worker_index]
            worker.set(action.splitter_name, action.splitter_value)
            self.actions.append(action)
        elif action.type == "pop":
            worker = self.workers[action.worker_index]
            worker.pop(action.splitter_name)
            self.actions.append(action)
        elif action.type == "access":
            worker = self.workers[action.worker_index]
            worker.access(action.splitter_name)
            self.actions.append(action)
        else:  # base action
            super().do_action(action)


class Worker(base.Worker):
    def __init__(self, index):
        super().__init__(index)
        # Keep track of splitter state
        self.hmap_deque = HMapDeque()
        self.cache = {}

    def access(self, splitter_name):
        if splitter_name in self.cache:
            return self.cache[splitter_name]
        # start searching
        hmap_to_search = self.hmap_deque.oldest_hmaps[-1]
        while splitter_name not in hmap_to_search:
            hmap_to_search = hmap_to_search.parent
            if hmap_to_search is None:
                raise InvalidActionError("Splitter {} not found".format(
                                         splitter_name))
        view = hmap_to_search.top_view(splitter_name)
        self.cache[splitter_name] = view
        return view

    def push(self, splitter_name):
        parent_view = self.access(splitter_name)
        new_view = View(parent_view.value)
        new_view.parent = parent_view
        hmap = self.hmap_deque.youngest_hmap
        if splitter_name not in hmap:
            hmap.base_map[splitter_name] = parent_view
        hmap.top_map[splitter_name] = new_view
        oldest_of_youngest = self.hmap_deque.oldest_of_youngest
        if splitter_name not in oldest_of_youngest:
            oldest_of_youngest.base_map[splitter] = parent_view
            oldest_of_youngest.top_map[splitter] = parent_view
        self.cache[splitter_name] = new_view

    def set(self, splitter_name, splitter_value):
        view = self.access(splitter_name)
        view.value = splitter_value

    def pop(self, splitter_name):
        view = self.access(splitter_name)
        parent_view = view.parent
        oldest_of_youngest = self.hmap_deque.oldest_of_youngest
        if (
            splitter_name not in oldest_of_youngest or
            oldest_of_youngest.base_map[splitter_name] is view
        ):
            raise InvalidActionError("Splitter {} cannot be popped".format(
                                     splitter_name))
        youngest = self.hmap_deque.youngest_hmap
        if (
            splitter_name not in youngest or
            youngest.top_map[splitter_name] is youngest.base_map[splitter_name]
        ):  # push back base
            youngest.top_map[splitter_name] = parent_view
            youngest.base_map[splitter_name] = parent_view
        else:
            youngest.top_map[splitter_name] = parent_view
        self.cache[splitter_name] = parent_view

    def print_state(self):
        # interleave call stack and hypermaps
        # under each call stack, print hypermaps in order of oldest to youngest
        assert(len(self.deque) == len(self.hmap_deque))
        str_comp = []
        for i, (stacklet, hmaps) in enumerate(zip(self.deque, self.hmap_deque)):
            pos_comp = []
            pos_comp.append(str(stacklet))
            pos_comp.append("\n")
            for hmap in hmaps:
                pos_comp.append("\t")
                pos_comp.append(str(hmap))
                pos_comp.append("\n")
            pos_str = "".join(pos_comp)
            if i == len(self.deque) - 1:  # active stacklet, indicate by color
                str_comp.append(color(pos_str, "grey"))
            else:
                str_comp.append(pos_str)
        str_comp.append("Cache: ")
        str_comp.append(str(self.cache))
        str_comp.append("\n")
        return "".join(str_comp)


class HMap(object):
    def __init__(self, parent):
        self.top_map = {}
        self.base_map = {}
        self.parent = parent

    def top_view(self, splitter_name):
        return self.top_map[splitter_name]

    def __contains__(self, key):
        return key in self.base_map

    def __str__(self):
        assert(self.base_map.keys() == self.top_map.keys())
        str_comp = []
        for splitter_name in self.base_map:
            str_comp.append(splitter_name)
            str_comp.append(": ")
            base_view = self.base_map[splitter_name]
            iter_view = self.top_map[splitter_name]
            values = []
            while iter_view is not base_view:
                values.append(iter_view.value)
                iter_view = iter_view.parent
            values.append(iter_view.value)
            values.reverse()  # oldest in front, youngest at end
            str_comp.append("<-".join(values))
            str_comp.append("    ")
        return "".join(str_comp)

class HMapDeque(object):
    def __init__(self):
        self.deque = []  # each entry is a list from oldest to youngest in order

    def __len__(self):
        return len(self.deque)

    def __iter__(self):
        yield from self.deque

    @property
    def oldest_hmaps(self):
        return self.deque[0]

    @property
    def youngest_hmaps(self):
        return self.deque[-1]

    @property
    def youngest_hmap(self):
        return self.youngest_hmaps[-1]

    @property
    def oldest_of_youngest(self):
        return self.youngest_hmaps[0]

    def append(self, hmap):
        self.deque.append([hmap])

class View(object):
    def __init__(self, value):
        self.value = value
        self.parent = None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class Stacklet(base.Stacklet):
    pass


class Frame(base.Frame):
    pass
