"""Fájlküldő - a GitHub Actions workflow hívja (.github/workflows/kuldes.yml).

Letölti az oldal által feltöltött titkosított blobot, kibontja a
FAJLKULDO_KULCS secrettel, és SMTP-n (Gmail App Password) elküldi a
fájlokat a megadott címzettnek.

A repó nyilvános, ezért a napló SOHA nem írja ki a címzettet, a tárgyat
vagy a fájlneveket.
"""

import base64
import hashlib
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_OSSZMERET = 25 * 1024 * 1024  # a Gmail csatolmány-korlátja
MAX_CIMZETT = 10
ALAP_DOMAINEK = "szamosiskola.hu,tanulo.szamosiskola.hu"
PBKDF2_KOROK = 200_000  # ugyanannyi, mint az index.html-ben
EMAIL_MINTA = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hiba(szoveg):
    print(f"::error::{szoveg}")
    sys.exit(1)


def kotelezo(nev):
    ertek = os.environ.get(nev, "").strip()
    if not ertek:
        hiba(f"Hiányzik a(z) {nev} secret a repó beállításaiból.")
    return ertek


def blob_letoltes(sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        hiba("Érvénytelen blob azonosító.")
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/git/blobs/{sha}"
    keres = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(keres, timeout=60) as v:
        return v.read()


def kibontas(csomag, kulcs_jelszo, letolto=blob_letoltes):
    # A blob tartalma a titkosított bájtok base64-es alakja.
    titkos = base64.b64decode(letolto(csomag["sha"]))
    salt = base64.b64decode(csomag["salt"])
    iv = base64.b64decode(csomag["iv"])
    kulcs = hashlib.pbkdf2_hmac("sha256", kulcs_jelszo.encode("utf-8"), salt, PBKDF2_KOROK, 32)
    try:
        nyers = AESGCM(kulcs).decrypt(iv, titkos, None)
    except Exception:
        hiba("Nem sikerült kibontani a csomagot: az oldalon megadott kulcs nem egyezik a FAJLKULDO_KULCS secrettel.")
    return json.loads(nyers.decode("utf-8"))


def level_osszeallitas(adat, felado, felado_nev, domainek):
    cimzettek = [c.lower() for c in re.split(r"[,;\s]+", str(adat.get("cimzett", ""))) if c]
    if not cimzettek:
        hiba("Nincs címzett megadva.")
    if len(cimzettek) > MAX_CIMZETT:
        hiba(f"Legfeljebb {MAX_CIMZETT} címzett adható meg.")
    if any(not EMAIL_MINTA.match(c) for c in cimzettek):
        hiba("Érvénytelen e-mail-cím a címzettek között.")
    if any(c.rsplit("@", 1)[1] not in domainek for c in cimzettek):
        hiba("Csak az engedélyezett domainekre lehet küldeni.")

    targy = re.sub(r"[\r\n]+", " ", str(adat.get("targy", ""))).strip()
    if not targy:
        hiba("Nincs tárgy megadva.")

    fajlok = adat.get("fajlok") or []
    if not fajlok:
        hiba("Nincs csatolt fájl.")

    msg = EmailMessage()
    msg["From"] = formataddr((felado_nev, felado)) if felado_nev else felado
    msg["To"] = ", ".join(cimzettek)
    msg["Subject"] = targy

    uzenet = str(adat.get("uzenet", "")).strip()
    nevek = "\n".join(f"- {f.get('nev', 'fajl')}" for f in fajlok)
    msg.set_content((uzenet + "\n\n" if uzenet else "") + f"Csatolt fájlok ({len(fajlok)} db):\n{nevek}")

    osszmeret = 0
    for f in fajlok:
        bajtok = base64.b64decode(f.get("base64", ""))
        osszmeret += len(bajtok)
        tipus = str(f.get("tipus") or "application/octet-stream")
        fo, _, al = tipus.partition("/")
        if not fo or not al:
            fo, al = "application", "octet-stream"
        msg.add_attachment(bajtok, maintype=fo, subtype=al, filename=str(f.get("nev") or "fajl"))
    if osszmeret > MAX_OSSZMERET:
        hiba("A fájlok együtt nagyobbak 25 MB-nál.")
    return msg, cimzettek


def kuldes(msg, cimzettek, felado, jelszo, host, port):
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=60) as s:
            s.login(felado, jelszo)
            s.send_message(msg, from_addr=felado, to_addrs=cimzettek)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(felado, jelszo)
            s.send_message(msg, from_addr=felado, to_addrs=cimzettek)


def main():
    kulcs_jelszo = kotelezo("FAJLKULDO_KULCS")
    felado = kotelezo("EMAIL_KULDO")
    jelszo = kotelezo("EMAIL_JELSZO").replace(" ", "")
    host = os.environ.get("SMTP_HOST", "").strip() or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT", "").strip() or 465)

    try:
        csomag = json.loads(os.environ.get("CSOMAG", ""))
    except json.JSONDecodeError:
        hiba("Hibás csomag-adat.")

    domainek = {d.strip().lower().lstrip("@") for d in (os.environ.get("ENGEDETT_DOMAINEK", "").strip() or ALAP_DOMAINEK).split(",") if d.strip()}

    adat = kibontas(csomag, kulcs_jelszo)
    msg, cimzettek = level_osszeallitas(adat, felado, os.environ.get("EMAIL_NEV", "").strip(), domainek)

    try:
        kuldes(msg, cimzettek, felado, jelszo, host, port)
    except smtplib.SMTPAuthenticationError:
        hiba("Az SMTP szerver nem fogadta el a belépést: ellenőrizd az EMAIL_KULDO és EMAIL_JELSZO (App Password) secreteket.")
    except (smtplib.SMTPException, OSError) as e:
        hiba(f"Nem sikerült elküldeni a levelet ({type(e).__name__}).")

    print(f"Elküldve: {len(cimzettek)} címzett, {len(adat['fajlok'])} csatolmány.")


if __name__ == "__main__":
    main()
