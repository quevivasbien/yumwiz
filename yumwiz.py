import re
from dataclasses import dataclass
from fractions import Fraction
from pypdf import PdfReader
from typing import List, Union


@dataclass
class Ingredient:
    quantity: Fraction
    unit: Union[str | None]
    name: str
    note: Union[str | None] = None

@dataclass
class Recipe:
    name: str
    ingredients: List[Ingredient]

    def __str__(self) -> str:
        ingredients = '\n '.join(str(i) for i in self.ingredients)
        return f"{self.name}\n {ingredients}"


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


def extract_ingredient_lines(ingredient_text: str) -> Union[List[str], None]:
    """Extracts the ingredients section from a recipe text and returns a list of ingredients.

    Args:
        recipe_text: The full text of the recipe.

    Returns:
        A list of ingredients, where each ingredient is a string.
    """

    lines = ingredient_text.splitlines()
    # Loop through ingredients again to make sure each line starts with a number
    ingredients = []
    for i, line in enumerate(lines):
        line = line.strip().lower()
        if line[:1].isdigit():
            ingredients.append(line)
        elif ingredients:
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
        (?P<quantity>(?:(?:\d+\s)?\d/\d)|\d+)\s+  # Quantity (fractions, whole numbers)
        (?:(?P<unit>                              # Unit group
            tsp|tbsp|teaspoons?|tablespoons?|cups?|ounces?|oz|lbs?|g|ml|kg|
            bunch(?:es)?|cans?|cloves?|pinch(?:es)?|pounds?|pieces?|packages?
        )\.?\s+)?
        (?P<ingredient>[^,(]+)                    # Ingredient name (rest of the line up to comma or parenthesis)
        (?:.\s*(?P<notes>[^)]+))?                 # Modifier (rest of line after comma)
    """
    match = re.match(pattern, ingredient_line, re.VERBOSE)

    if match:
        return Ingredient(
            quantity=to_fraction(match.group("quantity")),
            unit=match.group("unit"),
            name=match.group("ingredient").strip(),
            note=match.group("notes"),
        )
    else:
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


def parse_text(text: str) -> List[Recipe]:
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
    return recipes
    

def main(args):
    if len(args) < 2:
        print("Usage: python yumwiz.py <recipe_file>")
        return

    recipe_file = args[1]
    recipe_text = read_pdf(recipe_file)

    recipes = parse_text(recipe_text)

    for recipe in recipes:
        print(recipe)
    
if __name__ == "__main__":
    import sys
    main(sys.argv)
