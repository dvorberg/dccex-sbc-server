import time
from ..baseclasses import Turnout

class Threeway(Turnout):
    left = 1
    middle = 0
    right = 2

    states = { left, middle, right, }

    def __init__(self, left_turnout:Turnout, right_turnout:Turnout):
        """
        This thinks itself as two consecutive turnouts in opposite
        directions, (left, right). If both turnouts are reset, vehicles
        will go streight. If the left turnout is thrown, they will go
        left and vice versa. Before a turnout is thrown, they will
        both be reset.
        """
        self.left_turnout = left_turnout
        self.right_turnout = right_turnout

    def reset(self):
        self.left_turnout.reset()
        self.right_turnout.reset()

    def throw_left(self):
        self.right_turnout.reset()
        self.left_turnout.throw()

    def throw_right(self):
        self.left_turnout.reset()
        self.right_turnout.throw()

    @property
    def thrown(self):
        return self.left_turnout.thrown() or self.right_turnout.thrown()

    @property
    def state(self) -> int:
        if self.left_turnout.thrown:
            return self.left
        elif self.right_turnout.thrown:
            return self.right
        else:
            return self.middle

    def set(self, state:int):
        if state == self.state:
            return

        if state == 0:
            self.reset()
        elif state == 1:
            self.throw_left()
        elif state == 2:
            self.throw_right()
        else:
            raise ValueError(state)

class Cross(Turnout):
    """
    This models a symmetrical cross like Märklin 2260 as two
    regular turnouts that face the same way.

    There are four ways over the cross:
    - Diagonally, when both virtual turnouts are reset (ab).
    - Diagonally the other way, when both turnouts are thrown (AB).
    - Around one curve, when only one virtual turnout is thrown (Ab).
    - Around the other curve, when the only other is thrown (aB).

    A sketch and a little try and error help: Draw the main line and
    one turnouts on either side facing away from another. The main
    line’s end points are a and b. The turnout’s ends are A and B.
    """

    ab = 0
    Ab = 1
    aB = 2
    AB = 3

    states = { ab, Ab, aB, AB, }

    def __init__(self, a:Turnout, b:Turnout):
        self._a = a
        self._b = b

    def reset(self):
        self._a.reset()
        self._b.reset()

    @property
    def thrown(self):
        return self._a.thrown() or self._b.thrown()

    @property
    def state(self) -> int:
        # Ah, nothing like a little binary arithmetic to get the brain cells
        # going! Feels like writing C. Too bad this thing doesn’t have
        # pointer arithmetic. — Then again: not really.
        return self._a.state | self._b.state << 1

    def set(self, state:int):
        if state == self.state:
            return

        self._a.set(state & 1)
        self._b.set(state & 2)

    def throw_ab(self):
        self.set(self.ab)

    def throw_Ab(self):
        self.set(self.Ab)

    def throw_aB(self):
        self.set(self.aB)

    def throw_AB(self):
        self.set(self.AB)
