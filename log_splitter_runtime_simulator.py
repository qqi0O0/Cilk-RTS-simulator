#####
#
# Additional options for inputs:
#
# access (worker id) (splitter name)
# write (worker id) (splitter name)
#
#####


from copy import copy

from helpers import (
    color, frame_id_assigner, InvalidActionError, ActionParseError, Action
)
import base_runtime_simulator as base


def parse_action(s):
    try:
        s_comp = s.split()
        action_type = s_comp[0]
        if action_type == "access":
            action = Action(action_type, worker_id=s_comp[1],
                            splitter_name=s_comp[2])
        elif action_type == "write":
            action = Action(action_type, worker_id=s_comp[1],
                            splitter_name=s_comp[2], splitter_value=s_comp[3])
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
        self.workers = {}
        for i in range(self.num_workers):
            worker_id = chr(65 + i)  # chr(65) = A
            self.workers[worker_id] = Worker(worker_id)
        # One worker starts with initial frame
        self.initial_frame = base.Frame("initial")
        init_worker = self.workers['A']
        init_worker.deque.push(base.Stacklet(self.initial_frame))
        self.initial_frame.worker = self.workers['A']
        # That worker starts with a basic record
        init_worker.record_deque.append(Record())
        # Keep track of all actions, for restoring
        self.actions = []

    def do_action(self, action):
        if action.type == "access":
            worker = self.get_worker(action.worker_id)
            worker.access(action.splitter_name)
            self.actions.append(action)
        else:  # base action
            super().do_action(action)


class Worker(base.Worker):
    def __init__(self, id_):
        super().__init__(id_)
        self.record_deque = []  # list of records
        self.cache = set()  # Just splitter name is ok, just maps to the leaf

    @property
    def cur_record(self):
        assert(len(self.record_deque) != 0)
        return self.record_deque[-1]

    @property
    def cur_tree(self):
        return self.cur_record.tree

    def access(self, splitter_name):
        if self.deque.is_empty():
            raise InvalidActionError("Cannot access splitter from empty worker")
        leaf_array = self.cur_record.tree.get_leaf_array(splitter_name)
        if splitter_name in self.cache:
            return leaf_array[-1][1]  # last pair, value in (d, v) pair has index 1
        # Otherwise, not in cache
        # First, figure out right depth to search at
        search_d = self.cur_tree.get_depth(splitter_name)
        assert(search_d is not None)
        # Second, search for the right value
        target_v = self.cur_tree.search_leaf(splitter_name, search_d)
        # Third, path copy
        new_tree = self.cur_tree.path_copy(splitter_name, target_v)
        # Finally, update record and cache
        self.cur_record.tree = new_tree
        self.cache.add(splitter_name)

    def print_state(self):
        str_comp = []
        for stacklet, record in zip(self.deque, self.record_deque):
            str_comp.append(str(stacklet))
            str_comp.append("\n")
            str_comp.append(color(str(record), "purple"))
            str_comp.append("\n")
        str_comp.append("Cache: ")
        str_comp.append(str(self.cache))
        str_comp.append("\n")
        return "".join(str_comp)


class Record(object):
    def __init__(self, tree=None):
        self.tree = tree
        if self.tree is None:
            self.tree = SplitterTree()
        self.simple_log = []
        self.complex_log = []

    def __str__(self):
        s = "{}\nSimple log: {}\nComplex log: {}".format(
            self.tree, self.simple_log, self.complex_log)
        return s


class SplitterTree(object):
    def __init__(self):
        """
        Holds 4 splitters.
        """
        # d values recorded in order from top to bottom, left to right
        # self.d_values = [' ', ' ', ' ', ' ', ' ', ' ']  # space = NIL
        self.d_values = [0, 0, ' ', ' ', ' ', ' ']  # space = NIL
        self.splitter_names = ['W', 'X', 'Y', 'Z']
        self.leaf_arrays = [
            [(-1, "init-W")],  # depth of -1, same idea as depth of -infty
            [(-1, "init-X")],
            [(-1, "init-Y")],
            [(-1, "init-Z")],
        ]

    def __str__(self):
        #       .
        #      / \
        #    1/   \2
        #    /     \
        #   .       . 
        # 3/ \4   5/ \6
        # W   X   Y   Z
        # array contents on the right of the tree
        lines = [
            "      .",
            "     / \\",
            "   {}/   \\{}".format(*self.d_values[:2]),
            "   /     \\",
            "  .       . ",
            "{}/ \\{}   {}/ \\{}".format(*self.d_values[2:]),
            "W   X   Y   Z",
        ]
        lines = [line.ljust(25) for line in lines]
        # Put array contents on the right
        for i, (name, array) in enumerate(zip(self.splitter_names, self.leaf_arrays)):
            lines[i + 2] += "{}: {}".format(name, array)
        return '\n'.join(lines)

    def get_edge_indices(self, leaf_index):
        """
        Return the edge indices on the root-to-leaf path to the leaf at the
        given leaf index.
        """
        first_index = 0 if leaf_index <= 1 else 1
        second_index = 2 + 2 * first_index + (0 if leaf_index % 2 == 0 else 1)
        return (first_index, second_index)

    def get_depth(self, leaf):
        leaf_index = self.get_leaf_index(leaf)
        edge_indices = self.get_edge_indices(leaf_index)
        for i in range(len(edge_indices) - 1, - 1, -1):
            if self.d_values[edge_indices[i]] != ' ':
                return self.d_values[edge_indices[i]]
        return None  # depth of NIL

    def get_sibling_edge_index(self, edge_index):
        """
        Return the 'sibling' of the edge at the given index, i.e. the edge that
        starts from the same parent but goes to a different child.
        """
        base = (edge_index // 2) * 2
        return (2 * base + 1 - edge_index)

    def get_leaf_index(self, leaf):
        if leaf not in self.splitter_names:
            raise InvalidActionError("Splitter {} does not exist.".format(leaf))
        return self.splitter_names.index(leaf)

    def get_leaf_array(self, leaf):
        return self.leaf_arrays[self.get_leaf_index(leaf)]

    def search_leaf(self, leaf, d):
        """
        Returns the value v from the pair (d', v) in the array corresponding to
        the leaf, such that d' is the largest value that is less than or equal
        to d.
        """
        array = self.get_leaf_array(leaf)
        # This "should" be a binary search, but who cares
        last_v = None
        for d_, v in array:
            if d_ > d:
                assert(last_v is not None)
                return last_v
            last_v = v
        # Loop done, we want last element
        return last_v

    def path_copy(self, leaf, value):
        """
        leaf is one of the characters in self.splitter_names.
        Return a new SplitterTree, such that the depth of the specified leaf is
        NIL and the array at the specified leaf only contains (-1, value), and
        the depth of all other leafs is unchanged.
        """
        leaf_index = self.get_leaf_index(leaf)
        new_splitter_tree = SplitterTree()
        # Set leaves
        new_splitter_tree.leaf_arrays = self.leaf_arrays
        new_splitter_tree.leaf_arrays[leaf_index] = [(-1, value)]
        # Update edge weights
        new_d_values = copy(self.d_values)
        first_index, second_index = self.get_edge_indices(leaf_index)
        # First level edge weight
        latest_d = new_d_values[first_index]
        new_d_values[first_index] = ' '
        # Second level edge weight
        sibling_index = self.get_sibling_edge_index(second_index)
        if new_d_values[sibling_index] == ' ':
            new_d_values[sibling_index] = latest_d
        new_d_values[second_index] = ' '
        new_splitter_tree.d_values = new_d_values
        return new_splitter_tree

    def root_copy(self, d):
        """
        Return a new SplitterTree, such that the depth of any leaf that was
        previously NIL is now d, any the depth of any leaf that was previously
        not NIL is still not NIL.
        """
        new_splitter_tree = SplitterTree()
        # Set leaves
        new_splitter_tree.leaf_arrays = self.leaf_arrays
        # Update weights at root
        new_d_values = copy(self.d_values)
        if new_d_values[0] == ' ':
            new_d_values[0] = d
        if new_d_values[1] == ' ':
            new_d_values[1] = d
        new_splitter_tree.d_values = new_d_values
        return new_splitter_tree





# t1 = SplitterTree()
# print(t1)
# t2 = t1.root_copy(1)
# print(t2)
# t3 = t2.path_copy('X', 'new-X')
# print(t3)
# t4 = t3.root_copy(2)
# print(t4)
# t5 = t4.path_copy('Y', 'new-Y')
# print(t5)
