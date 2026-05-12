#!/usr/bin/env python3
"""Regeneruje ``animals_seed_generated.py`` i ``plants_seed_generated.py``.

Uruchomienie (bez sieci): ``uv run python scripts/build_fauna_flora_mvp.py``

Listy to ręcznie kurowany MVP po polsku — rozszerzaj edytując stałe
``_ANIMALS_RAW`` / ``_PLANTS_RAW`` w tym skrypcie, potem ponownie odpal build.
"""

from __future__ import annotations

import pathlib


def _norm(s: str) -> str:
    s = s.strip().lower().replace("-", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def _emit(name: str, items: list[str]) -> str:
    lines = [
        '"""MVP: znormalizowane nazwy (jak ``manager.normalize_text``).',
        "Wygenerowane przez ``scripts/build_fauna_flora_mvp.py`` — nie edytuj ręcznie.",
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Final",
        "",
        f"{name}: Final[frozenset[str]] = frozenset({{",
    ]
    for it in items:
        lines.append(f'    "{it}",')
    lines.append("})")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    src = root / "src" / "panstwa_miasta"

    animals = sorted({_norm(x) for x in _ANIMALS_RAW.strip().splitlines() if x.strip()})
    plants = sorted({_norm(x) for x in _PLANTS_RAW.strip().splitlines() if x.strip()})

    (src / "animals_seed_generated.py").write_text(
        _emit("ANIMALS_NORMS", animals), encoding="utf-8"
    )
    (src / "plants_seed_generated.py").write_text(_emit("PLANTS_NORMS", plants), encoding="utf-8")
    print(f"OK: {len(animals)} zwierząt, {len(plants)} roślin -> {src}")


_ANIMALS_RAW = """
bóbr
bizon
bocian
baran
byk
cielę
cielak
dzik
delfin
foka
fretka
gęś
gepard
gołąb
goryl
indyk
irbis
jastrząb
jednorożec
jeż
jeżozwierz
jeleń
kangur
karp
koi
kobra
kogut
koza
kozioł
krokodyl
krowa
królik
kret
krewetka
kura
kurczak
łabędź
łosoś
lew
lama
lis
los
małpa
makak
mangusta
meduza
mewa
minóg
morświn
motyl
mucha
mysz
niedźwiedź
nietoperz
nosorożec
orka
orzeł
osioł
owca
pająk
panda
pantera
paw
pers
pingwin
puma
pyton
renifer
rekin
ryś
ryba
rybitwa
sarna
sęp
słoń
sokół
sowa
ślimak
świerszcz
świnka morska
świstak
szczupak
szczur
szpak
szympans
traszka
tryton
trzmiel
tuńczyk
tygrys
wąż
węgorz
wielbłąd
wieloryb
wiewiórka
wilk
wombat
wrona
wróbel
zebra
zając
żaba
żółw
żubr
żuk
żuraw
bocian biały
bocian czarny
kot domowy
pies domowy
niedźwiedź brunatny
niedźwiedź polarny
orzeł bielik
orzeł przedni
wąż zielony
żmija zielona
żmija szara
"""

_PLANTS_RAW = """
agrest
akacja
aralia
aronia
astilba
azalia
babka lancetowata
bambus
barwinek
bazylia
begonia
berberys
bez czarny
bez czerwony
bez pospolity
bluszcz
bodziszek
borówka czarna
borówka wysoka
bratek
brzoskwinia
bukszpan
bylica
chaber bławatek
chmiel
chryzantema
chrzan
cebula
cebula czerwona
cebula dymka
cyprys
cyprysik
cytryna
czarna porzeczka
czereśnia
czosnek
czosnek niedźwiedzi
czyściec
dąb
dąb szypułkowy
dalia
deren
dynia
endywia
forsycja
fuksja
geranium
gladiola
goździk
grusza
groszek
groch
hosta
hortensja
iglak
jabłoń
jałowiec
jarząb
jaśmin
jeżyna
jodła
judaszowiec
kaktus
kalafior
kalina
kapusta
kapusta pekińska
karczoch
kasztan
koniczyna
konwalia
koper
krokus
kukurydza
lawenda
len
lipa
lucerna
łubin
magnolia
malina
malwa
marchew
melisa
mięta
mniszek lekarski
modrzew
morela
narcyz
niecierpek
niezapominajka
ogórek
oliwka
orzech laskowy
orzech włoski
ostrożeń
owies
palma
paproć
pelargonia
peon
petunia
pigwa
pigwowiec
pomidor
por
porzeczka czerwona
porzeczka czarna
poziomka
pszenica
pszenżyto
róża
rokitnik
rozmaryn
ruta
rzodkiew
rzepa
seler
słonecznik
sosna
szafir
szalwia
szarotka
szparag
szpinak
śliwa
świerk
tulipan
winorośl
wiśnia
wierzba
wiesiołek
ziemniak
żurawina
żubrówka
"""

if __name__ == "__main__":
    main()
