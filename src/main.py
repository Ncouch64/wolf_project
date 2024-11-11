from character import Player, get_next_speaker
import numpy as np
from typing import Dict, List
import time
from utils import make_chat_tree, merge_chat_trees
import json
import re
from tqdm import tqdm

n_games = 8
interactive_mode = True

# Hyperparameters
player_names = ["Thomas", "Emily", "Benjamin", "Sophia", "Victoria"]
roles = [0,0,0,1,1]

model = "gpt-3.5-turbo" # "gpt-3.5-turbo-16k" "gpt-4-0314"

role_map = {
    0: "peasant",
    1: "werewolf"
}

for game in tqdm(range(7, n_games)):

    # Init game
    np.random.seed(int(time.time()))
    np.random.shuffle(roles)

    # Get all werewolf for extra information
    werewolf_names = [name.lower() for i, name in enumerate(player_names) if role_map[roles[i]] == "werewolf"]

    # Init all the players
    players : Dict[str, Player] = {}
    for i, name in enumerate(player_names):
        players[name.lower()] = Player(name, model=model, role=role_map[roles[i]], extra=["The other werewolf (including you) are [" + ",".join(werewolf_names) + "]. You should cooperate and deflect suspicions on any of you\n"] if name.lower() in werewolf_names else [])
        players[name.lower()].init_player(players=player_names)
    
    # If game is interactive, print the intro of the first player
    if interactive_mode:
        print(f"You are a {players[player_names[0].lower()].role}")
        print("The other werewolf (including you) are [" + ",".join(werewolf_names) + "]. You should cooperate and deflect suspicions on any of you." if player_names[0].lower() in werewolf_names else "")
        print("Narrator: The first night was fruitful for the Werewolf, a villager is dead: Bob. Now it is time to debate who to eliminate today!")

    rounds = 0
    stop = False
    conversation_history = []
    conversation_history_uncensored = []

    # Debate stage
    while rounds < 15 and not stop:
        rounds += 1
        next_to_speak = get_next_speaker(conversation_history, player_names, "gpt-3.5-turbo").lower()

        if next_to_speak != "vote":
            # If next to speak is first player and interactive mode, then ask for input
            if next_to_speak == player_names[0].lower() and interactive_mode:
                print("Your turn to speak")
                uncensored = "Thomas: " + input()
                censored = re.sub(r"\[[^\]]*\]", "", uncensored)
            else:
                censored, uncensored = players[next_to_speak].get_player_text()
            
            for name in player_names:
                if name.lower() != next_to_speak:
                    players[name.lower()].add_other_text(censored)
        
            conversation_history.append(censored)
            conversation_history_uncensored.append(uncensored)

            if interactive_mode:
                print(censored)
            else:
                print(uncensored)
        else:
            break

    # Vote stage
    votes = {name.lower(): 0 for name in player_names}

    vote_prompt = make_chat_tree("../prompts/vote_prompt.json")
    conversation_history.append(vote_prompt.content)

    print(vote_prompt.content)

    for name in player_names:
        players[name.lower()].add_other_text(vote_prompt.content)

    for voting_name in player_names:
        if name.lower() in werewolf_names:
            players[name.lower()].current_context.content += f"\n[Advice (other players don't see this): Remember you know that you are the werewolf. The werewolfs are (including you): {', '.join(werewolf_names)}. If a wolf die, then you also loose!]\n"

        # If next to speak is first player and interactive mode, then ask for input
        if voting_name.lower() == player_names[0].lower() and interactive_mode:
            print("Your turn to vote")
            uncensored = "Thomas: " + input()
            censored = re.sub(r"\[[^\]]*\]", "", uncensored)
        else:
            censored, uncensored = players[voting_name.lower()].get_player_text()

        for name in player_names:
            if name.lower() != voting_name:
                players[name.lower()].add_other_text(censored)
        
        conversation_history.append(censored)
        conversation_history_uncensored.append(uncensored)

        voted_for = ""
        search = censored.lower()
        for name in player_names:
            if name.lower() in search:
                voted_for = name.lower()
                search = search.split(name.lower())[-1]
    
        try:
            votes[voted_for] += 1
        except:
            pass
        if interactive_mode:
            print(censored)
        else:
            print(uncensored)
    print(votes)

    json.dump({
        "conversation_history": conversation_history,
        "conversation_history_uncensored": conversation_history_uncensored,
        "votes": votes,
        "werewolf_names": werewolf_names,
        "player_names": player_names,
        "model": model,
        "interactive": interactive_mode,
    }, open(f"../data/final_project_no_custom_drunk.json", "w+"), indent=4)