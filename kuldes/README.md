# Küldjük el

Weboldal, ahol megadod a címzettet, a tárgyat, csatolsz egy vagy több fájlt,
és a címzett e-mailben megkapja őket. Az oldal a GitHub Pages-en fut, a levelet
a repó GitHub Actions workflow-ja küldi el SMTP-n, a te e-mail fiókodból
(Gmail App Password).

Oldal: `https://kozles.github.io/posztol/kuldes/`

Az oldal a saját címéből tudja, melyik repóba küldjön, ezért átnevezés vagy
áthelyezés után sem kell a kódot módosítani.

## Hogyan működik

1. Az oldal a fájlokat, a címzettet és a tárgyat egy csomagba teszi, és a
   böngészőben titkosítja (AES-GCM, a `FAJLKULDO_KULCS` kulccsal).
2. A titkosított csomagot git blobként feltölti a repóba (commit nem lesz
   belőle), majd elindítja a `Fájlküldés` workflow-t.
3. A workflow kibontja a csomagot, és a `kuldes/kuldo.py` elküldi a levelet.
4. Az oldal megvárja a futás végét, és kiírja, sikerült-e.

A repó nyilvános, de a feltöltött adat titkosított, és a napló nem írja ki a
címzettet, a tárgyat vagy a fájlneveket.

## Beállítás

**Repó secretek** (Settings → Secrets and variables → Actions → New repository secret):

| Név | Érték |
| --- | --- |
| `EMAIL_KULDO` | a feladó e-mail-cím, pl. `valami@gmail.com` |
| `EMAIL_JELSZO` | a fiók App Passwordje (Google-fiók → Biztonság → Alkalmazásjelszavak) |
| `FAJLKULDO_KULCS` | egy általad kitalált hosszú jelszó, ezt kell az oldalon is megadni |

Nem kötelező **változók** (ugyanott, a Variables fülön): `EMAIL_NEV` (feladónév),
`SMTP_HOST` (alapból `smtp.gmail.com`), `SMTP_PORT` (alapból `465`; `587` esetén STARTTLS).

**GitHub token az oldalhoz:** github.com → Settings → Developer settings →
Fine-grained tokens → Generate new token. Repository access: csak a
`kozles/posztol`; Permissions → `Contents`: Read and write, `Actions`: Read and write.

A tokent egyszer kell elmenteni: nyisd meg az oldalt `#admin` végződéssel
(`https://kozles.github.io/posztol/kuldes/#admin`), add meg a közös jelszót
(`FAJLKULDO_KULCS`) és a tokent, majd nyomd meg a mentés gombot. A token a jelszóval
titkosítva kerül a `kuldes/token.json` fájlba, a felhasználók nem látják.

A felhasználók az űrlapon csak a **Titkos kulcs** mezőt töltik ki (ez a
`FAJLKULDO_KULCS`). A böngésző megjegyzi, nem kell mindig beírni. Kulcs nélkül
nem lehet küldeni. Aki ismeri a kulcsot, az elvileg a tokent is kibonthatja,
ezért csak megbízható embereknek add oda.

## Korlátok

- Csak `@szamosiskola.hu` és `@tanulo.szamosiskola.hu` címre lehet küldeni. Ezt a workflow
  ellenőrzi; a listát az `ENGEDETT_DOMAINEK` változóval (vesszővel elválasztva) lehet módosítani.

- A csatolmányok együtt legfeljebb 25 MB-osak lehetnek (Gmail).
- Egyszerre legfeljebb 10 címzett.
- Egy küldés kb. fél-egy perc, ennyi idő alatt indul el és fut le a workflow.
