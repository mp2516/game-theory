from mesa import Agent
import random
import math
from .logger import logger
import numpy as np

def round_to_unity(probabilities):
    probs_round = [np.floor(prob) for prob in probabilities]
    remainder = [(probabilities[i] - prob_round) for (i, prob_round) in enumerate(probs_round)]
    while sum(probs_round) < 1:
        key = np.argmax(remainder)
        probs_round[key] += 1
        remainder[key] = 0
    return probs_round

class GameAgent(Agent):
    unique_id = 1
    def __init__(self, pos, model):
        super().__init__(GameAgent.unique_id, model)
        GameAgent.unique_id += 1
        self.pos = pos
        # the length of this array is 8 as their are 8 neighbours for every agent
        self.scores = [0, 0, 0, 0, 0, 0, 0, 0]
        self.total_score = 0
        self.move, self.next_move = None, None
        self.neighbors = []
        self.probabilities, self.new_probabilities = [1/3, 1/3, 1/3, 0], [1/3, 1/3, 1/3, 0]
        self.evolved = False
        self.strategy = ""
        self.new_strategy = ""

        if self.model.game_mode == "Pure":
            if self.model.biomes:
                for i in range(len(self.model.biome_boundaries)-1):
                    if self.model.biome_boundaries[i] <= self.pos[0] < self.model.biome_boundaries[i+1]:
                        self.strategy = self.model.agent_strategies[i]
            else:
                self.strategy = np.random.choice(a=self.model.agent_strategies, p=self.model.initial_population_sizes)

    def evolve_strategy(self):
        if random.random() <= self.model.probability_mutation:
            if self.model.game_mode == "Pure":
                available_strategies = [strategy for strategy in self.model.agent_strategies if strategy != self.strategy]
                self.new_strategy = random.choice(available_strategies)
            elif self.model.game_mode == "Impure":
                # the larger the strength_of_mutation the smaller the weights which means a bigger variance on the initial probabilities
                self.model.new_probabilities = np.random.dirichlet([prob * (1/self.model.strength_of_mutation) for prob in self.probabilities])
        elif self.total_score <= self.model.cull_score and random.random() <= self.model.probability_adoption:
            # TODO: Benchmark strongest_neighbour to test whether this part of the code is even necessary
            self.neighbors = self.model.grid.get_neighbors(self.pos, moore=True)
            strongest_neighbour = self.neighbors[np.argmax([neighbour.total_score for neighbour in self.model.grid.neighbor_iter(self.pos)])]
            if strongest_neighbour.total_score > self.total_score:
                if self.model.game_mode == "Impure":
                    for num, i in enumerate(self.probabilities):
                        for j in strongest_neighbour.probabilities:
                            # the bad_agents probabilities will tend towards the probabilities of the strongest_neighbour
                            # with the strength_of_adoption dictating how much it tends towards
                            self.new_probabilities[num] = i + ((j - i) * self.model.strength_of_adoption)
                elif self.model.game_mode == "Pure":
                    self.new_strategy = strongest_neighbour.strategy
                    self.model.num_mutating_agents += 1
            else:
                self.new_strategy = self.strategy
                self.new_probabilities = self.probabilities
        else:
            self.new_strategy = self.strategy
            self.new_probabilities = self.probabilities
            
    def kill_weak(self):
        if random.random() < 0:
            cull_threshold = self.model.cull_score - 1
        else:
            cull_threshold = self.model.cull_score
        if self.total_score < cull_threshold and random.random() <= self.model.probability_adoption:
            self.new_strategy = "empty"
        else:
            self.new_strategy = self.strategy
            self.new_probabilities = self.probabilities
        

    def kill_crowded(self):       
#        if int(len(game_no)/self.model.dimensions**2) % 2 == 0:        
#            if all(self.strategy == neighbour.strategy for neighbour in self.neighbours):
#                self.new_strategy = "empty"         
#            else:
#                self.new_strategy = self.strategy
#                self.new_probabilities = self.probabilities
        crowded_players = [player for player in self.model.schedule.agents if all(self.strategy == neighbour.strategy for neighbour in self.neighbours)]
        if all(self.strategy == neighbour.strategy for neighbour in self.neighbours):
            crowded_players.append(self)
            if int(len(game_no)/self.model.dimensions**2) % 2 == 1:
                if (len(game_no)/self.model.dimensions**2).is_integer():
                    for player in crowded_players:
                        player.strategy = "empty"
                    crowded_players.clear()
##        crowded_players = [player for player in self.model.schedule.agents if all(self.strategy == neighbour.strategy for neighbour in self.neighbours)]


# =============================================================================
#     def reproduce(self):
# #        if not all(neighbour.strategy == "empty" for neighbour in self.neighbors):
# #        neighbours_not_empty = [neighbour for neighbour in self.neighbors if neighbour.strategy != "empty"]
# #        random.shuffle(neighbours_not_empty)
# #        strongest_neighbour = neighbours_not_empty[np.argmax([neighbour.total_score for neighbour in neighbours_not_empty])]
#         
#         random_neighbour = random.choice([neighbour for neighbour in self.neighbors if neighbour.strategy != "empty"])
#         if self.strategy == "empty" and strongest_neighbour.total_score >= 0 and random.random() <= self.model.probability_adoption and random.random() > self.model.probability_mutation:
#             self.new_strategy =  random_neighbour.strategy
#         elif self.strategy == "empty" and strongest_neighbour.total_score >= 0 and random.random() <= self.model.probability_adoption and random.random() <= self.model.probability_mutation:
#             self.new_strategy = random.choice(random.choices(
#                     population = ["all_r", "all_p", "all_s", "empty"],
#                     weights = [100, 100, 100, 0],
#                     k = 1
#                     ))
#         else:
#             self.new_strategy = self.strategy
#             self.new_probabilities = self.probabilities
# #        else:
# #            self.new_strategy = self.strategy
# #            self.new_probabilities = self.probabilities
# =============================================================================
            

    def reproduce(self):
        self.neighbors = self.model.grid.get_neighbors(self.pos, moore=True)
        if not all(neighbour.strategy == "empty" for neighbour in self.neighbors):
            neighbours_not_empty = [neighbour for neighbour in self.neighbors if neighbour.strategy != "empty"]
            random.shuffle(neighbours_not_empty)
            strongest_neighbour = neighbours_not_empty[np.argmax([neighbour.total_score for neighbour in neighbours_not_empty])]
            random_neighbour = random.choice([neighbour for neighbour in self.neighbors if neighbour.strategy != "empty"])
            rand = random.random()
            if self.strategy == "empty" and strongest_neighbour.total_score >= 0 and rand <= self.model.probability_adoption and rand > self.model.probability_mutation:
                self.new_strategy =  strongest_neighbour.strategy
            elif self.strategy == "empty" and strongest_neighbour.total_score >= 0 and rand <= self.model.probability_adoption and rand <= self.model.probability_mutation:
                self.new_strategy = random.choice(random.choices(
                        population = ["all_r", "all_p", "all_s"],
                        weights = [100, 100, 100],
                        k = 1
                        ))
#            else:
#                self.new_strategy = self.strategy
#                self.new_probabilities = self.probabilities
        else:
            self.new_strategy = self.strategy
            self.new_probabilities = self.probabilities


class RPSAgent(GameAgent):
    def __init__(self, pos, model):
        super().__init__(pos, model)

        if self.model.game_mode == "Pure":
            self.implement_pure_stragies()

        elif self.model.game_mode == "Impure":
            self.probabilities = np.random.dirichlet([1, 1, 1])
            self.moves = np.random.choice(a=self.model.agent_moves, size=self.model.num_moves_per_set, p=self.probabilities)

    def increment_score(self):
        for num, neighbor in enumerate(self.model.grid.neighbor_iter(self.pos)):
            if self.model.game_mode == "Pure":
                self.scores[num] = 0
                self.scores[num] += self.model.payoff[self.move, neighbor.move]
            elif self.model.game_mode == "Impure":
                score = 0
                for i in range(self.model.num_moves_per_set):
                    score += self.model.payoff[self.moves[i], neighbor.moves[i]]
                self.scores[num] = score
        self.total_score = sum(self.scores)

    def implement_pure_stragies(self):
        if self.strategy == "all_r":
            self.probabilities = [1, 0, 0, 0]
            self.move = "R"
        elif self.strategy == "all_p":
            self.probabilities = [0, 1, 0, 0]
            self.move = "P"
        elif self.strategy == "all_s":
            self.probabilities = [0, 0, 1, 0]
            self.move = "S"
        elif self.strategy == "empty":
            self.probabilities = [0, 0, 0, 1]            
            self.move = "E"
            

    def implement_strategy(self):
        self.strategy = self.new_strategy
        self.probabilities = self.new_probabilities

        if self.model.game_mode == "Pure":
            self.implement_pure_stragies()
        elif self.model.game_mode == "Impure":
            # whilst the linear interpolation should lead to probabilities that sum to 1
            self.probabilities = [prob / sum(self.probabilities) for prob in self.probabilities]
            self.moves = np.random.choice(a=self.model.agent_moves, size=self.model.num_moves_per_set, p=self.probabilities)


class PDAgent(GameAgent):
    def __init__(self, pos, model):
        super().__init__(pos, model)
        self.previous_moves = []
        self.implement_strategy()

    def play_reactive_strategy(self, move_count, neighbor):
        if self.strategy == "tit_for_tat":
            if move_count == 0:
                self.move = "C"
            else:
                self.move = neighbor.previous_moves[-1]
        elif self.strategy == "spiteful":
            if "D" in neighbor.previous_moves:
                self.move = "D"
            else:
                self.move = "C"

    def implement_strategy(self):
        if self.strategy == "all_c":
            self.move = "C"
        elif self.strategy == "all_d":
            self.move = "D"
        elif self.strategy == "random":
            self.move = np.random.choice(a=self.model.agent_moves)
        elif self.strategy == "tit_for_tat":
            self.move = "C"
        elif self.strategy == "spiteful":
            self.move = "D"

    def increment_score(self, move_count):
        for num, neighbor in enumerate(self.model.grid.neighbor_iter(self.pos)):
            self.play_reactive_strategy(move_count, neighbor)
            self.scores[num] += self.model.payoff[self.move, neighbor.move]
        self.total_score = sum(self.scores)
        move_count += 1
        return move_count