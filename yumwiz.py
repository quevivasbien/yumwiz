from enum import Enum, auto
import json
import os
import re
from dataclasses import dataclass
from fractions import Fraction
import unicodedata
from pypdf import PdfReader
from typing import List, Union


@dataclass
class Ingredient:
    quantity: Union[Fraction, None]
    unit: Union[str, None]
    name: str
    note: Union[str, None] = None

    def to_dict(self) -> dict:
        return {
            "quantity": str(self.quantity),
            "unit": self.unit,
            "name": self.name,
            "note": self.note
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Ingredient":
        return Ingredient(quantity=Fraction(data["quantity"]), unit=data["unit"], name=data["name"], note=data["note"])

@dataclass
class Recipe:
    name: str
    ingredients: List[Ingredient]

    def __str__(self) -> str:
        ingredients = '\n '.join(str(i) for i in self.ingredients)
        return f"{self.name}\n {ingredients}"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ingredients": [i.to_dict() for i in self.ingredients]
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Recipe":
        return Recipe(name=data["name"], ingredients=[Ingredient.from_dict(i) for i in data["ingredients"]])
    

def dump_json(recipes: List[Recipe], filename: str) -> None:
    """Dumps a list of Recipe objects to a JSON file.

    Args:
        recipes: A list of Recipe objects.
        filename: The name of the JSON file to write.
    """
    with open(filename, "w") as f:
        json.dump([r.to_dict() for r in recipes], f, indent=2)


def read_json(filename: str) -> List[Recipe]:
    """Reads a JSON file and returns a list of Recipe objects.

    Args:
        filename: The name of the JSON file to read.

    Returns:
        A list of Recipe objects.
    """
    with open(filename, "r") as f:
        data = json.load(f)
    return [Recipe.from_dict(d) for d in data]


def read_pdf(filename: str) -> str:
    """Reads a PDF file and returns its text content.

    Args:
        filename: The name of the PDF file to read.

    Returns:
        The text content of the PDF file.
    """
    reader = PdfReader(filename)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def replace_vulgar_fractions(text: str) -> str:
    """Replaces unicode vulgar fractions with ascii equivalents.
    """
    vulgar_fractions = {
        unicodedata.normalize("NFKD", "\u00BC"): "1/4",
        unicodedata.normalize("NFKD", "\u00BD"): "1/2",
        unicodedata.normalize("NFKD", "\u00BE"): "3/4",
        unicodedata.normalize("NFKD", "\u2150"): "1/7",
        unicodedata.normalize("NFKD", "\u2151"): "1/9",
        unicodedata.normalize("NFKD", "\u2152"): "1/10",
        unicodedata.normalize("NFKD", "\u2153"): "1/3",
        unicodedata.normalize("NFKD", "\u2154"): "2/3",
        unicodedata.normalize("NFKD", "\u2155"): "1/5",
        unicodedata.normalize("NFKD", "\u2156"): "2/5",
        unicodedata.normalize("NFKD", "\u2157"): "3/5",
        unicodedata.normalize("NFKD", "\u2158"): "4/5",
        unicodedata.normalize("NFKD", "\u2159"): "1/6",
        unicodedata.normalize("NFKD", "\u215A"): "5/6",
        unicodedata.normalize("NFKD", "\u215B"): "1/8",
        unicodedata.normalize("NFKD", "\u215C"): "3/8",
        unicodedata.normalize("NFKD", "\u215D"): "5/8",
        unicodedata.normalize("NFKD", "\u215E"): "7/8",
    }
    text = unicodedata.normalize("NFKD", text)
    for key, value in vulgar_fractions.items():
        text = text.replace(key, value)
    return text

def should_ignore(line: str) -> bool:
    return line.startswith("get step by step")

def should_keep(line: str) -> bool:
    pattern = r"pinch|handful|salt|(?:(?:freshly cracked black )?pepper)"
    return bool(re.search(pattern, line, re.IGNORECASE))

class LineAction(Enum):
    KEEP = auto()
    IGNORE = auto()
    COMBINE = auto()

    @staticmethod
    def from_line(line: str) -> "LineAction":
        if line[:1].isdigit():
            return LineAction.KEEP
        elif should_ignore(line):
            return LineAction.IGNORE
        elif should_keep(line):
            return LineAction.KEEP
        else:
            return LineAction.IGNORE

def extract_ingredient_lines(ingredient_text: str) -> Union[List[str], None]:
    """Extracts the ingredients section from a recipe text and returns a list of ingredients.

    Args:
        recipe_text: The full text of the recipe.

    Returns:
        A list of ingredients, where each ingredient is a string.
    """

    ingredient_text = replace_vulgar_fractions(ingredient_text)
    lines = ingredient_text.splitlines()
    # Loop through ingredients again to make sure each line starts with a number
    ingredients = []
    for i, line in enumerate(lines):
        line = line.strip().lower()
        action = LineAction.from_line(line)
        if action == LineAction.KEEP:
            ingredients.append(line)
        elif action == LineAction.COMBINE:
            ingredients[-1] += " " + line
    return ingredients

def to_fraction(string: str) -> Fraction:
    fraction_match = re.search(r"(\d+\s)?(\d)/(\d)", string)
    if fraction_match:
        whole = int(fraction_match.group(1) or 0)
        frac = Fraction(int(fraction_match.group(2)), int(fraction_match.group(3)))
        quantity = whole + frac
    else:
        quantity = Fraction(string)
    return quantity

def parse_ingredient(ingredient_line: str) -> Union[Ingredient, None]:
    """Parses an ingredient line and extracts quantity, unit, and ingredient name.

    Args:
        ingredient_line: A string representing a single ingredient line.

    Returns:
        A tuple of (quantity, unit, ingredient) if a match is found, otherwise None.
    """
    pattern = r"""
        (?:(?P<quantity>(?:(?:\d+\s)?\d/\d)|[\d\.]+)\s+)?  # Quantity (fractions, decimal or whole numbers)
        (?:(?P<unit>                                      # Unit group
            tsp|tbsp|teaspoons?|tablespoons?|cups?|ounces?|oz|lbs?|g|ml|kg|
            bunch(?:es)?|cans?|cloves?|handfuls?pinch(?:es)?|pounds?|pieces?|packages?
        )\.?\s+)?
        (?P<ingredient>[^,(]+)                            # Ingredient name (rest of the line up to comma or parenthesis)
        (?:.\s*(?P<notes>[^)]+))?                         # Modifier (rest of line after comma)
    """
    match = re.match(pattern, ingredient_line, re.VERBOSE)

    if match:
        quantity = match.group("quantity")
        return Ingredient(
            quantity=to_fraction(quantity) if quantity is not None else None,
            unit=match.group("unit"),
            name=match.group("ingredient").strip(),
            note=match.group("notes"),
        )
    else:
        print("No match found for:", ingredient_line)
        return None

def parse_ingredients(ingredient_text: str) -> List[Ingredient]:
    """Parses the ingredients section of a recipe and returns a list of Ingredient objects.

    Args:
        ingredient_text: The full text of the ingredients section.

    Returns:
        A list of Ingredient objects.
    """
    ingredient_lines = extract_ingredient_lines(ingredient_text)
    if not ingredient_lines:
        return []
    ingredients = []
    for line in ingredient_lines:
        ingredient = parse_ingredient(line)
        if ingredient:
            ingredients.append(ingredient)
    return ingredients


def parse_text(text: str, savename: Union[None, str] = None) -> List[Recipe]:
    """Parses a text file and returns a list of recipes.

    Args:
        text: The text content of the PDF file.

    Returns:
        A list of Recipe objects.
    """
    recipes = []
    pattern = r"""
        (?P<weekday>MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\n
        (?P<name>[A-Z\s]+)\nSERVINGS.*?
        INGREDIENTS(?P<ingredients>.*?)
        INSTRUCTIONS
    """
    for match in re.finditer(pattern, text, re.VERBOSE | re.DOTALL):
        name = re.sub(r'\s+', ' ', match.group("name").strip())
        ingredients = parse_ingredients(match.group("ingredients").strip())
        recipes.append(Recipe(name=name, ingredients=ingredients))

    if savename is not None:
        dump_json(recipes, savename)
    
    return recipes
    

def main(args):
    if len(args) < 2:
        print("Usage: python yumwiz.py <recipe_file> [--reload]")
        return

    recipe_file = args[1]
    reload_ = "--reload" in args
    # check if there's a pre-processed version of this file available
    json_name = f"{''.join(recipe_file.split('.')[:-1])}.json"
    if not reload_ and os.path.exists(json_name):
        recipes = read_json(json_name)
    elif os.path.exists(recipe_file):
        print("Reading PDF...")
        recipe_text = read_pdf(recipe_file)
        print("Processing recipes...")
        recipes = parse_text(recipe_text, savename=json_name)
    else:
        print(f"Recipe file not found: {recipe_file}")
        return

    for recipe in recipes:
        print(recipe)
    
if __name__ == "__main__":
    import sys
    main(sys.argv)
