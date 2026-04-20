import time
from ..baseclasses import Turnout

import icecream; icecream.install()

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
    regular turnouts that face in opposite ways.

    There are four ways over the cross:
    - Diagonally, when both virtual turnouts are reset (AB).
    - Diagonally the other way, when both turnouts are thrown (ab).
    - Around one curve, when only one virtual turnout is thrown (Aa).
    - Around the other curve, when the only other is thrown (Bb).

            b
             \
              \
    A ----------------------B
                \
                 \
                  a
    """

    AB = 0
    Aa = 1
    bB = 2
    ab = 3

    states = { AB, Aa, bB, ab }

    def __init__(self, a:Turnout, b:Turnout):
        self.a = a
        self.b = b

    def reset(self):
        self.a.reset()
        self.b.reset()

    @property
    def thrown(self):
        return self.a.thrown() or self.b.thrown()

    @property
    def state(self) -> int:
        return self.a.state | self.b.state << 1

    def set(self, state:int):
        if state == self.state:
            return

        ic(state)
        self.a.set(state & 1)
        self.b.set( (state & 2) >> 1 )

    def throw_AB(self):
        self.set(self.AA)

    def throw_Aa(self):
        self.set(self.Aa)

    def throw_bB(self):
        self.set(self.bB)

    def throw_ab(self):
        self.set(self.ab)

        
