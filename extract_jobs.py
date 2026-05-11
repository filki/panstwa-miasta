import json


def extract_opis(obj, result):
    if isinstance(obj, dict):
        if "opis" in obj:
            result.add(obj["opis"])
        for _k, v in obj.items():
            extract_opis(v, result)
    elif isinstance(obj, list):
        for item in obj:
            extract_opis(item, result)


with open("data/hierarchiczny.json", encoding="utf-8") as fh:
    d = json.load(fh)
res = set()
extract_opis(d, res)
with open("data/raw_jobs.txt", "w", encoding="utf-8") as f:
    for opis in sorted(res):
        f.write(opis + "\n")
