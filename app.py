import requests
import random
import os
import sys
import tty
import termios
import webbrowser
import shlex
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, BarColumn, TextColumn

console = Console(record=True)


def fetch_anime_list(USER_NAME):
    query = """
    query ($username: String) {
      MediaListCollection(userName: $username, type: ANIME) {
        lists {
          name
          entries {
            media {
              id
              title {
                romaji
                english
                native
              }
              format
              status
              episodes
              genres
              studios {
                nodes {
                  name
                }
              }
              tags {
                name
              }
              relations {
                edges {
                  node {
                    id
                    title {
                      romaji
                      english
                      native
                    }
                    format
                    status
                  }
                }
              }
              nextAiringEpisode {
                airingAt
                timeUntilAiring
                episode
              }
            }
            status
            score
            progress
            repeat
            priority
            private
            notes
            hiddenFromStatusLists
            advancedScores
            startedAt {
              year
              month
              day
            }
            completedAt {
              year
              month
              day
            }
            updatedAt
          }
        }
      }
    }
    """
    variables = {"username": USER_NAME}

    url = "https://graphql.anilist.co"
    response = requests.post(
        url, json={"query": query, "variables": variables}, timeout=10
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Query failed to run by returning code of {response.status_code}. {response.text}"
        )


def calculate_weights(anime_list):
    weights = []
    anime_entries = []
    completed_ids = set()

    # Gather IDs of completed anime
    for list_section in anime_list["data"]["MediaListCollection"]["lists"]:
        for entry in list_section["entries"]:
            if entry["status"] == "COMPLETED":
                completed_ids.add(entry["media"]["id"])

    for list_section in anime_list["data"]["MediaListCollection"]["lists"]:
        for entry in list_section["entries"]:
            # Exclude 'completed' and 'dropped' statuses
            if entry["status"] in ["COMPLETED", "DROPPED"]:
                continue

            progress = entry["progress"] or 0
            episodes = entry["media"]["episodes"] or 1
            weight = progress / episodes

            # Higher weight for 'watching' status
            if entry["status"] == "CURRENT":
                weight *= 2

            # Additional weight if any related entries are completed
            for related in entry["media"]["relations"]["edges"]:
                if related["node"]["id"] in completed_ids:
                    weight *= 1.5
                    break

            weights.append(weight)
            anime_entries.append(entry)

    return anime_entries, weights


def select_random_anime(anime_entries, weights):
    total_weight = sum(weights)
    r = random.uniform(0, total_weight)
    upto = 0
    for entry, weight in zip(anime_entries, weights):
        if upto + weight >= r:
            return entry
        upto += weight
    raise ValueError("Failed to select a random anime.")


def format_date(date_dict):
    if (
        date_dict["year"] is None
        or date_dict["month"] is None
        or date_dict["day"] is None
    ):
        return "N/A"
    return f"{date_dict['year']}-{date_dict['month']:02d}-{date_dict['day']:02d}"


def print_anime_details(selected_entry):
    console.clear()
    selected_anime = selected_entry["media"]
    progress = selected_entry["progress"]
    episodes = selected_anime["episodes"] or 1

    genres = ", ".join(selected_anime["genres"][:4])
    studios = ", ".join(
        studio["name"] for studio in selected_anime["studios"]["nodes"][:4]
    )
    tags = ", ".join(tag["name"] for tag in selected_anime["tags"][:4])

    table = Table(
        title=selected_anime["title"]["romaji"],
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Field", style="dim", width=20)
    table.add_column("Value")

    table.add_row("English Title", selected_anime["title"]["english"])
    table.add_row("Romaji Title", selected_anime["title"]["romaji"])
    table.add_row("Native Title", selected_anime["title"]["native"])
    table.add_row("Format", selected_anime["format"])
    table.add_row("Status", selected_anime["status"])
    table.add_row("Episodes", str(episodes))
    table.add_row("Score", str(selected_entry["score"]))
    table.add_row("Genres", genres)
    table.add_row("Studios", studios)
    table.add_row("Tags", tags)
    table.add_row("Library Status", selected_entry["status"])
    table.add_row("Started At", format_date(selected_entry["startedAt"]))

    console.print(table, justify="center")

    # Calculate the width of the rendered table
    rendered_table = console.export_text()
    table_width = max(len(line) for line in rendered_table.splitlines() if line.strip())

    # Display progress bar if the anime is in progress or paused
    if selected_entry["status"] in ["CURRENT", "PAUSED"]:
        progress_text = f"Progress: {progress}/{episodes}"
        console.print(f"[bold yellow]{progress_text}[/bold yellow]", justify="center")
        progress_bar_width = min(
            table_width, 50
        )  # Set a max width for the progress bar
        progress_bar = Progress(
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            BarColumn(bar_width=progress_bar_width),
            TextColumn(f"{progress}/{episodes}"),
        )
        console.print(progress_bar, justify="center")

    return selected_anime["id"], selected_anime["title"]["romaji"]


def get_keypress():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def print_key_guide():
    key_guide = (
        "[bold red][Q][/bold red] Quit    "
        "[bold yellow][W][/bold yellow] ani-cli    "
        "[bold blue][E][/bold blue] AniList    "
        "[bold green][R][/bold green] Refresh"
    )
    console.print(
        Panel(key_guide, title="Key Guide", border_style="magenta"), justify="center"
    )


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


# Ask for the AniList username
USER_NAME = Prompt.ask("[bold cyan]Enter your AniList username[/bold cyan]")

anime_list = fetch_anime_list(USER_NAME)


def main_loop():
    while True:
        anime_entries, weights = calculate_weights(anime_list)
        selected_entry = select_random_anime(anime_entries, weights)
        anime_id, anime_title = print_anime_details(selected_entry)

        print_key_guide()

        while True:
            key = get_keypress()

            if key.lower() == "q":
                clear_terminal()
                exit()
            elif key.lower() == "r":
                break
            elif key.lower() == "e":
                webbrowser.open(f"https://anilist.co/anime/{anime_id}")
            elif key.lower() == "w":
                subprocess.run(["ani-cli", shlex.quote(anime_title)], check=True)
            else:
                continue  # Skip clearing and reprinting if key is not recognized

        console.clear()  # Clear the console at the end of each loop iteration


main_loop()
