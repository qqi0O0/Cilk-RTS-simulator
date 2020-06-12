#####
#
# Options for inputs:
#
# undo
# call (worker index)
# spawn (worker index)
# return (worker index)
# steal (thief index) (victim index)
# sync (worker index)
#
#####


from enum import Enum, auto


ID = 0

def assign_id():
    global ID
    to_return = ID
    ID += 1
    return to_return

def reset_id():
    global ID
    ID = 0


class ActionType(Enum):
    UNDO = "undo"
    CALL = "call"
    SPAWN = "spawn"
    RETURN = "return"  # return from spawn or call
    STEAL = "steal"
    SYNC = "sync"  # may cause a suspended frame

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

def parse_action(s):
    """Parse string s, return an Action object."""
    try:
        s_comp = s.split()
        action_type = ActionType(s_comp[0])
        if action_type is ActionType.UNDO:
            action = Action(action_type)
        elif action_type is ActionType.CALL:
            action = Action(action_type, worker_index=int(s_comp[1]))
        elif action_type is ActionType.SPAWN:
            action = Action(action_type, worker_index=int(s_comp[1]))
        elif action_type is ActionType.RETURN:
            action = Action(action_type, worker_index=int(s_comp[1]))
        elif action_type is ActionType.STEAL:
            action = Action(action_type, thief_index=int(s_comp[1]),
                            victim_index=int(s_comp[2]))
        elif action_type is ActionType.SYNC:
            action = Action(action_type, worker_index=int(s_comp[1]))
        return action
    except:
        raise ActionParseError()


class RTS(object):
    def __init__(self, num_workers):
        reset_id()
        self.num_workers = num_workers
        # Initialize blank workers
        self.workers = []
        for i in range(self.num_workers):
            self.workers.append(Worker(i))
        # One worker starts with initial frame
        self.initial_frame = Frame("initial")
        self.workers[0].deque.push(Stacklet(self.initial_frame))
        self.initial_frame.worker = self.workers[0]
        # Keep track of all actions, for restoring
        self.actions = []

    def do_action(self, action):
        if action.type is ActionType.UNDO:
            if len(self.actions) > 0:
                self.actions.pop()
            self.restore()
        else:
            # Attempt to perform action
            if action.type is ActionType.CALL:
                worker = self.workers[action.worker_index]
                worker.call()
            elif action.type is ActionType.SPAWN:
                worker = self.workers[action.worker_index]
                worker.spawn()
            elif action.type is ActionType.RETURN:
                worker = self.workers[action.worker_index]
                worker.ret()
            elif action.type is ActionType.STEAL:
                thief = self.workers[action.thief_index]
                victim = self.workers[action.victim_index]
                thief.steal(victim)
            elif action.type is ActionType.SYNC:
                worker = self.workers[action.worker_index]
                worker.sync()
            # If action performed without error, add to history
            self.actions.append(action)

    def _print_full_frame_tree_helper(self, frame, level):
        indent = "  " * level
        str_comp = []
        str_comp.append("{}{}\n".format(indent, frame))
        for child in frame.children:
            str_comp.append(self._print_full_frame_tree_helper(child, level + 1))
        return "".join(str_comp)

    def print_state(self):
        """Print a representation of the state of the runtime system."""
        str_comp = []
        # Print full frame tree
        str_comp.append("Full frame tree:\n\n")
        str_comp.append(self._print_full_frame_tree_helper(self.initial_frame, 0))
        # Print worker deques
        str_comp.append("\n\nWorker deques:\n\n")
        for worker in self.workers:
            str_comp.append("* Worker {} *\n".format(worker.index))
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
    def __init__(self, index):
        self.deque = Deque()
        self.index = index  # identifier for this worker in the RTS

    def steal(self, victim):
        """Steal from victim's deque, only keep top frame in stacklet."""
        if not self.deque.is_empty():
            raise InvalidActionError("Thief deque is not empty, cannot steal.")
        if len(victim.deque) <= 1:
            raise InvalidActionError("Victim does not have available stacklet "
                                     "to steal.")
        stolen_stacklet = victim.deque.pop_head()
        # remove all frames from stacklet except for youngest frame
        for frame in stolen_stacklet.frames:
            frame.worker = None
        youngest_frame = stolen_stacklet.youngest_frame
        youngest_frame.worker = self
        stolen_stacklet.frames = [youngest_frame]
        # add stolen stacklet to deque
        self.deque.push(stolen_stacklet)

    def sync(self):
        """Sync, either no-op or suspend frame (and empty deque)."""
        if self.deque.is_empty():  # no frame on deque, nothing to sync
            raise InvalidActionError("There is no frame on deque to sync.")
        cur_frame = self.deque.youngest_frame
        if len(cur_frame.children) == 0:  # no-op
            return
        else:  # suspend
            assert(self.deque.is_single_frame())
            cur_frame.worker = None
            self.deque.pop()

    def spawn(self):
        """Spawn, add a new frame on new stacklet."""
        if self.deque.is_empty():  # no frame on deque, must steal first
            raise InvalidActionError("There is no frame on deque, cannot spawn.")
        new_frame = Frame("spawn")
        new_frame.worker = self
        new_frame.attach(self.deque.youngest_frame)
        new_stacklet = Stacklet(new_frame)
        self.deque.push(new_stacklet)

    def call(self):
        """Call, add a new frame on current stacklet."""
        if self.deque.is_empty():  # no frame on deque, must steal first
            raise InvalidActionError("There is no frame on deque, cannot call.")
        new_frame = Frame("call")
        new_frame.worker = self
        self.deque.youngest_stacklet.push(new_frame)

    def ret(self):
        """Return from the last call or spawn, possible removing a stacklet."""
        if self.deque.is_empty():
            raise InvalidActionError("There is no frame on deque to return.")
        if self.deque.youngest_frame.type == "initial":
            raise InvalidActionError("Cannot return from initial frame in this "
                                     "simulation.")
        if len(self.deque.youngest_frame.children) != 0:
            raise InvalidActionError("Frame has outstanding children, cannot "
                                     "return until all children are finished.")
        ret_frame = self.deque.youngest_frame
        ret_frame.worker = None
        parent_frame = ret_frame.parent
        ret_frame.detach()
        if len(self.deque.youngest_stacklet) == 1:  # last frame of stacklet
            self.deque.pop()  # destroy stacklet
        else:  # not last frame of stacklet
            self.deque.youngest_stacklet.pop()  # remove frame from stacklet
        # If deque now empty, attempt to steal parent
        if self.deque.is_empty():
            self._psteal(parent_frame)

    def _psteal(self, parent_frame):
        """Provably good/unconditional steal of parent."""
        if not self.deque.is_empty():
            # this shouldn't happen, _psteal should only be called in situations
            # where a provably good/unconditional steal can happen, so where the
            # thief's deque is empty.
            raise AssertionError()
        if (
            len(parent_frame.children) == 0 and  # if no outstanding children
            parent_frame.worker is None  # and not being worked on
        ):
            parent_frame.worker = self
            self.deque.push(Stacklet(parent_frame))  # steal parent

    def print_state(self):
        str_comp = []
        for stacklet in self.deque:
            for frame in stacklet.frames:
                str_comp.append("{}\t\t".format(str(frame)))
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
        self.id = assign_id()
        self.type = frame_type
        self.parent = None
        self.children = []
        self.worker = None

    def __str__(self):
        if self.worker is None:
            return "{} {}".format(self.type, self.id)
        else:
            return "{} {} (Worker {})".format(self.type, self.id, self.worker.index)

    def attach(self, parent):
        """Add self as child to frame `parent`."""
        assert(self.parent == None)
        parent.children.append(self)
        self.parent = parent

    def detach(self):
        """Remove self as child to parent frame."""
        self.parent.children.remove(self)
        self.parent = None


rts = RTS(4)  # 4 workers


# Main loop
while True:
    print(rts.print_state())
    print("> ", end="")
    # User describes action, perform action
    inp = input()
    print("\n")
    try:
        action = parse_action(inp)
    except ActionParseError:
        print(">> Unable to parse action\n\n")
        continue
    try:
        rts.do_action(action)
    except InvalidActionError as e:
        print(">> Invalid action: {}\n\n".format(e))
        rts.restore()
