"""Аватары и шутки: у каждой роли — свой зверь, можно выбрать другого или загрузить фото.

Зачем: на событии людей ищут глазами. Эмодзи или фото на карточке помогает узнать человека
в зале, а шутка про роль снимает напряжение у тех, кому трудно начать разговор первым.
"""
from __future__ import annotations

import base64
import io

# роль → (эмодзи, шутка про роль на трёх языках)
ROLE_ANIMAL = {
    "backend": ("🦫", {"ru": "бобр: строит то, чего никто не видит, но всё на этом держится",
                      "kk": "құндыз: ешкім көрмейтінді салады, бірақ бәрі соған сүйенеді",
                      "en": "beaver: builds what no one sees, yet everything rests on it"}),
    "frontend": ("🦚", {"ru": "павлин: отвечает за то, чтобы было красиво",
                       "kk": "тауыс: әдемі болуына жауап береді",
                       "en": "peacock: in charge of looking good"}),
    "fullstack": ("🦆", {"ru": "утка: и плавает, и ходит, и летает",
                        "kk": "үйрек: жүзеді де, жүреді де, ұшады да",
                        "en": "duck: swims, walks and flies"}),
    "mobile": ("🐿️", {"ru": "белка: всё своё носит в кармане",
                     "kk": "тиін: бар дүниесін қалтасында ұстайды",
                     "en": "squirrel: keeps everything in a pocket"}),
    "gamedev": ("🐉", {"ru": "дракон: живёт в выдуманных мирах",
                      "kk": "айдаһар: ойдан шығарылған әлемдерде өмір сүреді",
                      "en": "dragon: lives in invented worlds"}),
    "ml": ("🦜", {"ru": "попугай: учится на примерах и уверенно повторяет",
                 "kk": "тотықұс: мысалдардан үйреніп, сенімді қайталайды",
                 "en": "parrot: learns from examples and repeats them confidently"}),
    "data": ("🦉", {"ru": "сова: видит закономерности даже ночью",
                   "kk": "үкі: түнде де заңдылықты көреді",
                   "en": "owl: spots patterns even at night"}),
    "data_engineer": ("🐜", {"ru": "муравей: таскает данные туда, где они нужны",
                            "kk": "құмырсқа: деректі керек жерге тасиды",
                            "en": "ant: carries data to where it's needed"}),
    "devops": ("🐙", {"ru": "осьминог: восемь рук — восемь серверов",
                     "kk": "сегізаяқ: сегіз қол — сегіз сервер",
                     "en": "octopus: eight arms, eight servers"}),
    "security": ("🦔", {"ru": "ёж: никого не пускает без проверки",
                       "kk": "кірпі: тексермей ешкімді кіргізбейді",
                       "en": "hedgehog: lets no one in unchecked"}),
    "qa": ("🐈", {"ru": "кот: всегда найдёт, что уронить со стола",
                 "kk": "мысық: үстелден не құлатуға болатынын әрқашан табады",
                 "en": "cat: always finds something to knock off the table"}),
    "pm": ("🐕", {"ru": "пёс-пастух: собирает задачи и людей в одно стадо",
                 "kk": "бақташы ит: тапсырмалар мен адамдарды бір отарға жинайды",
                 "en": "sheepdog: herds tasks and people together"}),
    "analyst": ("🐝", {"ru": "пчела: превращает таблицы в мёд",
                      "kk": "ара: кестелерді балға айналдырады",
                      "en": "bee: turns spreadsheets into honey"}),
    "designer": ("🦄", {"ru": "единорог: рисует то, чего ещё не бывает",
                       "kk": "бірмүйіз: әлі жоқ нәрсені салады",
                       "en": "unicorn: draws what doesn't exist yet"}),
    "lead": ("🐘", {"ru": "слон: помнит все решения команды",
                   "kk": "піл: команданың барлық шешімін есте сақтайды",
                   "en": "elephant: remembers every team decision"}),
    "recruiter": ("🦅", {"ru": "орёл: замечает таланты с высоты",
                        "kk": "бүркіт: таланттарды биіктен байқайды",
                        "en": "eagle: spots talent from above"}),
    "founder": ("🦁", {"ru": "лев: ведёт стаю туда, где ещё никого нет",
                      "kk": "арыстан: тобын әлі ешкім жоқ жерге бастайды",
                      "en": "lion: leads the pride where no one has gone"}),
    "student": ("🐣", {"ru": "цыплёнок: только вылупился, а уже хочет в прод",
                      "kk": "балапан: жаңа шықты, бірақ продқа асығып тұр",
                      "en": "chick: just hatched, already wants to ship to prod"}),
}
EXTRA_AVATARS = ["🐱", "🦊", "🐼", "🐸", "🦖", "🤖", "👽", "😎"]


def role_avatar(role: str) -> str:
    return ROLE_ANIMAL.get(role, ("🙂", {}))[0]


def role_joke(role: str, lang: str) -> str:
    jokes = ROLE_ANIMAL.get(role, ("", {}))[1]
    return jokes.get(lang) or jokes.get("ru", "")


def avatar_choices(role: str) -> list[str]:
    own = role_avatar(role)
    return [own] + [a for a in EXTRA_AVATARS if a != own]


def profile_avatar(p: dict) -> str:
    """Эмодзи участника: свой выбор, а если его нет — зверь его роли."""
    return p.get("avatar") or role_avatar(p.get("role", ""))


# Фото: обрезаем по центру в квадрат 160 px и пересохраняем в WEBP. Исходный файл не храним:
# так в данных нет EXIF (геометка, модель телефона), а запись весит ~5 КБ.
PHOTO_SIZE = 160
MAX_UPLOAD = 6 * 1024 * 1024


def photo_data_uri(raw: bytes) -> str | None:
    if not raw or len(raw) > MAX_UPLOAD:
        return None
    from PIL import Image, ImageOps, UnidentifiedImageError  # Pillow ставится вместе со Streamlit
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        img = ImageOps.fit(img.convert("RGB"), (PHOTO_SIZE, PHOTO_SIZE))
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    out = io.BytesIO()
    img.save(out, "WEBP", quality=72)
    return "data:image/webp;base64," + base64.b64encode(out.getvalue()).decode("ascii")


# Запасные первые фразы: кнопка-кубик на карточке перебирает их после «умной» фразы из подбора.
FUN_OPENERS = {
    "ru": ["{name}, если бы ваш стек был блюдом — что бы это было?",
           "{name}, какой баг вы до сих пор вспоминаете с ужасом?",
           "{name}, какой самый странный вопрос вам задавали на собеседовании?",
           "{name}, кофе или чай — и сколько чашек уже сегодня?",
           "{name}, какой доклад здесь вы бы точно не пропустили?"],
    "kk": ["{name}, стегіңіз тағам болса, қандай тағам болар еді?",
           "{name}, әлі күнге дейін есіңізден кетпейтін баг бар ма?",
           "{name}, сұхбатта сізге қойылған ең оғаш сұрақ қандай болды?",
           "{name}, кофе ме, шай ма — бүгін неше кесе болды?",
           "{name}, мұнда қай баяндаманы міндетті түрде тыңдар едіңіз?"],
    "en": ["{name}, if your stack were a dish, what would it be?",
           "{name}, which bug still haunts you?",
           "{name}, what's the weirdest interview question you've been asked?",
           "{name}, coffee or tea — and how many cups so far today?",
           "{name}, which talk here would you never skip?"],
}


def opener(smart: str, name: str, lang: str, turn: int) -> str:
    """turn 0 — фраза из подбора (по общему стеку и интересам), дальше — по кругу запасные."""
    pool = FUN_OPENERS.get(lang) or FUN_OPENERS["ru"]
    if turn % (len(pool) + 1) == 0:
        return smart
    return pool[(turn - 1) % len(pool)].format(name=name.split()[0] if name else "")
