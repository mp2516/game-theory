from mesa.datacollection import DataCollector
from mesa.space import SingleGrid
from mesa import Model
from mesa.time import RandomActivation
from .agent import RPSAgent
import numpy as np
import random
from .logger import logger

def key(x, y):
    """
    Args:
        x: x value
        y: y value
    Returns:
        Cantor pair function of x and y (maps two integers to one).
    Notes:
        See: https://en.wikipedia.org/wiki/Pairing_function#Cantor_pairing_function
    """
    return int(0.5 * (x + y) * (x + y + 1) + y)


def biome_boundaries(initial_population_probabilities, width):
    """
    Args:
        initial_population_probabilities: the proportion of the grid that is filled with each probability
        width: the length along one edge of the grid
    Returns:
        A list of x values which indicate the boundaries of the biomes with the least possible error from the
        initial_population_probabilities.
    Notes:
        This is a form of allocation problem, here I have used the algorithm called the Hungarian Algorithm
        https://hackernoon.com/the-assignment-problem-calculating-the-minimum-matrix-sum-python-1bba7d15252d
    """
    exact_split = [(prob*width) for prob in initial_population_probabilities]
    probs_round = [int(np.floor(split)) for split in exact_split]
    remainder = [(exact_split[i] - prob_round) for (i, prob_round) in enumerate(probs_round)]
    while sum(probs_round) < width:
        index = int(np.argmax(remainder))
        probs_round[index] += 1
        remainder[index] = 0
    probs_round.append(0)
    probs_round.sort()
    cumulative = np.cumsum(probs_round)
    # this ensures that the strategy generation goes onto the last column in the grid
    cumulative[-1] += 1
    return cumulative


class GameGrid(Model):
    ''' Model class for iterated, spatial prisoner's dilemma model. '''

    # This dictionary holds the payoff for the agent that makes the first move in the key
    # keyed on: (my_move, other_move)

    def __init__(self, config):
        '''
        Create a new Spatial Game Model

        Args:
            self.dimension: GameGrid size. There will be one agent per grid cell.
            self.num_moves_per_set: The number of moves each player makes with each other before evolving
            self.game_type: The type of game to play
            self.game_mode: The mode of that game to play
            self.cull_score: The minimum score a player must achieve in order to survive
        '''
        super().__init__()

        if config['square']:
            self.dimension = config['dimension']
            self.grid = SingleGrid(self.dimension, self.dimension, torus=config['periodic_BC'])
            self.height = self.dimension
            self.width = self.dimension
        else:
            self.height = config['height']
            self.width = config['width']
            self.dimension = self.width
            self.grid = SingleGrid(self.width, self.height, torus=config['periodic_BC'])

        self.step_num = 0

        self.num_moves_per_set = config['num_moves_per_set']

        self.initial_population_sizes = config['initial_population_sizes']
        self.biomes = config['biomes']
        if self.biomes:
            self.biome_boundaries = biome_boundaries(self.initial_population_sizes, self.width)

        self.cull_score = config['cull_score']
        self.kill_crowded = config['kill_crowded']

        self.probability_adoption = config['probability_adoption']
        self.probability_mutation = config['probability_mutation']
        self.probability_exchange = config['probability_exchange']
        self.probability_playing = config['probability_playing']
        self.probability_death = config['probability_death']

        self.agent_strategies = config['agent_strategies']
        self.agent_moves = config['agent_moves']

        self.schedule = RandomActivation(self)
        self.running = True

        # self.datacollector_populations = DataCollector()
        # self.datacollector_probabilities = DataCollector()

        self.num_mutating = 0
        self.fraction_mutating = 0

        self.num_dead = 0
        self.num_dying = 0
        self.num_evolving = 0
        self.fraction_evolving = 0
        self.crowded_players = []

    def run(self, n):
        ''' Run the model for n steps. '''
        for _ in range(n):
            self.step()


    @staticmethod
    def count_populations(model, agent_strategy):
        """
        Helper method to count agents with a given strategy in a given model.
        """
        count_pop = 0
        for agent in model.schedule.agents:
            if agent.strategy == agent_strategy:
                count_pop += 1
        return count_pop

    @staticmethod
    def count_scores(model, agent_strategy):
        """
        Helper method to count total scores in a given condition in a given model.
        """
        count_score = 0
        for agent in model.schedule.agents:
            if agent.strategy == agent_strategy:
                count_score += agent.total_score
        return count_score


class RPSModel(GameGrid):
    def __init__(self, config):
        super().__init__(config)
        self.epsilon = config['epsilon']
        self.payoff = {("R", "R"): 0,
                       ("R", "P"): -self.epsilon,
                       ("R", "S"): 1,
                       ("R", "E"): 0,
                       ("P", "R"): 1,
                       ("P", "P"): 0,
                       ("P", "S"): -self.epsilon,
                       ("P", "E"): 0,
                       ("S", "R"): -self.epsilon,
                       ("S", "P"): 1,
                       ("S", "S"): 0,
                       ("S", "E"): 0,
                       ("E", "R"): 0,
                       ("E", "P"): 0,
                       ("E", "S"): 0,
                       ("E", "E"): 0}

        for x in range(self.width):
            for y in range(self.height):
                agent = RPSAgent([x, y], self)
                self.grid.place_agent(agent, (x, y))
                self.schedule.add(agent)

        self.datacollector_population = DataCollector(
            {"Rock": lambda m: self.count_populations(m, "all_r"),
             "Paper": lambda m: self.count_populations(m, "all_p"),
             "Scissors": lambda m: self.count_populations(m, "all_s")}
        )

        self.datacollector_score = DataCollector(
            {"Rock Scores": lambda m: self.count_scores(m, "all_r"),
             "Paper Scores": lambda m: self.count_scores(m, "all_p"),
             "Scissors Scores": lambda m: self.count_scores(m, "all_s")}
        )

        if self.probability_mutation > 0:
            self.datacollector_mutating_agents = DataCollector(
                {"Num Mutating Agents": "fraction_mutating"}
            )

        self.datacollector_evolving_agents = DataCollector(
            {"Num Evolving Agents": "fraction_evolving"}
        )

    def step(self):
        self.step_num += 1
        logger.warn("STEP NUMBER: {} \n".format(self.step_num))

        if self.probability_mutation > 0:
            self.num_mutating = 0
        self.num_evolving = 0
        self.num_dying = 0

        for agent in self.schedule.agents:
            agent.increment_score()
        for agent in self.schedule.agents:
            agent.kill_weak()
        for agent in self.schedule.agents:
            logger.warn("\nAgent {} is being reproduced, mutated and updated".format(agent.unique_id))
            agent.reproduce_strong()
        for agent in self.schedule.agents:
            agent.update_strategy()
            agent.implement_strategy()
        for agent in self.schedule.agents:
            agent.exchange()

        logger.warn("\nThere are in total:"
                     "\n{} agents dead"
                     "\n{} agents evolving"
                     "\n{} mutating"
                     "\n{} who were below the cull threshold".format(
            self.num_dead, self.num_evolving, self.num_mutating, self.num_dying
        ))

        if self.kill_crowded:
            for player in self.crowded_players:
                player.strategy = "empty"

        self.datacollector_score.collect(self)
        self.datacollector_population.collect(self)

        self.fraction_evolving = self.num_evolving / (self.dimension**2)
        self.datacollector_evolving_agents.collect(self)

        if self.probability_mutation > 0:
            self.fraction_mutating = self.num_mutating / (self.dimension ** 2)
            self.datacollector_mutating_agents.collect(self)

        logger.warn(" " + "\n", color=41)