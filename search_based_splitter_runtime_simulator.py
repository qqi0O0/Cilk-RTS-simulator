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


all_views = []


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
        all_views.clear()
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
        x_init_view = View("init-x")
        y_init_view = View("init-y")
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

    def print_state(self):
        views_str = color("Views:\n\n", "yellow") + str(all_views) + "\n\n"
        return views_str + super().print_state()


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
        view = hmap_to_search.top_map[splitter_name]
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
            view.destroy()
        self.cache[splitter_name] = parent_view

    def call(self):
        """Call, add a new frame on current stacklet."""
        self.check_call_valid()
        new_frame = Frame("call")
        new_frame.worker = self
        self.deque.youngest_stacklet.push(new_frame)

    def spawn(self):
        self.check_spawn_valid()
        new_frame = Frame("spawn")
        new_frame.worker = self
        new_frame.attach(self.deque.youngest_frame)
        new_stacklet = Stacklet(new_frame)
        self.deque.push(new_stacklet)
        new_hmap = HMap(self.hmap_deque.youngest_hmap)
        self.hmap_deque.append(new_hmap)

    def ret_from_spawn(self):
        if len(self.hmap_deque.youngest_hmaps) > 1:
            raise InvalidActionError("Cannot return, hypermaps have not been "
                                     "merged. Sync before returning.")
        youngest_hmap = self.hmap_deque.youngest_hmap
        if any(
            youngest_hmap.top_map[splitter] is not youngest_hmap.base_map[splitter]
            for splitter in youngest_hmap
        ):
            raise InvalidActionError("Cannot return without having popped "
                                     "all pushed splitters.")
        self.hmap_deque.pop()
        super().ret_from_spawn()

    def steal(self, victim):
        super().steal(victim)
        stolen_hmaps = victim.hmap_deque.pop(0)
        assert(len(self.hmap_deque) == 0)
        self.hmap_deque.deque.append(stolen_hmaps)
        new_hmap = HMap(self.hmap_deque.youngest_hmap)
        self.hmap_deque.youngest_hmaps.append(new_hmap)
        self.cache.clear()

    def sync(self):
        self.check_sync_valid()
        if not self.deque.is_single_frame():  # no-op
            return
        else:  # pop, try to provably good steal back
            cur_frame = self.deque.youngest_frame
            cur_frame.worker = None
            self.deque.pop()
            # Change ownership of hypermaps
            assert(cur_frame.cache is None and cur_frame.hmaps == [])
            cur_frame.hmaps = self.hmap_deque.pop()
            assert(len(self.hmap_deque) == 0)
            cur_frame.cache = self.cache
            self.cache = None
            self.provably_good_steal(cur_frame)

    def provably_good_steal_success(self, frame):
        super().provably_good_steal_success(frame)
        assert(frame.cache is not None and frame.hmaps != [])
        self.cache = frame.cache
        frame.cache = None
        # merge hypermaps
        hmaps = frame.hmaps
        frame.hmaps = []
        accum = hmaps[0]
        for i in range(1, len(hmaps)):
            child = hmaps[i]
            for splitter_name in child:
                top_view = accum.top_map[splitter_name]
                base_view = child.base_map[splitter_name]
                # Destroy from top to base, not including base
                iter_view = top_view
                while iter_view is not base_view:
                    print(iter_view)
                    iter_view.destroy()
                    iter_view = iter_view.parent
                # Update top view
                accum.top_map[splitter_name] = child.top_map[splitter_name]
        self.hmap_deque.append(accum)

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

    def __contains__(self, key):
        return key in self.base_map

    def __iter__(self):
        yield from self.base_map.keys()

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
            str_comp.append("; ")
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

    def pop(self, index=-1):
        return self.deque.pop(index)

class View(object):
    def __init__(self, value):
        self.value = value
        self.parent = None
        all_views.append(self)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)

    def destroy(self):
        assert(self in all_views)
        all_views.remove(self)


class Stacklet(base.Stacklet):
    pass


class Frame(base.Frame):
    def __init__(self, frame_type):
        super().__init__(frame_type)
        self.hmaps = []
        self.cache = None

    def __str__(self):
        str_comp = []
        base_str = super().__str__()
        if self.cache is None:
            assert self.hmaps == []
            return base_str
        str_comp.append(base_str)
        str_comp.append("; Hypermaps: ")
        for hmap in self.hmaps:
            str_comp.append("(")
            str_comp.append(str(hmap))
            str_comp.append(") ")
        str_comp.append("Cache: ")
        str_comp.append(str(self.cache))
        return "".join(str_comp)
