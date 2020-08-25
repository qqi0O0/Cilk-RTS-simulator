#####
#
# Additional options for inputs:
#
# access (worker index) (splitter name)
# write (worker index) (splitter name)
#
#####


from copy import copy
from textwrap import dedent

from helpers import InvalidActionError


class SplitterTree(object):
    def __init__(self):
        """
        Holds 4 splitters.
        """
        # d values recorded in order from top to bottom, left to right
        self.d_values = [' ', ' ', ' ', ' ', ' ', ' ']  # space = NIL
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





t1 = SplitterTree()
print(t1)
t2 = t1.root_copy(1)
print(t2)
t3 = t2.path_copy('X', 'new-X')
print(t3)
t4 = t3.root_copy(2)
print(t4)
t5 = t4.path_copy('Y', 'new-Y')
print(t5)
