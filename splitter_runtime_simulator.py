#####
#
# Additional options for inputs:
#
# push (worker index) (splitter name)
# set (worker index) (splitter name) (splitter value)
# pop (worker index) (splitter name)
#
#####


from copy import copy

from helpers import color
import base_runtime_simulator as base


def parse_action(s):
    """Parse string s, return an Action object, including new splitter actions."""
    try:  # see if s is a splitter action first
        s_comp = s.split()
        action_type = s_comp[0]
        if action_type == "push":
            action = base.Action(action_type, worker_index=int(s_comp[1]),
                                 splitter_name=s_comp[2])
        elif action_type == "set":
            action = base.Action(action_type, worker_index=int(s_comp[1]),
                                 splitter_name=s_comp[2], splitter_value=s_comp[3])
        elif action_type == "pop":
            action = base.Action(action_type, worker_index=int(s_comp[1]),
                                 splitter_name=s_comp[2])
        return action
    except Exception:  # then try parsing as a base action
        try:
            return base.parse_action(s)
        except Exception:  # raise error if both fail
            raise base.ActionParseError()


class RTS(base.RTS):
    def __init__(self, num_workers):
        base.frame_id_assigner.reset()
        self.num_workers = num_workers
        # Initialize blank workers
        self.workers = []
        for i in range(self.num_workers):
            self.workers.append(Worker(i))  # NOTE: override to use new Worker class
        # One worker starts with initial frame
        self.initial_frame = Frame("initial")
        init_worker = self.workers[0]
        init_worker.deque.push(base.Stacklet(self.initial_frame))
        self.initial_frame.worker = init_worker
        init_worker.aug_hmap_deque.append(AugmentedHmap())
        init_worker.ancestor_hmap = copy(initial_hmap)
        init_worker.active_hmap = copy(initial_hmap)
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
        else:  # base action
            super().do_action(action)


class Worker(base.Worker):
    def __init__(self, index):
        super().__init__(index)
        # Keep track of splitter state
        self.aug_hmap_deque = []
        self.ancestor_hmap = None
        self.active_hmap = None

    @property
    def oldest_aug_hmap(self):
        return self.aug_hmap_deque[0]

    @property
    def youngest_aug_hmap(self):
        return self.aug_hmap_deque[-1]

    def _check_splitter_action_valid(self, splitter_name):
        if self.deque.is_empty():
            raise base.InvalidActionError("There is no frame, can't operation "
                                          "on splitter")
        assert(self.active_hmap is not None)
        assert(self.ancestor_hmap is not None)
        if splitter_name not in self.active_hmap:
            raise base.InvalidActionError("Splitter {} not found".format(
                                          splitter_name))

    def push(self, splitter_name):
        self._check_splitter_action_valid(splitter_name)
        prev_active_view = self.active_hmap[splitter_name]
        new_view = View(prev_active_view.value)
        new_view.parent = prev_active_view
        self.active_hmap[splitter_name] = new_view
        self.youngest_aug_hmap.push(splitter_name, new_view)

    def set(self, splitter_name, splitter_value):
        self._check_splitter_action_valid(splitter_name)
        self.active_hmap[splitter_name].value = splitter_value

    def pop(self, splitter_name):
        self._check_splitter_action_valid(splitter_name)
        self.active_hmap[splitter_name].count -= 1
        self.youngest_aug_hmap.pop(splitter_name)
        self.active_hmap[splitter_name] = self.active_hmap[splitter_name].parent

    def steal(self, victim):
        self.check_steal_valid(victim)
        # Construct new ancestor hypermap for victim
        thief_ancestor_hmap = copy(victim.ancestor_hmap)
        victim_ancestor_hmap = victim.ancestor_hmap
        for name, view in victim.oldest_aug_hmap.cur_map.items():
            victim_ancestor_hmap[name] = view
        # Set hypermaps
        self.ancestor_hmap = thief_ancestor_hmap
        self.active_hmap = copy(victim_ancestor_hmap)
        aug_hmap = victim.aug_hmap_deque.pop(0)
        self.aug_hmap_deque.append(aug_hmap)
        super().steal(victim)

    def sync(self):
        self.check_sync_valid()
        if not self.deque.is_single_frame():  # no-op
            return
        else:  # pop, try to provably good steal back
            cur_frame = self.deque.youngest_frame
            cur_frame.worker = None
            self.deque.pop()
            # Change ownership of hypermaps
            assert(cur_frame.ancestor_hmap is None and cur_frame.aug_hmap is None)
            cur_frame.aug_hmap = self.aug_hmap_deque.pop()
            assert(len(self.aug_hmap_deque) == 0)
            cur_frame.ancestor_hmap = self.ancestor_hmap
            self.ancestor_hmap = None
            self.active_hmap = None
            self.provably_good_steal(cur_frame)

    def spawn(self):
        self.check_spawn_valid()
        new_frame = Frame("spawn")
        new_frame.worker = self
        new_frame.attach(self.deque.youngest_frame)
        new_stacklet = Stacklet(new_frame)
        self.deque.push(new_stacklet)
        self.aug_hmap_deque.append(AugmentedHmap())

    def call(self):
        self.check_call_valid()
        new_frame = Frame("call")
        new_frame.worker = self
        self.deque.youngest_stacklet.push(new_frame)

    def ret_from_call(self):
        super().ret_from_call()  # no changes to any hypermaps either here or at
                                 # unconditional steal

    def ret_from_spawn(self):
        if len(self.youngest_aug_hmap) != 0:
            raise base.InvalidActionError("Cannot return without having popped "
                                          "all pushed splitters.")
        self.aug_hmap_deque.pop()
        super().ret_from_spawn()
        # TODO: correctly simulate "destroy view" since python garbage collects

    def provably_good_steal_success(self, frame):
        super().provably_good_steal_success(frame)
        assert(frame.ancestor_hmap is not None and frame.aug_hmap is not None)
        # Change ownership of ancestor/deque hypermaps
        self.ancestor_hmap = frame.ancestor_hmap
        frame.ancestor_hmap = None
        self.aug_hmap_deque.append(frame.aug_hmap)
        frame.aug_hmap = None
        # Set active hypermap to copy of the two combined
        self.active_hmap = copy(self.ancestor_hmap)
        for name, view in self.aug_hmap_deque[0].cur_map.items():
            self.active_hmap[name] = view

    def print_state(self):
        base_str = super().print_state()
        str_comp = []
        str_comp.append(base_str)
        str_comp.append("\nAncestor hmap: \t")
        str_comp.append(str(self.ancestor_hmap))
        str_comp.append("\n")
        for i, hmap in enumerate(self.aug_hmap_deque):
            if i == len(self.aug_hmap_deque) - 1:  # corresopnds to active stacklet
                str_comp.append(color(str(hmap), "grey"))
            else:
                str_comp.append(str(hmap))
            str_comp.append("\n")
        str_comp.append("\nActive hmap: \t")
        str_comp.append(str(self.active_hmap))
        str_comp.append("\n")
        return "".join(str_comp)


class AugmentedHmap(object):
    def __init__(self):
        self.cur_map = {}
        self.start_map = {}

    def __len__(self):
        assert(self.cur_map.keys() == self.start_map.keys())
        return len(self.cur_map)

    def push(self, splitter_name, view):
        """Push view into hypermap at deque position."""
        assert(self.cur_map.keys() == self.start_map.keys())
        if splitter_name in self.cur_map:
            self.cur_map[splitter_name] = view
        else:
            self.cur_map[splitter_name] = view
            self.start_map[splitter_name] = view.parent

    def pop(self, splitter_name):
        assert(self.cur_map.keys() == self.start_map.keys())
        if splitter_name not in self.cur_map:
            raise base.InvalidActionError("Cannot pop splitter {}".format(
                                          splitter_name))
        popped_view = self.cur_map[splitter_name]
        if popped_view.parent is self.start_map[splitter_name]:
            # popped to the beginning of the stack
            self.cur_map.pop(splitter_name)
            self.start_map.pop(splitter_name)
        else:
            self.cur_map[splitter_name] = popped_view.parent

    def __str__(self):
        assert(self.cur_map.keys() == self.start_map.keys())
        return str(self.cur_map)


class View(object):
    def __init__(self, value):
        self.value = value
        self.parent = None
        self.count = 1

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class Stacklet(base.Stacklet):
    pass


class Frame(base.Frame):
    def __init__(self, frame_type):
        super().__init__(frame_type)
        self.ancestor_hmap = None
        self.aug_hmap = None

    def __str__(self):
        base_str = super().__str__()
        if self.ancestor_hmap is not None:
            assert(self.aug_hmap is not None)
            base_str += "; Ancestor map: {}; ".format(self.ancestor_hmap)
            base_str += "Augmented map: {}".format(self.aug_hmap)
        return base_str


initial_hmap = {"x": View("init-val"), "y": View("init-val")}
