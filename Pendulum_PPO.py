import click
from collections import namedtuple
import gym
import numpy as np
import os
import pickle
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Normal

# References:
# https://arxiv.org/abs/1707.06347

SAVE_FILE_PATH = "Pendulum-PPO.torch"

class Actor(nn.Module):

    HIDDEN_LAYER_SIZE = 128

    def __init__(self, inputs, outputs_range):
        super(Actor, self).__init__()

        self.scale = torch.tensor((outputs_range[1] - outputs_range[0]) / 2.0)

        self.h1_mean = nn.Linear(inputs, self.HIDDEN_LAYER_SIZE)
        self.pi_mean = nn.Linear(self.HIDDEN_LAYER_SIZE, 1)

        self.h1_std = nn.Linear(inputs, self.HIDDEN_LAYER_SIZE)
        self.pi_std = nn.Linear(self.HIDDEN_LAYER_SIZE, 1)

    def forward(self, x):

        x_mean = F.relu(self.h1_mean(x))
        mean = torch.tanh(self.pi_mean(x_mean)) * self.scale

        x_std = F.relu(self.h1_std(x))
        std = F.softplus(self.pi_std(x_std))

        return mean, std

class Critic(nn.Module):

    HIDDEN_LAYER_SIZE = 128

    def __init__(self, inputs):
        super(Critic, self).__init__()

        self.h1 = nn.Linear(inputs, self.HIDDEN_LAYER_SIZE)
        self.v = nn.Linear(self.HIDDEN_LAYER_SIZE, 1)

    def forward(self, x):

        x = F.relu(self.h1(x))
        return self.v(x)

class PPO:

    ALPHA = 5e-5
    GAMMA = 0.9
    EPSILON = 2e-1
    ENTROPY = 1e-6
    VALUE = 1e-6
    EPOCH = 10
    MEMORY_SIZE = 10000.0
    BATCH_SIZE = 32
    UPDATE = 1

    experience = namedtuple('Experience', ('s', 's2', 'r', 'a', 'done', 'old_log_prob'))

    memory = []
    update = 0

    def __init__(self, inputs, outputs_range):

        self.outputs_range = [outputs_range[0][0], outputs_range[1][0]]

        self.actor = Actor(inputs, outputs_range)
        self.critic = Critic(inputs)

        self.optimizer_actor = torch.optim.Adam(self.actor.parameters(), lr=self.ALPHA)
        self.optimizer_critic = torch.optim.Adam(self.critic.parameters(), lr=self.ALPHA)

    def action(self, s):

        with torch.no_grad():
            pi_mean, pi_std = self.actor(torch.as_tensor(s).float())

        pi = Normal(pi_mean, pi_std)
        a = pi.sample()

        return a.clamp(self.outputs_range[0], self.outputs_range[1]), pi.log_prob(a)

    def store(self, *args):

        self.memory.append(self.experience(*args))

        # If no more memory for memory, removes the first one
        if len(self.memory) > self.MEMORY_SIZE:
            self.memory.pop(0)

    def train(self):

        if len(self.memory) < self.BATCH_SIZE:
            return

        self.update += 1

        # Train the network each UPDATE episode
        if self.update % self.UPDATE != 0:
            return

        samples = random.sample(self.memory, self.BATCH_SIZE)
        batch = self.experience(*zip(*samples))

        states = torch.as_tensor(batch.s).float()
        next_states = torch.as_tensor(batch.s2).float()
        actions = torch.as_tensor(batch.a)
        rewards = torch.as_tensor(batch.r)
        done = torch.as_tensor(batch.done)
        q = torch.zeros([self.BATCH_SIZE, 1])
        old_log_prob = torch.as_tensor(batch.old_log_prob)

        with torch.no_grad():

            v2 = self.critic(next_states).detach()
            v = self.critic(states)

            # The terminal state is not considered as it doesn't change from
            # the other state
            for i in range(self.BATCH_SIZE):
                q[i] = rewards[i] + self.GAMMA * v2[i]

            adv = (q - v)

        for i in range(self.EPOCH):

            surr = torch.zeros(self.BATCH_SIZE)
            entropy = torch.zeros(self.BATCH_SIZE)

            pi_mean, pi_std = self.actor(states)
            v = self.critic(states)

            for y in range(self.BATCH_SIZE):

                pi = Normal(pi_mean[y], pi_std[y])
                entropy[y] = pi.entropy()

                ratio = torch.exp(pi.log_prob(actions[y]) - (old_log_prob[y] + 1e-10))
                clip = ratio.clamp(1.0 - self.EPSILON, 1.0 + self.EPSILON)
                surr[y] = torch.min(ratio * adv[y], clip * adv[y])

            loss_critic = torch.nn.MSELoss()(v, q)
            loss_critic_detached = loss_critic.clone().detach()

            loss_actor = \
                - surr.mean() + \
                self. VALUE * loss_critic_detached - \
                self.ENTROPY * entropy.mean()

            self.optimizer_critic.zero_grad()
            loss_critic.backward()
            self.optimizer_critic.step()

            self.optimizer_actor.zero_grad()
            loss_actor.backward()
            self.optimizer_actor.step()

def play_agent(env, agent):

    results = []
    episodes = 0

    while 1:

        steps = 0
        s = env.reset()

        while 1:

            env.render()
            a, _ = agent.action(s)
            s, r, done, _ = env.step(a)

            steps += 1

            if done:

                episodes += 1

                print("Episode", episodes,
                      "finished after", steps)

                break

def train_agent(env, agent):

    episode = 0
    results = np.full(100, -2000).tolist()

    while 1:

        rewards = 0
        s = env.reset()

        while 1:

            a, log_prob = agent.action(s)
            s2, r, done, _ = env.step(a)

            rewards += r

            # reward betweem -16.2736044 to 0
            r = (r / 16.2736044) + 0.5

            agent.store(s, s2, r, a, done, log_prob)
            agent.train()

            s = s2

            if done:

                # Calcul the score total over 100 episodes
                results.append(rewards)
                if len(results) > 100:
                    results.pop(0)

                score = np.sum(np.asarray(results)) / 100

                if score >= -300:
                    print("Finished!!!")
                    torch.save((agent.critic.state_dict(), agent.actor.state_dict()), SAVE_FILE_PATH)
                    exit()

                episode += 1

                print("Episode", episode,
                      "rewards", rewards,
                      "score", score)

                # Save the state of the agent
                if episode % 20 == 0:
                    torch.save((agent.critic.state_dict(), agent.actor.state_dict()), SAVE_FILE_PATH)

                break

def clean_agent():
    os.remove(SAVE_FILE_PATH)

@click.command()
@click.option('--play', flag_value='play', default=False)
@click.option('--train', flag_value='train', default=True)
@click.option('--clean', flag_value='clean', default=False)
def run(play, train, clean):

    if clean:
        clean_agent()
        exit()

    # Start OpenAI environment
    env = gym.make('Pendulum-v0')

    # Create an agent
    agent = PPO(
        env.observation_space.shape[0], [env.action_space.low, env.action_space.high])

    try:
        critic, actor = torch.load(SAVE_FILE_PATH)
        agent.critic.load_state_dict(critic)
        agent.actor.load_state_dict(actor)

        print("Agent loaded!!!")
    except:
        print("Agent created!!!")

    if play:
        agent.critic.eval()
        agent.actor.eval()
        play_agent(env, agent)
    elif train:
        train_agent(env, agent)


if __name__ == '__main__':
    run()
