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
from rich.align import Align

console = Console(record=True)


def fetch_anime_list(USER_NAME, SEARCH_SCOPE):
    if SEARCH_SCOPE == "Y":
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
          Page(perPage: 50) {
            media(type: ANIME, sort: TRENDING_DESC) {
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
            }
          }
        }
        """
    else:
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


def calculate_weights(anime_list, SEARCH_SCOPE):
    weights = []
    anime_entries = []
    completed_ids = set()
    completed_genres = set()
    completed_tags = set()
    completed_studios = set()

    # Gather IDs, genres, tags, and studios of completed anime
    for list_section in anime_list["data"]["MediaListCollection"]["lists"]:
        for entry in list_section["entries"]:
            if entry["status"] == "COMPLETED":
                completed_ids.add(entry["media"]["id"])
                completed_genres.update(entry["media"].get("genres", []))
                completed_tags.update(
                    tag["name"] for tag in entry["media"].get("tags", [])
                )
                completed_studios.update(
                    studio["name"]
                    for studio in entry["media"].get("studios", {"nodes": []})["nodes"]
                )

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
                weight *= 5

            # Additional weight if any related entries are completed
            for related in entry["media"]["relations"]["edges"]:
                if related["node"]["id"] in completed_ids:
                    weight *= 2
                    break

            weights.append(weight)
            anime_entries.append(entry)

    if SEARCH_SCOPE == "Y":
        for entry in anime_list["data"]["Page"]["media"]:
            if entry["id"] not in completed_ids:
                weight = 0.1

                # Increase weight for matching genres, tags, and studios
                weight += 0.02 * len(set(entry.get("genres", [])) & completed_genres)
                weight += 0.02 * len(
                    set(tag["name"] for tag in entry.get("tags", [])) & completed_tags
                )
                weight += 0.02 * len(
                    set(
                        studio["name"]
                        for studio in entry.get("studios", {"nodes": []})["nodes"]
                    )
                    & completed_studios
                )

                if weight > 0.1:
                    weight = 0.1

                weights.append(weight)
                anime_entries.append({"media": entry, "status": "GLOBAL"})

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
    year = date_dict.get("year")
    month = date_dict.get("month")
    day = date_dict.get("day")

    if year is None or month is None or day is None:
        return "N/A"
    return f"{year}-{month:02d}-{day:02d}"


def print_anime_details(selected_entry):
    console.clear()
    selected_anime = selected_entry["media"]
    progress = selected_entry.get("progress", 0)
    episodes = selected_anime.get("episodes", 1)
    score = selected_entry.get("score", "N/A")
    genres = ", ".join(selected_anime.get("genres", [])[:4])
    studios = ", ".join(
        studio["name"]
        for studio in selected_anime.get("studios", {"nodes": []})["nodes"][:4]
    )
    tags = ", ".join(tag["name"] for tag in selected_anime.get("tags", [])[:4])
    started_at = format_date(selected_entry.get("startedAt", {}))

    # Print the anime title in English if available, else in Romaji, else in Native
    anime_title = (
        selected_anime.get("title", {}).get("english")
        or selected_anime.get("title", {}).get("romaji")
        or selected_anime.get("title", {}).get("native", "Unknown Title")
    )

    table = Table(
        title=anime_title,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Field", style="dim", width=20)
    table.add_column("Value")

    table.add_row("English Title", selected_anime["title"].get("english", "N/A"))
    table.add_row("Romaji Title", selected_anime["title"].get("romaji", "N/A"))
    table.add_row("Native Title", selected_anime["title"].get("native", "N/A"))
    table.add_row("Format", selected_anime.get("format", "N/A"))
    table.add_row("Status", selected_anime.get("status", "N/A"))
    table.add_row("Episodes", str(episodes))
    table.add_row("Score", str(score))  # Use the score variable
    table.add_row("Genres", genres)
    table.add_row("Studios", studios)
    table.add_row("Tags", tags)
    table.add_row("Library Status", selected_entry.get("status", "N/A"))
    table.add_row("Started At", started_at)

    console.print(table, justify="center")

    # Display progress bar if the anime is in progress or paused
    if selected_entry.get("status") in ["CURRENT", "PAUSED"] and progress > 0:
        progress_text = f"Progress: {progress}/{episodes}"
        console.print(f"[bold yellow]{progress_text}[/bold yellow]", justify="center")
        progress_bar_width = min(
            50, console.width - 20
        )  # Set a max width for the progress bar
        progress_bar = Progress(
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            BarColumn(bar_width=progress_bar_width),
            TextColumn(f"{progress}/{episodes}"),
        )
        task = progress_bar.add_task("", total=episodes, completed=progress)
        console.print(Align.center(progress_bar))
    else:
        if selected_entry.get("status") == "GLOBAL":
            status_text = "✨ Recommended Anime"
        else:
            status_text = f"Progress: {selected_entry.get('status', 'N/A')}"
        console.print(f"[bold yellow]{status_text}[/bold yellow]", justify="center")

    return selected_anime["id"], anime_title


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


# Ask for the AniList username and search prefs
USER_NAME = Prompt.ask("[bold cyan]Enter your AniList username[/bold cyan]")
SEARCH_SCOPE = Prompt.ask(
    "[bold cyan]Include recommendations from outside of your lists? (Y/N)[/bold cyan]",
)

anime_list = fetch_anime_list(USER_NAME, SEARCH_SCOPE)


def main_loop():
    while True:
        anime_entries, weights = calculate_weights(anime_list, SEARCH_SCOPE)
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
                subprocess.run(["ani-cli", anime_title])
            else:
                continue

        console.clear()


main_loop()
