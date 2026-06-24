import datetime
import os
import requests
from dateutil import relativedelta
from lxml import etree

USER_NAME = os.environ.get("USER_NAME", "ltcmnk")
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]

BIRTHDAY = datetime.datetime(2002, 1, 17)
SVG_FILES = ["dark_mode.svg", "light_mode.svg"]

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
        age += " (>∀<☆) "

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


def get_profile_stats():
    query = """
    query($login: String!) {
      user(login: $login) {
        followers {
          totalCount
        }
        repositories(first: 100, ownerAffiliations: OWNER) {
          totalCount
          nodes {
            stargazerCount
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
        }
        repositoriesContributedTo(
          first: 100,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY],
          includeUserRepositories: true
        ) {
          totalCount
        }
      }
    }
    """

    user = graphql(query, {"login": USER_NAME})["user"]

    repos = user["repositories"]["nodes"]

    repo_count = user["repositories"]["totalCount"]
    contributed_count = user["repositoriesContributedTo"]["totalCount"]
    follower_count = user["followers"]["totalCount"]

    star_count = sum(repo["stargazerCount"] for repo in repos)

    commit_count = 0
    for repo in repos:
        branch = repo.get("defaultBranchRef")
        if branch and branch.get("target"):
            commit_count += branch["target"]["history"]["totalCount"]

    return {
        "age_data": calculate_age(),
        "repo_data": repo_count,
        "contrib_data": contributed_count,
        "star_data": star_count,
        "follower_data": follower_count,
        "commit_data": commit_count,
        "loc_data": "soon",
        "loc_add": "0",
        "loc_del": "0",
    }


def find_and_replace(root, element_id, new_text):
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = str(new_text)


def justify_format(root, element_id, new_text, length=0):
    if isinstance(new_text, int):
        new_text = f"{new_text:,}"

    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)

    if length <= 0:
        return

    remaining = max(0, length - len(new_text))

    if remaining <= 2:
        dot_string = {0: "", 1: " ", 2: ". "}[remaining]
    else:
        dot_string = " " + ("." * remaining) + " "

    find_and_replace(root, f"{element_id}_dots", dot_string)


def update_svg(filename, stats):
    tree = etree.parse(filename)
    root = tree.getroot()

    justify_format(root, "age_data", stats["age_data"], 31)
    justify_format(root, "repo_data", stats["repo_data"], 6)
    justify_format(root, "star_data", stats["star_data"], 6)
    justify_format(root, "follower_data", stats["follower_data"], 6)
    justify_format(root, "commit_data", stats["commit_data"], 8)
    justify_format(root, "loc_data", stats["loc_data"], 9)

    find_and_replace(root, "contrib_data", stats["contrib_data"])
    find_and_replace(root, "loc_add", stats["loc_add"])
    find_and_replace(root, "loc_del", stats["loc_del"])

    tree.write(filename, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    stats = get_profile_stats()

    for svg_file in SVG_FILES:
        update_svg(svg_file, stats)

    print("Updated SVG stats:")
    for key, value in stats.items():
        print(f"{key}: {value}")
