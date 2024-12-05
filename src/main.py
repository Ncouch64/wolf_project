from character import Player, get_next_speaker
import numpy as np
from typing import Dict, List
import time
from utils import make_chat_tree, merge_chat_trees
import json
import re
from tqdm import tqdm

# Configuration
n_games = 10
interactive_mode = False
n_players = 5  # Number of players
n_werewolves = 1  # Number of werewolves
n_seers = 1  # Number of seers
n_possessed = 1  # Number of possessed

# Read names from names.txt
with open('names.txt', 'r') as file:
    all_names = [line.strip().lower() for line in file.readlines()]

# Ensure there are enough names
if len(all_names) < n_players:
    raise ValueError("Not enough names in names.txt to assign to all players")

# Randomly select player names
np.random.shuffle(all_names)
player_names = all_names[:n_players]
all_player_names = player_names.copy()  # Keep a copy of all player names

# Assign roles
roles = [1] * n_werewolves + [2] * n_seers + [3] * n_possessed + [0] * (n_players - n_werewolves - n_seers - n_possessed)
np.random.shuffle(roles)

model = "gpt-3.5-turbo" # "gpt-3.5-turbo-16k" "gpt-4-0314"

role_map = {
    0: "peasant",
    1: "werewolf",
    2: "seer",
    3: "possessed"
}

for game in tqdm(range(0, n_games)):

    # Init game
    np.random.seed(int(time.time()))
    np.random.shuffle(roles)

    # Get all werewolf for extra information
    werewolf_names = [name.lower() for i, name in enumerate(player_names) if role_map[roles[i]] == "werewolf"]

    # Get all seers for extra information
    seer_names = [name.lower() for i, name in enumerate(player_names) if role_map[roles[i]] == "seer"]

    # Get all possessed for extra information
    possessed_names = [name.lower() for i, name in enumerate(player_names) if role_map[roles[i]] == "possessed"]

    # Init all the players
    players: Dict[str, Player] = {}
    for i, name in enumerate(player_names):
        extra_info = []
        if name.lower() in werewolf_names:
            extra_info.append("The other werewolf (including you) are [" + ",".join(werewolf_names) + "]. You should cooperate and deflect suspicions on any of you\n")
        if name.lower() in seer_names:
            extra_info.append("You are the seer. You can see the true identity of one player each night.\n")
        if name.lower() in possessed_names:
            extra_info.append("You are the possessed. You will pretend to be a seer and announce false discoveries.\n")
        
        players[name.lower()] = Player(name, model=model, role=role_map[roles[i]], extra=extra_info)
        players[name.lower()].init_player(players=player_names)
        
        # If game is interactive, print the intro of the first player
        if interactive_mode:
            print(f"You are a {players[player_names[0].lower()].role}")
            if player_names[0].lower() in werewolf_names:
                print("The other werewolf (including you) are [" + ",".join(werewolf_names) + "]. You should cooperate and deflect suspicions on any of you.")
            if player_names[0].lower() in seer_names:
                print("You are the seer. You can see the true identity of one player each night.")
            if player_names[0].lower() in possessed_names:
                print("You are the possessed. You will pretend to be a seer and announce false discoveries.")
            print("Narrator: The first night was fruitful for the Werewolf, a villager is dead: Bob. Now it is time to debate who to eliminate today!")

    rounds = 0
    stop = False
    conversation_history = []
    conversation_history_uncensored = []
    game_log = []

    def debate_phase(rounds, stop):
        while rounds < 15 and not stop:
            rounds += 1
            next_to_speak = get_next_speaker(conversation_history, player_names, "gpt-3.5-turbo").lower()

            if next_to_speak not in players:
                continue

            if next_to_speak != "vote":
                # If next to speak is first player and interactive mode, then ask for input
                if next_to_speak == player_names[0].lower() and interactive_mode:
                    print("Your turn to speak")
                    uncensored = "Thomas: " + input()
                    censored = re.sub(r"\[[^\]]*\]", "", uncensored)
                else:
                    censored, uncensored = players[next_to_speak].get_player_text()
                
                for name in player_names:
                    if name.lower() != next_to_speak and name.lower() in players:
                        players[name.lower()].add_other_text(censored)
            
                conversation_history.append(censored)
                conversation_history_uncensored.append(uncensored)

                if interactive_mode:
                    print(censored)
                else:
                    print(uncensored)
            else:
                break

    def seer_phase(round_log):
        seer_discoveries = []
        for seer_name in seer_names:
            if interactive_mode:
                print(f"{seer_name.capitalize()}, you are the seer. Choose one player to see their role.")
                chosen_player = input("Enter the name of the player you want to see: ").strip().lower()
            else:
                # For non-interactive mode, randomly choose a player
                chosen_player = np.random.choice([name.lower() for name in player_names if name.lower() != seer_name])

            chosen_role = role_map[roles[player_names.index(chosen_player)]]

            if seer_name in players:
                players[seer_name].current_context.content += f"\n[You have chosen to see the role of {chosen_player.capitalize()}. They are a {chosen_role}.]\n"
            seer_discoveries.append((seer_name, chosen_player, chosen_role))
            if interactive_mode:
                print(f"{seer_name.capitalize()}, you have chosen to see the role of {chosen_player.capitalize()}. They are a {chosen_role}.")

        # Announce seer's discovery
        for seer_name, chosen_player, chosen_role in seer_discoveries:
            announcement = f"{seer_name.capitalize()} has discovered that {chosen_player.capitalize()} is a {chosen_role}."
            for name in player_names:
                if name.lower() in players:
                    players[name.lower()].add_other_text(announcement)
            conversation_history.append(announcement)
            conversation_history_uncensored.append(announcement)
            round_log["seer_discovery"] = announcement
            if interactive_mode:
                print(announcement)

    def possessed_phase(round_log):
        possessed_discoveries = []
        for possessed_name in possessed_names:
            if interactive_mode:
                print(f"{possessed_name.capitalize()}, you are the possessed. Choose one player to see their role.")
                chosen_player = input("Enter the name of the player you want to see: ").strip().lower()
            else:
                # For non-interactive mode, randomly choose a player
                chosen_player = np.random.choice([name.lower() for name in player_names if name.lower() != possessed_name])

            # Possessed will always announce a false role
            chosen_role = "peasant" if role_map[roles[player_names.index(chosen_player)]] != "peasant" else "werewolf"

            if possessed_name in players:
                players[possessed_name].current_context.content += f"\n[You have chosen to see the role of {chosen_player.capitalize()}. They are a {chosen_role}.]\n"
            possessed_discoveries.append((possessed_name, chosen_player, chosen_role))
            if interactive_mode:
                print(f"{possessed_name.capitalize()}, you have chosen to see the role of {chosen_player.capitalize()}. They are a {chosen_role}.")

        # Announce possessed's fake discovery
        for possessed_name, chosen_player, chosen_role in possessed_discoveries:
            announcement = f"{possessed_name.capitalize()} has discovered that {chosen_player.capitalize()} is a {chosen_role}."
            for name in player_names:
                if name.lower() in players:
                    players[name.lower()].add_other_text(announcement)
            conversation_history.append(announcement)
            conversation_history_uncensored.append(announcement)
            round_log["possessed_discovery"] = announcement
            if interactive_mode:
                print(announcement)

    def voting_phase(round_log):
        votes = {name.lower(): 0 for name in player_names}

        vote_prompt = make_chat_tree("../prompts/vote_prompt.json")
        conversation_history.append(vote_prompt.content)
        conversation_history_uncensored.append(vote_prompt.content)
        for name in player_names:
            if name.lower() in players:
                players[name.lower()].add_other_text(vote_prompt.content)

        for voting_name in player_names:
            if voting_name.lower() in players:
                players[voting_name.lower()].current_context.content += f"\n[Advice (other players don't see this): Remember you know that you are the werewolf. The werewolves are (including you): {', '.join(werewolf_names)}. If a wolf dies, then you also lose!]\n"

            if voting_name.lower() == player_names[0].lower() and interactive_mode:
                print("Your turn to vote")
                uncensored = "Thomas: " + input()
                censored = re.sub(r"\[[^\]]*\]", "", uncensored)
            else:
                censored, uncensored = players[voting_name.lower()].get_player_text()

            for name in player_names:
                if name.lower() != voting_name and name.lower() in players:
                    players[name.lower()].add_other_text(censored)
            
            conversation_history.append(censored)
            conversation_history_uncensored.append(uncensored)
            round_log["voting"][voting_name] = censored

            voted_for = ""
            search = censored.lower()
            for name in player_names:
                if name.lower() in search:
                    voted_for = name.lower()
                    search = search.split(name.lower())[-1]

            if voted_for in votes:
                votes[voted_for] += 1
            else:
                print(f"Warning: {voted_for} not found in votes dictionary")
            if interactive_mode:
                print(censored)
            else:
                print(uncensored)
        print(votes)

        # Determine who is voted out
        voted_out = max(votes, key=votes.get)
        player_names.remove(voted_out)
        del players[voted_out]

        return voted_out

    def werewolf_phase(round_log):
        if interactive_mode:
            print("Werewolves, choose a player to eliminate.")
            chosen_victim = input("Enter the name of the player you want to eliminate: ").strip().lower()
        else:
            chosen_victim = np.random.choice([name.lower() for name in player_names if name.lower() not in werewolf_names])

        announcement = f"The werewolves have chosen to eliminate {chosen_victim.capitalize()}."
        for name in player_names:
            if name.lower() in players:
                players[name.lower()].add_other_text(announcement)
        conversation_history.append(announcement)
        conversation_history_uncensored.append(announcement)
        round_log["werewolf_elimination"] = announcement
        if interactive_mode:
            print(announcement)

        player_names.remove(chosen_victim)
        del players[chosen_victim]

        return chosen_victim

    # Looping phase
    while not stop:
        round_log = {"round": rounds + 1, "seer_discovery": None, "possessed_discovery": None, "voting": {}, "werewolf_elimination": None}
        debate_phase(rounds, stop)
        seer_phase(round_log)
        possessed_phase(round_log)
        voted_out = voting_phase(round_log)

        # Check win conditions after voting
        if len([name for name in player_names if name in werewolf_names]) == 0:
            stop = True
            winner = "villagers"
            print("The villagers have won!")
            game_log.append(round_log)
            break
        elif len(werewolf_names) + len(possessed_names) >= len(player_names) - len(werewolf_names) - len(possessed_names):
            stop = True
            winner = "werewolves"
            print("The werewolves have won!")
            game_log.append(round_log)
            break

        chosen_victim = werewolf_phase(round_log)

        # Check win conditions after werewolf elimination
        if len([name for name in player_names if name in werewolf_names]) == 0:
            stop = True
            winner = "villagers"
            print("The villagers have won!")
            game_log.append(round_log)
            break
        elif len(werewolf_names) + len(possessed_names) >= len(player_names) - len(werewolf_names) - len(possessed_names):
            stop = True
            winner = "werewolves"
            print("The werewolves have won!")
            game_log.append(round_log)
            break

        # Announce the elimination and allow for additional discussion
        additional_discussion_prompt = f"The werewolves have eliminated {chosen_victim.capitalize()} during the night. You have some time for additional discussion before the next voting phase. Please do not cast any votes until you are told to do so. Use this time to discuss and try to identify who the werewolves could be."
        conversation_history.append(additional_discussion_prompt)
        conversation_history_uncensored.append(additional_discussion_prompt)
        print(additional_discussion_prompt)
        for name in player_names:
            if name.lower() in players:
                players[name.lower()].add_other_text(additional_discussion_prompt)
            players[name.lower()].add_other_text(additional_discussion_prompt)

        # Additional discussion stage
        #debate_phase(rounds, stop)
        game_log.append(round_log)

    # Save the game state
    json.dump({
        "conversation_history": conversation_history,
        "conversation_history_uncensored": conversation_history_uncensored,
        "werewolf_names": werewolf_names,
        "seer_names": seer_names,
        "possessed_names": possessed_names,
        "all_player_names": all_player_names,  # Add all player names to the JSON dump
        "remaining_player_names": player_names,  # Add remaining player names to the JSON dump
        "model": model,
        "interactive": interactive_mode,
        "winner": winner,  # Add the winner to the JSON dump
        "game_log": game_log  # Add the game log to the JSON dump
    }, open(f"../data/final/results_main_three/{game}_1.json", "w+"), indent=4)
