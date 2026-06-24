import datetime
import xml.etree.ElementTree as ET
from dateutil import relativedelta

BIRTHDAY = datetime.datetime(2002, 1, 17)
SVG_FILES = ["dark_mode.svg", "light_mode.svg"]


def format_plural(value):
    return "s" if value != 1 else ""


def daily_readme(birthday):
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)

    age = "{} {}, {} {}, {} {}".format(
        diff.years,
        "year" + format_plural(diff.years),
        diff.months,
        "month" + format_plural(diff.months),
        diff.days,
        "day" + format_plural(diff.days),
    )

    if diff.months == 0 and diff.days == 0:
        age += "°ʚ(*´꒳`*)ɞ°"

    return age


def find_by_id(root, element_id):
    for element in root.iter():
        if element.attrib.get("id") == element_id:
            return element
    return None


def justify_format(root, element_id, new_text, length=29):
    new_text = str(new_text)

    value_element = find_by_id(root, element_id)
    dots_element = find_by_id(root, f"{element_id}_dots")

    if value_element is not None:
        value_element.text = new_text

    if dots_element is not None:
        remaining = max(0, length - len(new_text))

        if remaining <= 2:
            dot_string = {0: "", 1: " ", 2: ". "}[remaining]
        else:
            dot_string = " " + ("." * remaining) + " "

        dots_element.text = dot_string


def update_svg(filename, age_data):
    ET.register_namespace("", "http://www.w3.org/2000/svg")

    tree = ET.parse(filename)
    root = tree.getroot()

    justify_format(root, "age_data", age_data, 31)

    tree.write(filename, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    age_data = daily_readme(BIRTHDAY)

    for svg_file in SVG_FILES:
        update_svg(svg_file, age_data)
