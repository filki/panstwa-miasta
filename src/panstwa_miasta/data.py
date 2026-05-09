import csv
import pathlib

# Baza danych krajów
COUNTRIES = {
    "afganistan", "albania", "algieria", "andora", "angola", "antigua i barbuda", "arabia saudyjska",
    "argentyna", "armenia", "australia", "austria", "azerbejdżan", "bahamy", "bahrajn", "bangladesz",
    "barbados", "belgia", "belize", "benin", "bhutan", "białoruś", "boliwia", "bośnia i hercegowina",
    "botswana", "brazylia", "brunei", "bułgaria", "burkina faso", "burundi", "chile", "chiny",
    "chorwacja", "cypr", "czad", "czarnogóra", "czechy", "dania", "demokratyczna republika konga",
    "dominika", "dominikana", "dżibuti", "egipt", "ekwador", "erytrea", "estonia", "eswatini",
    "etiopia", "fidżi", "filipiny", "finlandia", "francja", "gabon", "gambia", "ghana", "grecja",
    "grenada", "gruzja", "gujana", "gwatemala", "gwinea", "gwinea bissau", "gwinea równikowa", "haiti",
    "hiszpania", "holandia", "honduras", "indie", "indonezja", "irak", "iran", "irlandia", "islandia",
    "izrael", "jamajka", "japonia", "jemen", "jordania", "kambodża", "kamerun", "kanada", "katar",
    "kazachstan", "kenia", "kirgistan", "kiribati", "kolumbia", "komory", "kongo", "korea południowa",
    "korea północna", "kostaryka", "kuba", "kuwejt", "laos", "lesotho", "liban", "liberia", "libia",
    "liechtenstein", "litwa", "luksemburg", "łotwa", "macedonia północna", "madagaskar", "malawi",
    "malediwy", "malezja", "mali", "malta", "maroko", "mauretania", "mauritius", "meksyk", "mikronezja",
    "mjanma", "birma", "mołdawia", "monako", "mongolia", "mozambik", "namibia", "nauru", "nepal",
    "niemcy", "niger", "nigeria", "nikaragua", "norwegia", "nowa zelandia", "oman", "pakistan", "palau",
    "panama", "papua-nowa gwinea", "paragwaj", "peru", "polska", "portugalia", "republika środkowoafrykańska",
    "republika zielonego przylądka", "rosja", "rpa", "republika południowej afryki", "rumunia", "rwanda",
    "saint kitts i nevis", "saint lucia", "saint vincent i grenadyny", "salwador", "samoa", "san marino",
    "senegal", "serbia", "seszele", "sierra leone", "singapur", "słowacja", "słowenia", "somalia",
    "sri lanka", "stany zjednoczone", "usa", "suazi", "sudan", "sudan południowy", "surinam", "syria",
    "szwajcaria", "szwecja", "tadżykistan", "tajlandia", "tajwan", "tanzania", "togo", "tonga",
    "trynidad i tobago", "tunezja", "turcja", "turkmenistan", "tuvalu", "uganda", "ukraina", "urugwaj",
    "uzbekistan", "vanuatu", "watykan", "wenezuela", "węgry", "wielka brytania", "anglia", "wietnam",
    "włochy", "wybrzeże kości słoniowej", "wyspy marshalla", "wyspy salomona", "wyspy świętego tomasza i książęca",
    "zambia", "zimbabwe", "zjednoczone emiraty arabskie"
}

# Bardzo okrojona lista najpopularniejszych imion na start (można rozbudowywać)
NAMES = {
    "adam", "adrian", "agata", "agnieszka", "alan", "albert", "aleksander", "aleksandra", "alicja",
    "amelia", "andrzej", "ania", "anna", "antoni", "antonina", "arek", "arkadiusz", "artur", "barbara",
    "bartłomiej", "bartosz", "bartek", "beata", "blanka", "błażej", "bogdan", "bogusław", "borys",
    "bożena", "brajan", "bruno", "cecylia", "celina", "cezary", "czarek", "cyprian", "czesław",
    "dagmara", "damian", "daniel", "danuta", "daria", "dariusz", "darek", "dawid", "diana", "dominik",
    "dominika", "dorota", "edyta", "eliza", "elżbieta", "emil", "emilia", "emilian", "eryk", "ewa",
    "ewelina", "fabian", "feliks", "filip", "franciszek", "franek", "gabriel", "gabriela", "grzegorz",
    "halina", "hanna", "hania", "henryk", "hubert", "iga", "ignacy", "igor", "ilona", "irena", "ireneusz",
    "iwo", "iwona", "iza", "izabela", "jacek", "jadwiga", "jakub", "kuba", "jan", "janina", "janusz",
    "jarek", "jarosław", "jeremi", "jerzy", "jola", "jolanta", "joanna", "asia", "józef", "józefa", "julia",
    "julian", "julita", "justyna", "kacper", "kaja", "kamil", "kamila", "karol", "karolina", "kasia",
    "katarzyna", "kazimierz", "klaudia", "klara", "klemens", "konrad", "kornel", "kornelia", "krystian",
    "krystyna", "krzysztof", "ksawery", "laura", "lena", "leon", "leszek", "lidia", "liliana", "lucyna",
    "ludwik", "luiza", "łucja", "łukasz", "maciej", "maciek", "magda", "magdalena", "maja", "maksymilian",
    "maks", "malwina", "marcel", "marcelina", "marcin", "marek", "maria", "marian", "mariola", "mariusz",
    "marta", "martyna", "maryla", "marzena", "mateusz", "matylda", "melania", "michalina", "michał",
    "mieczysław", "mikołaj", "milena", "miłosz", "mira", "mirella", "miron", "mirosław", "mirosława",
    "monika", "nadia", "natalia", "natan", "nela", "nikodem", "nina", "norbert", "ola", "olaf", "oleg",
    "oliwia", "oliwier", "oskar", "patrycja", "patryk", "paulina", "paweł", "piotr", "ola", "polina",
    "przemysław", "przemek", "radosław", "radek", "rafał", "robert", "roksana", "roman", "róża", "rufus",
    "rysiek", "ryszard", "sabina", "sandra", "sebastian", "seba", "seweryn", "sławomir", "sławek",
    "sonia", "stanisław", "stefan", "stella", "sylwia", "szymon", "tadeusz", "tamara", "teresa",
    "tomasz", "tomek", "tymon", "tymoteusz", "urszula", "ula", "wacław", "waldemar", "walenty",
    "wanda", "weronika", "wiesław", "wiesława", "wiktor", "wiktoria", "wiola", "wioletta", "witold",
    "władysław", "włodzimierz", "wojciech", "wojtek", "zbyszek", "zbigniew", "zdzisław", "zenon",
    "zofia", "zosia", "zuzanna", "zuza", "zygmunt"
}

# Dynamiczne ścieżki do plików danych
base_path = pathlib.Path(__file__).parent.parent.parent
data_dir = base_path / "data"

# Ładowanie imion z PESEL (CSV)
for csv_file in data_dir.glob("*.csv"):
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and row[0]:
                    NAMES.add(row[0].strip().lower())
        print(f"✅ Załadowano imiona z pliku: {csv_file.name}")
    except Exception as e:
        print(f"❌ Błąd podczas ładowania {csv_file}: {e}")

# Ładowanie zawodów z bazy hierarchiczny.json (wyekstrahowanej do raw_jobs.txt)
JOBS = set()
zawody_path = data_dir / "raw_jobs.txt"
if zawody_path.exists():
    try:
        with open(zawody_path, "r", encoding="utf-8") as f:
            for line in f:
                job = line.strip().lower().replace("*", "").replace(",", "").replace("(", "").replace(")", "").replace("/", " ")
                if job:
                    JOBS.add(job)
        print(f"✅ Załadowano zawodów (wersja ludzka): {len(JOBS)}")
    except Exception as e:
        print(f"❌ Błąd podczas ładowania zawodów: {e}")

print(f"Całkowita liczba unikalnych imion w bazie: {len(NAMES)}")
