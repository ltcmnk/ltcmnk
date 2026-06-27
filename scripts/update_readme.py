import datetime
import json
import os
from pathlib import Path

import requests
from dateutil import relativedelta
from lxml import etree

USER_NAME = os.environ.get("USER_NAME", "ltcmnk")
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]

BIRTHDAY = datetime.datetime(2002, 1, 17)

SVG_FILES = ["dark_mode.svg", "light_mode.svg"]
CACHE_FILE = Path("cache/loc_cache.json")

# Visible character columns in the right-hand panel. Because the SVG uses a
# monospace font, keeping values on these columns makes the dot leaders line up.
RIGHT_COLUMN = 57
REPO_VALUE_COLUMN = 16
FOLLOWER_VALUE_COLUMN = 20
LOC_VALUE_COLUMN = 22

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def format_plural(value):
    return "s" if value != 1 else ""


def calculate_age():
    diff = relativedelta.relativedelta(datetime.datetime.today(), BIRTHDAY)

    age = "{} {}, {} {}, {} {}".format(
        diff.years,
        "year" + format_plural(diff.years),
        diff.months,
        "month" + format_plural(diff.months),
        diff.days,
        "day" + format_plural(diff.days),
    )

    if diff.months == 0 and diff.days == 0:
        age += " ଘ(੭*ˊᵕˋ)੭* "

    return age


def graphql(query, variables):
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(f"GitHub API error: {response.status_code} {response.text}")

    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    return data["data"]


def load_cache():
    if not CACHE_FILE.exists():
        return {}

    with CACHE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with CACHE_FILE.open("w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)


def get_user_info():
    query = """
    query($login: String!) {
      user(login: $login) {
        id
        followers {
          totalCount
        }
      }
    }
    """

    user = graphql(query, {"login": USER_NAME})["user"]

    return {
        "id": user["id"],
        "followers": user["followers"]["totalCount"],
    }


def get_owned_repositories():
    query = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
          nodes {
            nameWithOwner
            stargazers {
              totalCount
            }
            defaultBranchRef {
              target {
                ... on Commit {
                  history {
                    totalCount
                  }
                }
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    repos = []
    cursor = None

    while True:
        data = graphql(query, {"login": USER_NAME, "cursor": cursor})["user"]["repositories"]
        repos.extend(data["nodes"])

        if not data["pageInfo"]["hasNextPage"]:
            break

        cursor = data["pageInfo"]["endCursor"]

    return repos


def get_contributed_repositories():
    query = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        repositoriesContributedTo(
          first: 100,
          after: $cursor,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY],
          includeUserRepositories: true
        ) {
          nodes {
            nameWithOwner
            stargazers {
              totalCount
            }
            defaultBranchRef {
              target {
                ... on Commit {
                  history {
                    totalCount
                  }
                }
              }
            }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                }
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    repos = []
    cursor = None

    while True:
        data = graphql(query, {"login": USER_NAME, "cursor": cursor})["user"]["repositoriesContributedTo"]
        repos.extend(data["nodes"])

        if not data["pageInfo"]["hasNextPage"]:
            break

        cursor = data["pageInfo"]["endCursor"]

    return repos


def get_default_branch_commit_count(repo):
    branch = repo.get("defaultBranchRef")

    if not branch:
        return 0

    target = branch.get("target")

    if not target or "history" not in target:
        return 0

    return target["history"]["totalCount"]


def count_loc_for_repo(name_with_owner, owner_id):
    owner, repo_name = name_with_owner.split("/", 1)

    query = """
    query($owner: String!, $repo: String!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, after: $cursor) {
                edges {
                  node {
                    additions
                    deletions
                    author {
                      user {
                        id
                      }
                    }
                  }
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
          }
        }
      }
    }
    """

    additions = 0
    deletions = 0
    commits = 0
    cursor = None

    while True:
        data = graphql(
            query,
            {
                "owner": owner,
                "repo": repo_name,
                "cursor": cursor,
            },
        )["repository"]

        if data is None or data["defaultBranchRef"] is None:
            return {
                "additions": additions,
                "deletions": deletions,
                "commits": commits,
            }

        history = data["defaultBranchRef"]["target"]["history"]

        for edge in history["edges"]:
            commit = edge["node"]
            author = commit.get("author") or {}
            user = author.get("user")

            if user and user.get("id") == owner_id:
                additions += commit["additions"]
                deletions += commit["deletions"]
                commits += 1

        if not history["pageInfo"]["hasNextPage"]:
            break

        cursor = history["pageInfo"]["endCursor"]

    return {
        "additions": additions,
        "deletions": deletions,
        "commits": commits,
    }


def aggregate_languages(repositories, top_n=5):
    lang_bytes = {}

    for repo in repositories:
        for edge in (repo.get("languages") or {}).get("edges", []):
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]

    total = sum(lang_bytes.values())

    if total == 0:
        return []

    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:top_n]

    BAR_WIDTH = 16
    MAX_KEY = 12

    result = []
    for name, bytes_count in sorted_langs:
        pct = bytes_count / total * 100
        fill_count = round(pct / 100 * BAR_WIDTH)
        empty_count = BAR_WIDTH - fill_count
        display_name = name[:MAX_KEY]
        result.append({
            "name": display_name,
            "pad": " " * (MAX_KEY - len(display_name)),
            "fill": "█" * fill_count,
            "empty": "░" * empty_count,
            "pct": f"{pct:5.1f}%",
        })

    return result


def calculate_loc(owner_id, repositories):
    cache = load_cache()

    total_additions = 0
    total_deletions = 0
    total_commits = 0

    for repo in repositories:
        name_with_owner = repo["nameWithOwner"]
        default_branch_commits = get_default_branch_commit_count(repo)

        cached_repo = cache.get(name_with_owner)

        if cached_repo and cached_repo.get("default_branch_commits") == default_branch_commits:
            repo_loc = cached_repo
        else:
            counted = count_loc_for_repo(name_with_owner, owner_id)

            repo_loc = {
                "default_branch_commits": default_branch_commits,
                "additions": counted["additions"],
                "deletions": counted["deletions"],
                "commits": counted["commits"],
            }

            cache[name_with_owner] = repo_loc

        total_additions += int(repo_loc["additions"])
        total_deletions += int(repo_loc["deletions"])
        total_commits += int(repo_loc["commits"])

    save_cache(cache)

    return {
        "additions": total_additions,
        "deletions": total_deletions,
        "total": total_additions - total_deletions,
        "commits": total_commits,
    }


def get_profile_stats():
    user = get_user_info()

    owned_repos = get_owned_repositories()
    contributed_repos = get_contributed_repositories()

    star_count = sum(repo["stargazers"]["totalCount"] for repo in owned_repos)

    loc = calculate_loc(user["id"], contributed_repos)
    languages = aggregate_languages(contributed_repos)

    return {
        "age_data": calculate_age(),
        "repo_data": len(owned_repos),
        "contrib_data": len(contributed_repos),
        "star_data": star_count,
        "follower_data": user["followers"],
        "commit_data": loc["commits"],
        "loc_data": loc["total"],
        "loc_add": loc["additions"],
        "loc_del": loc["deletions"],
        "languages": languages,
    }


def find_and_replace(root, element_id, new_text):
    element = root.find(f".//*[@id='{element_id}']")

    if element is not None:
        element.text = str(new_text)


def format_stat(new_text):
    if isinstance(new_text, int):
        return f"{new_text:,}"

    return str(new_text)


def make_dot_leader(prefix_width, value, target_column):
    available = max(0, target_column - prefix_width - len(value))

    if available <= 2:
        return {0: "", 1: " ", 2: ". "}[available]

    return " " + ("." * (available - 2)) + " "


def justify_format(root, element_id, new_text, prefix_width, target_column):
    new_text = format_stat(new_text)
    dot_string = make_dot_leader(prefix_width, new_text, target_column)

    find_and_replace(root, element_id, new_text)
    find_and_replace(root, f"{element_id}_dots", dot_string)

    return len(dot_string) + len(new_text)


def update_svg(filename, stats):
    tree = etree.parse(filename)
    root = tree.getroot()

    age = format_stat(stats["age_data"])
    repo = format_stat(stats["repo_data"])
    contrib = format_stat(stats["contrib_data"])
    stars = format_stat(stats["star_data"])
    followers = format_stat(stats["follower_data"])
    commits = format_stat(stats["commit_data"])
    loc = format_stat(stats["loc_data"])

    justify_format(root, "age_data", age, len(". Uptime:"), RIGHT_COLUMN)

    repo_width = justify_format(
        root, "repo_data", repo, len(". Repos:"), REPO_VALUE_COLUMN
    )
    star_prefix_width = (
        len(". Repos:")
        + repo_width
        + len(" {Contrib: ")
        + len(contrib)
        + len("} | Stars:")
    )
    justify_format(root, "star_data", stars, star_prefix_width, RIGHT_COLUMN)

    follower_width = justify_format(
        root,
        "follower_data",
        followers,
        len(". Followers:"),
        FOLLOWER_VALUE_COLUMN,
    )
    commit_prefix_width = (
        len(". Followers:") + follower_width + len(" | Commits:")
    )
    justify_format(root, "commit_data", commits, commit_prefix_width, RIGHT_COLUMN)

    justify_format(root, "loc_data", loc, len(". LOC:"), LOC_VALUE_COLUMN)

    find_and_replace(root, "contrib_data", contrib)
    find_and_replace(root, "loc_add", f"{stats['loc_add']:,}")
    find_and_replace(root, "loc_del", f"{stats['loc_del']:,}")

    for i, lang in enumerate(stats.get("languages", [])[:5], 1):
        find_and_replace(root, f"lang_{i}_key", lang["name"])
        find_and_replace(root, f"lang_{i}_pad", lang["pad"])
        find_and_replace(root, f"lang_{i}_fill", lang["fill"])
        find_and_replace(root, f"lang_{i}_empty", lang["empty"])
        find_and_replace(root, f"lang_{i}_pct", lang["pct"])

    tree.write(filename, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    stats = get_profile_stats()

    for svg_file in SVG_FILES:
        update_svg(svg_file, stats)

    print("Updated SVG stats:")
    for key, value in stats.items():
        print(f"{key}: {value}")
