#####
#
# Options for inputs:
#
# undo
# call (worker id)
# spawn (worker id)
# return (worker id)
# steal (thief id) (victim id)
# sync (worker id)
#
#####


from helpers import (
    color, frame_id_assigner, InvalidActionError, ActionParseError, Action
)


def parse_action(s):
    """Parse string s, return an Action object."""
    try:
        s_comp = s.split()
        action_type = s_comp[0]
        if action_type == "undo":
            action = Action(action_type)
        elif action_type == "help":
            action = Action(action_type)
        elif action_type == "call":
            action = Action(action_type, worker_id=s_comp[1])
        elif action_type == "spawn":
            action = Action(action_type, worker_id=s_comp[1])
        elif action_type == "return":
            action = Action(action_type, worker_id=s_comp[1])
        elif action_type == "steal":
            action = Action(action_type, thief_id=s_comp[1], victim_id=s_comp[2])
        elif action_type == "sync":
            action = Action(action_type, worker_id=s_comp[1])
        else:
            raise ActionParseError()
        return action
    except Exception:
        raise ActionParseError()


class RTS(object):
    def __init__(self, num_workers):
        frame_id_assigner.reset()
        self.num_workers = num_workers
        # Initialize blank workers
        self.workers = {}
        for i in range(self.num_workers):
            worker_id = chr(65 + i)  # chr(65) = A
            self.workers[worker_id] = Worker(worker_id)
        # One worker starts with initial frame
        self.initial_frame = Frame("initial")
        self.workers['A'].deque.push(Stacklet(self.initial_frame))
        self.initial_frame.worker = self.workers['A']
        # Keep track of all actions, for restoring
        self.actions = []

    def get_worker(self, worker_id):
        if worker_id not in self.workers:
            raise InvalidActionError("Worker {} not found.".format(worker_id))
        return self.workers[worker_id]

    def do_action(self, action):
        if action.type == "undo":
            if len(self.actions) > 0:
                self.actions.pop()
            self.restore()
        elif action.type == "help":
            print(color(
                "Options:\n"
                "undo\n"
                "call (worker id)\n"
                "spawn (worker id)\n"
                "return (worker id)\n"
                "steal (thief id) (victim id)\n"
                "sync (worker id)\n\n",
                "red"
            ))
        else:
            # Attempt to perform action
            if action.type == "call":
                worker = self.get_worker(action.worker_id)
                worker.call()
            elif action.type == "spawn":
                worker = self.get_worker(action.worker_id)
                worker.spawn()
            elif action.type == "return":
                worker = self.get_worker(action.worker_id)
                worker.ret()
            elif action.type == "steal":
                thief = self.get_worker(action.thief_id)
                victim = self.get_worker(action.victim_id)
                thief.steal(victim)
            elif action.type == "sync":
                worker = self.get_worker(action.worker_id)
                worker.sync()
            # If action performed without error, add to history
            self.actions.append(action)

    def _print_full_frame_tree_helper(self, frame):
        """Returns a list of strings that represent `frame` as a tree."""
        str_comp = []
        str_comp.append("{}\n".format(frame))
        for i, child in enumerate(frame.children):
            child_str_comp = self._print_full_frame_tree_helper(child)
            if i < len(frame.children) - 1:
                # children up to the last child has vertical line in front
                str_comp.append("|-{}".format(child_str_comp[0]))
                for line in child_str_comp[1:]:
                    str_comp.append("| {}".format(line))
            else:
                # last child does not have vertical line in front
                str_comp.append("`-{}".format(child_str_comp[0]))
                for line in child_str_comp[1:]:
                    str_comp.append("  {}".format(line))
        return str_comp

    def print_state(self):
        """Print a representation of the state of the runtime system."""
        str_comp = []
        # Print full frame tree
        str_comp.append(color("Full frame tree:\n\n", "yellow"))
        str_comp.extend(self._print_full_frame_tree_helper(self.initial_frame))
        # Print worker deques
        str_comp.append(color("\n\nWorker deques:\n\n", "yellow"))
        for worker in self.workers.values():
            str_comp.append(color("Worker {}\n".format(worker.id), "blue"))
            str_comp.append(worker.print_state())
            str_comp.append("\n")
        return "".join(str_comp)

    def restore(self):
        """Restore the state of the RTS after performing actions in self.actions."""
        actions_to_restore = self.actions
        self.__init__(self.num_workers)
        # Restore actions
        for action in actions_to_restore:
            self.do_action(action)


class Worker(object):
    """
    Worker object that performs actions on its deque at various control points.
    """
    def __init__(self, id_):
        self.deque = Deque()
        self.id = id_  # identifier for this worker in the RTS

    def check_steal_valid(self, victim):
        if not self.deque.is_empty():
            raise InvalidActionError("Thief deque is not empty, cannot steal.")
        if len(victim.deque) <= 1:
            raise InvalidActionError("Victim does not have available stacklet "
                                     "to steal.")

    def steal(self, victim):
        """Steal from victim's deque, only keep top frame in stacklet."""
        self.check_steal_valid(victim)
        stolen_stacklet = victim.deque.pop_head()
        # remove all frames from stacklet except for youngest frame
        for frame in stolen_stacklet.frames:
            frame.worker = None
        youngest_frame = stolen_stacklet.youngest_frame
        youngest_frame.worker = self
        stolen_stacklet.frames = [youngest_frame]
        # add stolen stacklet to deque
        self.deque.push(stolen_stacklet)

    def check_sync_valid(self):
        if self.deque.is_empty():  # no frame on deque, nothing to sync
            raise InvalidActionError("There is no frame on deque to sync.")

    def sync(self):
        """Sync, either no-op or suspend frame (and empty deque)."""
        self.check_sync_valid()
        if not self.deque.is_single_frame():  # no-op
            return
        else:  # pop, try to provably good steal back
            cur_frame = self.deque.youngest_frame
            cur_frame.worker = None
            self.deque.pop()
            self.provably_good_steal(cur_frame)

    def check_spawn_valid(self):
        if self.deque.is_empty():  # no frame on deque, must steal first
            raise InvalidActionError("There is no frame on deque, cannot spawn.")

    def spawn(self):
        """Spawn, add a new frame on new stacklet."""
        self.check_spawn_valid()
        new_frame = Frame("spawn")
        new_frame.worker = self
        new_frame.attach(self.deque.youngest_frame)
        new_stacklet = Stacklet(new_frame)
        self.deque.push(new_stacklet)

    def check_call_valid(self):
        if self.deque.is_empty():  # no frame on deque, must steal first
            raise InvalidActionError("There is no frame on deque, cannot call.")

    def call(self):
        """Call, add a new frame on current stacklet."""
        self.check_call_valid()
        new_frame = Frame("call")
        new_frame.worker = self
        self.deque.youngest_stacklet.push(new_frame)

    def check_ret_valid(self):
        if self.deque.is_empty():
            raise InvalidActionError("There is no frame on deque to return.")
        if self.deque.youngest_frame.type == "initial":
            raise InvalidActionError("Cannot return from initial frame in this "
                                     "simulation.")
        if len(self.deque.youngest_frame.children) != 0:
            raise InvalidActionError("Frame has outstanding children, cannot "
                                     "return until all children are finished.")

    def ret(self):
        """Return from the last call or spawn, possible removing a stacklet."""
        self.check_ret_valid()
        ret_frame = self.deque.youngest_frame
        if ret_frame.type == "call":
            self.ret_from_call()
        elif ret_frame.type == "spawn":
            self.ret_from_spawn()
        else:
            raise AssertionError()

    def ret_from_call(self):
        ret_frame = self.deque.youngest_frame
        parent_frame = ret_frame.parent
        ret_frame.detach()
        if not self.deque.is_single_frame():
            self.deque.youngest_stacklet.pop()  # remove frame from stacklet
        else:
            self.deque.pop()  # destroy stacklet
            self.unconditional_steal(parent_frame)  # unconditional steal of parent

    def ret_from_spawn(self):
        ret_frame = self.deque.youngest_frame
        parent_frame = ret_frame.parent
        ret_frame.detach()
        self.deque.pop()  # remove stacklet
        if self.deque.is_empty():  # empty after removing last frame/stacklet
            self.provably_good_steal(parent_frame)  # try to steal parent

    def provably_good_steal(self, frame):
        """Provably good steal of frame."""
        assert(self.deque.is_empty())  # thief should have empty deque
        if (
            len(frame.children) == 0 and  # if no outstanding children
            frame.worker is None  # and not being worked on
        ):
            self.provably_good_steal_success(frame)

    def provably_good_steal_success(self, frame):
        frame.worker = self
        self.deque.push(Stacklet(frame))  # steal

    def unconditional_steal(self, frame):
        """Unconditional steal of frame."""
        assert(self.deque.is_empty() or frame.worker is not None)
        frame.worker = self
        self.deque.push(Stacklet(frame))  # steal

    def print_state(self):
        str_comp = []
        for i, stacklet in enumerate(self.deque):
            if i == len(self.deque) - 1:  # active stacklet, indicate by color
                str_comp.append(color(str(stacklet), "grey"))
            else:
                str_comp.append(str(stacklet))
            str_comp.append("\n")
        return "".join(str_comp)


class Deque(object):
    """
    Stores a deque of stacklets.
    """
    def __init__(self):
        self.deque = []  # beginning of list is head (steals), end is tail (work)

    def __len__(self):
        return len(self.deque)

    def __contains__(self, frame):
        return any(frame in stacklet for stacklet in self.deque)

    def __iter__(self):
        yield from self.deque

    @property
    def youngest_stacklet(self):
        assert(len(self.deque) != 0)
        return self.deque[-1]

    @property
    def youngest_frame(self):
        return self.youngest_stacklet.youngest_frame

    def push(self, stacklet):
        self.deque.append(stacklet)

    def pop(self):
        assert(len(self.deque) > 0)
        return self.deque.pop()

    def pop_head(self):
        assert(len(self.deque) > 0)
        return self.deque.pop(0)

    def is_empty(self):
        return len(self.deque) == 0

    def is_single_frame(self):
        return len(self.deque) == 1 and len(self.deque[0]) == 1


class Stacklet(object):
    """
    Stores a sequence of frames.
    """
    def __init__(self, first_frame):
        self.frames = [first_frame]  # first entry is oldest

    def __len__(self):
        return len(self.frames)

    def __contains__(self, frame):
        return frame in self.frames

    def __str__(self):
        str_comp = []
        for frame in self.frames:
            str_comp.append("{}\t\t".format(str(frame)))
        return "".join(str_comp)

    @property
    def youngest_frame(self):
        return self.frames[-1]

    @property
    def oldest_frame(self):
        return self.frames[0]

    def push(self, frame):
        """Add `frame` on top of the stacklet."""
        frame.attach(self.youngest_frame)
        self.frames.append(frame)

    def pop(self, index=-1):
        """Pop the top frame. Only valid if stacklet nonempty after."""
        assert(len(self.frames) > 1)
        self.frames.pop(index)


class Frame(object):
    """
    Stores parent/children pointers.
    """
    def __init__(self, frame_type):
        self.id = frame_id_assigner.assign()
        self.type = frame_type
        self.parent = None
        self.children = []
        self.worker = None

    def __str__(self):
        if self.worker is None:
            return "{} {}".format(self.type, self.id)
        else:
            return "{} {} (Worker {})".format(self.type, self.id, self.worker.id)

    def attach(self, parent):
        """Add self as child to frame `parent`."""
        assert(self.parent == None)
        parent.children.append(self)
        self.parent = parent

    def detach(self):
        """Remove self as child to parent frame."""
        self.parent.children.remove(self)
        self.parent = None
