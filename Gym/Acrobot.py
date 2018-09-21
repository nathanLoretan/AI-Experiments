# -*- coding: utf-8 -*-
"""
@author: Nathan Loretan
"""

import sys
import gym
import time
import math
import numpy as np
from math import sqrt, exp
from random import randint
from collections import defaultdict

def relu(x):
    x[x < 0] = 0
    return x

def sigmoid(x):
      return 1.0 / (1.0 + np.exp(-x))

def softmax(x):
     e = np.exp(x, dtype=np.float)
     return e / np.sum(e)

class PolicyGradient():

    def __init__(self, out, inp, alpha=0.9, gamma=0.9):

        # alpha     learning factor
        # gamma     reward factor
        # A         list of possible actions
        # s         state
        # a         action
        # r         reward
        # pi         policy

        self.gamma    = gamma
        self.alpha    = alpha
        self.s        = None
        self.a        = None
        self.l        = None
        self.pi       = None
        self.w        = np.random.uniform(-0.1, 0.1, (out, inp))
        self.b        = np.zeros(out)
        self.epi      = []

    def reset(self):

        self.s  = None
        self.a  = None
        self.r  = None
        self.l  = None
        self.pi = None

        self.epi = []

    def update(self):

        dw = np.zeros(self.w.shape)
        db = np.zeros(self.b.shape)

        for r, s, a, l in self.epi:

            l, pi = l

            # gradient = (l(s,a) - E[l(s, .)]) * r
            grad = np.zeros(len(pi))
            grad[a] = (l[a] - np.dot(l, pi)) * r
            dw += self.alpha * grad[np.newaxis, :].T * np.asarray(s)
            db += self.alpha * grad

        self.w += dw
        self.b += db

        self.epi = []

    def __call__(self, ns, r):

        s  = self.s
        a  = self.a
        l  = self.l

        if s is not None:

            # Save the step
            s = tuple(s)
            self.epi.append((r, s, a, l))

            # Calculate the discount reward
            for i in range(len(self.epi)-2, -1, -1):
                _r, _s, _a, _l = self.epi[i]
                _r += r * self.gamma**(len(self.epi)-1-i)
                self.epi[i] = _r, _s, _a, _l

        # Calculate the policy and select the next action
        l = np.dot(self.w, ns) + self.b
        pi = softmax(l)

        self.a  = np.random.choice(len(pi), 1, p=pi)[0]
        self.s  = ns
        self.l  = (l, pi)

        return self.a

# STATE:
# ------
# cos(theta1) sin(theta1) cos(theta2) sin(theta2) thetaDot1 thetaDot2

# ACTIONS:
# --------
# +1, 0 or -1

EPSIODES = 10000
ALPHA = 0.01
GAMMA = 0.7

if __name__ == "__main__":

    env = gym.make('Acrobot-v1')
    agent = PolicyGradient(3, 6, ALPHA, GAMMA)

    score = 0.0

    for e in range(EPSIODES):

        t = 0
        r = 0
        R = 0
        s = env.reset()

        ref_x = s[0]+s[2]
        ref_y = s[1]

        while True:

            env.render()

            if ref_x > s[0]+s[2] and ref_y * s[1] < 0 and s[4]*s[5] > 0:
                a = agent(s, (2 - s[0] - s[2]))
                ref_x = s[0]+s[2]
                ref_y = s[1]
            else:
                a = agent(s, 0)

            s, r, done, info = env.step(a)

            R += r

            if done:
                if t+1 >= 500:
                    agent(s, -10)
                else:
                    agent(s, 10)

                score += R
                print "Episode {} finished after {} timesteps, score {}"\
                                                .format(e+1, t+1, score/(e+1))
                break


            t += 1

        agent.update()
        agent.reset()