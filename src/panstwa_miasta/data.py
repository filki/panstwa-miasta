"""Runtime dictionaries used for answer validation.

Source of truth:

* ``COUNTRIES``  -> SQL table ``countries`` (seeded from
  :mod:`panstwa_miasta.countries_seed`). The set below is just an in-memory
  cache populated by :func:`reload_countries` after the database is
  initialised. Importing this module before :func:`db.init_db` runs is fine
  -- ``COUNTRIES`` will simply be empty until the first reload.
* ``NAMES``      -> hand-curated Polish first names below + any CSV files in
  ``data/`` (PESEL extracts). Migration to SQL is planned but out of scope
  for this change.
* ``JOBS``       -> ``data/*.txt`` (currently ``zawody.txt``) with a smart
  first-word alias for multi-word PKD entries.
"""

import csv
import pathlib

COUNTRIES: set[str] = set()


async def reload_countries() -> None:
    """Refresh ``COUNTRIES`` from the SQL ``countries`` table.

    Mutates the existing set in place so callers that already hold a
    reference (e.g. ``from panstwa_miasta.data import COUNTRIES``) keep
    seeing the up-to-date view.
    """
    from .db import load_country_norms

    norms = await load_country_norms()
    COUNTRIES.clear()
    COUNTRIES.update(norms)


# ----------------------------------------------------------------------------
# Polish first names (kept inline until the SQL migration -- see TODO).
# ----------------------------------------------------------------------------
# Bardzo okrojona lista najpopularniejszych imion na start (można rozbudowywać)
NAMES = {
    "adam",
    "adrian",
    "agata",
    "agnieszka",
    "alan",
    "albert",
    "aleksander",
    "aleksandra",
    "alicja",
    "amelia",
    "andrzej",
    "ania",
    "anna",
    "antoni",
    "antonina",
    "arek",
    "arkadiusz",
    "artur",
    "barbara",
    "bartłomiej",
    "bartosz",
    "bartek",
    "beata",
    "blanka",
    "błażej",
    "bogdan",
    "bogusław",
    "borys",
    "bożena",
    "brajan",
    "bruno",
    "cecylia",
    "celina",
    "cezary",
    "czarek",
    "cyprian",
    "czesław",
    "dagmara",
    "damian",
    "daniel",
    "danuta",
    "daria",
    "dariusz",
    "darek",
    "dawid",
    "diana",
    "dominik",
    "dominika",
    "dorota",
    "edyta",
    "eliza",
    "elżbieta",
    "emil",
    "emilia",
    "emilian",
    "eryk",
    "ewa",
    "ewelina",
    "fabian",
    "feliks",
    "filip",
    "franciszek",
    "franek",
    "gabriel",
    "gabriela",
    "grzegorz",
    "halina",
    "hanna",
    "hania",
    "henryk",
    "hubert",
    "iga",
    "ignacy",
    "igor",
    "ilona",
    "irena",
    "ireneusz",
    "iwo",
    "iwona",
    "iza",
    "izabela",
    "jacek",
    "jadwiga",
    "jakub",
    "kuba",
    "jan",
    "janina",
    "janusz",
    "jarek",
    "jarosław",
    "jeremi",
    "jerzy",
    "jola",
    "jolanta",
    "joanna",
    "asia",
    "józef",
    "józefa",
    "julia",
    "julian",
    "julita",
    "justyna",
    "kacper",
    "kaja",
    "kamil",
    "kamila",
    "karol",
    "karolina",
    "kasia",
    "katarzyna",
    "kazimierz",
    "klaudia",
    "klara",
    "klemens",
    "konrad",
    "kornel",
    "kornelia",
    "krystian",
    "krystyna",
    "krzysztof",
    "ksawery",
    "laura",
    "lena",
    "leon",
    "leszek",
    "lidia",
    "liliana",
    "lucyna",
    "ludwik",
    "luiza",
    "łucja",
    "łukasz",
    "maciej",
    "maciek",
    "magda",
    "magdalena",
    "maja",
    "maksymilian",
    "maks",
    "malwina",
    "marcel",
    "marcelina",
    "marcin",
    "marek",
    "maria",
    "marian",
    "mariola",
    "mariusz",
    "marta",
    "martyna",
    "maryla",
    "marzena",
    "mateusz",
    "matylda",
    "melania",
    "michalina",
    "michał",
    "mieczysław",
    "mikołaj",
    "milena",
    "miłosz",
    "mira",
    "mirella",
    "miron",
    "mirosław",
    "mirosława",
    "monika",
    "nadia",
    "natalia",
    "natan",
    "nela",
    "nikodem",
    "nina",
    "norbert",
    "ola",
    "olaf",
    "oleg",
    "oliwia",
    "oliwier",
    "oskar",
    "patrycja",
    "patryk",
    "paulina",
    "paweł",
    "piotr",
    "polina",
    "przemysław",
    "przemek",
    "radosław",
    "radek",
    "rafał",
    "robert",
    "roksana",
    "roman",
    "róża",
    "rufus",
    "rysiek",
    "ryszard",
    "sabina",
    "sandra",
    "sebastian",
    "seba",
    "seweryn",
    "sławomir",
    "sławek",
    "sonia",
    "stanisław",
    "stefan",
    "stella",
    "sylwia",
    "szymon",
    "tadeusz",
    "tamara",
    "teresa",
    "tomasz",
    "tomek",
    "tymon",
    "tymoteusz",
    "urszula",
    "ula",
    "wacław",
    "waldemar",
    "walenty",
    "wanda",
    "weronika",
    "wiesław",
    "wiesława",
    "wiktor",
    "wiktoria",
    "wiola",
    "wioletta",
    "witold",
    "władysław",
    "włodzimierz",
    "wojciech",
    "wojtek",
    "zbyszek",
    "zbigniew",
    "zdzisław",
    "zenon",
    "zofia",
    "zosia",
    "zuzanna",
    "zuza",
    "zygmunt",
}

# Dynamiczne ścieżki do plików danych
base_path = pathlib.Path(__file__).parent.parent.parent
data_dir = base_path / "data"

# Ładowanie imion z PESEL (CSV)
for csv_file in data_dir.glob("*.csv"):
    try:
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and row[0]:
                    NAMES.add(row[0].strip().lower())
        print(f"✅ Załadowano imiona z pliku: {csv_file.name}")
    except Exception as e:
        print(f"❌ Błąd podczas ładowania {csv_file}: {e}")

# Ladowanie zawodow z curated zawody.txt.
#
# Historia bledu: wczesniej rozbijalismy kazda linie na slowa >3 znaki, co
# wpychalo do JOBS smieci typu "spraw" / "specjalista" / "ofert" (z PKD-owych
# wielowyrazowych nazw w surowym raw_jobs.txt). raw_jobs.txt zniknal z repo,
# a tu zostawiamy pelne frazy plus jeden bezpieczny alias.
#
# Alias: dla N-wyrazowych entries dodajemy pierwsze slowo (>3 znakow) jako
# pojedynczy zawod -- zeby gracz wpisujacy "agent" trafial w zbior, gdy w
# zawody.txt jest tylko "agent celny", "agent klarujacy" itd. Pierwsze slowo
# w PKD jest niemal zawsze rzeczownikiem glownym (lekarz, agent, analityk),
# z wyjatkiem nielicznych entries zaczynajacych sie od przymiotnika
# kwalifikujacego -- te pomijamy.
JOB_ALIAS_PREFIX_SKIP = frozenset({"akredytowany", "pomocniczy"})

JOBS = set()
for txt_file in data_dir.glob("*.txt"):
    try:
        with open(txt_file, encoding="utf-8") as f:
            for line in f:
                job = line.strip().lower()
                if not job:
                    continue
                JOBS.add(job)
                words = job.split()
                if len(words) >= 2:
                    head = words[0]
                    if len(head) > 3 and head not in JOB_ALIAS_PREFIX_SKIP:
                        JOBS.add(head)
        print(f"OK Zaladowano zawody z pliku: {txt_file.name}")
    except Exception as e:
        print(f"BLAD podczas ladowania zawodow {txt_file.name}: {e}")

print(f"Całkowita liczba unikalnych imion w bazie: {len(NAMES)}")
