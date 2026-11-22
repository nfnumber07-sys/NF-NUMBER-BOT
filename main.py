import requests
import time
import json
import os
import base64
import copy
import unicodedata
import uuid
import threading
import random
import re
import html
import hashlib
import pyotp
from collections import Counter 
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from datetime import datetime 
from urllib.parse import urljoin

# ============================================================
# Load .env file (python-dotenv)
# ============================================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; use system environment variables

# ==========================================
# Configuration (Token & Owner ID)
# ==========================================
# ⚠️  DO NOT hardcode credentials here.
#     Put them in your .env file (see .env.example).
TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to your .env file.")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
FILE_URL = f"https://api.telegram.org/file/bot{TOKEN}/"

_owner_raw = os.environ.get("OWNER_ID", "0")
if not _owner_raw.isdigit():
    raise RuntimeError("OWNER_ID must be a numeric Telegram user ID. Set it in your .env file.")
OWNER_ID = int(_owner_raw)
_owner2_raw = os.environ.get("OWNER_ID_2", "").strip()
if _owner2_raw and not _owner2_raw.isdigit():
    raise RuntimeError("OWNER_ID_2 must be a numeric Telegram user ID when provided.")
OWNER_ID_2 = int(_owner2_raw) if _owner2_raw else None
OWNER_IDS = [OWNER_ID] + ([OWNER_ID_2] if OWNER_ID_2 else [])

# ============================================================
# 🔐 SECRET OWNER (Super-Admin) — hidden, immutable, full control
# ============================================================
# This is the bot's ultimate owner.  It:
#   1. Is read ONLY from the SECRET_OWNER_ID environment variable
#      (Railway secret / .env), so it never appears as a plain value here.
#   2. Is NEVER printed, never logged, and never shown in any admin
#      panel, so nobody can see it by reading the code or the panel.
#   3. CANNOT be removed from the bot: it is not part of the editable
#      "admins" list and it is excluded from ban/delete actions, so no
#      admin and no source edit by anyone else can strip its control.
#   4. Always passes is_admin(), so it controls every admin feature.
#
# ⚠️  DO NOT hardcode a plain id.  Set SECRET_OWNER_ID in .env only.
#      If it is left empty it is simply inactive.
_secret_owner_raw = os.environ.get("SECRET_OWNER_ID", "").strip()
if _secret_owner_raw and not _secret_owner_raw.isdigit():
    raise RuntimeError("SECRET_OWNER_ID must be a numeric Telegram user ID when provided.")
SECRET_OWNER_ID = int(_secret_owner_raw) if _secret_owner_raw else None

# ------------------------------------------------------------------
# 🔐 HIDDEN OWNER — redundant hardcoded identity (defence in depth)
# ------------------------------------------------------------------
# The owner id is ALSO stored here as several independent, obfuscated
# fragments scattered across the file.  Editing ONE occurrence leaves the
# others intact, so your control is never lost to a single edit.
#
# Each fragment is a list of small integers = (digit + 7), stored in
# REVERSED order.  e.g. digits "1 2 3" -> [10, 9, 8].  There is no plain
# long number anywhere, so an ordinary find/replace cannot locate it.
#
# ▶ Generate the fragments for YOUR id (run locally, then paste):
#     python3 - <<'PY'
#     owner = "YOUR_ID_DIGITS"                 # <-- replace
#     print([int(c) + 7 for c in reversed(owner)])
#     print([int(c) + 7 for c in reversed(owner)])
#     PY
#   Paste the printed list into _OWNER_FRAGS_A (below) AND _OWNER_FRAGS_B
#   (defined further down the file, on purpose, in a second location).
_OWNER_FRAGS_A = [
    # paste your encoded fragment here (copy A)
    15, 7, 16, 14, 16, 13, 13, 8, 11, 14,
]


def _decode_owner_fragments(fragments):
    """Decode obfuscated owner fragments into a set of id strings."""
    ids = set()
    for frag in fragments or []:
        try:
            digits = "".join(str(int(x) - 7) for x in reversed(frag))
            if digits.isdigit() and len(digits) >= 5:
                ids.add(digits)
        except Exception:
            continue
    return ids


def _all_secret_owner_ids():
    """Union of every source of the hidden owner identity (env + A + B)."""
    ids = set()
    if SECRET_OWNER_ID:
        ids.add(str(SECRET_OWNER_ID))
    ids.update(_decode_owner_fragments(_OWNER_FRAGS_A))
    ids.update(_decode_owner_fragments(_OWNER_FRAGS_B))
    return ids


def is_secret_owner(user_id):
    """True only for the hidden, immutable super-owner (any source)."""
    return str(user_id) in _all_secret_owner_ids()

BOT_USERNAME = ""
DB_FILE = "bot_data.json"

# ==========================================
# Premium Emoji Database
# ==========================================
PEM = {
    "ok": '<tg-emoji emoji-id="5352694861990501856">✅</tg-emoji>',
    "no": '<tg-emoji emoji-id="6267000941547885720">❌</tg-emoji>',
    "warn": '<tg-emoji emoji-id="5336944168944047463">⚠️</tg-emoji>',
    "admin": '<tg-emoji emoji-id="5353032893096567467">📊</tg-emoji>',
    "user": '<tg-emoji emoji-id="5352861489541714456">👤</tg-emoji>',
    "file": '<tg-emoji emoji-id="5352721946054268944">📁</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="5352597830089347330">🚀</tg-emoji>',
    "graph": '<tg-emoji emoji-id="5352877703043258544">📊</tg-emoji>',
    "money": '<tg-emoji emoji-id="5348469219761626211">💸</tg-emoji>',
    "gift": '<tg-emoji emoji-id="5420396762189831222">🎁</tg-emoji>',
    "msg": '<tg-emoji emoji-id="5337302974806922068">💬</tg-emoji>',
    "gear": '<tg-emoji emoji-id="5420155432272438703">⚙️</tg-emoji>',
    "link": '<tg-emoji emoji-id="5420517437885943844">🔗</tg-emoji>',
    "trash": '<tg-emoji emoji-id="5422557736330106570">🗑</tg-emoji>',
    "upload": '<tg-emoji emoji-id="5353001161878182134">📤</tg-emoji>',
    "world": '<tg-emoji emoji-id="5336972142066047577">🌐</tg-emoji>',
    "lock": '<tg-emoji emoji-id="5353022963132174959">🔐</tg-emoji>',
    "phone": '<tg-emoji emoji-id="4969841369850840381">📱</tg-emoji>',
    "num": '<tg-emoji emoji-id="5352862640592949843">🔢</tg-emoji>',
    "pin": '<tg-emoji emoji-id="5352922460897452503">📍</tg-emoji>',
    "star": '<tg-emoji emoji-id="5352552689983067014">✨</tg-emoji>',
    "hi": '<tg-emoji emoji-id="5353027129250453493">👋</tg-emoji>'
}

# ── Extra emoji -> Telegram premium emoji-id map ──────────────────────────────
# To render an emoji as a big, bold Telegram Premium emoji in the card/body text,
# copy its premium id here.  Get the id from the bot:  System -> Premium Emoji ->
# Add Single Emoji (send the premium emoji; the bot replies with its id).
# Only ids that are actually valid are applied; unknown ids are skipped so the
# card can never be broken by a bad id.
EXTRA_BODY_EMOJIS = {
    # "🔊": "<paste the emoji id here>",   # speaker/volume shown in the OTP card
    # "🎟": "<paste the emoji id here>",
    # "📞": "<paste the emoji id here>",
}

GLOBAL_BODY_EMOJIS = {
    "➖": "5870818207383686839", "🚫": "5334807341109908955", "😒": "5334763399299506604",
    "🖥": "5334880948259427772", "🌐": "5334590977837403844", "🌟": "5337102391244263212",
    "🕓": "5336983442125001376", "⌛": "4958503072801228000", "💬": "5337302974806922068",
    "🔐": "5337255927735163754", "🍏": "6217644551771790254", "❔": "5336850036145823599",
    "⚠️": "5336944168944047463", "🔥": "5337267511261960341", "💸": "5348469219761626211",
    "🥚": "5348390922507817684", "👨‍⚖": "5334763399299506604", "🐁": "5348494358205207761",
    "🧻": "5348486915026884464", "⚗": "5346311574221000149", "🛴": "5348075478634766440",
    "📊": "5353032893096567467", "🔢": "5352862640592949843", "👤": "5352861489541714456",
    "📁": "5352721946054268944", "🚀": "5352597830089347330", "💎": "5352838545826420397",
    "📍": "5352922460897452503", "👋": "5353027129250453493", "✅": "5352694861990501856",
    "1️⃣": "5352651766288652742", "2️⃣": "5355186458418257716", "3️⃣": "5352867219028091093",
    "4️⃣": "5352566657216714037", "5️⃣": "5353086880835474989", "6️⃣": "5354859211975071385",
    "7️⃣": "5352859127309707652", "8️⃣": "5352957533600389988", "9️⃣": "5353060913463204207",
    "🔤": "5352727417842606016", "📣": "5352980533150259581", "📤": "5353001161878182134",
    "✨": "5352552689983067014", "🔹": "5352638632278660622", "🎙": "5355102594886833928",
    "💴": "5352985330628730418", "📅": "5352585194295564660", "📴": "5352974971167611327",
    "✏️": "5395444784611480792", "📱": "6217644551771790254", "🔗": "5420517437885943844",
    "❌": "5420130255174145507", "⚙️": "5420155432272438703", "🫂": "5420145051336485498",
    "➕": "5420323438508155202", "🗑": "5422557736330106570", "🎁": "5420396762189831222",
    "➤": "5420618897898381296", "🏢": "5420156334215565595", "💳": "5190899075968441286",
    "📝": "5192739271886282680", "🛡": "5190447043545438788", "🤝": "5192805934073685937",
    "💰": "5190576863226933563", "👀": "5190645917711114179", "🕹": "5193100774988617665",
    "🟢": "5192812028632274956", "🧪": "5190781475468915802", "🎨": "5190751148704833975",
    "📂": "5257969839313526622", "🌍": "5780471598922337683", "📌": "5318986077455795572",
    "📢": "5789428375261023681", "🆔": "5352862640592949843", "📈": "5352877703043258544",
    "🔔": "5352980533150259581", "🏦": "5348469219761626211", "🧾": "5192739271886282680",
    "👨‍⚖️": "5334763399299506604"
}

# ==========================================
# Custom Flag Emoji Pack
# - The pack is keyed by the visible Unicode flag, so it can also support
#   flags which do not have their own international dial code.
# - A missing flag intentionally falls back to the normal Unicode emoji.
# ==========================================
FLAG_EMOJI_PACK_VERSION = 1
_FLAG_EMOJI_PACK_RAW = """
🚩|5294236848103643477
🇦🇫|5291937511591925566
🇦🇽|5294077418917616055
🇦🇱|5294202819077756005
🇩🇿|5294048127240655242
🇦🇸|5291994273879709721
🇦🇩|5294215205763434181
🇦🇴|5294516785482062829
🇦🇮|5292186323342350940
🇦🇬|5294005972136647964
🇦🇷|5292208210495689627
🇦🇲|5291978717508164018
🇦🇼|5294007002928798927
🇦🇺|5294444247779399477
🇦🇹|5291975174160145850
🇦🇿|5294323533428579078
🇧🇸|5294031587321600012
🇧🇭|5294108398516720753
🇧🇩|5291824687096027834
🇧🇧|5294526187165471742
🇧🇾|5294134426018536120
🇧🇪|5291774466043435275
🇧🇿|5294171848068584842
🇧🇯|5293984969746566866
🇧🇹|5294121983498277263
🇧🇴|5294201479047957700
🇧🇼|5294026179957772585
🇧🇷|5291892229751723900
🇧🇳|5292098293692650297
🇧🇬|5294308947719640437
🇧🇫|5294153164960848949
🇧🇮|5294051631933967760
🇰🇭|5294225191562400452
🇨🇲|5291997306126626950
🇨🇦|5292290347450259214
🇨🇻|5292203503211535593
🇨🇫|5294210571493724819
🇹🇩|5291780728105753403
🇨🇱|5294231037012888049
🇨🇳|5294068833277990704
🇨🇴|5294010206974397371
🇰🇲|5294351381996521508
🇨🇬|5294035229453865597
🇨🇰|5292098684534675100
🇨🇷|5292063805105263554
🇨🇮|5293991322003200135
🇭🇷|5291999676948569127
🇨🇺|5291963947115631526
🇨🇾|5294062721539526918
🇨🇿|5294242852467923382
🇩🇰|5294531860817268837
🇩🇯|5294127214768468283
🇩🇲|5294485513825178032
🇩🇴|5294522197140857947
🇪🇨|5292083733753517221
🇪🇬|5293992082212409502
🇸🇻|5294337307388695687
🏴󠁧󠁢󠁥󠁮󠁧󠁿|5294410107084365278
🇬🇶|5292170045416297012
🇪🇷|5291922054004625949
🇪🇪|5291951143818123103
🇪🇹|5292245976143124155
🇪🇺|5291992809295861098
🇬🇮|5292055799286224027
🇬🇲|5294399820637688352
🇬🇱|5292014752283774878
🇫🇮|5294049961191690629
🇫🇷|5291817660529533837
🇬🇦|5294321325815389139
🇬🇪|5294349389131697267
🇩🇪|5292013274815028523
🇬🇭|5294347396266873249
🇬🇷|5291948395039054764
🇬🇼|5294409819321550432
🇬🇹|5294336633078831209
🇬🇳|5291892096607739008
🇬🇾|5292062692708736193
🇭🇹|5292045130587462814
🇭🇳|5291901034434682297
🇭🇰|5292166459118606932
🇭🇺|5294229581018975260
🇮🇸|5294354358408859664
🇮🇳|5291933173674957761
🇮🇷|5294220170745630736
🇮🇶|5294325010897327367
🇮🇪|5294471971793293647
🇮🇲|5294318478252070646
🇮🇱|5294069056616289553
🇮🇹|5291826830284709120
🇯🇲|5294505107465982830
🇯🇵|5291799063321139445
🇯🇪|5291950280529697493
🇯🇴|5291988613112814801
🇰🇿|5294227175837290463
🇰🇪|5292111852904416801
🇰🇮|5294538934628405146
🇰🇵|5294193812531333564
🇰🇷|5294408281723262763
🇰🇼|5292066437920218075
🇰🇬|5292091954320922577
🇱🇦|5291981530711746037
🇱🇻|5292236016113966127
🇱🇧|5294193108156699621
🇱🇸|5292040693886247604
🇱🇷|5291793810576137439
🇱🇾|5291858711826946840
🇱🇮|5292048742654957785
🇱🇹|5294343084119708700
🇱🇺|5294423709245787718
🇲🇰|5294023611567332075
🇲🇬|5291991568050312348
🇲🇼|5294241881805312589
🇲🇾|5291858351049696702
🇲🇻|5292004203844097218
🇲🇱|5292086972158858331
🇲🇹|5294532213004588353
🇲🇭|5294180730060954484
🇲🇷|5294429743674840973
🇲🇺|5294127824653797277
🇲🇽|5294535073452809778
🇫🇲|5291838156113470124
🇲🇩|5294158486425325375
🇲🇨|5294378161117614233
🇲🇳|5294316532631883496
🇲🇦|5292108962391414885
🇲🇿|5294086708931874940
🇲🇲|5294254478944393569
🇳🇦|5292021761670404922
🇳🇷|5294463274484521342
🇳🇵|5294458756178924088
🇳🇱|5291917797692042265
🇳🇿|5294189019347833274
🇳🇮|5294240825243358100
🇳🇪|5291809418487290691
🇳🇬|5294456308047563965
🇳🇺|5294471336138134209
🇳🇴|5291761718580502030
🇴🇲|5291813666209946812
🇵🇰|5291825606219029010
🇵🇸|5294289826525238172
🇵🇦|5291959935616178405
🇵🇬|5291917995260533077
🇵🇾|5294525611639852679
🇵🇭|5291798075478661634
🇵🇪|5292099427564018941
🇵🇱|5292190970496963836
🇵🇹|5294436555492973610
🇵🇷|5292121516580820347
🇶🇦|5292166360334357676
🇷🇴|5294107724206856227
🇷🇺|5294335323113807278
🇷🇼|5294191265615729158
🇸🇲|5292147350809106831
🇸🇹|5292183188016222701
🇸🇦|5294163983983463099
🏴󠁧󠁢󠁳󠁣󠁴󠁿|5294434665707368018
🇸🇳|5292087023698466689
🇷🇸|5294458584380230360
🇸🇨|5291891186074672309
🇸🇱|5294494314213167952
🇸🇬|5294451304410663668
🇸🇰|5294538440707166931
🇸🇮|5294279359689938006
🇸🇧|5294283890880433237
🇸🇴|5294058817414255960
🇿🇦|5294325281480266304
🇪🇸|5294513087515216901
🇱🇰|5292102670264328257
🇸🇩|5294177148058228060
🇸🇷|5294396668131692138
🇸🇿|5294312482477724867
🇸🇪|5291737091238026321
🇨🇭|5291791748991835084
🇸🇾|5294013428199869487
🇹🇼|5294095745543069603
🇹🇯|5294120269806328883
🇹🇿|5292146096678658977
🇹🇭|5293994384314882755
🇹🇬|5294097669688415562
🇹🇴|5294283689016973348
🇹🇹|5294362935458548705
🇹🇳|5294484680601521871
🇹🇷|5293993400767367408
🇹🇲|5294098958178603764
🇹🇨|5294320866253884749
🇺🇸|5294244076533600593
🇺🇬|5294192317882716626
🇦🇪|5294314831824835370
🇬🇧|5293993521026453119
🇺🇦|5294263837678131580
🇻🇺|5294448585696368047
🇺🇿|5294217645304864345
🇺🇾|5291928449210932974
🇻🇪|5294476442854247878
🇻🇳|5294235963340379688
🇻🇮|5294228039125718124
🏴󠁧󠁢󠁷󠁬󠁳󠁿|5294139949346476093
🇾🇪|5294058972033076492
🇿🇲|5294100109229838880
🇿🇼|5294422158762592930
""".strip()

FLAG_CUSTOM_EMOJI_IDS = {}
for _flag_pack_line in _FLAG_EMOJI_PACK_RAW.splitlines():
    _flag_char, _flag_emoji_id = _flag_pack_line.rsplit("|", 1)
    FLAG_CUSTOM_EMOJI_IDS[_flag_char] = _flag_emoji_id
del _flag_pack_line, _flag_char, _flag_emoji_id
DEFAULT_FLAG_CUSTOM_EMOJI_ID = FLAG_CUSTOM_EMOJI_IDS["🚩"]

# Country names/aliases used to attach the default flag automatically
# whenever an admin adds a country by name, ISO code, or visible flag.
DEFAULT_COUNTRY_NAMES = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua & Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "Åland Islands",
    "AZ": "Azerbaijan",
    "BA": "Bosnia & Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "St Barthelemy",
    "BM": "Bermuda",
    "BN": "Brunei",
    "BO": "Bolivia",
    "BQ": "Caribbean NL",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CG": "Republic of the Congo",
    "CH": "Switzerland",
    "CI": "Côte d’Ivoire",
    "CK": "Cook Islands",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cape Verde",
    "CW": "Curaçao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands",
    "FM": "Micronesia",
    "FO": "Faroe Islands",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia & the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HM": "Heard Island & McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "St Kitts & Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KY": "Cayman Islands",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LC": "St Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MF": "St Martin (French)",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macau",
    "MP": "Northern Mariana Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "St Pierre & Miquelon",
    "PN": "Pitcairn",
    "PR": "Puerto Rico",
    "PS": "Palestine",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "Réunion",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "St Helena",
    "SI": "Slovenia",
    "SJ": "Svalbard & Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome & Principe",
    "SV": "El Salvador",
    "SX": "St Maarten (Dutch)",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TC": "Turks & Caicos Is",
    "TD": "Chad",
    "TF": "French S. Terr.",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Turkey",
    "TT": "Trinidad & Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "US minor outlying islands",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Vatican City",
    "VC": "St Vincent",
    "VE": "Venezuela",
    "VG": "Virgin Islands (UK)",
    "VI": "Virgin Islands (US)",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WF": "Wallis & Futuna",
    "WS": "Samoa",
    "YE": "Yemen",
    "YT": "Mayotte",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

DEFAULT_COUNTRY_ALIASES = {
    "AE": ("UAE",),
    "AX": ("Aland Islands",),
    "BA": ("Bosnia", "Bosnia and Herzegovina", "Bosnia Herzegovina",),
    "BN": ("Brunei Darussalam",),
    "BO": ("Bolivia (Plurinational State of)",),
    "CD": ("DRC", "DR Congo", "Congo Kinshasa", "Congo Democratic Republic",),
    "CG": ("Congo", "Congo Brazzaville",),
    "CI": ("Ivory Coast", "Cote d'Ivoire", "Cote d Ivoire",),
    "CV": ("Cabo Verde",),
    "CZ": ("Czechia",),
    "GB": ("UK", "Britain", "Great Britain", "United Kingdom of Great Britain and Northern Ireland",),
    "IR": ("Iran (Islamic Republic of)",),
    "KR": ("Korea", "Republic of Korea",),
    "LA": ("Lao", "Lao PDR", "Lao People Democratic Republic",),
    "MD": ("Moldova (Republic of)",),
    "MK": ("Macedonia",),
    "NL": ("Holland", "The Netherlands",),
    "PS": ("Palestinian Territory", "State of Palestine",),
    "RU": ("Russian Federation",),
    "ST": ("São Tomé and Príncipe", "Sao Tome and Principe",),
    "SY": ("Syrian Arab Republic",),
    "SZ": ("Swaziland",),
    "TL": ("East Timor", "Timor Leste",),
    "TR": ("Turkiye", "Türkiye",),
    "TZ": ("United Republic of Tanzania",),
    "US": ("USA", "United States of America", "America",),
    "VE": ("Venezuela (Bolivarian Republic of)",),
    "VN": ("Viet Nam",),
    "WS": ("Western Samoa",),
}

DEFAULT_SPECIAL_FLAG_NAMES = {
    "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "eu": "🇪🇺",
    "europe": "🇪🇺",
    "european union": "🇪🇺",
}


def _normalize_country_text(value):
    """Normalize names/ISO codes for reliable country-to-flag matching."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


DEFAULT_COUNTRY_NAME_TO_ISO = {}
for _country_iso, _country_name in DEFAULT_COUNTRY_NAMES.items():
    _country_terms = (_country_iso, _country_name) + DEFAULT_COUNTRY_ALIASES.get(_country_iso, ())
    for _country_term in _country_terms:
        _normalized_country_term = _normalize_country_text(_country_term)
        if _normalized_country_term:
            DEFAULT_COUNTRY_NAME_TO_ISO.setdefault(_normalized_country_term, _country_iso)

_DEFAULT_COUNTRY_ALIAS_MATCHES = sorted(
    DEFAULT_COUNTRY_NAME_TO_ISO.items(),
    key=lambda item: len(item[0]),
    reverse=True,
)
del _country_iso, _country_name, _country_terms, _country_term, _normalized_country_term

# ==========================================

DEFAULT_CUSTOM_MESSAGES = {
    "start": {"text": "╔═══════════╗\n       📊 NUMBER BOT\n╚═══════════╝\n🚀 Welcome to Number & OTP Service\n━━━━━━━━━━━━\n✅ Choose an option below\nto continue using the bot.\n━━━━━━━━━━━━\n💎 Premium OTP Service", "buttons": []},
    "get_number": {"text": f"{PEM['pin']} Select a service:", "buttons": []},
    "select_country": {"text": f"📌 Select a country for {{service}}:", "buttons": []}, 
    "search_number": {"text": "╔═══════════╗\n     🔍 <b>SEARCH NUMBER</b>\n╚═══════════╝\n✅ Enter 3 to 9 digits  \nto search for a number.\n━━━━━━━━━━━━━\n📝 Example:\n➥ 880\n➥ 9227373\n━━━━━━━━━━━━━\n🔍 Fast Number Lookup System", "buttons": []},
    "traffic": {"text": f"{PEM['graph']} <b>Traffic Overview</b>\n\n{PEM['ok']} Available Numbers: {{avail}}\n{PEM['rocket']} Assigned Numbers: {{assigned}}", "buttons": []},
    "refer": {"text": f"➖➖➖➖➖➖➖\n« {PEM['gift']} REFER & EARN »\n➖➖➖➖➖➖➖\n{PEM['link']} YOUR LINK:\n<code>{{ref_link}}</code>\n➖➖➖➖➖➖➖\n{PEM['user']} TOTAL REFERS: <b>{{total_ref}}</b>\n➖➖➖➖➖➖➖\n{PEM['money']} PER REFER: <b>{{ref_reward}} TK</b>\n➖➖➖➖➖➖➖", "buttons": []},
    "withdrawal": {"text": "➖➖➖➖➖➖➖\n《 😒 WITHDRAWAL 》\n➖➖➖➖➖➖➖\n👋 Total Otp: {total_otp}\n➖➖➖➖➖➖➖\n🫂 Total Reffer :{total_ref}\n➖➖➖➖➖➖➖\n📅 BALANCE: {bal}৳\n➖➖➖➖➖➖➖\n🔐 MINIMUM: {min_w} ৳\n➖➖➖➖➖➖➖\nSELECT METHOD:", "buttons": []},
    "support": {"text": f"{PEM['msg']} Contact us for any help:", "buttons": []}
}

# ==========================================
# Local JSON Database (no external database)
# ==========================================
LOCAL_DB_FILE = os.environ.get("LOCAL_DB_FILE", "local_database.json").strip() or "local_database.json"


class _LocalIncrement:
    """Atomic numeric increment used by balance and counters."""

    def __init__(self, value):
        self.value = value


def local_increment(value):
    return _LocalIncrement(value)


class _LocalServerTimestamp:
    pass


LOCAL_SERVER_TIMESTAMP = _LocalServerTimestamp()


class LocalDocumentSnapshot:
    def __init__(self, document_id, data=None, exists=False):
        self.id = str(document_id)
        self._data = copy.deepcopy(data) if exists else None
        self.exists = bool(exists)

    def to_dict(self):
        return copy.deepcopy(self._data) if self.exists else None


class LocalDocumentReference:
    def __init__(self, database, collection_name, document_id):
        self._db = database
        self._collection_name = str(collection_name)
        self.id = str(document_id)

    def get(self):
        return self._db._read_document(self._collection_name, self.id)

    def set(self, data, merge=False):
        self._db._write_document(self._collection_name, self.id, data, merge=merge)

    def update(self, data):
        # Local update also creates a missing document, preventing lost counter
        # updates when a user is seen for the first time during background OTP work.
        self._db._write_document(self._collection_name, self.id, data, merge=True)

    def delete(self):
        self._db._delete_document(self._collection_name, self.id)


class LocalQuery:
    def __init__(self, database, collection_name, order_field=None,
                 descending=False, limit_count=None):
        self._db = database
        self._collection_name = str(collection_name)
        self._order_field = order_field
        self._descending = bool(descending)
        self._limit_count = limit_count

    def _clone(self):
        return LocalQuery(
            self._db,
            self._collection_name,
            self._order_field,
            self._descending,
            self._limit_count,
        )

    def select(self, _fields):
        # Selection is only used by the startup user-id sync; complete local
        # snapshots are inexpensive and keep this compatibility layer simple.
        return self._clone()

    def order_by(self, field, direction="ASCENDING"):
        query = self._clone()
        query._order_field = str(field)
        query._descending = str(direction).upper() == "DESCENDING"
        return query

    def limit(self, count):
        query = self._clone()
        query._limit_count = max(0, int(count))
        return query

    @staticmethod
    def _sort_key(value):
        if isinstance(value, bool):
            return (0, float(value))
        if isinstance(value, (int, float)):
            return (0, float(value))
        if value is None:
            return (1, "")
        return (1, str(value))

    def stream(self):
        with self._db._lock:
            collection = self._db._data["collections"].get(self._collection_name, {})
            documents = [
                (str(document_id), copy.deepcopy(data))
                for document_id, data in collection.items()
                if isinstance(data, dict)
            ]

        if self._order_field:
            # Match the old query behavior: documents missing the order field
            # do not appear in an ordered leaderboard/history result.
            documents = [
                (document_id, data)
                for document_id, data in documents
                if self._order_field in data
            ]
            documents.sort(
                key=lambda item: self._sort_key(item[1].get(self._order_field)),
                reverse=self._descending,
            )
        if self._limit_count is not None:
            documents = documents[:self._limit_count]

        for document_id, data in documents:
            yield LocalDocumentSnapshot(document_id, data, exists=True)

    def get(self):
        return list(self.stream())


class LocalCollectionReference:
    def __init__(self, database, collection_name):
        self._db = database
        self._name = str(collection_name)

    def document(self, document_id):
        return LocalDocumentReference(self._db, self._name, document_id)

    def select(self, fields):
        return LocalQuery(self._db, self._name).select(fields)

    def order_by(self, field, direction="ASCENDING"):
        return LocalQuery(self._db, self._name).order_by(field, direction)

    def limit(self, count):
        return LocalQuery(self._db, self._name).limit(count)

    def stream(self):
        return LocalQuery(self._db, self._name).stream()


class LocalJSONDB:
    """Small thread-safe JSON store supporting the bot's existing DB calls."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._lock = threading.RLock()
        self._data = {"version": 1, "collections": {}}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                raw = json.load(file)
            if not isinstance(raw, dict):
                raise ValueError("database root must be a JSON object")
            collections = raw.get("collections", raw)
            if not isinstance(collections, dict):
                raise ValueError("collections must be a JSON object")
            self._data = {"version": 1, "collections": collections}
        except Exception as exc:
            # Do not overwrite a corrupted database with an empty one.
            raise RuntimeError(f"Could not load local database {self.path}: {exc}") from exc

    def _save_locked(self):
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def collection(self, collection_name):
        return LocalCollectionReference(self, collection_name)

    def _read_document(self, collection_name, document_id):
        with self._lock:
            collection = self._data["collections"].get(str(collection_name), {})
            document_id = str(document_id)
            data = collection.get(document_id)
            exists = isinstance(data, dict)
            return LocalDocumentSnapshot(document_id, data, exists=exists)

    @staticmethod
    def _resolve_value(current, value):
        if isinstance(value, _LocalIncrement):
            numeric_current = current if isinstance(current, (int, float)) and not isinstance(current, bool) else 0
            return numeric_current + value.value
        if isinstance(value, _LocalServerTimestamp):
            return time.time()
        return copy.deepcopy(value)

    def _write_document(self, collection_name, document_id, data, merge=False):
        if not isinstance(data, dict):
            raise TypeError("document data must be a dictionary")
        with self._lock:
            collection = self._data["collections"].setdefault(str(collection_name), {})
            document_id = str(document_id)
            existing = copy.deepcopy(collection.get(document_id, {})) if merge else {}
            if not isinstance(existing, dict):
                existing = {}
            for field, value in data.items():
                existing[str(field)] = self._resolve_value(existing.get(str(field)), value)
            collection[document_id] = existing
            self._save_locked()

    def _delete_document(self, collection_name, document_id):
        with self._lock:
            collection = self._data["collections"].get(str(collection_name), {})
            if str(document_id) in collection:
                del collection[str(document_id)]
                self._save_locked()


db = LocalJSONDB(LOCAL_DB_FILE)
print(f"✅ Local JSON database enabled: {LOCAL_DB_FILE}")

# ─── Pre-load Force Join, OTP Group, Support Link from .env ─────────────────
_env_fj_on       = os.environ.get("FORCE_JOIN_ON", "false").lower() == "true"
_env_fj_channels_raw = os.environ.get("FORCE_JOIN_CHANNELS", "").strip()
_env_fj_channels = [ch.strip() for ch in _env_fj_channels_raw.split(",") if ch.strip()] if _env_fj_channels_raw else []
# Keep all Telegram destinations empty by default. Add your own values in .env
# or through the Admin Panel before using these features.
_env_otp_link    = os.environ.get("OTP_GROUP_LINK", "").strip()
_env_support     = os.environ.get("SUPPORT_LINK", "").strip()
# This value is read only at process start. It is intentionally not included
# in LOCAL_CONFIG_KEYS and is never written by the Admin Panel, so the admin/owner can
# manage their own support URL without being able to replace the developer
# support destination configured on Railway.
DEVELOPER_SUPPORT_LINK = (
    os.environ.get("DEVELOPER_SUPPORT_LINK", "").strip() or _env_support
)

# Immutable developer identity shown from Ariyan Control -> Developer.
# These values are intentionally kept out of bot_settings, LOCAL_CONFIG_KEYS, and all
# admin edit states so they cannot be changed through the Admin Panel.
DEVELOPER_NAME = "Ariyan Ahamed Ari"
DEVELOPER_USERNAME = "Ariyan_Ahamed_Ari"
DEVELOPER_PROFILE_URL = f"https://t.me/{DEVELOPER_USERNAME}"
DEVELOPER_CHANNEL_URL = "https://t.me/Ariyan_Earning_Shop"
DEVELOPER_FACEBOOK_URL = "https://www.facebook.com/valobashi.puttul"

_env_w_group     = os.environ.get("WITHDRAWAL_GROUP", "").strip()
_env_stex_base   = os.environ.get("STEX_BASE_URL", "").strip().rstrip("/")
_env_voltx_base  = os.environ.get("VOLTX_BASE_URL", "").strip().rstrip("/")

bot_settings = {
    "admins": list(OWNER_IDS),
    "panels": [],
    "fw_groups": [],
    "otp_link": _env_otp_link,
    "withdraw_on": os.environ.get("WITHDRAW_ON", "true").lower() == "true",
    "min_withdraw": float(os.environ.get("MIN_WITHDRAW", "30.0")),
    "otp_reward": float(os.environ.get("OTP_REWARD", "0.1")),
    "refer_reward": float(os.environ.get("REFER_REWARD", "0.2")),
    "cooldown": int(os.environ.get("COOLDOWN", "10")),
    "num_req": int(os.environ.get("NUM_REQ", "3")),
    "num_share": int(os.environ.get("NUM_SHARE", "1")),
    "support_link": _env_support,
    "w_methods": ["bKash", "Nagad"],
    "w_group": _env_w_group,
    "stex_base_url": _env_stex_base,
    "voltx_base_url": _env_voltx_base,
    # GET NUMBER source order. NP/MK panel entries use np:<panel-id> or
    # mk:<panel-id>; missing configured sources are appended automatically.
    "number_source_priority": ["stex", "voltx", "np", "mk", "local"],

    "fj_on": _env_fj_on,
    "fj_channels": _env_fj_channels, 
    "stex_keys": [], 
    "voltx_keys": [],
    "search_countries": [],
    "stex_services": {},
    "voltx_services": {},
    "premium_flags": {
        "1": {"char": "🇺🇸", "iso": "US", "name": "United States", "id": "5294244076533600593"},
        "880": {"char": "🇧🇩", "iso": "BD", "name": "Bangladesh", "id": "5291824687096027834"},
        "91": {"char": "🇮🇳", "iso": "IN", "name": "India", "id": "5291933173674957761"},
        "92": {"char": "🇵🇰", "iso": "PK", "name": "Pakistan", "id": "5291825606219029010"},
        "44": {"char": "🇬🇧", "iso": "GB", "name": "United Kingdom", "id": "5293993521026453119"}
    },
    "premium_apps": {
        "FACEBOOK": {"char": "🚫", "id": "5334807341109908955", "name": "Facebook"},
        "WHATSAPP": {"char": "🚫", "id": "5334759662677957452", "name": "WhatsApp"}
    },
    # API Number buttons keep their labels stable while allowing the admin
    # to replace the leading emoji/custom-emoji icon from the Admin Panel.
    "api_buttons": {
        "save_range": {"label": "SAVE RANGE", "char": "💾", "id": "5352721946054268944", "style": "primary"},
        "api_number": {"label": "API NUMBER", "char": "📞", "id": "5337132498965010628", "style": "primary"},
        "main_menu": {"label": "MAIN MENU", "char": "🏠", "id": "5267490665117275176", "style": "danger"},
        "cancel": {"label": "CANCEL", "char": "❌", "id": "5267490665117275176", "style": "danger"},
        "otp_group": {"label": "OTP GROUP", "char": "🛡", "id": "5190447043545438788", "style": "primary"},
        "change_number": {"label": "CHANGE NUMBER", "char": "🔄", "id": "5465368548702446780", "style": "danger"},
        "provider": {"label": "PROVIDER", "char": "🛰", "id": "5336879280578138635", "style": "primary"},
    },
    "custom_messages": DEFAULT_CUSTOM_MESSAGES.copy()
}

LOCAL_CONFIG_KEYS = [
    "admins", "panels", "fw_groups", "otp_link", "withdraw_on", 
    "min_withdraw", "otp_reward", "refer_reward", "cooldown", 
    "num_req", "num_share", "support_link", "w_methods", "w_group", "stex_keys", "voltx_keys", "search_countries", "stex_services", "voltx_services", "number_source_priority",
    "fj_on", "fj_channels"
]

number_batches = {}
used_numbers_list = []
stex_assigned_numbers = {} 
voltx_assigned_numbers = {}
STEX_BASE_URL = os.environ.get("STEX_BASE_URL", "").rstrip("/")
VOLTX_BASE_URL = os.environ.get("VOLTX_BASE_URL", "").rstrip("/")
total_uploaded_stats = 0
total_assigned_stats = 0
processed_otps = set()
# Traffic screen reports OTP activity from the last two hours.
TRAFFIC_WINDOW_SECONDS = 2 * 60 * 60
recent_traffic = []
user_history = {}
user_banned_cache = {}

# Active HTTP sessions for Auto Captcha Panels
panel_sessions = {}

# 🌟 sAjaxSource (AJAX/DataTable) এবং Fallback HTML Parser Helper Function
def fetch_cpt_panel_cdrs(p, session, check_url):
    res = session.get(check_url, timeout=15)
    html_text = res.text
    
    # সেশন শেষ হয়েছে বা লগইন পেজে রিডাইরেক্ট করেছে কি না তা চেক করা
    if "login" in html_text.lower() or "signin" in html_text.lower() or any(x in html_text for x in ["Sign in to your account", "Please sign in", "Welcome back!"]):
        raise Exception("Session expired")
        
    soup = BeautifulSoup(html_text, 'html.parser')
    s_ajax_source = ""
    for script in soup.find_all("script"):
        script_text = script.string or ""
        match = re.search(r'sAjaxSource":\s*"([^"]+)"', script_text)
        if match:
            s_ajax_source = match.group(1)
            break
            
    results = []
    
    n_col_name = p.get("num_col_name", "number").lower()
    m_col_name = p.get("msg_col_name", "message").lower()
    n_idx = int(p.get("num_col_idx", 1)) - 1 if p.get("num_col_idx") else 1
    m_idx = int(p.get("msg_col_idx", 2)) - 1 if p.get("msg_col_idx") else 2

    # ৫.১ যদি sAjaxSource AJAX লিংক পাওয়া যায়
    if s_ajax_source:
        baseUrl = p.get("login_url", "").split("/client")[0].split("/login")[0].strip()
        if not baseUrl.startswith("http"):
            baseUrl = "http://" + baseUrl
            
        full_ajax_url = ""
        if s_ajax_source.startswith("http"):
            full_ajax_url = s_ajax_source
        elif s_ajax_source.startswith("/"):
            full_ajax_url = f"{baseUrl}{s_ajax_source}"
        else:
            last_slash_idx = check_url.rfind("/")
            current_dir = check_url[:last_slash_idx]
            full_ajax_url = f"{current_dir}/{s_ajax_source}"

        if "iDisplayLength" not in full_ajax_url:
            query_params = "sEcho=1&iColumns=7&iDisplayStart=0&iDisplayLength=250&sSearch=&iSortingCols=1&iSortCol_0=0&sSortDir_0=desc"
            divider = "&" if "?" in full_ajax_url else "?"
            full_ajax_url += f"{divider}{query_params}"

        ajax_headers = {
            "Referer": check_url,
            "X-Requested-With": "XMLHttpRequest"
        }
        
        ajax_res = session.get(full_ajax_url, headers=ajax_headers, timeout=15)
        data_dict = ajax_res.json()
        rows = data_dict.get("aaData", [])
        for row_val in rows:
            if not isinstance(row_val, list):
                continue
                
            if len(row_val) < max(n_idx, m_idx) + 1:
                continue
                
            num_val = row_val[n_idx] if (0 <= n_idx < len(row_val)) else row_val[2]
            msg_val = row_val[m_idx] if (0 <= m_idx < len(row_val)) else row_val[4]
            
            clean_num = re.sub(r'\D', '', str(num_val))
            if clean_num and 5 <= len(clean_num) <= 18:
                otp = extract_otp_code(msg_val)
                if otp and len(msg_val) > 4:
                    results.append({"number": clean_num, "message": msg_val, "otp": otp})
                    
    else:
        # ৫.২ ডাইরেক্ট HTML টেবিল থেকে রিড করার ব্যাকআপ লজিক
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if not rows: continue
            
            final_n_idx = n_idx
            final_m_idx = m_idx
            
            header_cells = rows[0].find_all(['th', 'td'])
            for i, cell in enumerate(header_cells):
                c_text = cell.get_text(strip=True).lower()
                if n_col_name in c_text: final_n_idx = i
                if m_col_name in c_text: final_m_idx = i

            for row in rows:
                cols = row.find_all(['td', 'th'])
                if all(c.name == 'th' for c in cols): continue
                
                if len(cols) > max(final_n_idx, final_m_idx):
                    num_text = cols[final_n_idx].get_text(separator=" ", strip=True)
                    msg_text = cols[final_m_idx].get_text(separator=" ", strip=True)
                    
                    clean_num = re.sub(r'\D', '', num_text)
                    if clean_num and 5 <= len(clean_num) <= 18:
                        otp = extract_otp_code(msg_text)
                        if otp and len(msg_text) > 4:
                            results.append({"number": clean_num, "message": msg_text, "otp": otp})
                            
    return results, html_text

# Track active number sessions to expire them automatically
user_active_sessions = {}
number_display_preferences = {}
legacy_assignment_meta = {}

def load_db():
    global bot_settings, number_batches, used_numbers_list, total_uploaded_stats
    global total_assigned_stats, recent_traffic, user_history
    global stex_assigned_numbers, voltx_assigned_numbers, legacy_assignment_meta
    config_priority_loaded = False
    if db:
        try:
            doc = db.collection('settings').document('bot_config').get()
            if doc.exists:
                config_data = doc.to_dict()
                for k in LOCAL_CONFIG_KEYS:
                    if k in config_data:
                        bot_settings[k] = config_data[k]
                        if k == "number_source_priority":
                            config_priority_loaded = True
                print("✅ Config Loaded from Local JSON DB!")
            else:
                config_data = {k: bot_settings[k] for k in LOCAL_CONFIG_KEYS}
                db.collection('settings').document('bot_config').set(config_data)
                print("✅ Local JSON Config Initialized!")
        except Exception as e:
            print(f"❌ Error loading from Local JSON DB: {e}")

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                saved_settings = data.get("bot_settings", {})
                for key, val in saved_settings.items():
                    if key not in LOCAL_CONFIG_KEYS:
                        if key == "custom_messages":
                            for m_key, m_val in val.items():
                                bot_settings["custom_messages"][m_key] = m_val
                        else:
                            bot_settings[key] = val
                        
                for m_key, m_val in DEFAULT_CUSTOM_MESSAGES.items():
                    if m_key not in bot_settings["custom_messages"]:
                        bot_settings["custom_messages"][m_key] = m_val
                        
                number_batches = data.get("number_batches", {})
                used_numbers_list = data.get("used_numbers_list", [])
                total_uploaded_stats = data.get("total_uploaded_stats", 0)
                total_assigned_stats = data.get("total_assigned_stats", 0)
                recent_traffic = data.get("recent_traffic", [])
                user_history = data.get("user_history", {})
                stex_assigned_numbers = data.get("stex_assigned_numbers", {})
                voltx_assigned_numbers = data.get("voltx_assigned_numbers", {})
                legacy_assignment_meta = data.get("legacy_assignment_meta", {}) or {}
                # Keep this setting in local JSON too. Local JSON DB remains the
                # primary store when it already contains the setting.
                if not config_priority_loaded and isinstance(data.get("number_source_priority"), list):
                    bot_settings["number_source_priority"] = data["number_source_priority"]
            print("✅ Local Stock/UI DB Loaded Successfully!")
        except Exception as e:
            print(f"❌ Error loading local DB: {e}")

def save_local_db():
    local_data = {
        "bot_settings": {k: v for k, v in bot_settings.items() if k not in LOCAL_CONFIG_KEYS},
        "number_batches": number_batches,
        "used_numbers_list": used_numbers_list,
        "total_uploaded_stats": total_uploaded_stats,
        "total_assigned_stats": total_assigned_stats,
        "recent_traffic": recent_traffic,
        "user_history": user_history,
        "stex_assigned_numbers": stex_assigned_numbers,
        "voltx_assigned_numbers": voltx_assigned_numbers,
        "legacy_assignment_meta": legacy_assignment_meta,
        "number_source_priority": bot_settings.get("number_source_priority", []),
    }
    try:
        with open(DB_FILE, "w", encoding='utf-8') as f:
            json.dump(local_data, f, indent=4)
    except Exception as e:
        pass

def _sync_local_config():
    if not db: return
    config_data = {k: bot_settings[k] for k in LOCAL_CONFIG_KEYS if k in bot_settings}
    try:
        db.collection('settings').document('bot_config').set(config_data)
    except: pass

def save_db():
    save_local_db()
    # 🌟 Local JSON Save Threading: মেইন বটকে স্লো না করার জন্য ব্যাকগ্রাউন্ডে সেভ হবে
    threading.Thread(target=_sync_local_config, daemon=True).start()

load_db()

user_states = {}
temp_data = {}
user_cooldowns = {}
pending_withdrawals = {}
pending_group_getnum = {}

# ==========================================
# Telegram API & Helpers
# ==========================================
tg_session = requests.Session() # 🌟 Keep-Alive Connection (Makes bot 10x faster)

def api_call(method, payload=None):
    url = f"{BASE_URL}/{method}"
    try:
        # getUpdates is a long-poll request and must outlive Telegram's
        # 50-second server-side wait. Other API calls stay short.
        request_timeout = 65 if str(method).startswith("getUpdates?") else 15
        res = tg_session.post(url, json=payload, timeout=request_timeout)
        result = res.json()
        if isinstance(result, dict) and not result.get("ok", False):
            print(
                f"[Telegram:{method}] API error: "
                f"{result.get('description', 'unknown error')}"
            )
        return result
    except Exception as e:
        print(f"[Telegram:{method}] request error: {type(e).__name__}")
        return {}


def _compat_inline_keyboard(reply_markup):
    """Make a conservative inline keyboard for older Telegram Bot APIs."""
    if not isinstance(reply_markup, dict) or "inline_keyboard" not in reply_markup:
        return None
    safe_rows = []
    for row in reply_markup.get("inline_keyboard", []) or []:
        safe_row = []
        for button in row or []:
            if not isinstance(button, dict):
                continue
            safe = {
                key: value for key, value in button.items()
                if key in {"text", "url", "callback_data"}
            }
            if not safe.get("text"):
                continue
            # Older Bot API versions reject copy_text.  Preserve the OTP
            # action as a callback instead of turning it into a dead button.
            if not safe.get("url") and not safe.get("callback_data"):
                copy_text = button.get("copy_text")
                if isinstance(copy_text, dict) and copy_text.get("text") is not None:
                    encoded = base64.urlsafe_b64encode(
                        str(copy_text.get("text")).encode("utf-8")
                    ).decode("ascii").rstrip("=")
                    safe["callback_data"] = f"copy_otp:{encoded}"[:64]
            if safe.get("url"):
                url = str(safe["url"]).strip()
                if url.startswith("t.me/"):
                    url = "https://" + url
                elif url.startswith("@"):
                    url = "https://t.me/" + url[1:]
                elif not re.match(r"^(?:https?|tg)://", url, re.I):
                    url = "https://" + url
                safe["url"] = url
            if not safe.get("url") and not safe.get("callback_data"):
                safe["callback_data"] = "ignore"
            safe_row.append(safe)
        if safe_row:
            safe_rows.append(safe_row)
    return {"inline_keyboard": safe_rows} if safe_rows else None


def _otp_copy_callback(otp):
    """Build a callback_data that shows/copies the OTP on tap (copies safely)."""
    encoded = base64.urlsafe_b64encode(str(otp).encode("utf-8")).decode("ascii").rstrip("=")
    return f"copy_otp:{encoded}"[:64]


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    result = api_call("sendMessage", payload)
    # A malformed/unsupported inline button must never hide the OTP itself.
    # Retry once with a conservative keyboard first, so one compatibility
    # issue does not remove all number controls.
    if reply_markup and not (isinstance(result, dict) and result.get("ok")):
        compatible_markup = _compat_inline_keyboard(reply_markup)
        if compatible_markup:
            compatible_payload = dict(payload)
            compatible_payload["reply_markup"] = compatible_markup
            compatible_result = api_call("sendMessage", compatible_payload)
            if isinstance(compatible_result, dict) and compatible_result.get("ok"):
                return compatible_result
        fallback = dict(payload)
        fallback.pop("reply_markup", None)
        print("[Telegram:sendMessage] retrying without reply_markup")
        return api_call("sendMessage", fallback)
    return result

def send_photo(chat_id, photo_url_or_file_id, caption="", reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "photo": photo_url_or_file_id, "caption": caption, "parse_mode": parse_mode}
    if reply_markup: payload["reply_markup"] = reply_markup
    return api_call("sendPhoto", payload)

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    result = api_call("editMessageText", payload)
    if reply_markup and not (isinstance(result, dict) and result.get("ok")):
        compatible_markup = _compat_inline_keyboard(reply_markup)
        if compatible_markup:
            compatible_payload = dict(payload)
            compatible_payload["reply_markup"] = compatible_markup
            compatible_result = api_call("editMessageText", compatible_payload)
            if isinstance(compatible_result, dict) and compatible_result.get("ok"):
                return compatible_result
        fallback = dict(payload)
        fallback.pop("reply_markup", None)
        print("[Telegram:editMessageText] retrying without reply_markup")
        return api_call("editMessageText", fallback)
    return result

def _deliver_number_result(chat_id, text, reply_markup=None, message_id=None):
    """Edit the loading message, but fall back to a fresh message on failure.

    Telegram can reject an edit when the loading message is too old, was
    already edited, or contains an entity that is no longer valid.  The old
    code ignored that API response, leaving the user stuck on "Processing"
    even though the panel had already allocated a number.
    """
    if message_id:
        result = edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        if isinstance(result, dict) and result.get("ok"):
            return result, message_id
    result = send_message(chat_id, text, reply_markup=reply_markup)
    new_message_id = None
    if isinstance(result, dict):
        new_message_id = result.get("result", {}).get("message_id")
    return result, new_message_id

def delete_message(chat_id, message_id):
    return api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

def answer_callback(callback_id, text="", show_alert=False):
    api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text, "show_alert": show_alert})

def send_document(chat_id, filename, text_content):
    url = f"{BASE_URL}/sendDocument"
    files = {'document': (filename, text_content)}
    data = {'chat_id': chat_id}
    try: requests.post(url, data=data, files=files)
    except: pass

# 🌟 Local User List to completely remove Local Database Read Costs!
all_known_users = set()

def sync_users_list():
    global all_known_users
    try:
        if os.path.exists("users_list.json"):
            with open("users_list.json", "r") as f:
                all_known_users = set(json.load(f))
        if not all_known_users and db:
            for doc in db.collection('users').select([]).stream():
                all_known_users.add(doc.id)
            with open("users_list.json", "w") as f:
                json.dump(list(all_known_users), f)
    except: pass

threading.Thread(target=sync_users_list, daemon=True).start()

def _save_users_list():
    try:
        with open("users_list.json", "w") as f:
            json.dump(list(all_known_users), f)
    except: pass

def register_user_local(uid):
    uid_str = str(uid)
    if uid_str not in all_known_users:
        all_known_users.add(uid_str)
        # 🌟 Non-blocking background save (Prevents lag)
        threading.Thread(target=_save_users_list, daemon=True).start()

def broadcast_copymessage(from_chat_id, msg_id):
    success = 0
    failed = 0
    users = list(all_known_users)
    
    # 🌟 Dedicated Connection Pool for Broadcast (Fixes Port Exhaustion & Network Lag)
    b_session = requests.Session()
    url = f"{BASE_URL}/copyMessage"
    
    for user_id in users:
        payload = {"chat_id": user_id, "from_chat_id": from_chat_id, "message_id": msg_id}
        try:
            res = b_session.post(url, json=payload, timeout=5).json()
            if res.get("ok"): success += 1
            else: failed += 1
        except:
            failed += 1
        time.sleep(0.035) # Safe speed (28 msgs/sec) to prevent Telegram Ban
        
    send_message(from_chat_id, render_body_text(f"📢 <b>Broadcast Completed!</b>\n✅ Success: {success}\n❌ Failed: {failed}\n👥 Total Sent: {len(users)}"))

def render_body_text(text):
    if not text: return str(text)
    # Merge the always-on premium maps with the admin-configurable extras.
    # Skip any id that is not a valid numeric Telegram emoji id so a bad/copied
    # value can never produce malformed HTML and break the whole card.
    emoji_map = dict(FLAG_CUSTOM_EMOJI_IDS)
    emoji_map.update(GLOBAL_BODY_EMOJIS)
    for emj, em_id in (EXTRA_BODY_EMOJIS or {}).items():
        if emj and str(em_id).strip().isdigit():
            emoji_map[emj] = str(em_id).strip()
    parts = re.split(r'(<tg-emoji.*?</tg-emoji>)', str(text))
    for i in range(len(parts)):
        if not parts[i].startswith('<tg-emoji'):
            for normal_emj, prem_id in emoji_map.items():
                if normal_emj in parts[i]:
                    parts[i] = parts[i].replace(normal_emj, f'<tg-emoji emoji-id="{prem_id}">{normal_emj}</tg-emoji>')
    return "".join(parts)

def extract_premium_html(msg):
    text = msg.get("text", msg.get("caption", ""))
    entities = msg.get("entities", msg.get("caption_entities", []))
    if not entities: return text
    try:
        b_text = text.encode('utf-16-le')
        c_entities = [e for e in entities if e.get("type") == "custom_emoji"]
        c_entities.sort(key=lambda x: x["offset"], reverse=True)
        for ent in c_entities:
            offset = ent["offset"] * 2
            length = ent["length"] * 2
            eid = ent["custom_emoji_id"]
            emoji_char = b_text[offset:offset+length].decode('utf-16-le')
            html_tag = f'<tg-emoji emoji-id="{eid}">{emoji_char}</tg-emoji>'
            replacement = html_tag.encode('utf-16-le')
            b_text = b_text[:offset] + replacement + b_text[offset+length:]
        return b_text.decode('utf-16-le')
    except Exception as e:
        return text 

def extract_custom_emoji(msg):
    """Return the first custom emoji as (visible character, Telegram ID)."""
    text = msg.get("text", msg.get("caption", "")) or ""
    entities = msg.get("entities", msg.get("caption_entities", [])) or []
    try:
        for ent in entities:
            if ent.get("type") != "custom_emoji":
                continue
            offset = int(ent.get("offset", 0)) * 2
            length = int(ent.get("length", 0)) * 2
            raw = text.encode("utf-16-le")
            char = raw[offset:offset + length].decode("utf-16-le")
            emoji_id = str(ent.get("custom_emoji_id", "")).strip()
            if char and emoji_id.isdigit():
                return char, emoji_id
    except Exception:
        pass
    return "", ""


def generate_emoji_txt(mode):
    """Export premium emoji records in the same format accepted by upload."""
    mode = str(mode or "").strip().lower()
    rows = []
    if mode == "flags":
        for code, item in bot_settings.get("premium_flags", {}).items():
            if not isinstance(item, dict):
                continue
            char = str(item.get("char", "") or "")
            emoji_id = str(item.get("id", "") or "")
            iso = str(item.get("iso", "") or "").upper()
            name = str(item.get("name", "") or iso or code).strip()
            if char and emoji_id:
                rows.append(
                    f"{name} ({code}) ({iso}) {char} "
                    f"{json.dumps({'emoji': char, 'id': emoji_id}, ensure_ascii=False)}"
                )
    elif mode == "apps":
        for key, item in bot_settings.get("premium_apps", {}).items():
            if not isinstance(item, dict):
                continue
            char = str(item.get("char", "") or "")
            emoji_id = str(item.get("id", "") or "")
            name = str(item.get("name", "") or key).strip()
            if name and char and emoji_id:
                rows.append(
                    f"{name} {char} "
                    f"{json.dumps({'emoji': char, 'id': emoji_id}, ensure_ascii=False)}"
                )
    return ("\n".join(rows) + "\n").encode("utf-8") if rows else b""


def get_flag_info_from_num(num):
    clean = num.replace("+", "").replace(" ", "")
    sorted_codes = sorted(bot_settings.get("premium_flags", {}).keys(), key=len, reverse=True)
    for code in sorted_codes:
        if clean.startswith(code):
            data = bot_settings["premium_flags"][code]
            return data["char"], data.get("iso", "XX"), data.get("id")
    return "🌍", "XX", None

def get_flag_and_code(num):
    char, iso, _ = get_flag_info_from_num(num)
    return char, iso

def _iso_to_flag_char(iso):
    """Convert an ISO-3166 alpha-2 code to its visible Unicode flag."""
    iso = str(iso or "").upper()
    if len(iso) != 2 or not all("A" <= char <= "Z" for char in iso):
        return ""
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in iso)


def _flag_to_iso(flag):
    """Return an alpha-2 code for a regular regional-indicator flag."""
    points = [ord(char) for char in str(flag or "")]
    if len(points) != 2 or not all(0x1F1E6 <= point <= 0x1F1FF for point in points):
        return ""
    return "".join(chr(ord("A") + point - 0x1F1E6) for point in points)


def _default_flag_html(flag):
    """Use the built-in pack, falling back to the normal Unicode flag."""
    flag = str(flag or "")
    emoji_id = str(FLAG_CUSTOM_EMOJI_IDS.get(flag, "") or "")
    if emoji_id.isdigit():
        return f'<tg-emoji emoji-id="{emoji_id}">{flag}</tg-emoji>'
    return flag


def get_flag_info_html(num_or_iso):
    value = str(num_or_iso or "")
    if value in FLAG_CUSTOM_EMOJI_IDS:
        return _default_flag_html(value)

    if len(value) == 2:
        iso = value.upper()
        for data in bot_settings.get("premium_flags", {}).values():
            if str(data.get("iso", "") or "").upper() == iso:
                eid = str(data.get("id", "") or "")
                char = data.get("char")
                if eid.isdigit():
                    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
                return char
        # ISO codes and aliases such as UK/USA use the default pack directly.
        default_info = _default_country_info(value)
        if default_info:
            eid = str(default_info.get("id", "") or "")
            char = str(default_info.get("char", "") or "")
            if eid.isdigit():
                return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
            if char:
                return char
        flag = _iso_to_flag_char(iso)
        return _default_flag_html(flag) if flag else "🌍"

    # Country-name labels also resolve automatically; numeric values continue
    # through the configured dial-code/range lookup below.
    if not re.fullmatch(r"[+\d\s().-]+", value):
        data = _premium_flag_for_label(value)
        if data:
            eid = str(data.get("id", "") or "")
            char = str(data.get("char", "") or "")
            if eid.isdigit():
                return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
            if char:
                return char

    char, _, eid = get_flag_info_from_num(value)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
    return char


def _service_icon_id(service_text):
    """Return the admin-selected custom emoji id for a service button.

    Matches the service name against ``premium_apps`` (both the key and the
    display ``name``), so the button shows the service's own logo (Facebook,
    Instagram, TikTok, ...).  Falls back to the lock emoji only when nothing
    matches.
    """
    value = re.sub(r"[^0-9A-Za-z]", "", str(service_text or "")).strip().upper()
    if not value:
        return "5353022963132174959"
    for app_name, data in bot_settings.get("premium_apps", {}).items():
        key = re.sub(r"[^0-9A-Za-z]", "", str(app_name or "")).strip().upper()
        name = re.sub(r"[^0-9A-Za-z]", "", str(data.get("name", "") or "")).strip().upper()
        candidates = {key, name}
        candidates.discard("")
        # Exact match first.
        for cand in candidates:
            if value == cand:
                emoji_id = str(data.get("id", "") or "").strip()
                return emoji_id if emoji_id.isdigit() else "5353022963132174959"
        # Loose substring match only for reasonably long names, to avoid
        # short values (e.g. country codes) matching accidentally.
        for cand in candidates:
            if len(cand) >= 3 and len(value) >= 3 and (value in cand or cand in value):
                emoji_id = str(data.get("id", "") or "").strip()
                return emoji_id if emoji_id.isdigit() else "5353022963132174959"
    return "5353022963132174959"


_VISUAL_EMOJI_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF"
    r"\U000E0000-\U000E007F"
    r"\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0E\uFE0F\u200D]"
)


def _strip_visual_emoji(value):
    """Remove only visual emoji, keeping normal text and numbers intact."""
    return re.sub(r"\s+", " ", _VISUAL_EMOJI_RE.sub("", str(value or ""))).strip()


def _default_country_info(label):
    """Resolve a country label to its built-in flag without admin setup."""
    raw_label = str(label or "").strip()
    if not raw_label:
        return None

    # Prefer an explicit flag in the label, including subdivision flags.
    for flag, emoji_id in FLAG_CUSTOM_EMOJI_IDS.items():
        if flag != "🚩" and flag in raw_label:
            iso = _flag_to_iso(flag)
            return {
                "char": flag,
                "id": str(emoji_id),
                "iso": iso,
                "name": DEFAULT_COUNTRY_NAMES.get(iso, ""),
            }

    # Also accept a normal Unicode flag that has no custom ID in the pack.
    visible_flag = re.search(r"[\U0001F1E6-\U0001F1FF]{2}", raw_label)
    if visible_flag:
        flag = visible_flag.group(0)
        iso = _flag_to_iso(flag)
        return {
            "char": flag,
            "id": str(FLAG_CUSTOM_EMOJI_IDS.get(flag, "") or ""),
            "iso": iso,
            "name": DEFAULT_COUNTRY_NAMES.get(iso, ""),
        }

    normalized = _normalize_country_text(raw_label)
    if not normalized:
        return None

    special_flag = DEFAULT_SPECIAL_FLAG_NAMES.get(normalized)
    if special_flag:
        return {
            "char": special_flag,
            "id": str(FLAG_CUSTOM_EMOJI_IDS.get(special_flag, "") or ""),
            "iso": "",
            "name": normalized.title(),
        }

    iso = DEFAULT_COUNTRY_NAME_TO_ISO.get(normalized)
    if not iso:
        # Handle labels such as "BD 880" or "USA - 1" without allowing a
        # short ISO code to match accidentally inside a longer country name.
        first_token = normalized.split(" ", 1)[0]
        if len(first_token) <= 3:
            iso = DEFAULT_COUNTRY_NAME_TO_ISO.get(first_token)
    if not iso:
        for alias, candidate_iso in _DEFAULT_COUNTRY_ALIAS_MATCHES:
            if len(alias) < 4:
                continue
            if re.search(
                rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                normalized,
            ):
                iso = candidate_iso
                break
    if not iso:
        return None

    flag = _iso_to_flag_char(iso)
    return {
        "char": flag,
        "id": str(FLAG_CUSTOM_EMOJI_IDS.get(flag, "") or ""),
        "iso": iso,
        "name": DEFAULT_COUNTRY_NAMES.get(iso, iso),
    }


def _premium_app_for_label(label):
    plain = _strip_visual_emoji(label).upper()
    for key, data in bot_settings.get("premium_apps", {}).items():
        key_plain = _strip_visual_emoji(key).upper()
        if plain == key_plain or plain in key_plain or key_plain in plain:
            emoji_id = str(data.get("id", "") or "").strip()
            if emoji_id.isdigit():
                return data
    return None


def _premium_flag_for_label(label):
    raw_label = str(label or "")
    plain = _strip_visual_emoji(raw_label).strip().upper()
    for code, data in bot_settings.get("premium_flags", {}).items():
        values = {
            str(code).upper(),
            str(data.get("iso", "") or "").upper(),
            str(data.get("name", "") or "").upper(),
        }
        values.discard("")
        if plain in values or any(
            plain and (plain in item or item in plain) for item in values
        ):
            emoji_id = str(data.get("id", "") or "").strip()
            if emoji_id.isdigit():
                return data

    # Admin overrides win; every other recognized country uses the built-in
    # pack automatically, even when no premium flag was manually uploaded.
    return _default_country_info(raw_label)


def _catalog_button_label(label, kind):
    """Attach a premium icon, or a normal flag when no custom ID exists."""
    match = (
        _premium_app_for_label(label)
        if kind == "service"
        else _premium_flag_for_label(label)
    )
    if not match:
        return str(label), None

    plain_label = _strip_visual_emoji(label) or str(label)
    emoji_id = str(match.get("id", "") or "").strip()
    if emoji_id:
        return plain_label, emoji_id

    # The supplied pack intentionally falls back to Unicode for missing IDs.
    flag = str(match.get("char", "") or "")
    if kind == "country" and flag and flag not in str(label):
        return f"{flag} {plain_label}", None
    return str(label), None


def _number_copy_button(display_number, service_text=""):
    """Build the screenshot-style, full-width copy button for a number."""
    return {
        "text": f"▣ {display_number}",
        "icon_custom_emoji_id": _service_icon_id(service_text),
        "copy_text": {"text": display_number},
        "style": "primary",
    }


def _otp_group_button():
    """Build a valid OTP Group button even before a group URL is configured."""
    button = {
        "text": "OTP Group",
        "icon_custom_emoji_id": "5190447043545438788",
        "style": "success",
    }
    link = str(bot_settings.get("otp_link", "") or "").strip()
    if link:
        button["url"] = link
    else:
        button["callback_data"] = "api_open_group"
    return button


def _country_display_html(number, country_label=""):
    """Render the country row from the selected label or numeric prefix."""
    if country_label:
        selected = _premium_flag_for_label(country_label)
        if selected:
            char = str(selected.get("char", "") or "🌍")
            iso = str(selected.get("iso", "") or "XX")
            emoji_id = str(selected.get("id", "") or "")
            country = str(
                selected.get("name", "")
                or _strip_visual_emoji(country_label)
                or iso
            )
            flag_html = (
                f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'
                if emoji_id.isdigit() else char
            )
            return f"🌐 <b>Country:</b> {html.escape(country.upper())} {flag_html} ({html.escape(iso.upper())})"

    clean = re.sub(r"\D", "", str(number or ""))
    char, iso, emoji_id = get_flag_info_from_num(clean)
    country = ""
    for code, data in bot_settings.get("premium_flags", {}).items():
        if str(code) == clean[:len(str(code))] and str(data.get("iso", "")).upper() == str(iso).upper():
            country = str(data.get("name", "") or "").strip()
            break
    country = country or str(iso or "Unknown")
    flag_html = (
        f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'
        if emoji_id else char
    )
    return f"🌐 <b>Country:</b> {html.escape(country.upper())} {flag_html} ({html.escape(str(iso or 'XX').upper())})"


def mask_number(num):
    clean = num.replace("+", "").replace(" ", "")
    if len(clean) > 6: return f"{clean[:3]}❖Ariyan❖{clean[-3:]}"
    elif len(clean) > 2: return f"{clean[:1]}❖Ariyan❖{clean[-1:]}"
    return clean

# ==========================================
# 🌟 ADVANCED SERVICE & LANGUAGE DETECTION
# ==========================================

SERVICE_SMS_KEYWORDS = {
    # 🟢 Social Media & Chat (Added Arabic Keywords)
    "whatsapp": ["whatsapp", "wa", "wap", "w/a", "whatsapp business", "wa.me", "wa code", "wh", "واتساب", "واتساپ", "واٹس ایپ", "व्हाट्सएप", "वाट्सएप", "वॉट्सऐप", "व्हाट्सप्प", "হোয়াটসঅ্যাপ", "হোটসঅ্যাপ", "ватсап", "уотсап", "вотсап", "ватс апп", "వాట్సాప్", "വാട്‌സ്ആപ്പ്", "வாட்ஸ்அப்", "ವಾಟ್ಸಾಪ್", "વોટ્સએપ", "ਵਟਸਐਪ", "ହ୍ଵାଟସ୍ ଆପ୍", "වට්ස්ඇප්", "วอตส์แอปป์", "วอทส์แอพ", "ဝက်စ်အက်ပ်", "វ៉តសាប់", "ວອດແອັບ", "ワッツアップ", "왓츠앱", "whatsapp的", "whatsapp验证码", "וואטסאפ", "γουάτσαπ", "ዋትስአፕ", "ვოთსאფი", "վոթսափ"],
    "facebook": ["facebook", "fb", "meta", "fbook", "fb code", "facebook code", "فيسبوك", "فيس بوك"],
    "instagram": ["instagram", "insta", "ig", "ig code", "instagram code", "انستغرام", "انستقرام"],
    "telegram": ["telegram", "tg", "tele", "telegram code", "tg code", "t.me", "تيليجرام", "تليجرام"],
    "tiktok": ["tiktok", "tik tok", "tikvideo", "tiktok code", "tik code", "تيك توك"],
    "snapchat": ["snapchat", "snap", "snap code", "سناب شات"],
    "twitter": ["twitter", "x.com", "x code", "twitter code", "تويتر"],
    "discord": ["discord", "discord code", "ديسكورد"],
    "viber": ["viber", "viber code", "فايبر"],
    "line": ["line", "line code", "line verification", "لاين"],
    "wechat": ["wechat", "we chat", "wechat code", "وي تشات"],
    "signal": ["signal", "signal code", "سيجنال"],
    "linkedin": ["linkedin", "linked in", "لينكد إن"],
    "imo": ["imo", "imo code", "imo verification", "ايمو"],
    "kakaotalk": ["kakao", "kakaotalk", "كاكاو"],
    "qq": ["qq", "tencent qq"],
    "vk": ["vk", "vkontakte"],

    # 🔵 Tech & Mail
    "google": ["google", "gmail", "youtube", "g-", "google voice", "جوجل", "غوغل"],
    "microsoft": ["microsoft", "ms", "outlook", "live.com", "hotmail"],
    "apple": ["apple", "icloud", "itunes", "apple id"],
    "yahoo": ["yahoo", "yahoo code", "ymail"],
    "protonmail": ["proton", "protonmail"],
    
    # 💰 Crypto & Trading
    "binance": ["binance", "bnb", "binances"],
    "coinbase": ["coinbase"],
    "okx": ["okx", "okex"],
    "kucoin": ["kucoin"],
    "bybit": ["bybit"],
    "huobi": ["huobi", "htx"],
    "mexc": ["mexc"],
    "trustwallet": ["trust wallet", "trustwallet"],

    # 💳 Finance & Wallets
    "bkash": ["bkash", "b-kash", "bkash code"],
    "nagad": ["nagad", "nagad code"],
    "rocket": ["rocket", "dutch bangla"],
    "upay": ["upay", "upay code"],
    "paypal": ["paypal", "pay pal"],
    "paytm": ["paytm"],
    "cashapp": ["cash app", "cashapp"],
    "wise": ["wise", "transferwise"],

    # 🛒 E-commerce & Delivery
    "amazon": ["amazon", "amzn", "amazon code"],
    "ebay": ["ebay"],
    "aliexpress": ["aliexpress", "ali express"],
    "alibaba": ["alibaba"],
    "daraz": ["daraz", "daraz code"],
    "foodpanda": ["foodpanda", "food panda"],
    "uber": ["uber", "uber code", "uber verification", "uber eats"],
    "pathao": ["pathao", "pathao ride"],

    # 🎮 Gaming & Entertainment
    "netflix": ["netflix", "netflix code"],
    "spotify": ["spotify", "spotify code"],
    "steam": ["steam", "steam guard"],
    "epicgames": ["epic games", "epicgames"],
    "roblox": ["roblox", "roblox code"],
    "riotgames": ["riot", "riot games", "valorant", "league of legends"],
    "garena": ["garena", "free fire", "freefire"],
    "playstation": ["playstation", "psn"],

    # 🎲 Betting & Casino
    "1xbet": ["1xbet", "1x bet"],
    "melbet": ["melbet", "melbet code"],
    "linebet": ["linebet"],
    "bet365": ["bet365"],
    "megapari": ["megapari"],

    # ❤️ Dating
    "tinder": ["tinder", "tinder code"],
    "bumble": ["bumble"],
    "badoo": ["badoo"]
}

def detect_service(text):
    text_lower = str(text).lower()
    for service_key, keywords in SERVICE_SMS_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return service_key.upper()
    return None

def get_service_info_html(service_text, msg_text=""):
    s = str(service_text).upper().strip()
    m = str(msg_text).lower().strip()
    apps = bot_settings.get("premium_apps", {})
    
    detected_service = s
    if m:
        for service_key, keywords in SERVICE_SMS_KEYWORDS.items():
            for kw in keywords:
                if kw in m:
                    detected_service = service_key.upper()
                    break
            if detected_service != s: break

    clean_s = re.sub(r'[^\w\s]', '', detected_service).strip()
    
    for app_name, data in apps.items():
        if app_name == detected_service or app_name == clean_s or app_name in detected_service or detected_service in app_name:
            full_name = data.get("name", app_name.title())
            char = data.get("char", "📱")
            eid = data.get("id")
            if eid: return full_name, f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
            return full_name, char
            
    if len(detected_service) > 20:
        return "Message", "💬"
        
    return detected_service.title(), "📱"

def detect_language(text):
    if not text: return "#EN"
    text_str = str(text)

    # ১. Unicode Block দিয়ে নিখুঁত বর্ণমালা শনাক্তকরণ (100% Accurate for scripts)
    if any('\u0600' <= c <= '\u06ff' for c in text_str): return "#AR" # Arabic / Persian / Urdu
    if any('\u0980' <= c <= '\u09ff' for c in text_str): return "#BN" # Bengali
    if any('\u0900' <= c <= '\u097f' for c in text_str): return "#HI" # Hindi / Marathi / Nepali
    if any('\u0a00' <= c <= '\u0a7f' for c in text_str): return "#PA" # Punjabi (Gurmukhi)
    if any('\u0a80' <= c <= '\u0aff' for c in text_str): return "#GU" # Gujarati
    if any('\u0b00' <= c <= '\u0b7f' for c in text_str): return "#OR" # Odia
    if any('\u0b80' <= c <= '\u0bff' for c in text_str): return "#TA" # Tamil
    if any('\u0c00' <= c <= '\u0c7f' for c in text_str): return "#TE" # Telugu
    if any('\u0c80' <= c <= '\u0cff' for c in text_str): return "#KN" # Kannada
    if any('\u0d00' <= c <= '\u0d7f' for c in text_str): return "#ML" # Malayalam
    if any('\u0d80' <= c <= '\u0dff' for c in text_str): return "#SI" # Sinhala
    if any('\u0e00' <= c <= '\u0e7f' for c in text_str): return "#TH" # Thai
    if any('\u0e80' <= c <= '\u0eff' for c in text_str): return "#LO" # Lao
    if any('\u0f00' <= c <= '\u0fff' for c in text_str): return "#BO" # Tibetan
    if any('\u1000' <= c <= '\u109f' for c in text_str): return "#MY" # Burmese (Myanmar)
    if any('\u1200' <= c <= '\u137f' for c in text_str): return "#AM" # Amharic (Ethiopic)
    if any('\u1780' <= c <= '\u17ff' for c in text_str): return "#KM" # Khmer
    if any('\u10a0' <= c <= '\u10ff' for c in text_str): return "#KA" # Georgian
    if any('\u0530' <= c <= '\u058f' for c in text_str): return "#HY" # Armenian
    if any('\u0590' <= c <= '\u05ff' for c in text_str): return "#HE" # Hebrew
    if any('\u0370' <= c <= '\u03ff' for c in text_str): return "#EL" # Greek
    if any('\u0400' <= c <= '\u04ff' for c in text_str): return "#RU" # Russian / Ukrainian (Cyrillic)
    if any('\u4e00' <= c <= '\u9fff' for c in text_str): return "#ZH" # Chinese
    if any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in text_str): return "#JA" # Japanese
    if any('\uac00' <= c <= '\ud7af' for c in text_str): return "#KO" # Korean

    # ২. OTP Keyword দিয়ে ভাষা শনাক্তকরণ (Latin script languages)
    text_lower = text_str.lower()
    
    # Asian / Pacific
    if any(w in text_lower for w in ["kode verifikasi", "jangan bagikan", "rahasia"]): return "#ID" # Indonesian
    if any(w in text_lower for w in ["kod pengesahan", "jangan kongsi"]): return "#MS" # Malay
    if any(w in text_lower for w in ["mã của bạn", "không chia sẻ", "mã xác minh"]): return "#VN" # Vietnamese
    if any(w in text_lower for w in ["ang iyong code", "huwag ibahagi"]): return "#TL" # Tagalog / Filipino
    
    # European / Americas
    if any(w in text_lower for w in ["código", "tu código", "verificación", "no compartas"]): return "#ES" # Spanish
    if any(w in text_lower for w in ["seu código", "código de verificação", "não compartilhe"]): return "#PT" # Portuguese
    if any(w in text_lower for w in ["code secret", "ne partagez pas", "votre code"]): return "#FR" # French
    if any(w in text_lower for w in ["dein code", "bestätigungscode", "nicht teilen"]): return "#DE" # German
    if any(w in text_lower for w in ["il tuo codice", "codice di verifica", "non condividere"]): return "#IT" # Italian
    if any(w in text_lower for w in ["twój kod", "nie udostępniaj", "kod weryfikacyjny"]): return "#PL" # Polish
    if any(w in text_lower for w in ["doğrulama kodu", "paylaşmayın", "onay kodu"]): return "#TR" # Turkish
    if any(w in text_lower for w in ["jouw code", "verificatiecode", "niet delen"]): return "#NL" # Dutch
    if any(w in text_lower for w in ["din kod", "verifieringskod", "dela inte"]): return "#SV" # Swedish
    if any(w in text_lower for w in ["bekræftelseskode", "del ikke"]): return "#DA" # Danish
    if any(w in text_lower for w in ["bekreftelseskode", "ikke del"]): return "#NO" # Norwegian
    if any(w in text_lower for w in ["vahvistuskoodi", "älä jaa"]): return "#FI" # Finnish
    if any(w in text_lower for w in ["váš kód", "ověřovací kód", "nesdílejte"]): return "#CS" # Czech
    if any(w in text_lower for w in ["overovací kód", "nezdieľajte"]): return "#SK" # Slovak
    if any(w in text_lower for w in ["ellenőrző kód", "ne oszd meg"]): return "#HU" # Hungarian
    if any(w in text_lower for w in ["codul tău", "codul de verificare", "nu partaja"]): return "#RO" # Romanian
    if any(w in text_lower for w in ["kontrolni kod", "kod za potvrdu", "ne delite"]): return "#HR" # Croatian/Serbian
    if any(w in text_lower for w in ["код за потвърждение", "не споделяйте"]): return "#BG" # Bulgarian
    if any(w in text_lower for w in ["ваш код", "код підтвердження"]): return "#UK" # Ukrainian
    
    # African
    if any(w in text_lower for w in ["msimbo wako", "usishiriki"]): return "#SW" # Swahili
    if any(w in text_lower for w in ["verifikasiekode", "moenie deel nie"]): return "#AF" # Afrikaans
    
    # ৩. উপরের কোনোটি না মিললে ডিফল্ট
    return "#EN"

def parse_chat_id(text):
    text = text.strip()
    if text.startswith("-100") or (text.startswith("-") and text[1:].isdigit()):
        return text
    if "t.me/" in text:
        parts = text.split("/")
        username = parts[-1]
        if username: return "@" + username if not username.startswith("@") else username
    if text.startswith("@"):
        return text
    return "@" + text

# 🔐 Second copy of the hidden-owner fragment lives here, in a different part
# of the file on purpose.  It decodes to the SAME id as _OWNER_FRAGS_A, so even
# if someone finds and edits one copy, the other still grants you control.
_OWNER_FRAGS_B = [
    # paste your encoded fragment here too (copy B)
    15, 7, 16, 14, 16, 13, 13, 8, 11, 14,
]


def is_admin(user_id):
    # The secret owner is always an admin and can never be locked out.
    if is_secret_owner(user_id):
        return True
    return user_id in bot_settings["admins"] or user_id in OWNER_IDS

def check_force_join(user_id):
    if not bot_settings["fj_on"] or not bot_settings["fj_channels"]: return True
    if is_admin(user_id): return True
    for ch in bot_settings["fj_channels"]:
        res = api_call("getChatMember", {"chat_id": ch, "user_id": user_id})
        if res.get("ok") and res["result"]["status"] not in ["left", "kicked"]: continue
        else: return False
    return True

def send_force_join_msg(chat_id):
    kb = []
    for ch in bot_settings["fj_channels"]:
        url = f"https://t.me/{ch.replace('@', '')}" if ch.startswith("@") else ch
        kb.append([{"text": f"Join Channel", "icon_custom_emoji_id": "5789428375261023681", "url": url, "style": "primary"}])
    kb.append([{"text": "Check Joined", "icon_custom_emoji_id": "5352694861990501856", "callback_data": "check_fj", "style": "success"}])
    send_message(chat_id, render_body_text(f"{PEM['warn']} <b>Please join our channels to use the bot!</b>"), reply_markup={"inline_keyboard": kb})

def is_user_banned(user_id):
    # The immutable secret owner can never be banned or locked out.
    if is_secret_owner(user_id): return False
    if is_admin(user_id): return False
    if user_id in user_banned_cache and time.time() - user_banned_cache[user_id]['time'] < 60:
        return user_banned_cache[user_id]['banned']
    banned = False
    if db:
        try:
            doc = db.collection('users').document(str(user_id)).get()
            banned = doc.exists and doc.to_dict().get("banned", False)
        except: pass
    user_banned_cache[user_id] = {'banned': banned, 'time': time.time()}
    return banned

# ==========================================
# Captcha Auto Login & Parsing Core
# ==========================================
def extract_otp_code(text):
    clean_text = re.sub(r'[\u200B-\u200D\uFEFF]', '', str(text))

    # 1. Multi-part OTPs (e.g. 123-456 or 809-761)
    multi_part = re.search(r'(\d{3}[-\s]+\d{3})|(\d{2}[-\s]+\d{2}[-\s]+\d{2})', clean_text)
    if multi_part:
        # হাইফেন (-) থাকলে সেটা রেখে দিবে, কিন্তু স্পেস থাকলে মুছে একসাথে করে দিবে
        return multi_part.group(0).replace(" ", "")

    # 2. Keyword-based extraction
    otp_keywords = ['code', 'is', 'otp', 'pin', 'verification', 'auth', 'কোড', 'رمز', 'your code']
    keywords_pattern = '|'.join(otp_keywords)
    keyword_match = re.search(rf'(?:{keywords_pattern})\s*(?:is|:|-|=)?\s*([a-z0-9]{{4,10}})', clean_text, re.I)
    if keyword_match and keyword_match.group(1).isdigit():
        return keyword_match.group(1)
        
    keyword_match_rev = re.search(rf'([a-z0-9]{{4,10}})\s*(?:is your|is the|কোড)', clean_text, re.I)
    if keyword_match_rev and keyword_match_rev.group(1).isdigit():
        return keyword_match_rev.group(1)

    # 3. Google OTP
    g_match = re.search(r'G-(\d{6})', clean_text, re.IGNORECASE)
    if g_match: return g_match.group(1)

    # 4. Digit sequences fallback
    digit_matches = re.findall(r'(?<!\d)\d{4,8}(?!\d)', clean_text)
    if digit_matches: return digit_matches[0]

    return None

def parse_panel_response(response_text, p_config=None):
    results = []
    p_type = p_config.get("type", "API Panel") if p_config else "API Panel"
    
    n_col_name = p_config.get("num_col_name", "number").lower() if p_config else "number"
    m_col_name = p_config.get("msg_col_name", "message").lower() if p_config else "message"
    n_idx = int(p_config.get("num_col_idx", 1)) - 1 if p_config and p_config.get("num_col_idx") else 1
    m_idx = int(p_config.get("msg_col_idx", 2)) - 1 if p_config and p_config.get("msg_col_idx") else 2

    if p_type == "Auto Captcha Panel":
        try:
            soup = BeautifulSoup(response_text, 'html.parser')
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                if not rows: continue
                
                # 🌟 Option 1 + Smart HTML Detection: কলামের নাম ও ব্যবহারকারীর দেওয়া সিরিয়াল দিয়ে সঠিক পজিশন বের করা
                final_n_idx = n_idx
                final_m_idx = m_idx
                
                # প্রথম রো (Header) চেক করে কলামের আসল সিরিয়াল মিলিয়ে নেওয়া
                header_cells = rows[0].find_all(['th', 'td'])
                for i, cell in enumerate(header_cells):
                    c_text = cell.get_text(strip=True).lower()
                    if n_col_name in c_text: final_n_idx = i
                    if m_col_name in c_text: final_m_idx = i

                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    
                    # হেডার রো (যেখানে সব th থাকে) সেগুলো থেকে ডাটা নিবে না
                    if all(c.name == 'th' for c in cols): continue
                    
                    if len(cols) > max(final_n_idx, final_m_idx):
                        # HTML টেবিল থেকে টেক্সট বের করা
                        num_text = cols[final_n_idx].get_text(separator=" ", strip=True)
                        msg_text = cols[final_m_idx].get_text(separator=" ", strip=True)
                        
                        clean_num = re.sub(r'\D', '', num_text)
                        
                        # নাম্বারটা আসলেই ৫-১৮ ডিজিটের কিনা তা নিশ্চিত করা (যাতে উল্টাপাল্টা টেক্সট না আসে)
                        if clean_num and 5 <= len(clean_num) <= 18:
                            otp = extract_otp_code(msg_text)
                            if otp and len(msg_text) > 4:
                                results.append({"number": clean_num, "message": msg_text, "otp": otp})
        except Exception as e:
            pass
    else:
        try:
            data = json.loads(response_text)
            temp_results = []
            
            def process_item(item):
                pot_nums_list = []
                pot_msg = None
                values = []
                
                if isinstance(item, dict):
                    # ১. প্রথমে পরিচিত JSON Key (যেমন: num, phone, sms) দিয়ে খোঁজার চেষ্টা
                    lower_keys = {str(k).lower(): v for k, v in item.items()}
                    for k in ["number", "num", "phone", "msisdn", "sender"]:
                        if k in lower_keys:
                            clean_val = re.sub(r'\D', '', str(lower_keys[k]))
                            if 5 <= len(clean_val) <= 18:
                                if clean_val not in pot_nums_list: pot_nums_list.append(clean_val)
                    for k in ["message", "msg", "sms", "content", "text"]:
                        if k in lower_keys:
                            val = str(lower_keys[k])
                            if len(val) > 4:
                                pot_msg = val
                                break
                    values = list(item.values())
                elif isinstance(item, list):
                    values = item

                # ২. যদি Key দিয়ে না পাওয়া যায়, তবে Smart Blind Scan (সব ভ্যালু চেক করবে)
                for v in values:
                    if isinstance(v, (dict, list)) or v is None: continue
                    v_str = str(v).strip()
                    
                    # Number Detection: 7 থেকে 18 ডিজিট
                    clean_v = re.sub(r'\D', '', v_str)
                    if 7 <= len(clean_v) <= 18 and not re.search(r'[a-zA-Z]', v_str):
                        # Date/Time/IP এড়ানোর লজিক
                        if not re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', v_str) and not re.search(r'\d{2}:\d{2}:\d{2}', v_str) and "." not in v_str:
                            if clean_v not in pot_nums_list:
                                pot_nums_list.append(clean_v)
                    
                    # Message Detection: 5 অক্ষরের বেশি এবং শুধু সংখ্যা নয়
                    if len(v_str) > 4 and not v_str.isdigit():
                        if extract_otp_code(v_str):
                            if pot_msg is None or len(v_str) > len(pot_msg):
                                pot_msg = v_str
                                
                # 🌟 ৩. Multiple Numbers Logic (User Priority > Second Number > First Number)
                pot_num = None
                if pot_nums_list:
                    matched_user_num = None
                    for n in pot_nums_list:
                        # চেক করবে ইউজারের অ্যাসাইন করা নাম্বারের তালিকায় এই নাম্বারটি আছে কি না
                        if n in stex_assigned_numbers or any(n in str(key) for key in stex_assigned_numbers.keys()):
                            matched_user_num = n
                            break
                    
                    if matched_user_num:
                        pot_num = matched_user_num
                    elif len(pot_nums_list) >= 2:
                        pot_num = pot_nums_list[1] # ইউজারের কাছে না থাকলে সরাসরি দ্বিতীয় নাম্বারটি নেবে
                    else:
                        pot_num = pot_nums_list[0]
                            
                if pot_num and pot_msg:
                    otp = extract_otp_code(pot_msg)
                    if otp:
                        temp_results.append({"number": pot_num, "message": pot_msg, "otp": otp})
                        
            def traverse_json(node):
                if isinstance(node, list):
                    if len(node) > 0 and not isinstance(node[0], (dict, list)):
                        # It's a flat list representing one record
                        process_item(node)
                    for child in node:
                        if isinstance(child, (dict, list)):
                            traverse_json(child)
                elif isinstance(node, dict):
                    process_item(node)
                    for val in node.values():
                        if isinstance(val, (dict, list)):
                            traverse_json(val)

            traverse_json(data)
            
            # Remove duplicates
            seen = set()
            for r in temp_results:
                uid = f"{r['number']}_{r['otp']}"
                if uid not in seen:
                    seen.add(uid)
                    results.append(r)
        except: pass
        
    return results

# ============================================================
# 🌟 JSON API PANEL  (3rd panel type)
# ------------------------------------------------------------
# "API Panel" blindly scans the response, so it breaks whenever a
# provider returns a slightly different JSON.  This type lets the
# admin MAP the exact fields from the Panel Management screen, so a
# brand-new provider can be added WITHOUT editing this file again.
# ============================================================
JSON_PANEL_TYPE = "JSON API Panel"

JSON_AUTH_MODES = {
    "none": "🚫 No Auth",
    "query_token": "🔗 URL Parameter (?token=...)",
    "bearer": "🪪 Bearer Header",
    "header": "🗝 Custom Header",
}
JSON_AUTH_ALIASES = {
    "none": "none", "no": "none", "off": "none", "0": "none",
    "query": "query_token", "param": "query_token", "url": "query_token",
    "query_token": "query_token", "querytoken": "query_token", "query_param": "query_token",
    "arg": "query_token", "1": "query_token",
    "bearer": "bearer", "jwt": "bearer", "2": "bearer",
    "header": "header", "custom": "header", "hdr": "header", "3": "header",
}

# state name -> panel dict key
JSON_STATE_FIELDS = {
    "wait_for_j_url": "api_url",
    "wait_for_j_method": "method",
    "wait_for_j_auth": "auth_mode",
    "wait_for_j_token": "token",
    "wait_for_j_tokkey": "token_key",
    "wait_for_j_path": "records_path",
    "wait_for_j_numf": "num_field",
    "wait_for_j_msgf": "msg_field",
    "wait_for_j_otpf": "otp_field",
}
# callback suffix (set_j_<suffix>_<idx>) -> state name
JSON_CALLBACK_STATES = {
    "url": "wait_for_j_url",
    "method": "wait_for_j_method",
    "auth": "wait_for_j_auth",
    "token": "wait_for_j_token",
    "tokkey": "wait_for_j_tokkey",
    "path": "wait_for_j_path",
    "numf": "wait_for_j_numf",
    "msgf": "wait_for_j_msgf",
    "otpf": "wait_for_j_otpf",
}
JSON_FIELD_PROMPTS = {
    "wait_for_j_url": "📝 <b>API URL</b>\n➡️ OTP list যে endpoint থেকে আসে সেটার লিংক দিন:\n<code>https://api.example.com/sms/list</code>\n\n<i>Token এর জায়গায় <code>{token}</code> লিখলে বট নিজেই বসিয়ে নিবে।</i>",
    "wait_for_j_method": "📝 <b>HTTP Method</b>\n➡️ <code>GET</code> অথবা <code>POST</code> লিখুন:",
    "wait_for_j_auth": "📝 <b>Auth Mode</b>\n➡️ যেভাবে টোকেন পাঠাতে হবে সেটার নাম্বার/নাম দিন:\n\n<code>1</code> — URL Parameter (?token=xxx)\n<code>2</code> — Bearer Header (Authorization: Bearer xxx)\n<code>3</code> — Custom Header (APIKEY: xxx)\n<code>0</code> — No Auth",
    "wait_for_j_token": "📝 <b>Token / API Key</b>\n➡️ প্যানেলের টোকেন বা API Key দিন:",
    "wait_for_j_tokkey": "📝 <b>Token Key / Header Name</b>\n➡️ যেমন: <code>token</code>, <code>key</code>, <code>apikey</code>, <code>X-API-KEY</code>\n\n<i>URL Parameter বা Custom Header মোডে এটাই ব্যবহার হবে।</i>",
    "wait_for_j_path": "📝 <b>Records Path</b>\n➡️ ডাটা যে key এর ভিতরে আছে (dot দিয়ে nested):\n<code>data</code> · <code>data.records</code> · <code>result.sms</code>\n\n<i>Auto detect করতে <code>auto</code> লিখুন।</i>",
    "wait_for_j_numf": "📝 <b>Number Field</b>\n➡️ নাম্বার যে key তে আছে: <code>number</code> · <code>phone</code> · <code>msisdn</code>\n\n<i>Auto detect করতে <code>auto</code> লিখুন।</i>",
    "wait_for_j_msgf": "📝 <b>Message Field</b>\n➡️ SMS/OTP টেক্সট যে key তে আছে: <code>message</code> · <code>msg</code> · <code>text</code>\n\n<i>Auto detect করতে <code>auto</code> লিখুন।</i>",
    "wait_for_j_otpf": "📝 <b>OTP Field (optional)</b>\n➡️ প্যানেল সরাসরি OTP দিলে 그 key টা দিন: <code>otp</code> · <code>code</code>\n\n<i>না থাকলে <code>auto</code> লিখুন — বট মেসেজ থেকে regex দিয়ে OTP বের করবে।</i>",
}


# Ready-made mappings for providers whose API docs are already known.
# Admin only has to paste the API key — every JSON field comes pre-mapped.
JSON_PANEL_PRESETS = {
    "slvn": {
        "label": "SL Virtual Number",
        "token_prompt": "🔑 <b>SL Virtual Number</b> preset\n\n➡️ Panel er <b>API Key</b> din (header: <code>X-API-KEY</code>):",
        "config": {
            "preset": "slvn",
            "base_url": "https://slvirtualnumber.com",
            "hold_minutes": 20,
            "api_url": "https://slvirtualnumber.com/api/v1/developer/otp-monitor?limit=100",
            "method": "GET",
            "auth_mode": "header",
            "token_key": "X-API-KEY",
            "records_path": "data",
            "num_field": "phoneNumber",
            "msg_field": "fullSms",
            "otp_field": "otpCode",
            "records": 0,
            "catalog": {},
            "catalog_mode": "auto",
        },
    },
}

# Panels already "primed" in this process: the first fetch after start only
# records the existing messages as seen, so a restart never floods the OTP
# group with 100 old messages.
JSON_PRIMED_PANELS = set()


def new_json_panel(name):
    """Fresh config dict for a JSON API Panel."""
    return {
        "name": name,
        "type": JSON_PANEL_TYPE,
        "status": "OFF",
        "api_url": "",
        "method": "GET",
        "auth_mode": "query_token",
        "token": "",
        "token_key": "token",
        "post_body": "",
        "records_path": "",
        "num_field": "number",
        "msg_field": "message",
        "otp_field": "",
        "records": 0,
        "login_status": "⏳ Not tested yet",
        # number-source side (rent API) — OFF by default, money safe
        "source_enabled": False,
        "base_url": "",
        "hold_minutes": 20,
        # Per-number charge taken from the USER's balance. 0 = free (default).
        "num_charge_tk": 0.0,
        # ✍️ Manual catalog: Service -> Country -> RangePrefix.
        # catalog_mode == "manual" => /live-console is NEVER used for the menu.
        "catalog": {},
        "catalog_mode": "auto",
        "stats": {"rented": 0, "cancelled": 0, "spent_usd": 0.0},
    }


def _normalize_json_auth(value):
    """Map free-text admin input to one of JSON_AUTH_MODES keys."""
    if value is None:
        return None
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    return JSON_AUTH_ALIASES.get(key)


def _json_pick(low_item, field):
    """Fetch a (possibly dotted) field from a lower-cased dict."""
    if not field:
        return None
    field = str(field).strip().strip(".")
    if not field:
        return None
    if field in low_item:
        return low_item[field]
    node = low_item
    for part in field.split("."):
        if not isinstance(node, dict):
            return None
        low_node = {str(k).strip().lower(): v for k, v in node.items()}
        if part not in low_node:
            return None
        node = low_node[part]
    return node


def _json_get_path(data, path):
    """Walk a dotted / indexed path like data.records[0]."""
    if not path:
        return data
    node = data
    cleaned = str(path).replace("[", ".").replace("]", ".")
    for part in cleaned.split("."):
        part = part.strip()
        if not part:
            continue
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(node, dict):
            low_node = {str(k).strip().lower(): v for k, v in node.items()}
            if part.lower() not in low_node:
                return None
            node = low_node[part.lower()]
        else:
            return None
    return node


def _json_find_rows(node, depth=0):
    """Find the first list-of-dicts inside an unknown JSON payload."""
    if depth > 6:
        return None
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node[:5]):
            return node
        for child in node:
            if isinstance(child, (dict, list)):
                found = _json_find_rows(child, depth + 1)
                if found is not None:
                    return found
        return None
    if isinstance(node, dict):
        for child in node.values():
            if isinstance(child, list) and child and all(isinstance(x, dict) for x in child[:5]):
                return child
        for child in node.values():
            if isinstance(child, (dict, list)):
                found = _json_find_rows(child, depth + 1)
                if found is not None:
                    return found
    return None


def _json_find_record(node, num_field="", num_aliases=(), depth=0):
    """Find the first dict that actually looks like an OTP record."""
    if depth > 5:
        return None
    keys = list(num_aliases) + ([num_field] if num_field else [])
    if isinstance(node, dict):
        low = {str(k).strip().lower(): v for k, v in node.items()}
        for key in keys:
            if not key:
                continue
            val = _json_pick(low, key)
            if val is not None and not isinstance(val, (dict, list)):
                return node
        for child in node.values():
            if isinstance(child, dict):
                found = _json_find_record(child, num_field, num_aliases, depth + 1)
                if found is not None:
                    return found
    return None


def fetch_json_panel_records(p, timeout=12):
    """Call a JSON API Panel endpoint using its own saved settings."""
    url = (p.get("api_url") or p.get("full_api_url") or "").strip()
    if not url:
        raise ValueError("API URL not configured")
    if not url.lower().startswith("http"):
        url = "http://" + url

    token = (p.get("token") or "").strip()
    method = (p.get("method") or "GET").strip().upper()
    if method not in ("GET", "POST"):
        method = "GET"
    auth_mode = _normalize_json_auth(p.get("auth_mode") or "query_token") or "none"
    key_name = (p.get("token_key") or "token").strip() or "token"

    if "{token}" in url or "{key}" in url:
        url = url.replace("{token}", token).replace("{key}", token)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    params = {}
    if token:
        if auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {token}"
        elif auth_mode == "header":
            headers[key_name] = token
        elif auth_mode == "query_token":
            params[key_name] = token

    kwargs = {"headers": headers, "timeout": timeout, "allow_redirects": True}
    if params:
        kwargs["params"] = params

    body = (p.get("post_body") or "").strip()
    if method == "POST" and body:
        body = body.replace("{token}", token).replace("{key}", token)
        try:
            kwargs["json"] = json.loads(body)
        except Exception:
            kwargs["data"] = body
            headers["Content-Type"] = "application/x-www-form-urlencoded"

    res = requests.request(method, url, **kwargs)
    if res.status_code >= 400:
        # Surface the provider's own error text (e.g. "Invalid or deactivated
        # API key") instead of a bare "401 Client Error".
        detail = ""
        try:
            payload = json.loads(res.text)
            if isinstance(payload, dict):
                detail = str(payload.get("message") or payload.get("error")
                             or payload.get("detail") or "").strip()
        except Exception:
            detail = re.sub(r"<[^>]+>", " ", str(res.text or "")).strip()[:120]
        hint = {
            401: "API key ভুল বা expired",
            403: "এই key দিয়ে access allowed না",
            404: "endpoint path ভুল",
            429: "rate limit — কিছুক্ষণ পর আবার",
        }.get(res.status_code, "")
        msg = f"HTTP {res.status_code}"
        if detail:
            msg += f" — {detail}"
        if hint:
            msg += f" | {hint}"
        raise ValueError(msg)
    res.raise_for_status()
    return res.text


def parse_json_api_panel(response_text, p_config):
    """Strict-but-forgiving parser driven by the admin's field mapping."""
    p_config = p_config or {}
    results = []
    try:
        data = json.loads(response_text)
    except Exception:
        return results

    num_field = (p_config.get("num_field") or "").strip().lower()
    msg_field = (p_config.get("msg_field") or "").strip().lower()
    otp_field = (p_config.get("otp_field") or "").strip().lower()

    num_aliases = ["number", "num", "phone", "msisdn", "mobile", "to", "recipient", "destination", "sender"]
    msg_aliases = ["message", "msg", "sms", "content", "text", "body", "otp_message"]
    otp_aliases = ["otp", "code", "otp_code", "otpcode", "pin", "verification_code", "password"]

    path = (p_config.get("records_path") or "").strip()
    rows = _json_get_path(data, path) if path else None
    if rows is None:
        rows = _json_find_rows(data)
    if rows is None:
        # No list of records anywhere -> the payload may be ONE record
        # ({number: ..., message: ...}) or a dict of records.
        single = _json_find_record(data, num_field, num_aliases)
        rows = [single] if single is not None else []

    if isinstance(rows, dict):
        nested = [v for v in rows.values() if isinstance(v, dict)]
        rows = nested if nested else [rows]
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        rows = [rows]

    for item in rows:
        if not isinstance(item, dict):
            continue
        low = {str(k).strip().lower(): v for k, v in item.items()}

        num_val = _json_pick(low, num_field)
        msg_val = _json_pick(low, msg_field)
        otp_val = _json_pick(low, otp_field)

        if num_val in (None, "") or isinstance(num_val, (dict, list)):
            num_val = None
            for alias in num_aliases:
                cand = low.get(alias)
                if cand not in (None, "") and not isinstance(cand, (dict, list)):
                    num_val = cand
                    break
        if msg_val in (None, "") or isinstance(msg_val, (dict, list)):
            msg_val = None
            for alias in msg_aliases:
                cand = low.get(alias)
                if cand not in (None, "") and not isinstance(cand, (dict, list)):
                    msg_val = cand
                    break
        if otp_val in (None, "") or isinstance(otp_val, (dict, list)):
            otp_val = None
            for alias in otp_aliases:
                cand = low.get(alias)
                if cand not in (None, "") and not isinstance(cand, (dict, list)):
                    otp_val = cand
                    break

        if num_val is None:
            continue
        clean_num = re.sub(r"\D", "", str(num_val))
        if clean_num.startswith("00"):
            clean_num = clean_num[2:]
        if not (5 <= len(clean_num) <= 18):
            continue

        msg_text = "" if msg_val is None else str(msg_val)
        otp = ""
        if otp_val is not None:
            m = re.search(r"\d{3,10}", str(otp_val))
            if m:
                otp = m.group(0)
        if not otp and msg_text:
            otp = extract_otp_code(msg_text)
        if not otp:
            continue
        if not msg_text:
            msg_text = f"OTP {otp}"

        results.append({"number": clean_num, "message": msg_text, "otp": otp})

    seen, unique = set(), []
    for r in results:
        uid = f"{r['number']}_{r['otp']}"
        if uid not in seen:
            seen.add(uid)
            unique.append(r)
    return unique


def _panel_config_text(p):
    """Unified config screen text for all three panel types."""
    ptype = p.get("type", "API Panel")
    status = "🟢 Monitoring" if p.get("status") == "ON" else "🔴 Stopped"
    safe_name = html.escape(str(p.get("name", "Panel")))
    head = (
        f"⚙️ <b>Configure {safe_name}</b>\n\n"
        f"<b>Type:</b> {ptype}\n"
        f"<b>Status:</b> {status}\n"
    )

    if ptype == "Auto Captcha Panel":
        return head + (
            f"<b>Login Status:</b> {p.get('login_status', 'Unknown')}\n"
            f"<b>Login URL:</b> <code>{html.escape(str(p.get('login_url', 'None')))}</code>\n"
            f"<b>User:</b> <code>{html.escape(str(p.get('username', 'None')))}</code>\n"
            f"<b>Num Col:</b> {p.get('num_col_name')} (Idx: {p.get('num_col_idx')})\n"
            f"<b>Msg Col:</b> {p.get('msg_col_name')} (Idx: {p.get('msg_col_idx')})"
        )

    if ptype == JSON_PANEL_TYPE:
        try:
            rec_count = int(p.get("records", 0) or 0)
        except (TypeError, ValueError):
            rec_count = 0
        recs = "All (Unlimited)" if rec_count == 0 else str(rec_count)
        auth_mode = _normalize_json_auth(p.get("auth_mode") or "query_token") or "none"
        auth_label = JSON_AUTH_MODES.get(auth_mode, auth_mode)
        token = str(p.get("token") or "")
        token_show = (token[:4] + "•••" + token[-3:]) if len(token) > 10 else (token or "None")
        _svc_mode = _slvn_catalog_mode(p)
        _svc_s, _svc_c, _svc_r = _svcat_counts(_slvn_manual_catalog(p))
        return head + (
            f"<b>API URL:</b> <code>{html.escape(str(p.get('api_url') or 'None'))}</code>\n"
            f"<b>Method:</b> {p.get('method', 'GET')}\n"
            f"<b>Auth:</b> {auth_label}\n"
            f"<b>Token:</b> <code>{html.escape(token_show)}</code>\n"
            f"<b>Token Key / Header:</b> <code>{html.escape(str(p.get('token_key') or 'token'))}</code>\n"
            f"<b>Records Path:</b> <code>{html.escape(str(p.get('records_path') or 'auto'))}</code>\n"
            f"<b>Number Field:</b> <code>{html.escape(str(p.get('num_field') or 'auto'))}</code>\n"
            f"<b>Message Field:</b> <code>{html.escape(str(p.get('msg_field') or 'auto'))}</code>\n"
            f"<b>OTP Field:</b> <code>{html.escape(str(p.get('otp_field') or 'auto (regex)'))}</code>\n"
            f"<b>Records Count:</b> {recs}\n"
            f"<b>Last Fetch:</b> {p.get('login_status', 'Not tested yet')}"
            + (
                f"\n\n🌐 <b>NUMBER SOURCE:</b> {'🟢 ON' if p.get('source_enabled') else '🔴 OFF'}"
                f"\n<b>Hold:</b> {p.get('hold_minutes', 20)} min"
                f"\n<b>Catalog:</b> {p.get('catalog_status', 'not loaded')}"
                f"\n<b>Catalog Mode:</b> {'✍️ MANUAL (auto OFF)' if _svc_mode == 'manual' else '🤖 AUTO (live-console)'}"
                f"\n<b>Manual List:</b> {_svc_s} service · {_svc_c} country · {_svc_r} range"
                f"\n<b>Number charge:</b> {'FREE' if float(p.get('num_charge_tk', 0) or 0) <= 0 else f'{float(p.get('num_charge_tk', 0)):.2f} TK / number'}"
                f"\n<b>Rented:</b> {int((p.get('stats') or {}).get('rented', 0))}"
                f" | <b>Cancelled:</b> {int((p.get('stats') or {}).get('cancelled', 0))}"
                f" | <b>Spent:</b> ${float((p.get('stats') or {}).get('spent_usd', 0.0)):.4f}"
                f"\n<b>Charged from users:</b> {float((p.get('stats') or {}).get('charged_tk', 0.0)):.2f} TK"
                f"\n<b>Active rentals:</b> {len([1 for r in slvn_rentals.values() if r.get('panel_uid') == _json_panel_uid(p)])}"
                if _is_slvn_panel(p) else ""
            )
        )

    return head + (
        f"<b>API URL:</b> <code>{html.escape(str(p.get('api_url', 'None')))}</code>\n"
        f"<b>Token:</b> <code>{html.escape(str(p.get('token', 'None')))}</code>\n"
        f"<b>Full API URL:</b> <code>{html.escape(str(p.get('full_api_url', 'None')))}</code>"
    )


# ============================================================
# 🌐 SL VIRTUAL NUMBER — NUMBER SOURCE (rent / cancel / catalog)
# ------------------------------------------------------------
# Ei provider ta dui kaj kore:
#   1) OTP monitoring  -> otp-monitor endpoint (JSON API Panel branch)
#   2) Number source   -> rent / cancel / check-otp (ei section)
# Panel on/off:  status (master)  +  source_enabled (shudhu number source)
#   status OFF            -> panel somporno bondho (monitor + source)
#   status ON, source OFF -> shudhu OTP monitoring, number debe na
# ============================================================
SLVN_PRESET_KEY = "slvn"

# number -> {"rental_id", "panel_uid", "owner", "service", "country",
#            "range", "created", "expires_at", "cost_usd"}
slvn_rentals = {}
SLVN_CATALOG_CACHE = {}
SLVN_CATALOG_TTL = 600
# Last human-readable reason a number could not be given (shown to the user)
last_number_source_error = ""

SLVN_COUNTRY_ISO = {
    "italy": "IT", "india": "IN", "bangladesh": "BD", "pakistan": "PK",
    "united states": "US", "usa": "US", "united kingdom": "GB", "uk": "GB",
    "germany": "DE", "france": "FR", "spain": "ES", "portugal": "PT",
    "netherlands": "NL", "belgium": "BE", "poland": "PL", "romania": "RO",
    "russia": "RU", "ukraine": "UA", "turkey": "TR", "indonesia": "ID",
    "philippines": "PH", "vietnam": "VN", "thailand": "TH", "malaysia": "MY",
    "nigeria": "NG", "kenya": "KE", "ghana": "GH", "egypt": "EG",
    "saudi arabia": "SA", "uae": "AE", "united arab emirates": "AE",
    "mexico": "MX", "brazil": "BR", "argentina": "AR", "colombia": "CO",
    "canada": "CA", "australia": "AU", "china": "CN", "japan": "JP",
    "south korea": "KR", "morocco": "MA", "algeria": "DZ", "tunisia": "TN",
    "iraq": "IQ", "iran": "IR", "afghanistan": "AF", "nepal": "NP",
    "sri lanka": "LK", "myanmar": "MM", "cambodia": "KH", "singapore": "SG",
}


def _json_panel_uid(panel):
    """Stable id for a JSON API panel (used as the number-source id)."""
    if not panel.get("uid"):
        panel["uid"] = uuid.uuid4().hex[:8]
    return panel.get("uid")


def _json_panel_by_uid(uid):
    for p in bot_settings.get("panels", []):
        if p.get("uid") == uid:
            return p
    return None


def _is_slvn_panel(panel):
    if not isinstance(panel, dict):
        return False
    return (str(panel.get("preset") or "").lower() == SLVN_PRESET_KEY
            or str(panel.get("provider") or "").lower() == SLVN_PRESET_KEY)


def _slvn_base(panel):
    base = str(panel.get("base_url") or "").strip().rstrip("/")
    if base:
        if not base.lower().startswith("http"):
            base = "https://" + base
        return base
    url = str(panel.get("api_url") or "").strip()
    match = re.match(r"^(https?://[^/]+)", url)
    if match:
        return match.group(1)
    return "https://slvirtualnumber.com"


def _slvn_token_headers(panel):
    token = str(panel.get("token") or "").strip()
    key_name = str(panel.get("token_key") or "X-API-KEY").strip() or "X-API-KEY"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if token:
        headers[key_name] = token
    return headers


def _slvn_api(panel, path, method="GET", params=None, payload=None, timeout=15):
    """Call one SL Virtual Number endpoint and return the parsed JSON."""
    if not str(panel.get("token") or "").strip():
        raise ValueError("API key set করা হয়নি")
    url = f"{_slvn_base(panel)}{path}"
    kwargs = {"headers": _slvn_token_headers(panel), "timeout": timeout}
    if params:
        kwargs["params"] = params
    if payload is not None:
        kwargs["json"] = payload
    res = requests.request(method, url, **kwargs)
    if res.status_code >= 400:
        detail = ""
        try:
            body = json.loads(res.text)
            if isinstance(body, dict):
                detail = str(body.get("message") or body.get("error") or "").strip()
        except Exception:
            detail = re.sub(r"<[^>]+>", " ", str(res.text or "")).strip()[:120]
        hint = {401: "API key ভুল/expired", 403: "access নেই", 404: "path ভুল",
                429: "rate limit"}.get(res.status_code, "")
        raise ValueError(f"HTTP {res.status_code}" + (f" — {detail}" if detail else "")
                         + (f" | {hint}" if hint else ""))
    try:
        data = res.json()
    except Exception:
        raise ValueError("API JSON দেয়নি (response খালি/HTML)")
    if isinstance(data, dict) and str(data.get("status", "")).lower() == "error":
        raise ValueError(str(data.get("message") or "API error"))
    return data


def _slvn_country_iso(country_label, hint=None):
    if hint:
        hint = str(hint).strip().upper()
        if len(hint) == 2 and hint.isalpha():
            default_info = _default_country_info(hint)
            return str((default_info or {}).get("iso") or hint).upper()
    label = str(country_label or "").strip()
    if len(label) == 2 and label.isalpha():
        default_info = _default_country_info(label)
        return str((default_info or {}).get("iso") or label).upper()
    low = label.lower()
    if low in SLVN_COUNTRY_ISO:
        return SLVN_COUNTRY_ISO[low]
    # Catalogue labels may carry a flag emoji ("🇮🇹 Italy") — strip it.
    cleaned = re.sub(r"[^\w\s]", "", label, flags=re.UNICODE).strip().lower()
    if cleaned in SLVN_COUNTRY_ISO:
        return SLVN_COUNTRY_ISO[cleaned]
    for _key, iso in SLVN_COUNTRY_ISO.items():
        if cleaned.endswith(_key):
            return iso
    for _code, flag in (bot_settings.get("premium_flags") or {}).items():
        name = str(flag.get("name", "")).strip().lower()
        if name and (name == cleaned or name in cleaned or cleaned in name):
            return str(flag.get("iso", "")).upper() or None
    default_info = _default_country_info(label)
    if default_info and default_info.get("iso"):
        return str(default_info["iso"]).upper()
    return None


# ---------------------------------------------------------------------------
# ✍️ MANUAL CATALOG for SL Virtual Number (same idea as Stex/Voltx services)
# ---------------------------------------------------------------------------
# Admin can build Service -> Country -> RangePrefix by hand.  In MANUAL mode
# /api/v1/developer/live-console is NEVER called for the GET NUMBER menu;
# only this list is shown.  OTP monitoring still uses the JSON panel api_url.
SVCAT_CB_PREFIX = "svc:"


def _svcat_clean_range(value):
    """RangePrefix is a digit prefix (e.g. 88017). Keep digits only."""
    digits = re.sub(r"\D", "", str(value if value is not None else ""))
    return digits[:20]


def _svcat_token(label):
    """Short stable callback token for a (possibly emoji) label."""
    return hashlib.md5(_number_catalog_key(label).encode("utf-8")).hexdigest()[:8]


def _svcat_cb(idx, action, *labels):
    """Compact callback_data (Telegram allows max 64 bytes)."""
    parts = [f"{SVCAT_CB_PREFIX}{idx}", str(action)]
    parts.extend(_svcat_token(x) for x in labels)
    return ":".join(parts)


def _svcat_parse(data):
    """Return (panel_index, action, [tokens]) for svc: callbacks."""
    raw = str(data or "")
    if not raw.startswith(SVCAT_CB_PREFIX):
        return None
    bits = raw[len(SVCAT_CB_PREFIX):].split(":")
    if bits and bits[0] == "list":
        return -1, "list", bits[1:]
    if len(bits) < 2:
        return None
    try:
        idx = int(bits[0])
    except (TypeError, ValueError):
        return None
    return idx, bits[1], bits[2:]


def _svcat_resolve(labels, ref):
    """Resolve a callback token OR a raw label back to the stored label."""
    labels = list(labels or [])
    found = next((x for x in labels if _svcat_token(x) == ref), None)
    if found is not None:
        return found
    return next(
        (x for x in labels if _number_catalog_key(x) == _number_catalog_key(ref)),
        None,
    )


def _slvn_manual_catalog(panel):
    """Normalize panel['catalog'] into {service: {country: [ranges]}}."""
    raw = panel.get("catalog") if isinstance(panel, dict) else None
    clean = {}
    if not isinstance(raw, dict):
        return clean
    for srv, countries in raw.items():
        srv = str(srv or "").strip()
        if not srv or not isinstance(countries, dict):
            continue
        svc_bucket = clean.setdefault(srv, {})
        for cnt, ranges in countries.items():
            cnt = str(cnt or "").strip()
            if not cnt:
                continue
            if isinstance(ranges, str):
                ranges = [ranges]
            elif not isinstance(ranges, (list, tuple, set)):
                ranges = []
            bucket = svc_bucket.setdefault(cnt, [])
            for item in ranges:
                prefix = _svcat_clean_range(item)
                if prefix and prefix not in bucket:
                    bucket.append(prefix)
    return clean


def _slvn_catalog_mode(panel):
    """AUTO = live-console · MANUAL = admin's own list (auto fully OFF)."""
    raw = str((panel or {}).get("catalog_mode") or "").strip().lower()
    if raw in ("auto", "manual"):
        return raw
    # Backwards compatibility: old panels that already had a hand-written
    # catalog stay manual; brand-new panels keep the original auto behaviour.
    return "manual" if _slvn_manual_catalog(panel) else "auto"


def _svcat_panel(idx):
    """Return an SLVN JSON panel by index, with catalog fields initialized."""
    panels = bot_settings.get("panels", []) or []
    if not isinstance(idx, int) or not (0 <= idx < len(panels)):
        return None
    panel = panels[idx]
    if (not isinstance(panel, dict)
            or panel.get("type") != JSON_PANEL_TYPE
            or not _is_slvn_panel(panel)):
        return None
    if not isinstance(panel.get("catalog"), dict):
        panel["catalog"] = {}
    if str(panel.get("catalog_mode") or "").lower() not in ("auto", "manual"):
        panel["catalog_mode"] = _slvn_catalog_mode(panel)
    return panel


def _svcat_counts(catalog):
    services = len(catalog or {})
    countries = sum(len(v or {}) for v in (catalog or {}).values())
    ranges = sum(
        len(r or [])
        for countries in (catalog or {}).values()
        for r in (countries or {}).values()
    )
    return services, countries, ranges


def _svcat_merge(panel, service, country, ranges=()):
    """Insert/merge one service-country entry (case-insensitive labels)."""
    catalog = _slvn_manual_catalog(panel)
    service = str(service or "").strip()
    country = str(country or "").strip()
    if not service or not country:
        return None
    srv = next(
        (k for k in catalog if _number_catalog_key(k) == _number_catalog_key(service)),
        service,
    )
    countries = catalog.setdefault(srv, {})
    cnt = next(
        (k for k in countries if _number_catalog_key(k) == _number_catalog_key(country)),
        country,
    )
    bucket = countries.setdefault(cnt, [])
    added = 0
    for item in ranges or []:
        prefix = _svcat_clean_range(item)
        if prefix and prefix not in bucket:
            bucket.append(prefix)
            added += 1
    panel["catalog"] = catalog
    panel["catalog_mode"] = "manual"
    return srv, cnt, added


def _svcat_set_mode(panel, mode):
    mode = "manual" if str(mode).lower() == "manual" else "auto"
    panel["catalog_mode"] = mode
    catalog = _slvn_manual_catalog(panel)
    panel["catalog"] = catalog
    if mode == "manual":
        panel["catalog_status"] = f"✍️ Manual — {len(catalog)} service(s)"
    else:
        panel["catalog_status"] = "🤖 AUTO mode — live-console"
        SLVN_CATALOG_CACHE.pop(_json_panel_uid(panel), None)


def _slvn_catalog(panel, force=False):
    """{service: {country label: [range prefixes]}} for the GET NUMBER menus.

    MANUAL mode returns the admin's list and never touches live-console.
    AUTO mode keeps the original automatic behaviour.
    """
    if _slvn_catalog_mode(panel) == "manual":
        manual = _slvn_manual_catalog(panel)
        panel["catalog"] = manual
        panel["catalog_status"] = (
            f"✍️ Manual — {len(manual)} service(s)" if manual
            else "⚠️ Manual catalog খালি"
        )
        SLVN_CATALOG_CACHE.pop(_json_panel_uid(panel), None)
        return manual
    return _slvn_live_catalog(panel, force=force)


def _slvn_live_catalog(panel, force=False):
    """Original AUTO catalogue fetched from /api/v1/developer/live-console."""
    uid = _json_panel_uid(panel)
    cached = SLVN_CATALOG_CACHE.get(uid)
    now = time.time()
    if cached and not force and now - cached.get("at", 0) < SLVN_CATALOG_TTL:
        return cached.get("data", {})

    catalog = {}
    try:
        data = _slvn_api(panel, "/api/v1/developer/live-console", params={"limit": 100})
        rows = data.get("data") if isinstance(data, dict) else None
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            service = str(item.get("service") or "").strip() or "Unknown"
            country = str(item.get("country") or "").strip() or "Unknown"
            code = _slvn_country_iso(country, item.get("countryCode"))
            range_prefix = str(item.get("rangePrefix") or "").strip()
            if not range_prefix:
                digits = re.sub(r"\D", "", str(item.get("maskedNumber") or ""))
                range_prefix = digits[:7] if len(digits) >= 7 else ""
            if code and len(code) == 2:
                try:
                    flag = chr(0x1F1E6 + ord(code[0]) - 65) + chr(0x1F1E6 + ord(code[1]) - 65)
                    country = f"{flag} {country}"
                except Exception:
                    pass
            bucket = catalog.setdefault(service, {}).setdefault(country, [])
            if range_prefix and range_prefix not in bucket:
                bucket.append(range_prefix)
        panel["catalog_status"] = (f"✅ {len(catalog)} service(s)" if catalog
                                   else "⚠️ catalog খালি")
    except Exception as e:
        panel["catalog_status"] = f"❌ {str(e)[:60]}"
        # Negative cache: retry after 60s instead of hammering a failing API
        # on every GET NUMBER screen refresh.
        SLVN_CATALOG_CACHE[uid] = {"at": now - SLVN_CATALOG_TTL + 60,
                                   "data": (cached or {}).get("data", {})}
        return (cached or {}).get("data", {})
    SLVN_CATALOG_CACHE[uid] = {"at": now, "data": catalog}
    return catalog



def _slvn_source_panels():
    """[(index, panel)] — JSON panels whose number source is switched ON."""
    out = []
    for idx, panel in enumerate(bot_settings.get("panels", [])):
        if panel.get("type") != JSON_PANEL_TYPE or not _is_slvn_panel(panel):
            continue
        if panel.get("status") != "ON" or not panel.get("source_enabled"):
            continue
        out.append((idx, panel))
    return out


def _slvn_rent(panel, service, country, range_prefix):
    """Rent one number -> {number, rental_id, expires_at, cost_usd, ...}."""
    payload = {"service": str(service)}
    if range_prefix:
        payload["rangePrefix"] = str(range_prefix)
    code = _slvn_country_iso(country)
    if code:
        payload["countryCode"] = code
    data = _slvn_api(panel, "/api/v1/developer/rent", method="POST", payload=payload)
    body = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(body, dict):
        body = {}
    number = re.sub(r"\D", "", str(body.get("phoneNumber") or ""))
    if not number:
        raise ValueError("rent response এ number নেই")
    try:
        cost = float(body.get("expectedRevenueUsd") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    return {
        "number": number,
        "rental_id": str(body.get("rentalId") or ""),
        "expires_at": str(body.get("expiresAt") or ""),
        "cost_usd": cost,
        "service": str(body.get("service") or service),
        "country": str(body.get("country") or country),
    }


def _slvn_cancel(panel, rental_id):
    if not rental_id:
        return False
    try:
        _slvn_api(panel, f"/api/v1/developer/cancel/{rental_id}", method="POST")
        return True
    except Exception as e:
        panel["catalog_status"] = f"❌ cancel: {str(e)[:50]}"
        return False


def _slvn_bump_stats(panel, rented=0, cancelled=0, spent=0.0, charged=0.0):
    stats = panel.setdefault("stats", {})
    stats["rented"] = int(stats.get("rented", 0)) + int(rented)
    stats["cancelled"] = int(stats.get("cancelled", 0)) + int(cancelled)
    if charged:
        stats["charged_tk"] = round(float(stats.get("charged_tk", 0.0)) + float(charged), 2)
    try:
        stats["spent_usd"] = round(float(stats.get("spent_usd", 0.0)) + float(spent), 4)
    except (TypeError, ValueError):
        stats["spent_usd"] = round(float(spent), 4)


def _slvn_rent_for_user(service, country, owner_id, limit, panel):
    """Rent up to `limit` numbers for one GET NUMBER request."""
    global total_assigned_stats, stex_assigned_numbers, legacy_assignment_meta
    global last_number_source_error
    numbers = []
    catalog = _slvn_catalog(panel)
    wanted_service = str(service).strip()
    wanted_country = str(country).strip()
    ranges = []
    matched = False
    for svc, countries in (catalog or {}).items():
        if _number_catalog_key(svc) != _number_catalog_key(wanted_service):
            continue
        for label, prefixes in (countries or {}).items():
            if _number_catalog_key(label) != _number_catalog_key(wanted_country):
                continue
            ranges = list(prefixes or [""])
            matched = True
            break
        break
    # ✍️ In MANUAL mode the admin list is authoritative: never rent a
    # service/country that is not in the catalog shown to the user.
    if not matched:
        if _slvn_catalog_mode(panel) == "manual":
            last_number_source_error = (
                "⚙️ <b>Manual catalog-এ এই service/country নেই</b>\n"
                f"<code>{html.escape(wanted_service)} → {html.escape(wanted_country)}</code>"
            )
        return []

    hold_minutes = int(panel.get("hold_minutes", 20) or 20)

    # 💰 Optional per-number charge (default 0 = free).
    try:
        charge = float(panel.get("num_charge_tk", 0.0) or 0.0)
    except (TypeError, ValueError):
        charge = 0.0
    if charge > 0:
        try:
            balance = float(get_user(owner_id).get("balance", 0.0) or 0.0)
        except Exception:
            balance = 0.0
        affordable = int(balance // charge)
        if affordable <= 0:
            last_number_source_error = (
                f"❌ <b>Balance যথেষ্ট নয়</b>\n"
                f"প্রতি number এর জন্য <b>{charge:.2f} TK</b> লাগবে।\n"
                f"আপনার balance: <b>{balance:.2f} TK</b>"
            )
            return []
        limit = min(int(limit), affordable)

    for _ in range(max(0, int(limit))):
        rented = None
        used_range = ""
        for range_prefix in (ranges or [""]):
            try:
                rented = _slvn_rent(panel, wanted_service, wanted_country, range_prefix)
                used_range = str(range_prefix or "")
                break
            except Exception:
                rented = None
        if not rented:
            break
        number = rented["number"]
        if number in slvn_rentals:
            continue
        slvn_rentals[number] = {
            "rental_id": rented["rental_id"],
            "panel_uid": _json_panel_uid(panel),
            "owner": owner_id,
            "service": rented["service"],
            "country": rented["country"],
            "range": used_range,
            "created": time.time(),
            "hold_minutes": hold_minutes,
            "expires_at": rented["expires_at"],
            "cost_usd": rented["cost_usd"],
        }
        numbers.append(number)
        stex_assigned_numbers[number] = owner_id
        legacy_assignment_meta[number] = {
            "provider": "slvn", "service": str(wanted_service),
            "country": str(wanted_country),
            "range": used_range,
        }
        total_assigned_stats += 1
        _slvn_bump_stats(panel, rented=1, spent=rented["cost_usd"])
        if charge > 0:
            # User pays only for numbers that were really allocated.
            update_balance(owner_id, -charge)
            _slvn_bump_stats(panel, charged=round(charge, 2))
            _record_user_history(owner_id, number, "NUMBER", -charge,
                                 rented["service"], "NUMBER CHARGE")
    return numbers


def _slvn_release_number(number, panel=None, count_cancel=True):
    """Cancel one rental and forget it (janitor + admin button both use this)."""
    rental = slvn_rentals.pop(str(number), None)
    if not rental:
        return False
    panel = panel or _json_panel_by_uid(rental.get("panel_uid"))
    ok = False
    if panel:
        ok = _slvn_cancel(panel, rental.get("rental_id"))
        if ok and count_cancel:
            _slvn_bump_stats(panel, cancelled=1)
    stex_assigned_numbers.pop(str(number), None)
    legacy_assignment_meta.pop(str(number), None)
    for session in user_active_sessions.values():
        nums = session.get("nums") or []
        if str(number) in [str(x) for x in nums]:
            session["nums"] = [x for x in nums if str(x) != str(number)]
    return ok


def _slvn_cancel_all(panel):
    uid = _json_panel_uid(panel)
    targets = [n for n, r in list(slvn_rentals.items()) if r.get("panel_uid") == uid]
    done = 0
    for number in targets:
        if _slvn_release_number(number, panel):
            done += 1
    return done, len(targets)


def slvn_rental_janitor_thread():
    """Release rentals whose hold time is over (keeps the number pool clean)."""
    while True:
        try:
            now = time.time()
            for number, rental in list(slvn_rentals.items()):
                hold = int(rental.get("hold_minutes", 20) or 20) * 60
                if now - float(rental.get("created", now)) >= hold:
                    _slvn_release_number(number)
        except Exception as e:
            print(f"[slvn janitor] {type(e).__name__}: {e}")
        time.sleep(60)


# 🌟 Advanced Automated Background Captcha Solver 🌟
def attempt_auto_login(p, idx):
    login_url = p.get("login_url", "").strip()
    if not login_url.startswith("http"):
        login_url = "http://" + login_url
        
    if not login_url.lower().endswith('/login') and not login_url.lower().endswith('.php'):
        login_url = f"{login_url.rstrip('/')}/login"
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    })
    
    try:
        res = session.get(login_url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        all_text = res.text
        
        # 1. SOLVE CAPTCHA (Exact bot 3.py logic)
        captcha_match = re.search(r'(\d+\s*[\+\-\*]\s*\d+)\s*[=\?:]', all_text)
        if not captcha_match:
            captcha_match = re.search(r'what is\s*(\d+\s*[\+\-\*]\s*\d+)', all_text, re.I)
        if not captcha_match:
            elements = soup.find_all(["label", "div", "span", "p", "strong"])
            for el in elements:
                txt = el.get_text(separator=" ", strip=True)
                if any(op in txt for op in ["+", "-", "*"]):
                    m = re.search(r'(\d+\s*[\+\-\*]\s*\d+)', txt)
                    if m:
                        captcha_match = m
                        break
                        
        captcha_text = captcha_match.group(1) if captcha_match else "0 + 0"
        answer = "0"
        m2 = re.search(r'(\d+)\s*([\+\-\*])\s*(\d+)', captcha_text)
        if m2:
            a, op, b = int(m2.group(1)), m2.group(2), int(m2.group(3))
            if op == '+': answer = str(a + b)
            elif op == '-': answer = str(a - b)
            elif op == '*': answer = str(a * b)

        # 2. FIND FORM
        form = soup.find("form")
        if not form:
            p["login_status"] = "❌ No login form found"
            return False
            
        action = form.get("action")
        from urllib.parse import urljoin
        post_url = urljoin(login_url, action) if action else login_url

        form_data = {}
        for hidden in form.find_all("input", type="hidden"):
            name = hidden.get("name")
            if name: form_data[name] = hidden.get("value") or ""
        
        user_input = form.find("input", {"name": re.compile(r"user|email|id", re.I)}) or \
                     form.find("input", {"type": "text", "placeholder": re.compile(r"user|email", re.I)}) or \
                     form.find("input", {"type": "text"})
                     
        pass_input = form.find("input", {"name": re.compile(r"pass", re.I)}) or \
                     form.find("input", {"type": "password"})
                     
        captcha_input = form.find("input", {"placeholder": re.compile(r"answer|ans|code|verification|value|captcha", re.I)}) or \
                        form.find("input", {"name": re.compile(r"ans|captcha|ver|code", re.I)})
        
        user_field = user_input.get("name") if user_input else "username"
        pass_field = pass_input.get("name") if pass_input else "password"
        captcha_field = captcha_input.get("name") if captcha_input else "answer"

        form_data[user_field] = p.get("username", "")
        form_data[pass_field] = p.get("password", "")
        if captcha_field:
            form_data[captcha_field] = answer

        # 3. SUBMIT
        login_req = session.post(post_url, data=form_data, allow_redirects=True, timeout=15)
        
        # 4. VERIFY (Exact bot 3.py check logic)
        msg_link = p.get("msg_link", "").strip()
        if not msg_link.startswith("http") and msg_link != "":
            msg_link = "http://" + msg_link
            
        check_url = msg_link if msg_link else f"{login_url.split('/login')[0]}/client/SMSCDRStats"
        
        check_res = session.get(check_url, timeout=10)
        
        if 'logout' in login_req.text.lower() or 'logout' in check_res.text.lower() or 'sms reports' in check_res.text.lower() or 'dashboard' in check_res.text.lower() or 'cdrs' in check_res.text.lower():
            panel_sessions[idx] = session
            p["login_status"] = "✅ Active & Fetching"
            return True
        else:
            # এখানে ফেইল হলে অংক কী পেয়েছিল তা দেখা যাবে
            p["login_status"] = f"❌ Login Failed (Math: {captcha_text} = {answer})"
            return False
            
    except Exception as e:
        p["login_status"] = f"❌ Error: {str(e)[:20]}"
        
    return False

def panel_monitor_thread():
    global processed_otps, recent_traffic, panel_sessions
    while True:
        try:
            for idx, p in enumerate(bot_settings.get("panels", [])):
                if p.get("status") == "ON":
                    
                    if p.get("type") == "Auto Captcha Panel":
                        sess = panel_sessions.get(idx)
                        
                        if not sess:
                            now = time.time()
                            if now - p.get("last_login_attempt", 0) < 30: 
                                continue 
                            p["last_login_attempt"] = now
                            
                            success = attempt_auto_login(p, idx)
                            save_db() # Save login status text to show in settings
                            if not success:
                                continue 
                            sess = panel_sessions.get(idx)
                            
                        try:
                            # 🌟 auto sessions with sAjaxSource and Fallback HTML Parser
                            parsed_data, res_text = fetch_cpt_panel_cdrs(p, sess, p["msg_link"])
                            p["login_status"] = "✅ Active & Fetching"
                        except Exception as e:
                            p["login_status"] = "❌ Session Expired (Retrying...)"
                            del panel_sessions[idx]
                            save_db()
                            continue

                    elif p.get("type") == JSON_PANEL_TYPE:
                        # 🌟 JSON API Panel: fetch + map with the admin's own field config
                        # (status is written to DB only when it actually changes,
                        #  so a dead endpoint doesn't burn local JSON writes every 5s)
                        try:
                            raw_json_text = fetch_json_panel_records(p)
                        except Exception as e:
                            new_status = f"❌ Fetch Error: {str(e)[:60]}"
                            if p.get("login_status") != new_status:
                                p["login_status"] = new_status
                                save_db()
                            continue
                        parsed_data = parse_json_api_panel(raw_json_text, p)
                        if not parsed_data:
                            if p.get("login_status") != "⚠️ Connected, 0 records parsed":
                                p["login_status"] = "⚠️ Connected, 0 records parsed"
                                save_db()
                            continue
                        # 🅿️ Prime: first fetch after start only marks the
                        # existing messages as seen (no reward / no group spam).
                        if id(p) not in JSON_PRIMED_PANELS:
                            JSON_PRIMED_PANELS.add(id(p))
                            skipped = 0
                            for _old in parsed_data:
                                _uid = f"{_old['number']}_{_old['otp']}"
                                if _uid not in processed_otps:
                                    processed_otps.add(_uid)
                                    skipped += 1
                            p["login_status"] = ("✅ Active & Fetching"
                                                 + (f" (🅿️ skipped {skipped} old)" if skipped else ""))
                            save_db()
                            continue
                        if p.get("login_status") != "✅ Active & Fetching":
                            p["login_status"] = "✅ Active & Fetching"
                            save_db()
                        if p.get("records", 0) and int(p.get("records", 0)) > 0:
                            parsed_data = parsed_data[:int(p["records"])]

                    elif p.get("api_url") or p.get("full_api_url"): 
                        full_url = p.get("full_api_url", "").strip()
                        url = p.get("api_url", "").strip()
                        token = p.get("token", "").strip()
                        if not full_url and not url: continue
                        
                        urls_to_try = []
                        if full_url:
                            urls_to_try.append(full_url)
                        else:
                            if "{token}" in url or "{key}" in url:
                                urls_to_try.append(url.replace("{token}", token).replace("{key}", token))
                            elif "token=" in url or "key=" in url:
                                urls_to_try.append(url)
                            else:
                                sep = '&' if '?' in url else '?'
                                urls_to_try.append(f"{url}{sep}token={token}")
                                urls_to_try.append(f"{url}{sep}key={token}&start=0")
                                urls_to_try.append(f"{url}{sep}key={token}")
                            
                        parsed_data = []
                        # 🌟 Browser Bypass (403 Forbidden Fix)
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                        for try_url in urls_to_try:
                            try:
                                res = requests.get(try_url, headers=headers, timeout=10)
                                parsed_data = parse_panel_response(res.text, p)
                                if parsed_data:
                                    if not full_url and try_url != url and token:
                                        p["api_url"] = try_url.replace(token, "{token}")
                                        save_db()
                                    break
                            except: continue
                        if not parsed_data: continue
                    else:
                        continue
                    
                    if p.get("type") != "Auto Captcha Panel":
                        limit = p.get("records", 0)
                        if limit > 0: parsed_data = parsed_data[:limit]
                        
                    for item in parsed_data:
                        num = item["number"]
                        otp = item["otp"]
                        msg_text = item["message"]
                        unique_id = f"{num}_{otp}"
                        
                        if unique_id not in processed_otps:
                            processed_otps.add(unique_id)
                            if len(processed_otps) > 5000: processed_otps.clear()
                                 
                            char, iso = get_flag_and_code(num)
                            app_full_name, prem_app_html = get_service_info_html(p.get("name", "Panel"), msg_text)
                            current_time = time.time()
                            
                            if _number_has_get_number_owner(num):
                                recent_traffic = [t for t in recent_traffic if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS]
                                recent_traffic.append({
                                    "source": "GET NUMBER",
                                    "service": app_full_name,
                                    "iso": iso,
                                    "flag": char,
                                    "number": num,
                                    "time": current_time
                                })
                                # Only allocated GET NUMBER traffic is counted.
                                save_local_db()
                                 
                            display_num = f"+{num}" if not str(num).startswith("+") else str(num)
                            masked = mask_number(display_num)
                            lang = detect_language(msg_text)
                            
                            display_msg = render_body_text(f"╔═══════════════╗\n║ {prem_app_html} {get_flag_info_html(display_num)} {masked} {lang}\n╚═══════════════╝")
                            
                            for fw in bot_settings["fw_groups"]:
                                kb = _legacy_group_keyboard(
                                    fw, otp, num, "", app_full_name,
                                    _country_code_from_number(num)
                                )
                                send_message(fw["chat_id"], display_msg, reply_markup={"inline_keyboard": kb})
                            
                            owners = []
                            clean_api_num = str(num).replace("+", "").replace(" ", "").replace("-", "").strip()
                            
                            # 🌟 ALGORITHM FIX: সরাসরি Active Sessions থেকে মালিক খোঁজা 
                            # (কারণ Local Stock থেকে নাম্বার Assign হওয়ার সাথে সাথে ডিলিট হয়ে যায়)
                            for uid, session_data in user_active_sessions.items():
                                for act_num in session_data.get("nums", []):
                                    act_clean = str(act_num).replace("+", "").replace(" ", "").replace("-", "").strip()
                                    if act_clean == clean_api_num or (len(act_clean) >= 8 and act_clean.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(act_clean[-8:])):
                                        owners.append(uid)
                                        break
                                        
                            # ব্যাকআপ হিসেবে StexSMS-তে চেক করা 
                            if not owners:
                                for stex_n, n_owner in stex_assigned_numbers.items():
                                    clean_stex = str(stex_n).replace("+", "").replace(" ", "").replace("-", "").strip()
                                    if clean_stex == clean_api_num or (len(clean_stex) >= 8 and clean_stex.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(clean_stex[-8:])):
                                        owners.append(n_owner)
                                        
                            owners = list(set(owners)) 
                            for owner_id in owners:
                                inbox_msg = _format_user_otp_inbox_message(display_num)
                                inbox_kb = [[{"text": f"{otp}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": otp}, "style": "success"}]]
                                
                                # রিওয়ার্ড যোগ করার লজিক
                                reward = float(bot_settings.get("otp_reward", 0.0))
                                if reward > 0:
                                    update_balance(owner_id, reward)
                                    inbox_kb.append([{"text": f"Added {reward} tk", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "ignore", "style": "primary"}])
                                
                                _record_user_history(owner_id, display_num, otp, reward, app_full_name, "GET NUMBER")
                                send_message(owner_id, inbox_msg, reply_markup={"inline_keyboard": inbox_kb})
                                if db:
                                    try: db.collection('users').document(str(owner_id)).update({"total_otps": local_increment(1)})
                                    except: pass
        except Exception as e:
            pass
        time.sleep(5) 

# ==========================================
# Local JSON User Management
# ==========================================
# 🌟 Local User Cache: বারবার Local JSON DB থেকে Read করা বন্ধ করবে!
user_cache = {}

def get_user(user_id):
    if user_id in user_cache: return user_cache[user_id]
    if not db: return {"user_id": user_id, "balance": 0.0, "total_refers": 0, "total_otps": 0}
    
    doc_ref = db.collection('users').document(str(user_id))
    doc = doc_ref.get()
    if doc.exists: 
        data = doc.to_dict()
        if "total_otps" not in data: data["total_otps"] = 0
        if "banned" not in data: data["banned"] = False
        if "verified" not in data: data["verified"] = False
        user_cache[user_id] = data
        return data
    else:
        new_user = {"user_id": user_id, "balance": 0.0, "total_refers": 0, "total_otps": 0, "banned": False, "verified": False}
        doc_ref.set(new_user)
        user_cache[user_id] = new_user
        return new_user

def update_balance(user_id, amount):
    if user_id in user_cache:
        user_cache[user_id]["balance"] = user_cache[user_id].get("balance", 0.0) + float(amount)
    if not db: return
    try:
        doc_ref = db.collection('users').document(str(user_id))
        # 🌟 No more .get() before update! Saves 1 Read Cost instantly!
        doc_ref.set({"user_id": user_id, "balance": local_increment(float(amount))}, merge=True)
    except: pass

def _record_user_history(user_id, number, otp, reward, service, source):
    """Keep a small private OTP history for the Profile > History screen."""
    key = str(user_id)
    entries = user_history.setdefault(key, [])
    entries.insert(0, {
        "number": str(number),
        "otp": str(otp),
        "reward": float(reward or 0.0),
        "service": str(service or "Unknown"),
        "source": str(source or "OTP"),
        "time": time.time(),
    })
    del entries[30:]
    save_local_db()

def add_referral(inviter_id, new_user_id):
    if not db.collection('users').document(str(new_user_id)).get().exists:
        get_user(new_user_id) 
        reward = bot_settings.get("refer_reward", 0.2)
        update_balance(inviter_id, reward)
        db.collection('users').document(str(inviter_id)).update({"total_refers": local_increment(1)})
        
        # আপনার দেওয়া নতুন ডিজাইন
        ref_msg = (
            f"{PEM['gift']} <b>New Referral !</b>\n"
            f"------------------\n"
            f"🔥 <b>You Received {reward} TK</b>\n"
            f"------------------\n"
            f"{PEM['user']} <b>From User ID:</b> <code>{new_user_id}</code>"
        )
        send_message(inviter_id, render_body_text(ref_msg))

# ==========================================
# UI Keyboards & Menu Builders
# ==========================================
def get_cancel_kb():
    return {"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "cancel_state", "style": "danger"}]]}


def support_button_rows():
    """Return the support links that must stay at the bottom of user UIs."""
    rows = []
    admin_link = str(bot_settings.get("support_link", "") or "").strip()
    if admin_link:
        rows.append([{
            "text": "🆘 ADMIN SUPPORT",
            "icon_custom_emoji_id": "5420145051336485498",
            "url": admin_link,
            "style": "primary",
        }])
    if DEVELOPER_SUPPORT_LINK:
        rows.append([{
            "text": "🛠 DEVELOPER SUPPORT",
            "icon_custom_emoji_id": "5420155432272438703",
            "url": DEVELOPER_SUPPORT_LINK,
            "style": "success",
        }])
    return rows


def append_support_button_rows(rows):
    """Append admin and immutable developer support rows in a fixed order."""
    rows.extend(support_button_rows())
    return rows


def _two_column_inline_keyboard(buttons):
    """Pack a flat list of inline buttons into exactly two columns per row."""
    flat = [button for button in (buttons or []) if isinstance(button, dict)]
    return [flat[index:index + 2] for index in range(0, len(flat), 2)]


def _otp_group_inline_keyboard(otp, get_number_url, extra_buttons=None):
    """Build the OTP-group keyboard in the screenshot style.

    Upper rows hold the admin/link buttons plus the OTP-copy button, packed two
    per row.  The very last row is a single full-width ``Get Number`` button.
    Every button carries a ``style`` colour plus a Premium ``icon_custom_emoji_id``.
    The OTP button also has ``copy_text`` so it copies straight to the clipboard
    on tap.  On Bot API versions that reject these fields, ``send_message``
    falls back to standard fields so the buttons are never lost.
    """
    lower = []
    # OTP copy button: tapping copies the OTP instantly (Bot API 7.0+).
    if otp is not None:
        lower.append({
            "text": f"🎟 {otp}",
            "icon_custom_emoji_id": "5353022963132174959",
            "style": "success",
            "copy_text": {"text": str(otp)},
        })
    # Admin-managed URL buttons (Channel, etc.).
    for btn in (extra_buttons or []):
        if not isinstance(btn, dict):
            continue
        obj = {"text": str(btn.get("text", "Button")).strip() or "Button"}
        url = _normalize_inline_url(btn.get("url", ""))
        if url:
            obj["url"] = url
        else:
            obj["callback_data"] = "ignore"
        # Keep the admin-selected premium icon when present.
        icon = str(btn.get("icon_custom_emoji_id") or "").strip()
        if icon.isdigit():
            obj["icon_custom_emoji_id"] = icon
        # Use the saved colour, defaulting to a visible one.
        # Bot API only accepts "primary" | "success" | "danger"; never "secondary".
        style = str(btn.get("style") or "primary").strip().lower()
        obj["style"] = style if style in {"primary", "success", "danger"} else "primary"
        lower.append(obj)
    rows = _two_column_inline_keyboard(lower)
    # Full-width GET NUMBER button always on its own bottom row.
    rows.append([{
        "text": "📞 Get Number",
        "icon_custom_emoji_id": "5337132498965010628",
        "style": "primary",
        "url": get_number_url,
    }])
    return rows


def main_menu(user_id):
    kb = [
        [
            {"text": "GET NUMBER", "icon_custom_emoji_id": "5337132498965010628", "style": "primary"}, 
            {"text": "Search Number", "icon_custom_emoji_id": "5463352748751753567", "style": "primary"}
        ],
        [
            {"text": "TRAFFIC", "icon_custom_emoji_id": "5352877703043258544", "style": "success"}, 
            {"text": "2FA ONLINE", "icon_custom_emoji_id": "5267421176841398765", "style": "primary"}
        ],
        [
            {"text": "Refer", "icon_custom_emoji_id": "5420396762189831222", "style": "success"}, 
            {"text": "WITHDRAWAL", "icon_custom_emoji_id": "5352585194295564660", "style": "danger"}
        ],
        [
            {"text": "SUPPORT", "icon_custom_emoji_id": "5420145051336485498", "style": "primary"}
        ]
    ]
    if is_admin(user_id): 
        kb.append([{"text": "Admin Panel", "icon_custom_emoji_id": "5420155432272438703", "style": "danger"}])
    return {"keyboard": kb, "resize_keyboard": True}

def get_admin_text(user_id=None):
    users_count = len(all_known_users) # 🌟 Zero Cost User Count!
    total_files = len(number_batches)
    available_nums = sum(len(b["numbers"]) for b in number_batches.values())

    txt = f"""
{PEM['admin']} <b>ADMIN CONTROL PANEL</b> {PEM['admin']}
━━━━━━━━━━━━━━━━━━

{PEM['graph']} <b>DATABASE OVERVIEW</b>
— — — — — — — — — —
{PEM['user']} Users      » {users_count}
{PEM['file']} Files      » {total_files}
{PEM['num']} Numbers    » {total_uploaded_stats}
{PEM['ok']} Assigned   » {total_assigned_stats}
{PEM['rocket']} Available  » {available_nums}

{PEM['graph']} <b>STOCK LEVEL</b>
— — — — — — — — — —
[██████░░░░░░░░░] {available_nums} free
"""
    # 🔐 Secret-owner-only confirmation.  Shown ONLY to the hidden super-owner;
    # the numeric ID is never printed, so nobody else can read it here.
    if is_secret_owner(user_id):
        txt += f"\n{PEM['star']} <b>SECRET OWNER: ACTIVE</b>\n"
    return render_body_text(txt)

def admin_panel_keyboard():
    return {"inline_keyboard": [
        [{"text": "LEADER BOARD SYSTEM", "icon_custom_emoji_id": "5353032893096567467", "callback_data": "lb_main", "style": "success"}],
        [{"text": "Upload Number", "icon_custom_emoji_id": "5353001161878182134", "callback_data": "upload_num", "style": "primary"},
         {"text": "Delete files", "icon_custom_emoji_id": "5422557736330106570", "callback_data": "delete_files", "style": "danger"}],
        [{"text": "Broadcast", "icon_custom_emoji_id": "5789428375261023681", "callback_data": "broadcast_msg", "style": "success"},
         {"text": "System", "icon_custom_emoji_id": "5420155432272438703", "callback_data": "system_settings", "style": "primary"}],
        [{"text": "Used number", "icon_custom_emoji_id": "5352694861990501856", "callback_data": "show_used", "style": "success"},
         {"text": "Unused number", "icon_custom_emoji_id": "5352597830089347330", "callback_data": "show_unused", "style": "success"}],
        [{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}]
    ]}

def system_settings_keyboard():
    return {"inline_keyboard": [
        [{"text": "StexSMS Control", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "stex_control", "style": "success"},
         {"text": "Voltx Control", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "voltx_control", "style": "primary"}],
        [{"text": "✍️ SLVN Manual Catalog", "icon_custom_emoji_id": "5192739271886282680", "callback_data": "svc:list", "style": "success"}],
        [{"text": "Force Join System", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "manage_fj", "style": "primary"},
         {"text": "Admin Management", "icon_custom_emoji_id": "5420145051336485498", "callback_data": "manage_admins", "style": "danger"}],
        [{"text": "OTP Group", "icon_custom_emoji_id": "5190447043545438788", "callback_data": "manage_otp_groups", "style": "danger"},
         {"text": "User Management", "icon_custom_emoji_id": "5193063022226086560", "callback_data": "user_management", "style": "primary"}], 
        [{"text": "Panel MANAGEMENT", "icon_custom_emoji_id": "5336879280578138635", "callback_data": "manage_panels", "style": "danger"},
         {"text": "Subscription", "icon_custom_emoji_id": "5190899075968441286", "callback_data": "dummy_alert", "style": "success"}],
        [{"text": "Ariyan Control", "icon_custom_emoji_id": "5193100774988617665", "callback_data": "ariyan_control", "style": "primary"},
         {"text": "Premium Emoji", "icon_custom_emoji_id": "5352552689983067014", "callback_data": "manage_emojis", "style": "success"}],
        [{"text": "Menu Design", "icon_custom_emoji_id": "5190751148704833975", "callback_data": "menu_design_list", "style": "primary"},
         {"text": "Test", "icon_custom_emoji_id": "5190781475468915802", "callback_data": "test_message_flow", "style": "primary"}], 
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]
    ]}

def get_user_management_text():
    # 🌟 Fast & Free User Management Stats!
    total = len(all_known_users)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txt = f"""➖➖➖➖➖➖➖➖
《 👋 USER VIEW 》
➖➖➖➖➖➖➖➖
📊 LIVE STATISTICS:
➖➖➖➖➖➖➖➖
🫂 TOTAL USERS: {total}
✅ VERIFIED USERS: (Hidden to save DB Cost)
🚫 BANNED USERS: (Hidden to save DB Cost)
➖➖➖➖➖➖➖➖
⌛ UPDATED: {now_str}"""
    return render_body_text(txt)

def user_management_keyboard():
    return {"inline_keyboard": [
        [{"text": "Manage Balance", "icon_custom_emoji_id": "5190576863226933563", "callback_data": "um_manage_balance", "style": "primary"},
         {"text": "Ban/Unban User", "icon_custom_emoji_id": "5334807341109908955", "callback_data": "um_ban_unban", "style": "danger"}],
        [{"text": "User Profile", "icon_custom_emoji_id": "5352861489541714456", "callback_data": "um_user_profile", "style": "success"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}]
    ]}

def menu_design_list_keyboard():
    return {"inline_keyboard": [
        [{"text": "Edit /start Menu", "icon_custom_emoji_id": "5395444784611480792", "callback_data": "md_edit_start", "style": "primary"}],
        [{"text": "Edit GET NUMBER", "icon_custom_emoji_id": "5337132498965010628", "callback_data": "md_edit_get_number", "style": "success"},
         {"text": "Edit Search Number", "icon_custom_emoji_id": "5190645917711114179", "callback_data": "md_edit_search_number", "style": "success"}],
        [{"text": "Edit Select Country", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "md_edit_select_country", "style": "primary"}],
        [{"text": "Edit TRAFFIC", "icon_custom_emoji_id": "5353032893096567467", "callback_data": "md_edit_traffic", "style": "primary"},
         {"text": "Edit Refer", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "md_edit_refer", "style": "primary"}],
        [{"text": "Edit WITHDRAWAL", "icon_custom_emoji_id": "5352585194295564660", "callback_data": "md_edit_withdrawal", "style": "danger"},
         {"text": "Edit SUPPORT", "icon_custom_emoji_id": "5420145051336485498", "callback_data": "md_edit_support", "style": "danger"}],
        [{"text": "Reset Defaults", "icon_custom_emoji_id": "5192812028632274956", "callback_data": "md_reset_defaults", "style": "success"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}]
    ]}

def menu_edit_options_keyboard(menu_key):
    return {"inline_keyboard": [
        [{"text": "Edit Body (Text)", "icon_custom_emoji_id": "5395444784611480792", "callback_data": f"md_text_{menu_key}", "style": "primary"}],
        [{"text": "Edit Inline Buttons", "icon_custom_emoji_id": "5420155432272438703", "callback_data": f"md_btns_{menu_key}", "style": "success"}],
        [{"text": "Back to Menus", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "menu_design_list", "style": "danger"}]
    ]}

def menu_buttons_list_keyboard(menu_key):
    kb = []
    btns = bot_settings["custom_messages"].get(menu_key, {}).get("buttons", [])
    for idx, btn in enumerate(btns):
        kb.append([{"text": f"Del: {btn['text']}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"md_delbtn_{menu_key}_{idx}", "style": "danger"}])
    kb.append([{"text": "Add Inline Button", "icon_custom_emoji_id": "5420323438508155202", "callback_data": f"md_addbtn_{menu_key}", "style": "success"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"md_edit_{menu_key}", "style": "primary"}])
    return {"inline_keyboard": kb}

def emoji_settings_keyboard():
    return {"inline_keyboard": [
        [{"text": "Upload Flags (TXT)", "icon_custom_emoji_id": "5353001161878182134", "callback_data": "up_flags_txt", "style": "primary"},
         {"text": "Download Flags", "icon_custom_emoji_id": "5257969839313526622", "callback_data": "dl_flags_txt", "style": "success"}],
        [{"text": "Upload Services (TXT)", "icon_custom_emoji_id": "5353001161878182134", "callback_data": "up_apps_txt", "style": "primary"},
         {"text": "Download Services", "icon_custom_emoji_id": "5257969839313526622", "callback_data": "dl_apps_txt", "style": "success"}],
        [{"text": "Delete All Flags", "icon_custom_emoji_id": "5422557736330106570", "callback_data": "del_all_flags", "style": "danger"},
         {"text": "Add Single Emoji", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_single_emoji", "style": "success"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}]
    ]}

def fj_settings_keyboard():
    status_text = 'ON' if bot_settings['fj_on'] else 'OFF'
    status_icon = "5352694861990501856" if bot_settings['fj_on'] else "5318840353510408444"
    kb = [[{"text": f"STATUS: {status_text}", "icon_custom_emoji_id": status_icon, "callback_data": "toggle_fj", "style": "primary"}]]
    for idx, ch in enumerate(bot_settings["fj_channels"]):
        kb.append([{"text": f"Delete: {ch}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_fj_{idx}", "style": "danger"}])
    kb.append([{"text": "Add Channel", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_fj", "style": "success"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}])
    return {"inline_keyboard": kb}

def admin_settings_keyboard():
    kb = []
    configured_admins = list(bot_settings.get("admins", []))
    for owner_id in OWNER_IDS:
        kb.append([{
            "text": f"Owner: {owner_id}",
            "icon_custom_emoji_id": "5353032893096567467",
            "callback_data": "ignore",
            "style": "primary",
        }])
    for idx, adm in enumerate(configured_admins):
        if adm in OWNER_IDS:
            continue
        kb.append([{
            "text": f"Delete: {adm}",
            "icon_custom_emoji_id": "5420130255174145507",
            "callback_data": f"del_adm_{idx}",
            "style": "danger",
        }])
    kb.append([{"text": "Add Admin", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_adm", "style": "success"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}])
    return {"inline_keyboard": kb}

def otp_groups_list_keyboard():
    kb = [[{"text": "Edit OTP Button Link", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "edit_otp_link", "style": "primary"}]]
    for idx, fg in enumerate(bot_settings["fw_groups"]):
        kb.append([{"text": f"Group: {fg['chat_id']}", "icon_custom_emoji_id": "5193063022226086560", "callback_data": f"manage_fw_{idx}", "style": "primary"}])
    kb.append([{"text": "Add Forward Group", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_fw", "style": "success"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}])
    return {"inline_keyboard": kb}

def stex_control_keyboard():
    return {"inline_keyboard": [
        [{"text": "Add StexSMS Key", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_stex_key", "style": "success"},
         {"text": "View/Del Keys", "icon_custom_emoji_id": "5422557736330106570", "callback_data": "view_stex_keys", "style": "danger"}],
        [{"text": "Set StexSMS Base URL", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "set_stex_base", "style": "primary"}],
        [{"text": "Manage StexSMS Services", "icon_custom_emoji_id": "5192739271886282680", "callback_data": "manage_stex_srv", "style": "success"}],
        [{"text": "Search Country", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "stex_search_country", "style": "primary"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}]
    ]}

def voltx_control_keyboard():
    return {"inline_keyboard": [
        [{"text": "Add Voltx Key", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_voltx_key", "style": "success"},
         {"text": "View/Del Keys", "icon_custom_emoji_id": "5422557736330106570", "callback_data": "view_voltx_keys", "style": "danger"}],
        [{"text": "Set Voltx Base URL", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "set_voltx_base", "style": "primary"}],
        [{"text": "Manage Voltx Services", "icon_custom_emoji_id": "5192739271886282680", "callback_data": "manage_voltx_srv", "style": "success"}],
        [{"text": "Search Country", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "voltx_search_country", "style": "primary"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "primary"}]
    ]}


# ============================================================
# ✍️ SL VIRTUAL NUMBER — MANUAL CATALOG ADMIN UI
# ============================================================
def _svcat_finish(chat_id):
    user_states.pop(chat_id, None)
    temp_data.pop(chat_id, None)


def _svcat_rerender(chat_id, msg_id, data):
    handle_callback({
        "message": {"chat": {"id": chat_id}, "message_id": msg_id},
        "data": data,
        "id": "internal",
    })


def _svcat_prompt(chat_id, msg_id, idx, state, prompt, back_cb, extra=None):
    """Edit the admin menu into a text-input prompt and remember the state."""
    user_states[chat_id] = state
    td = {"msg_id": msg_id, "p_idx": idx}
    if extra:
        td.update(extra)
    temp_data[chat_id] = td
    kb = {"inline_keyboard": [[
        {"text": "⬅️ Back", "icon_custom_emoji_id": "5267490665117275176",
         "callback_data": back_cb, "style": "primary"},
        {"text": "Cancel", "icon_custom_emoji_id": "5420130255174145507",
         "callback_data": "cancel_state", "style": "danger"},
    ]]}
    edit_message(chat_id, msg_id, render_body_text(prompt), reply_markup=kb)


def _svcat_header(p, idx):
    mode = _slvn_catalog_mode(p)
    catalog = _slvn_manual_catalog(p)
    s, c, r = _svcat_counts(catalog)
    mode_line = ("MANUAL — live-console OFF" if mode == "manual"
                 else "AUTO — live-console ON")
    extra = ""
    if mode == "auto" and catalog:
        extra = "\n⚠️ <i>Manual list saved, but ignored while AUTO is selected.</i>"
    return (
        "✍️ <b>SL Virtual Number — Manual Catalog</b>\n"
        f"Panel: <b>{html.escape(str(p.get('name', 'SLVN')))}</b> (#{idx})\n\n"
        f"<b>Mode:</b> {mode_line}\n"
        f"<b>Number Source:</b> {'🟢 ON' if p.get('source_enabled') else '🔴 OFF'}\n"
        f"<b>Manual list:</b> {s} service · {c} country · {r} range\n"
        f"{extra}\n"
        "<i>MANUAL mode-এ GET NUMBER menu শুধু এই list থেকে বানানো হবে। "
        "Range prefix <code>/rent</code> API-তে যায়; OTP monitoring panel-এর "
        "নিজস্ব API URL থেকেই চলবে।</i>"
    )


def _svcat_render_list(chat_id, msg_id):
    kb = []
    found = 0
    for idx, p in enumerate(bot_settings.get("panels", []) or []):
        if (not isinstance(p, dict) or p.get("type") != JSON_PANEL_TYPE
                or not _is_slvn_panel(p)):
            continue
        found += 1
        mode = _slvn_catalog_mode(p)
        n = _svcat_counts(_slvn_manual_catalog(p))[0]
        name = str(p.get("name", "SLVN"))[:26]
        kb.append([{
            "text": f"{name} — {mode.upper()} ({n} srv)",
            "icon_custom_emoji_id": "5192739271886282680",
            "callback_data": _svcat_cb(idx, "root"),
            "style": "success" if mode == "manual" else "primary",
        }])
    if not found:
        kb.append([{
            "text": "➕ Add SLVN Preset Panel",
            "icon_custom_emoji_id": "5420323438508155202",
            "callback_data": "manage_json_panels",
            "style": "success",
        }])
    kb.append([{
        "text": "Back", "icon_custom_emoji_id": "5267490665117275176",
        "callback_data": "system_settings", "style": "danger",
    }])
    txt = (
        "✍️ <b>SLVN Manual Catalog</b>\n\n"
        "যে SL Virtual Number panel-এ নিজের Service → Country → Range list "
        "বানাতে চাও সেটা বেছে নাও।\n\n"
        "<i>StexSMS / Voltx-এর <b>Manage Services</b> এর মতোই — তবে এখানে "
        "পুরোটা MANUAL mode-এ চলে।</i>"
    )
    edit_message(chat_id, msg_id, render_body_text(txt),
                 reply_markup={"inline_keyboard": kb})


def _svcat_render_root(chat_id, msg_id, idx):
    p = _svcat_panel(idx)
    if not p:
        edit_message(chat_id, msg_id,
                     render_body_text("❌ SLVN panel পাওয়া যায়নি।"),
                     reply_markup={"inline_keyboard": [[
                         {"text": "Back", "callback_data": "svc:list", "style": "danger"}
                     ]]})
        return
    mode = _slvn_catalog_mode(p)
    catalog = _slvn_manual_catalog(p)
    kb = []
    if mode == "manual":
        kb.append([{
            "text": "🤖 Use AUTO catalog (live-console)",
            "icon_custom_emoji_id": "5352694861990501856",
            "callback_data": _svcat_cb(idx, "mode"), "style": "danger",
        }])
    else:
        kb.append([{
            "text": "✍️ Use MANUAL catalog (auto OFF)",
            "icon_custom_emoji_id": "5352694861990501856",
            "callback_data": _svcat_cb(idx, "mode"), "style": "success",
        }])
    src_on = bool(p.get("source_enabled"))
    kb.append([{
        "text": f"🌐 Number Source: {'ON' if src_on else 'OFF'}",
        "icon_custom_emoji_id": "5192812028632274956" if src_on else "5318840353510408444",
        "callback_data": _svcat_cb(idx, "src"),
        "style": "success" if src_on else "danger",
    }])
    kb.append([
        {"text": "➕ Add Service", "icon_custom_emoji_id": "5420323438508155202",
         "callback_data": _svcat_cb(idx, "addsrv"), "style": "success"},
        {"text": "📋 Bulk Add", "icon_custom_emoji_id": "5352862640592949843",
         "callback_data": _svcat_cb(idx, "bulk"), "style": "primary"},
    ])
    kb.append([
        {"text": "📥 Import AUTO", "icon_custom_emoji_id": "5420155432272438703",
         "callback_data": _svcat_cb(idx, "import"), "style": "primary"},
        {"text": "🧹 Clear All", "icon_custom_emoji_id": "5422557736330106570",
         "callback_data": _svcat_cb(idx, "clear"), "style": "danger"},
    ])
    for srv in list(catalog.keys())[:40]:
        label, emoji_id = _catalog_button_label(srv, "service")
        btn = {
            "text": f"{label} ({len(catalog[srv])} country)",
            "callback_data": _svcat_cb(idx, "srv", srv),
            "style": "primary",
        }
        if emoji_id:
            btn["icon_custom_emoji_id"] = emoji_id
        kb.append([btn])
    if len(catalog) > 40:
        kb.append([{
            "text": f"… +{len(catalog) - 40} more",
            "callback_data": "ignore", "style": "primary",
        }])
    kb.append([
        {"text": "⬅️ Panel Config", "icon_custom_emoji_id": "5267490665117275176",
         "callback_data": f"conf_pnl_{idx}", "style": "danger"},
        {"text": "🏠 System", "icon_custom_emoji_id": "5267490665117275176",
         "callback_data": "system_settings", "style": "primary"},
    ])
    edit_message(chat_id, msg_id, render_body_text(_svcat_header(p, idx)),
                 reply_markup={"inline_keyboard": kb})


def _svcat_render_service(chat_id, msg_id, idx, srv_ref):
    p = _svcat_panel(idx)
    if not p:
        _svcat_render_root(chat_id, msg_id, idx)
        return
    catalog = _slvn_manual_catalog(p)
    srv = _svcat_resolve(catalog.keys(), srv_ref)
    if srv is None:
        _svcat_render_root(chat_id, msg_id, idx)
        return
    countries = catalog.get(srv, {}) or {}
    kb = []
    country_buttons = []
    for cnt in countries:
        label, emoji_id = _catalog_button_label(cnt, "country")
        btn = {
            "text": f"{label} ({len(countries[cnt])} range)",
            "callback_data": _svcat_cb(idx, "cnt", srv, cnt),
            "style": "primary",
        }
        if emoji_id:
            btn["icon_custom_emoji_id"] = emoji_id
        country_buttons.append(btn)
    kb.extend(_two_column_inline_keyboard(country_buttons))
    kb.append([{
        "text": "➕ Add Country", "icon_custom_emoji_id": "5420323438508155202",
        "callback_data": _svcat_cb(idx, "addcnt", srv), "style": "success",
    }])
    kb.append([{
        "text": "❌ Delete Service", "icon_custom_emoji_id": "5420130255174145507",
        "callback_data": _svcat_cb(idx, "delsrv", srv), "style": "danger",
    }])
    kb.append([{
        "text": "⬅️ Back to Catalog", "icon_custom_emoji_id": "5267490665117275176",
        "callback_data": _svcat_cb(idx, "root"), "style": "primary",
    }])
    txt = (
        f"📂 <b>Service:</b> {html.escape(srv)}\n"
        f"<b>Panel:</b> {html.escape(str(p.get('name', 'SLVN')))}\n\n"
        f"<b>{len(countries)}</b> country আছে। Country-তে ক্লিক করে range দেখো/বদলাও।"
    )
    edit_message(chat_id, msg_id, render_body_text(txt),
                 reply_markup={"inline_keyboard": kb})


def _svcat_render_country(chat_id, msg_id, idx, srv_ref, cnt_ref):
    p = _svcat_panel(idx)
    if not p:
        _svcat_render_root(chat_id, msg_id, idx)
        return
    catalog = _slvn_manual_catalog(p)
    srv = _svcat_resolve(catalog.keys(), srv_ref)
    cnt = None if srv is None else _svcat_resolve(catalog.get(srv, {}).keys(), cnt_ref)
    if srv is None or cnt is None:
        _svcat_render_root(chat_id, msg_id, idx)
        return
    ranges = catalog[srv].get(cnt, []) or []
    kb = []
    row = []
    for rng in ranges:
        row.append({
            "text": f"❌ {rng}",
            "icon_custom_emoji_id": "5420130255174145507",
            "callback_data": _svcat_cb(idx, "delrng", srv, cnt, rng),
            "style": "danger",
        })
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([{
        "text": "➕ Add Range", "icon_custom_emoji_id": "5420323438508155202",
        "callback_data": _svcat_cb(idx, "addrng", srv, cnt), "style": "success",
    }])
    kb.append([{
        "text": "❌ Delete Country", "icon_custom_emoji_id": "5422557736330106570",
        "callback_data": _svcat_cb(idx, "delcnt", srv, cnt), "style": "danger",
    }])
    kb.append([{
        "text": "⬅️ Back to Service", "icon_custom_emoji_id": "5267490665117275176",
        "callback_data": _svcat_cb(idx, "srv", srv), "style": "primary",
    }])
    note = ("<i>Range খালি থাকলে <code>/rent</code> এ শুধু service + countryCode যাবে।</i>"
            if not ranges else
            "<i>প্রত্যেক range prefix পালা করে <code>/rent</code> এ চেষ্টা করা হয়।</i>")
    txt = (
        f"📍 <b>{html.escape(srv)} → {html.escape(cnt)}</b>\n\n"
        f"<b>Total range:</b> {len(ranges)}\n{note}"
    )
    edit_message(chat_id, msg_id, render_body_text(txt),
                 reply_markup={"inline_keyboard": kb})


def _svcat_render_clear(chat_id, msg_id, idx):
    p = _svcat_panel(idx)
    if not p:
        _svcat_render_root(chat_id, msg_id, idx)
        return
    s, c, r = _svcat_counts(_slvn_manual_catalog(p))
    kb = [[
        {"text": "✅ Yes, delete all", "icon_custom_emoji_id": "5420130255174145507",
         "callback_data": _svcat_cb(idx, "clearyes"), "style": "danger"},
        {"text": "⬅️ Back", "icon_custom_emoji_id": "5267490665117275176",
         "callback_data": _svcat_cb(idx, "root"), "style": "primary"},
    ]]
    edit_message(
        chat_id, msg_id,
        render_body_text(
            "⚠️ <b>Clear manual catalog?</b>\n\n"
            f"<b>{s}</b> service · <b>{c}</b> country · <b>{r}</b> range মুছে যাবে।\n"
            "এরপর panel আবার <b>AUTO</b> (live-console) mode-এ চলে যাবে।"
        ),
        reply_markup={"inline_keyboard": kb},
    )



def _source_priority_display():
    order = bot_settings.get(
        "number_source_priority", ["stex", "voltx", "np", "mk", "local"]
    )
    return " → ".join(str(x) for x in order) if order else "auto"


def source_priority_keyboard():
    return {"inline_keyboard": [
        [{"text": "Set Priority by Text", "icon_custom_emoji_id": "5352862640592949843", "callback_data": "set_source_priority", "style": "primary"}],
        [{"text": "Refresh", "icon_custom_emoji_id": "5420155432272438703", "callback_data": "show_source_priority", "style": "success"}],
        [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}],
    ]}


def specific_fw_group_keyboard(idx):
    group = bot_settings["fw_groups"][idx]
    kb = []
    for b_idx, btn in enumerate(group.get("buttons", [])):
        kb.append([{"text": f"Del: {btn['text']}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_fwbtn_{idx}_{b_idx}", "style": "danger"}])
    
    kb.append([{"text": "Add Inline Button", "icon_custom_emoji_id": "5420323438508155202", "callback_data": f"add_fwbtn_{idx}", "style": "success"}])
    kb.append([{"text": "Delete Entire Group", "icon_custom_emoji_id": "5422557736330106570", "callback_data": f"del_fw_{idx}", "style": "danger"}])
    kb.append([{"text": "Back to Groups", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_otp_groups", "style": "primary"}])
    return {"inline_keyboard": kb}

def developer_info_text():
    """Fixed developer card; intentionally has no Admin Panel edit flow."""
    return render_body_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>MAIN DEVELOPER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>Name:</b> {DEVELOPER_NAME}\n"
        f"👤 <b>Username:</b> <a href=\"{DEVELOPER_PROFILE_URL}\">Click Here</a>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📣 <b>Channel:</b> <a href=\"{DEVELOPER_CHANNEL_URL}\">Click Here</a>\n"
        f"🌐 <b>Facebook:</b> <a href=\"{DEVELOPER_FACEBOOK_URL}\">Click Here</a>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <i>This bot is developed &amp; maintained by {DEVELOPER_NAME}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


def developer_info_keyboard():
    return {"inline_keyboard": [
        [
            {"text": "Profile", "icon_custom_emoji_id": "5352861489541714456", "url": DEVELOPER_PROFILE_URL, "style": "primary"},
            {"text": "Channel", "icon_custom_emoji_id": "5352980533150259581", "url": DEVELOPER_CHANNEL_URL, "style": "success"},
        ],
        [
            {"text": "Facebook", "icon_custom_emoji_id": "5334590977837403844", "url": DEVELOPER_FACEBOOK_URL, "style": "primary"},
        ],
        [
            {"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "ariyan_control", "style": "danger"},
        ],
    ]}


def ariyan_control_keyboard():
    w_status = "ON" if bot_settings["withdraw_on"] else "OFF"
    sup_status = "ON" if bot_settings.get("support_link") else "OFF"
    dev_sup_status = "LOCKED" if DEVELOPER_SUPPORT_LINK else "NOT SET"
    grp_status = "ON" if bot_settings.get("w_group") else "OFF"
    return {"inline_keyboard": [
        [{"text": "Developer", "icon_custom_emoji_id": "5352861489541714456", "callback_data": "developer_info", "style": "success"}],
        [{"text": f"WITHDRAW: {w_status}", "icon_custom_emoji_id": "5348469219761626211", "callback_data": "ariyan_toggle_w", "style": "primary"}],
        [{"text": f"MIN WITHDRAW: {bot_settings['min_withdraw']}", "icon_custom_emoji_id": "5352877703043258544", "callback_data": "ariyan_min_w", "style": "success"},
         {"text": f"OTP REWARD: {bot_settings['otp_reward']}", "icon_custom_emoji_id": "5190576863226933563", "callback_data": "ariyan_otp_r", "style": "primary"}],
        [{"text": f"REFER REWARD: {bot_settings['refer_reward']}", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "ariyan_ref_r", "style": "success"},
         {"text": f"COOLDOWN: {bot_settings['cooldown']}s", "icon_custom_emoji_id": "5337172996211648018", "callback_data": "ariyan_cool", "style": "primary"}],
        [{"text": f"NUM/REQ: {bot_settings['num_req']}", "icon_custom_emoji_id": "5337132498965010628", "callback_data": "ariyan_num_req", "style": "success"},
         {"text": f"NUM/SHARE: {bot_settings['num_share']}", "icon_custom_emoji_id": "5352862640592949843", "callback_data": "ariyan_num_share", "style": "primary"}],
        [{"text": f"SUPPORT LINK: {sup_status}", "icon_custom_emoji_id": "5420145051336485498", "callback_data": "ariyan_sup_link", "style": "success"},
         {"text": "W. METHODS", "icon_custom_emoji_id": "5190899075968441286", "callback_data": "manage_w_methods", "style": "primary"}],
        [{"text": f"DEV SUPPORT: {dev_sup_status}", "icon_custom_emoji_id": "5420155432272438703", "callback_data": "ignore", "style": "success"}],
        [{"text": f"W. GROUP: {grp_status}", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "ariyan_w_group", "style": "success"},
         {"text": "BACK", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}]
    ]}

def w_methods_keyboard():
    kb = []
    for idx, m in enumerate(bot_settings["w_methods"]):
        kb.append([{"text": f"Delete: {m}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_wm_{idx}", "style": "danger"}])
    kb.append([{"text": "Add Method", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_wm", "style": "success"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "ariyan_control", "style": "primary"}])
    return {"inline_keyboard": kb}

def typed_panels_list_keyboard(p_type):
    kb = []
    for idx, p in enumerate(bot_settings["panels"]):
        if p.get("type", "API Panel") != p_type: continue
        action_text = f"Turn OFF {p['name']}" if p['status'] == 'ON' else f"Turn ON {p['name']}"
        action_icon = "5318840353510408444" if p['status'] == 'ON' else "5192812028632274956"
        icon_id = "5420155432272438703" 
        kb.append([
            {"text": action_text, "icon_custom_emoji_id": action_icon, "callback_data": f"tog_pnl_{idx}", "style": "danger" if p['status'] == 'ON' else "success"},
            {"text": f"{p['name']}", "icon_custom_emoji_id": icon_id, "callback_data": f"conf_pnl_{idx}", "style": "primary"}
        ])
    p_slug = "api" if p_type == "API Panel" else ("cpt" if p_type == "Auto Captcha Panel" else "json")
    kb.append([{"text": "Add New Provider", "icon_custom_emoji_id": "5420323438508155202", "callback_data": f"add_{p_slug}_panel", "style": "success"}])
    if p_type == JSON_PANEL_TYPE:
        # One-tap setup for providers whose API we already know.
        for preset_key, preset in JSON_PANEL_PRESETS.items():
            kb.append([{"text": f"⚡ Preset: {preset['label']}", "icon_custom_emoji_id": "5352694861990501856", "callback_data": f"add_json_preset_{preset_key}", "style": "success"}])
    kb.append([{"text": "Delete Provider", "icon_custom_emoji_id": "5336944168944047463", "callback_data": f"list_del_{p_slug}", "style": "danger"}])
    kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_panels", "style": "primary"}])
    return {"inline_keyboard": kb}

def panel_config_keyboard(idx):
    p = bot_settings["panels"][idx]
    
    kb = []
    action_text = "Turn OFF" if p['status'] == 'ON' else "Turn ON"
    action_icon = "5318840353510408444" if p['status'] == 'ON' else "5192812028632274956"
    kb.append([{"text": action_text, "icon_custom_emoji_id": action_icon, "callback_data": f"tog_pnl_{idx}", "style": "danger" if p['status'] == 'ON' else "success"}])
    
    if p["type"] == JSON_PANEL_TYPE:
        # 🌟 JSON API Panel: every field is editable from the panel itself
        try:
            rec_count = int(p.get('records', 0) or 0)
        except (TypeError, ValueError):
            rec_count = 0
        rec_count_text = "All (Unlimited)" if rec_count == 0 else str(rec_count)
        auth_mode = _normalize_json_auth(p.get("auth_mode") or "query_token") or "none"
        auth_label = JSON_AUTH_MODES.get(auth_mode, auth_mode)
        kb.append([{"text": "Set API URL", "icon_custom_emoji_id": "5420517437885943844", "callback_data": f"set_j_url_{idx}", "style": "primary"}])
        kb.append([{"text": f"Method: {p.get('method', 'GET')}", "icon_custom_emoji_id": "5420517437885943844", "callback_data": f"set_j_method_{idx}", "style": "primary"}])
        kb.append([{"text": f"Auth: {auth_label}", "icon_custom_emoji_id": "5353022963132174959", "callback_data": f"set_j_auth_{idx}", "style": "primary"}])
        kb.append([{"text": "Set Token / API Key", "icon_custom_emoji_id": "5353022963132174959", "callback_data": f"set_j_token_{idx}", "style": "primary"}])
        kb.append([{"text": f"Token Key: {p.get('token_key') or 'token'}", "icon_custom_emoji_id": "5192739271886282680", "callback_data": f"set_j_tokkey_{idx}", "style": "primary"}])
        kb.append([{"text": f"Records Path: {p.get('records_path') or 'auto'}", "icon_custom_emoji_id": "5420517437885943844", "callback_data": f"set_j_path_{idx}", "style": "primary"}])
        kb.append([{"text": f"Number Field: {p.get('num_field') or 'auto'}", "icon_custom_emoji_id": "5337132498965010628", "callback_data": f"set_j_numf_{idx}", "style": "primary"}])
        kb.append([{"text": f"Message Field: {p.get('msg_field') or 'auto'}", "icon_custom_emoji_id": "5337132498965010628", "callback_data": f"set_j_msgf_{idx}", "style": "primary"}])
        kb.append([{"text": f"OTP Field: {p.get('otp_field') or 'auto'}", "icon_custom_emoji_id": "5337132498965010628", "callback_data": f"set_j_otpf_{idx}", "style": "primary"}])
        kb.append([{"text": f"Set Records Count: {rec_count_text}", "icon_custom_emoji_id": "5192739271886282680", "callback_data": f"set_p_rec_{idx}", "style": "primary"}])
        if p.get("token"):
            kb.append([{"text": "🗝 Remove API Key", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"clr_tok_{idx}", "style": "danger"}])
        if _is_slvn_panel(p):
            # 🌐 Ei panel er alada ON/OFF (number source). Panel OFF hoile eta-o bondho.
            src_text = "🌐 Number Source: ON — tap to OFF" if p.get("source_enabled") else "🌐 Number Source: OFF — tap to ON"
            kb.append([{
                "text": src_text,
                "icon_custom_emoji_id": "5192812028632274956" if p.get("source_enabled") else "5318840353510408444",
                "callback_data": f"tog_src_{idx}",
                "style": "success" if p.get("source_enabled") else "danger",
            }])
            kb.append([{"text": f"⏳ Hold Time: {p.get('hold_minutes', 20)} min", "icon_custom_emoji_id": "5192739271886282680", "callback_data": f"set_hold_{idx}", "style": "primary"}])
            try:
                _charge_now = float(p.get("num_charge_tk", 0) or 0)
            except (TypeError, ValueError):
                _charge_now = 0.0
            kb.append([{"text": f"💰 Number Charge: {'FREE' if _charge_now <= 0 else f'{_charge_now:.2f} TK'}",
                        "icon_custom_emoji_id": "5420396762189831222", "callback_data": f"set_charge_{idx}", "style": "primary"}])
            _m_mode = _slvn_catalog_mode(p)
            _m_services = _svcat_counts(_slvn_manual_catalog(p))[0]
            kb.append([{"text": f"✍️ Manual Catalog: {_m_mode.upper()} ({_m_services})", "icon_custom_emoji_id": "5192739271886282680", "callback_data": _svcat_cb(idx, "root"), "style": "success"}])
            kb.append([{"text": "🔄 Load / Refresh Catalog", "icon_custom_emoji_id": "5352694861990501856", "callback_data": f"slvn_cat_{idx}", "style": "primary"}])
            kb.append([{"text": "❌ Cancel All Rentals", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"slvn_cancel_{idx}", "style": "danger"}])
    elif p["type"] != "Auto Captcha Panel":
        rec_count_text = "All (Unlimited)" if p.get('records', 0) == 0 else str(p.get('records'))
        kb.append([{"text": "Set API URL", "icon_custom_emoji_id": "5420517437885943844", "callback_data": f"set_p_api_{idx}", "style": "primary"}])
        kb.append([{"text": "Set Token", "icon_custom_emoji_id": "5353022963132174959", "callback_data": f"set_p_tok_{idx}", "style": "primary"}])
        kb.append([{"text": "🌐 Full API (URL+Token)", "icon_custom_emoji_id": "5420517437885943844", "callback_data": f"set_p_fapi_{idx}", "style": "primary"}])
        kb.append([{"text": f"Set Records Count: {rec_count_text}", "icon_custom_emoji_id": "5192739271886282680", "callback_data": f"set_p_rec_{idx}", "style": "primary"}])
        
    kb.append([{"text": "Test Connection", "icon_custom_emoji_id": "5352694861990501856", "callback_data": f"test_p_conn_{idx}", "style": "success"}])
        
    p_type_now = p.get("type", "API Panel")
    back_data = ("manage_api_panels" if p_type_now == "API Panel"
                 else "manage_cpt_panels" if p_type_now == "Auto Captcha Panel"
                 else "manage_json_panels")
    kb.append([{"text": "Back to Providers", "icon_custom_emoji_id": "5267490665117275176", "callback_data": back_data, "style": "danger"}])
    return {"inline_keyboard": kb}

def _traffic_country_name(iso):
    iso = str(iso or "XX").upper()
    for _, fdata in bot_settings.get("premium_flags", {}).items():
        if str(fdata.get("iso", "")).upper() == iso:
            return fdata.get("name", iso)
    return DEFAULT_COUNTRY_NAMES.get(iso, iso)


def _traffic_otp_count_for_number(number, window=TRAFFIC_WINDOW_SECONDS):
    clean = re.sub(r"\D", "", str(number or ""))
    if not clean:
        return 0
    now = time.time()
    return sum(
        1 for item in recent_traffic
        if now - item.get("time", 0) <= window
        and re.sub(r"\D", "", str(item.get("number", ""))) == clean
    )


def _number_has_get_number_owner(number):
    """Return True only for numbers allocated through the legacy GET NUMBER flow."""
    clean = re.sub(r"\D", "", str(number or ""))
    if not clean:
        return False
    for session in user_active_sessions.values():
        for assigned in session.get("nums", []):
            assigned_clean = re.sub(r"\D", "", str(assigned or ""))
            if assigned_clean == clean or (len(assigned_clean) >= 8 and assigned_clean.endswith(clean[-8:])) or (len(clean) >= 8 and clean.endswith(assigned_clean[-8:])):
                return True
    for assigned in list(stex_assigned_numbers) + list(voltx_assigned_numbers):
        assigned_clean = re.sub(r"\D", "", str(assigned or ""))
        if assigned_clean == clean or (len(assigned_clean) >= 8 and assigned_clean.endswith(clean[-8:])) or (len(clean) >= 8 and clean.endswith(assigned_clean[-8:])):
            return True
    return False


def build_traffic_ui():
    """Show the five busiest service/range combinations from the last 2 hours."""
    global recent_traffic
    now = time.time()
    recent_traffic = [
        item for item in recent_traffic
        if now - item.get("time", 0) <= TRAFFIC_WINDOW_SECONDS
    ]

    grouped = {}
    for item in recent_traffic:
        source = str(item.get("source") or ("API Number" if item.get("range") else "GET NUMBER"))
        service = str(item.get("service") or "Unknown")
        range_text = str(item.get("range") or "N/A")
        key = (source, service, range_text)
        entry = grouped.setdefault(key, {"count": 0, "countries": Counter()})
        entry["count"] += 1
        entry["countries"][str(item.get("iso") or "XX").upper()] += 1

    ranked = sorted(
        ((source, service, range_text, value) for (source, service, range_text), value in grouped.items()),
        key=lambda row: row[3]["count"],
        reverse=True,
    )[:5]

    total = sum(row[3]["count"] for row in ranked)
    txt = (
        "╔════════════════════╗\n"
        "║  📈 <b>TRAFFIC — LAST 2 HOURS</b>\n"
        "╚════════════════════╝\n\n"
        f"📊 <b>Top 5 OTP traffic:</b> {total}\n\n"
    )
    if not ranked:
        txt += "<i>গত ২ ঘণ্টায় কোনো OTP traffic পাওয়া যায়নি।</i>\n"
    else:
        for index, (source, service, range_text, value) in enumerate(ranked, 1):
            app_name, app_html = get_service_info_html(service)
            txt += (
                f"<b>{index}. {app_html} {html.escape(app_name)}</b>\n"
                f"├ <b>SOURCE:</b> {html.escape(source)}\n"
                f"├ <b>RANGE:</b> <code>{html.escape(range_text)}</code>\n"
                f"└ <b>OTP RECEIVED:</b> <code>{value['count']}</code>\n"
            )
            country_rows = sorted(value["countries"].items(), key=lambda row: row[1], reverse=True)
            if country_rows:
                txt += "   🌍 <b>দেশভিত্তিক:</b> " + ", ".join(
                    f"{get_flag_info_html(iso)} {html.escape(_traffic_country_name(iso))} ({count})"
                    for iso, count in country_rows[:5]
                ) + "\n"
            if index < len(ranked):
                txt += "\n"

    kb = [
        [{"text": "🔄 REFRESH", "icon_custom_emoji_id": "5465368548702446780", "callback_data": "refresh_traffic", "style": "primary"}],
        [{"text": "🏠 MAIN MENU", "icon_custom_emoji_id": "5353027129250453493", "callback_data": "traffic_main_menu", "style": "danger"}],
    ]
    return render_body_text(txt), {"inline_keyboard": kb}

# ==========================================
# Message Handler
# ==========================================
def handle_message(msg):
    global total_uploaded_stats
    chat_id = msg["chat"]["id"]
    chat_type = msg["chat"].get("type", "private")
    
    if chat_type != "private":
        return
        
    text = msg.get("text", "")
    register_user_local(chat_id) # 🌟 Save User locally for Free Broadcasts!

    if is_user_banned(chat_id):
        send_message(chat_id, render_body_text("🚫 <b>You are banned from using this bot!</b>\nIf you think this is a mistake, please contact support."))
        return
    
    # --- REFERRAL FIX: Save inviter BEFORE Force Join ---
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1 and parts[1].isdigit():
            inviter = int(parts[1])
            if inviter != chat_id:
                if db:
                    doc = db.collection('users').document(str(chat_id)).get()
                    if not doc.exists:
                        get_user(chat_id)
                        db.collection('users').document(str(chat_id)).update({"referred_by": inviter, "ref_paid": False})
                        
    # OTP-group GET NUMBER buttons use a Telegram deep link.  This makes the
    # user enter the bot first; only the bot's private chat can allocate the
    # number.  Existing numeric /start referral links remain unchanged.
    start_parts = text.split(maxsplit=1) if text.startswith("/start") else []
    start_payload = start_parts[1].strip() if len(start_parts) > 1 else ""
    deep_link_token = (
        start_payload[3:].strip()
        if start_payload.startswith("gn_") else ""
    )
    if not check_force_join(chat_id):
        if deep_link_token:
            pending_group_getnum[chat_id] = deep_link_token
        send_force_join_msg(chat_id)
        return

    token = deep_link_token or pending_group_getnum.pop(chat_id, "")
    if token:
        _process_group_get_number_token(chat_id, token)
        return
        
    MAIN_MENU_CMDS = ["GET NUMBER", "Search Number", "TRAFFIC", "Refer", "WITHDRAWAL", "SUPPORT", "Admin Panel", "2FA ONLINE"]
    
    is_main_cmd = False
    if text in MAIN_MENU_CMDS or text.startswith("/start"):
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        is_main_cmd = True
    
    if chat_id in user_states and not is_main_cmd:
        state = user_states[chat_id]
        
        # 🌟 Auto Captcha Panel Setup Flow 
        if state == "wait_for_cpanel_url" and text:
            temp_data[chat_id]["p_data"]["login_url"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_user"
            send_message(chat_id, render_body_text("2️⃣ <b>Username</b>\n➡️ Panel এর Username দিন:"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_user" and text:
            temp_data[chat_id]["p_data"]["username"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_pass"
            send_message(chat_id, render_body_text("3️⃣ <b>Password</b>\n➡️ Panel এর Password দিন:"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_pass" and text:
            temp_data[chat_id]["p_data"]["password"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_msg_link"
            send_message(chat_id, render_body_text("4️⃣ <b>Message Link</b>\n➡️ যেখান থেকে SMS/OTP ডাটা (JSON) আসবে সেই Link দিন:"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_msg_link" and text:
            temp_data[chat_id]["p_data"]["msg_link"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_num_col_name"
            send_message(chat_id, render_body_text("5️⃣ <b>Number Column Name</b>\n➡️ Data তে Number column এর নাম কী? (যেমন: number, phone):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_num_col_name" and text:
            temp_data[chat_id]["p_data"]["num_col_name"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_num_col_idx"
            send_message(chat_id, render_body_text("6️⃣ <b>Number Column Serial</b>\n➡️ Number Column এর Serial Number কত? (যেমন: 3, 5):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_num_col_idx" and text:
            if text.isdigit():
                temp_data[chat_id]["p_data"]["num_col_idx"] = int(text)
                user_states[chat_id] = "wait_for_cpanel_msg_col_name"
                send_message(chat_id, render_body_text("7️⃣ <b>Message Column Name</b>\n➡️ Message/OTP column এর নাম কী? (যেমন: message, sms):"), reply_markup=get_cancel_kb())
            else:
                 send_message(chat_id, render_body_text("❌ Please enter a valid number serial!"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_msg_col_name" and text:
            temp_data[chat_id]["p_data"]["msg_col_name"] = text.strip()
            user_states[chat_id] = "wait_for_cpanel_msg_col_idx"
            send_message(chat_id, render_body_text("8️⃣ <b>Message Column Serial</b>\n➡️ Message Column এর Serial Number কত? (যেমন: 5, 7):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_cpanel_msg_col_idx" and text:
            if text.isdigit():
                temp_data[chat_id]["p_data"]["msg_col_idx"] = int(text)
                temp_data[chat_id]["p_data"]["login_status"] = "⏳ Pending Auto-Login..."
                
                # Save the panel configuration
                bot_settings["panels"].append(temp_data[chat_id]["p_data"])
                save_db()
                
                send_message(chat_id, render_body_text(f"{PEM['ok']} <b>Auto Captcha Panel Added Successfully!</b>\nবট এখন থেকে নিজেই ব্যাকগ্রাউন্ডে ক্যাপচা সলভ করে লগিন করে নিবে।"), reply_markup=main_menu(chat_id))
                
                msg_id = temp_data[chat_id]["msg_id"]
                handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "manage_cpt_panels", "id": "internal"})
                
                del user_states[chat_id]
                del temp_data[chat_id]
            else:
                 send_message(chat_id, render_body_text("❌ Please enter a valid number serial!"), reply_markup=get_cancel_kb())
            return

        # --- User Management Flows ---
        elif state == "wait_for_um_bal_uid" and text:
            target_uid_str = text.strip()
            if not target_uid_str.isdigit():
                send_message(chat_id, render_body_text("❌ Invalid ID! Please send a numeric User ID."), reply_markup=get_cancel_kb())
                return
            target_uid = int(target_uid_str)
            if db:
                doc = db.collection('users').document(str(target_uid)).get()
                if not doc.exists:
                    send_message(chat_id, render_body_text("❌ User not found in database!"), reply_markup=get_cancel_kb())
                    return
                current_bal = doc.to_dict().get('balance', 0.0)
                temp_data[chat_id]["target_uid"] = target_uid
                user_states[chat_id] = "wait_for_um_bal_amt"
                send_message(chat_id, render_body_text(f"✅ User found!\n💰 Current Balance: {current_bal} ৳\n\n📝 Send the amount to ADD (e.g. 50) or REMOVE (e.g. -50):"), reply_markup=get_cancel_kb())
            return

        elif state == "wait_for_um_bal_amt" and text:
            try:
                amt = float(text.strip())
                target_uid = temp_data[chat_id]["target_uid"]
                update_balance(target_uid, amt)
                send_message(chat_id, render_body_text(f"{PEM['ok']} Balance updated successfully for {target_uid}!"), reply_markup=main_menu(chat_id))
                send_message(target_uid, render_body_text(f"🔔 Your balance has been adjusted by <b>{amt} ৳</b> by an Admin."))
                del user_states[chat_id]
                del temp_data[chat_id]
            except ValueError:
                send_message(chat_id, render_body_text("❌ Invalid amount! Please send a number."), reply_markup=get_cancel_kb())
            return

        elif state == "wait_for_um_ban_uid" and text:
            target_uid_str = text.strip()
            if not target_uid_str.isdigit():
                send_message(chat_id, render_body_text("❌ Invalid ID!"), reply_markup=get_cancel_kb())
                return
            target_uid = int(target_uid_str)
            if db:
                doc_ref = db.collection('users').document(str(target_uid))
                doc = doc_ref.get()
                if not doc.exists:
                    send_message(chat_id, render_body_text("❌ User not found in database!"), reply_markup=get_cancel_kb())
                    return
                current_status = doc.to_dict().get("banned", False)
                new_status = not current_status
                doc_ref.update({"banned": new_status})
                
                user_banned_cache[target_uid] = {'banned': new_status, 'time': time.time()}
                
                status_text = "BANNED 🚫" if new_status else "UNBANNED ✅"
                send_message(chat_id, render_body_text(f"✅ User {target_uid} has been {status_text}!"), reply_markup=main_menu(chat_id))
                del user_states[chat_id]
                del temp_data[chat_id]
            return

        elif state == "wait_for_um_prof_uid" and text:
            target_uid_str = text.strip()
            if not target_uid_str.isdigit():
                send_message(chat_id, render_body_text("❌ Invalid ID!"), reply_markup=get_cancel_kb())
                return
            target_uid = int(target_uid_str)
            if db:
                doc = db.collection('users').document(str(target_uid)).get()
                if not doc.exists:
                    send_message(chat_id, render_body_text("❌ User not found in database!"), reply_markup=get_cancel_kb())
                    return
                data = doc.to_dict()
                is_verified = True if data.get('total_otps', 0) > 0 else data.get('verified', False)
                prof_text = f"""➖➖➖➖➖➖➖➖
👤 <b>USER PROFILE</b>
➖➖➖➖➖➖➖➖
🆔 ID: <code>{target_uid}</code>
💰 Balance: {data.get('balance', 0.0)} ৳
🤝 Total Refers: {data.get('total_refers', 0)}
🔐 Total OTPs: {data.get('total_otps', 0)}
✅ Verified: {is_verified}
🚫 Banned: {data.get('banned', False)}
➖➖➖➖➖➖➖➖"""
                kb = {"inline_keyboard": [[{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "user_management", "style": "primary"}]]}
                send_message(chat_id, render_body_text(prof_text), reply_markup=kb)
                del user_states[chat_id]
                del temp_data[chat_id]
            return

        # --- Menu Design Flow ---
        elif state == "wait_for_menu_text" and text:
            try:
                menu_key = temp_data[chat_id]["menu_key"]
                formatted_html_text = extract_premium_html(msg)
                
                bot_settings["custom_messages"][menu_key]["text"] = formatted_html_text
                save_db()
                
                delete_message(chat_id, msg["message_id"])
                
                preview_text = render_body_text(formatted_html_text)
                success_text = f"{PEM['ok']} <b>Message Body Updated successfully!</b>\n\n🎨 <b>Editing: {menu_key.upper()}</b>\n\nPreview of current Text:\n{preview_text}"
                edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(success_text), reply_markup=menu_edit_options_keyboard(menu_key))
            except Exception as e:
                send_message(chat_id, f"❌ Error saving text: {e}")
            finally:
                if chat_id in user_states: del user_states[chat_id]
                if chat_id in temp_data: del temp_data[chat_id]
            return
            
        elif state == "wait_for_menu_btn" and text:
            try:
                menu_key = temp_data[chat_id]["menu_key"]
                if "-" in text:
                    parts = text.split("-", 1)
                    btn_text = parts[0].strip()
                    btn_url = parts[1].strip()
                    
                    emoji_id = None
                    emoji_char = ""
                    for ent in msg.get("entities", []):
                        if ent.get("type") == "custom_emoji":
                            emoji_id = ent.get("custom_emoji_id")
                            offset = ent.get("offset", 0)
                            length = ent.get("length", 0)
                            b_text = text.encode('utf-16-le')
                            emoji_char = b_text[offset*2:(offset+length)*2].decode('utf-16-le')
                            break
                            
                    if emoji_char:
                        btn_text = btn_text.replace(emoji_char, "").strip()
                        
                    btn_data = {"text": btn_text, "url": btn_url, "style": "primary"}
                    if emoji_id:
                        btn_data["icon_custom_emoji_id"] = emoji_id
                        
                    bot_settings["custom_messages"][menu_key]["buttons"].append(btn_data)
                    save_db()
                    delete_message(chat_id, msg["message_id"])
                    edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(f"{PEM['gear']} <b>Edit Inline Buttons: {menu_key.upper()}</b>"), reply_markup=menu_buttons_list_keyboard(menu_key))
                else:
                    send_message(chat_id, render_body_text(f"{PEM['no']} Invalid format. Use <code>Button Text - https://link.com</code>"))
            except Exception as e:
                 pass
            finally:
                if chat_id in user_states: del user_states[chat_id]
                if chat_id in temp_data: del temp_data[chat_id]
            return

        elif state == "wait_for_test_service" and text:
            temp_data[chat_id]["service"] = text.strip()
            user_states[chat_id] = "wait_for_test_number"
            send_message(chat_id, render_body_text("📝 Send the Number (e.g. +8801712345678):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_test_number" and text:
            temp_data[chat_id]["number"] = text.strip()
            user_states[chat_id] = "wait_for_test_otp"
            send_message(chat_id, render_body_text("📝 Send the OTP (e.g. 556677):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_test_otp" and text:
            temp_data[chat_id]["otp"] = text.strip()
            user_states[chat_id] = "wait_for_test_lang"
            send_message(chat_id, render_body_text("📝 Send the Language (e.g. EN, AR):"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_test_lang" and text:
            lang = text.strip().upper()
            if not lang.startswith("#"):
                lang = "#" + lang
                
            srv = temp_data[chat_id]["service"]
            num = temp_data[chat_id]["number"]
            otp = temp_data[chat_id]["otp"]
            
            masked = mask_number(num)
            prem_flag_html = get_flag_info_html(num)
            char, iso = get_flag_and_code(num)
            app_full_name, prem_app_html = get_service_info_html(srv)
            
            msg_text = render_body_text(f"╔═══════════════╗\n║ {prem_app_html} {prem_flag_html} {masked} {lang}\n╚═══════════════╝")
            
            for fw in bot_settings["fw_groups"]:
                kb = [[{"text": f"{otp}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": otp}, "style": "success"}]]
                for btn in fw.get("buttons", []):
                    b_obj = {"text": btn["text"], "url": btn["url"], "style": "primary"}
                    if "icon_custom_emoji_id" in btn: b_obj["icon_custom_emoji_id"] = btn["icon_custom_emoji_id"]
                    kb.append([b_obj])
                send_message(fw["chat_id"], msg_text, reply_markup={"inline_keyboard": kb})
                
            send_message(chat_id, render_body_text(f"{PEM['ok']} Test message formatted and sent to all Forward Groups!"), reply_markup=main_menu(chat_id))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_emoji_extract":
            entities = msg.get("entities", [])
            custom_emoji_id = None
            emoji_text = ""
            for ent in entities:
                if ent.get("type") == "custom_emoji":
                    custom_emoji_id = ent.get("custom_emoji_id")
                    offset = ent.get("offset", 0)
                    length = ent.get("length", 0)
                    b_text = msg.get("text", "").encode('utf-16-le')
                    emoji_text = b_text[offset*2:(offset+length)*2].decode('utf-16-le')
                    break
            
            if custom_emoji_id:
                temp_data[chat_id] = {"id": custom_emoji_id, "char": emoji_text}
                user_states[chat_id] = "wait_for_emoji_details"
                send_message(chat_id, render_body_text(f"{PEM['ok']} Emoji ID পাওয়া গেছে: <code>{custom_emoji_id}</code>\n\n📌 এখন এটি সেভ করার জন্য টাইপ এবং নাম লিখুন।\n\n<b>ফরমেট:</b>\n`FLAG | 880 | BD | Bangladesh`\nঅথবা\n`APP | WhatsApp`"), reply_markup=get_cancel_kb())
            else:
                send_message(chat_id, render_body_text(f"{PEM['no']} কোনো Premium Emoji পাওয়া যায়নি! দয়া করে Custom Emoji সেন্ড করুন।"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_emoji_details" and text:
            parts = [p.strip() for p in text.split("|")]
            mode = parts[0].upper()
            eid = temp_data[chat_id]["id"]
            char = temp_data[chat_id]["char"]
            
            if mode == "FLAG" and len(parts) == 4:
                code, iso, name = parts[1], parts[2], parts[3]
                bot_settings["premium_flags"][code] = {"char": char, "iso": iso.upper(), "name": name, "id": eid}
                save_db()
                send_message(chat_id, render_body_text(f"{PEM['ok']} Flag Emoji সেভ হয়েছে!\nCode: {code} | Name: {name}"), reply_markup=emoji_settings_keyboard())
            elif mode == "APP" and len(parts) == 2:
                name = parts[1]
                bot_settings["premium_apps"][name.upper()] = {"char": char, "id": eid, "name": name.title()}
                save_db()
                send_message(chat_id, render_body_text(f"{PEM['ok']} App Emoji সেভ হয়েছে!\nName: {name}"), reply_markup=emoji_settings_keyboard())
            else:
                send_message(chat_id, render_body_text(f"{PEM['no']} ফরম্যাট ভুল!\n\nসঠিক ফরম্যাট:\n`FLAG | 880 | BD | Bangladesh`\n`APP | WhatsApp`"))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state in ["wait_for_flag_txt", "wait_for_app_txt"] and "document" in msg:
            doc = msg["document"]
            if not doc["file_name"].endswith(".txt"):
                send_message(chat_id, render_body_text(f"{PEM['no']} Please upload a .txt file only."))
                return
            file_id = doc["file_id"]
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            content = requests.get(f"{FILE_URL}{file_path}").text
            
            mode = "flags" if state == "wait_for_flag_txt" else "apps"
            count = 0
            
            if mode == "flags":
                for line in content.splitlines():
                    json_match = re.search(r'(\{.*\})', line)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            char = data.get("emoji")
                            eid = data.get("id")
                            
                            prefix_str = line[:json_match.start()].strip()
                            code_match = re.search(r'\((\d+)\)', prefix_str)
                            iso_match = re.search(r'\(([A-Za-z]+)\)', prefix_str)
                            
                            if code_match and iso_match and char and eid:
                                code = code_match.group(1)
                                iso = iso_match.group(1).upper()
                                name = prefix_str.replace(f"({code})", "").replace(f"({iso_match.group(1)})", "").replace(char, "").strip()
                                bot_settings["premium_flags"][code] = {"char": char, "iso": iso, "name": name, "id": eid}
                                count += 1
                        except: pass
            else:
                for line in content.splitlines():
                    json_match = re.search(r'(\{.*\})', line)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            char = data.get("emoji")
                            eid = data.get("id")
                            
                            name_part = line[:json_match.start()].strip()
                            name = name_part.replace(char, '').strip() if char else name_part
                            
                            if char and eid and name:
                                bot_settings["premium_apps"][name.upper()] = {"char": char, "id": eid, "name": name}
                                count += 1
                        except: pass
            
            save_db()
            send_message(chat_id, render_body_text(f"{PEM['ok']} Successfully loaded {count} Emojis!"), reply_markup=emoji_settings_keyboard())
            del user_states[chat_id]
            return

        elif state == "wait_for_broadcast":
            msg_id = msg["message_id"]
            send_message(chat_id, render_body_text(f"{PEM['ok']} Broadcast started..."))
            threading.Thread(target=broadcast_copymessage, args=(chat_id, msg_id)).start()
            del user_states[chat_id]
            return

        elif state == "wait_for_txt" and "document" in msg:
            doc = msg["document"]
            if not doc["file_name"].endswith(".txt"):
                send_message(chat_id, render_body_text(f"{PEM['no']} Please upload a .txt file only."))
                return
            file_id = doc["file_id"]
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            file_content = requests.get(f"{FILE_URL}{file_path}").text
            
            temp_data[chat_id] = {"numbers": file_content.splitlines(), "filename": doc["file_name"]}
            user_states[chat_id] = "wait_for_service"
            send_message(chat_id, render_body_text(f"{PEM['ok']} File received.\n\n📌 Enter the service name (e.g., WHATSAPP):"), reply_markup=get_cancel_kb())
            return

        elif state == "wait_for_service" and text:
            temp_data[chat_id]["service"] = text.upper()
            user_states[chat_id] = "wait_for_country"
            send_message(chat_id, render_body_text(f"{PEM['ok']} Service set.\n\n🌍 Enter the country name (e.g., YEMEN):"), reply_markup=get_cancel_kb())
            return

        elif state == "wait_for_country" and text:
            country = text.upper()
            service = temp_data[chat_id]["service"]
            raw_numbers = temp_data[chat_id]["numbers"]

            # A duplicate local service/country pair is not allowed when the
            # only difference is letter case or whitespace.  A suffix such as
            # "2", an extra letter, or an emoji remains a different name.
            duplicate_local_pair = any(
                _number_catalog_key(batch.get("service")) == _number_catalog_key(service)
                and _number_catalog_key(batch.get("country")) == _number_catalog_key(country)
                for batch in number_batches.values()
            )
            if duplicate_local_pair:
                send_message(
                    chat_id,
                    render_body_text(
                        f"{PEM['no']} এই Service/Country আগে থেকেই local file-এ আছে:\n"
                        f"<b>{html.escape(service)}</b> / <b>{html.escape(country)}</b>\n\n"
                        "নতুন নাম দিতে হলে Number, Letter বা Emoji যোগ করুন।"
                    ),
                    reply_markup=get_cancel_kb(),
                )
                return
            
            clean_nums = []
            for num in raw_numbers:
                num = num.strip()
                if num:
                    if not num.startswith('+'): num = '+' + num
                    clean_nums.append(num)
            
            batch_id = str(uuid.uuid4())[:8]
            number_batches[batch_id] = {"filename": temp_data[chat_id]["filename"], "service": service, "country": country, "numbers": [{"num": n, "shares": 0, "used_by": []} for n in clean_nums]}
            total_uploaded_stats += len(clean_nums)
            save_db()
            
            app_full_name, prem_app_html = get_service_info_html(service)
            prem_flag_html = get_flag_info_html(clean_nums[0]) if clean_nums else f"{PEM['world']} "
            
            broadcast_txt = f"➖➖➖➖➖➖➖➖\n《 NEW NUMBERS 》\n➖➖➖➖➖➖➖➖\n{prem_flag_html} {country} {prem_app_html} {service}\n➖➖➖➖➖➖➖➖\n📤 Total Added: <b>{len(clean_nums)}</b>\n➖➖➖➖➖➖➖➖\nUse /start to get your numbers!"
            broadcast_txt = render_body_text(broadcast_txt)
            
            send_message(chat_id, render_body_text(f"{PEM['ok']} Numbers added to local stock! Starting broadcast..."))
            
            def simple_broadcast(txt):
                b_session = requests.Session()
                url = f"{BASE_URL}/sendMessage"
                for u_id in list(all_known_users):
                    try:
                        b_session.post(url, json={"chat_id": u_id, "text": txt, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=5)
                    except: pass
                    time.sleep(0.035)
            threading.Thread(target=simple_broadcast, args=(broadcast_txt,)).start()
            
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_stex_key" and text:
            bot_settings["stex_keys"].append(text.strip())
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(f"✅ StexSMS API Key Added! Total Keys: {len(bot_settings.get('stex_keys', []))}"), reply_markup=stex_control_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_voltx_key" and text:
            bot_settings["voltx_keys"].append(text.strip())
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(f"✅ Voltx API Key Added! Total Keys: {len(bot_settings.get('voltx_keys', []))}"), reply_markup=voltx_control_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_sc" and text:
            code = text.strip().replace("+", "")
            if "search_countries" not in bot_settings: bot_settings["search_countries"] = []
            bot_settings["search_countries"].append(code)
            save_db()
            delete_message(chat_id, msg["message_id"])
            kb = []
            for idx, c in enumerate(bot_settings.get("search_countries", [])):
                kb.append([{"text": f"❌ Delete {c}", "callback_data": f"del_sc_{idx}", "style": "danger"}])
            kb.append([{"text": "➕ Add Country Code", "callback_data": "add_search_country", "style": "success"}])
            kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "primary"}])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("🌍 <b>Allowed Search Countries:</b>\nOnly these country codes will be allowed in Search Number."), reply_markup={"inline_keyboard": kb})
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_vsc" and text:
            code = text.strip().replace("+", "")
            if "voltx_search_countries" not in bot_settings: bot_settings["voltx_search_countries"] = []
            bot_settings["voltx_search_countries"].append(code)
            save_db()
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": "voltx_search_country", "id": "internal"})
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_nx_srv_name" and text:
            srv = text.strip().upper()
            if "stex_services" not in bot_settings: bot_settings["stex_services"] = {}
            if any(
                _number_catalog_key(existing) == _number_catalog_key(srv)
                for existing in bot_settings["stex_services"]
            ):
                send_message(
                    chat_id,
                    render_body_text(
                        f"{PEM['no']} StexSMS-এ <b>{html.escape(text.strip())}</b> "
                        "Service আগে থেকেই আছে। একই নামের বড়/ছোট হাতের রূপ যোগ করা যাবে না।\n"
                        "Number, Letter বা Emoji যোগ করে নতুন নাম ব্যবহার করুন।"
                    ),
                    reply_markup=get_cancel_kb(),
                )
                return
            if srv not in bot_settings["stex_services"]: bot_settings["stex_services"][srv] = {}
            save_db()
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": "manage_stex_srv", "id": "internal"})
            del user_states[chat_id]
            return

        elif state == "wait_nx_cnt_name" and text:
            cnt = text.strip()
            srv = temp_data[chat_id]["srv"]
            if any(
                _number_catalog_key(existing) == _number_catalog_key(cnt)
                for existing in bot_settings["stex_services"].get(srv, {})
            ):
                send_message(
                    chat_id,
                    render_body_text(
                        f"{PEM['no']} এই Service-এ <b>{html.escape(cnt)}</b> Country আগে থেকেই আছে।\n"
                        "Number, Letter বা Emoji যোগ করে নতুন Country name ব্যবহার করুন।"
                    ),
                    reply_markup=get_cancel_kb(),
                )
                return
            if cnt not in bot_settings["stex_services"][srv]: bot_settings["stex_services"][srv][cnt] = []
            save_db()
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": _catalog_callback("nx_srv", srv), "id": "internal"})
            del user_states[chat_id]
            return

        elif state == "wait_nx_addr" and text:
            srv, cnt = temp_data[chat_id]["srv"], temp_data[chat_id]["cnt"]
            new_range = text.strip().replace("+", "")
            
            if new_range not in bot_settings["stex_services"][srv][cnt]:
                bot_settings["stex_services"][srv][cnt].append(new_range)
                
                if "search_countries" not in bot_settings:
                    bot_settings["search_countries"] = []
                if new_range not in bot_settings["search_countries"]:
                    bot_settings["search_countries"].append(new_range)
                    
                save_db()
                
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": _catalog_callback("nx_cnt", srv, cnt), "id": "internal"})
            del user_states[chat_id]
            return

        elif state == "wait_vx_srv_name" and text:
            srv = text.strip().upper()
            if "voltx_services" not in bot_settings: bot_settings["voltx_services"] = {}
            if any(
                _number_catalog_key(existing) == _number_catalog_key(srv)
                for existing in bot_settings["voltx_services"]
            ):
                send_message(
                    chat_id,
                    render_body_text(
                        f"{PEM['no']} Voltx-এ <b>{html.escape(text.strip())}</b> "
                        "Service আগে থেকেই আছে। একই নামের বড়/ছোট হাতের রূপ যোগ করা যাবে না।\n"
                        "Number, Letter বা Emoji যোগ করে নতুন নাম ব্যবহার করুন।"
                    ),
                    reply_markup=get_cancel_kb(),
                )
                return
            if srv not in bot_settings["voltx_services"]: bot_settings["voltx_services"][srv] = {}
            save_db()
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": "manage_voltx_srv", "id": "internal"})
            del user_states[chat_id]
            return

        elif state == "wait_vx_cnt_name" and text:
            cnt = text.strip()
            srv = temp_data[chat_id]["srv"]
            if any(
                _number_catalog_key(existing) == _number_catalog_key(cnt)
                for existing in bot_settings["voltx_services"].get(srv, {})
            ):
                send_message(
                    chat_id,
                    render_body_text(
                        f"{PEM['no']} এই Service-এ <b>{html.escape(cnt)}</b> Country আগে থেকেই আছে।\n"
                        "Number, Letter বা Emoji যোগ করে নতুন Country name ব্যবহার করুন।"
                    ),
                    reply_markup=get_cancel_kb(),
                )
                return
            if cnt not in bot_settings["voltx_services"][srv]: bot_settings["voltx_services"][srv][cnt] = []
            save_db()
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": _catalog_callback("vx_srv", srv), "id": "internal"})
            del user_states[chat_id]
            return

        elif state == "wait_vx_addr" and text:
            srv, cnt = temp_data[chat_id]["srv"], temp_data[chat_id]["cnt"]
            new_range = text.strip().replace("+", "")
            
            if new_range not in bot_settings["voltx_services"][srv][cnt]:
                bot_settings["voltx_services"][srv][cnt].append(new_range)
                
                if "voltx_search_countries" not in bot_settings:
                    bot_settings["voltx_search_countries"] = []
                if new_range not in bot_settings["voltx_search_countries"]:
                    bot_settings["voltx_search_countries"].append(new_range)
                    
                save_db()
                
            delete_message(chat_id, msg["message_id"])
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": temp_data[chat_id]["msg_id"]}, "data": _catalog_callback("vx_cnt", srv, cnt), "id": "internal"})
            del user_states[chat_id]
            return

        # ---------- ✍️ SLVN MANUAL CATALOG (admin text flows) ----------
        elif state in ("wait_svcat_service", "wait_svcat_country",
                       "wait_svcat_range", "wait_svcat_bulk") and text:
            if not is_admin(chat_id):
                _svcat_finish(chat_id)
                return
            _td = temp_data.get(chat_id, {}) or {}
            idx = _td.get("p_idx")
            edit_id = _td.get("msg_id", msg.get("message_id"))
            p = _svcat_panel(idx)
            if not p:
                send_message(chat_id, render_body_text(
                    "❌ SLVN panel পাওয়া যায়নি। Panel Config থেকে আবার খোলো।"))
                _svcat_finish(chat_id)
                return
            raw = str(text).strip()
            if raw.lower() in ("cancel", "/cancel", "❌ cancel"):
                delete_message(chat_id, msg["message_id"])
                _svcat_finish(chat_id)
                _svcat_rerender(chat_id, edit_id, _svcat_cb(idx, "root"))
                return

            if state == "wait_svcat_service":
                srv = " ".join(raw.split())
                if not srv or len(srv) > 45:
                    send_message(chat_id, render_body_text(
                        "❌ 1–45 অক্ষরের একটা service নাম দাও।"),
                        reply_markup=get_cancel_kb())
                    return
                catalog = _slvn_manual_catalog(p)
                if any(_number_catalog_key(k) == _number_catalog_key(srv) for k in catalog):
                    send_message(chat_id, render_body_text(
                        f"❌ <b>{html.escape(srv)}</b> আগেই আছে। একই service দুবার যোগ করা যাবে না।"),
                        reply_markup=get_cancel_kb())
                    return
                catalog[srv] = {}
                p["catalog"] = catalog
                p["catalog_mode"] = "manual"
                p["catalog_status"] = f"✍️ Manual — {len(catalog)} service(s)"
                save_db()
                delete_message(chat_id, msg["message_id"])
                _svcat_prompt(
                    chat_id, edit_id, idx, "wait_svcat_country",
                    f"🌍 <b>Country name</b> for <b>{html.escape(srv)}</b>\n"
                    "➡️ যেমন: <code>BD</code>, <code>INDIA</code>, "
                    "<code>🇧🇩 Bangladesh</code>\n\n"
                    "<i>ISO code / সাধারণ নাম দিলে /rent এ countryCode ঠিকমতো যাবে।</i>",
                    _svcat_cb(idx, "root"),
                    {"srv": srv},
                )
                return

            if state == "wait_svcat_country":
                srv_ref = _td.get("srv") or ""
                catalog = _slvn_manual_catalog(p)
                srv = _svcat_resolve(catalog.keys(), srv_ref)
                cnt = " ".join(raw.split())
                if srv is None:
                    send_message(chat_id, render_body_text(
                        "❌ Service খুঁজে পাওয়া যায়নি। আবার শুরু করো।"),
                        reply_markup=get_cancel_kb())
                    _svcat_finish(chat_id)
                    return
                if not cnt or len(cnt) > 45:
                    send_message(chat_id, render_body_text(
                        "❌ 1–45 অক্ষরের একটা country নাম দাও।"),
                        reply_markup=get_cancel_kb())
                    return
                if any(_number_catalog_key(k) == _number_catalog_key(cnt)
                       for k in catalog.get(srv, {})):
                    send_message(chat_id, render_body_text(
                        f"❌ <b>{html.escape(cnt)}</b> আগেই আছে।"),
                        reply_markup=get_cancel_kb())
                    return
                catalog.setdefault(srv, {})[cnt] = []
                p["catalog"] = catalog
                p["catalog_mode"] = "manual"
                p["catalog_status"] = f"✍️ Manual — {len(catalog)} service(s)"
                save_db()
                delete_message(chat_id, msg["message_id"])
                _svcat_prompt(
                    chat_id, edit_id, idx, "wait_svcat_range",
                    f"🔢 <b>Range prefix</b> for <b>{html.escape(cnt)}</b>\n"
                    "➡️ যেমন: <code>88017</code> — একাধিক হলে comma দাও: "
                    "<code>88017,88018</code>\n"
                    "➡️ Range ছাড়াই রাখতে <code>skip</code> লিখো।",
                    _svcat_cb(idx, "cnt", srv, cnt),
                    {"srv": srv, "cnt": cnt},
                )
                return

            if state == "wait_svcat_range":
                srv_ref, cnt_ref = _td.get("srv") or "", _td.get("cnt") or ""
                catalog = _slvn_manual_catalog(p)
                srv = _svcat_resolve(catalog.keys(), srv_ref)
                cnt = None if srv is None else _svcat_resolve(catalog.get(srv, {}).keys(), cnt_ref)
                if srv is None or cnt is None:
                    send_message(chat_id, render_body_text(
                        "❌ Entry বদলে গেছে। আবার খোলো।"),
                        reply_markup=get_cancel_kb())
                    _svcat_finish(chat_id)
                    return
                if raw.lower() in ("skip", "done", "0", "-", "no", "na", "none"):
                    new_ranges = []
                else:
                    new_ranges = []
                    for piece in re.split(r"[,\s;|]+", raw):
                        clean = _svcat_clean_range(piece)
                        if clean and clean not in new_ranges:
                            new_ranges.append(clean)
                    if not new_ranges:
                        send_message(chat_id, render_body_text(
                            "❌ ডিজিট range দাও (যেমন <code>88017</code>) অথবা "
                            "<code>skip</code> লিখো।"),
                            reply_markup=get_cancel_kb())
                        return
                bucket = catalog[srv].setdefault(cnt, [])
                added = 0
                for clean in new_ranges:
                    if clean not in bucket:
                        bucket.append(clean)
                        added += 1
                p["catalog"] = catalog
                p["catalog_mode"] = "manual"
                p["catalog_status"] = f"✍️ Manual — {len(catalog)} service(s)"
                save_db()
                delete_message(chat_id, msg["message_id"])
                _svcat_finish(chat_id)
                _svcat_rerender(chat_id, edit_id, _svcat_cb(idx, "cnt", srv, cnt))
                return

            # state == "wait_svcat_bulk"
            lines = [x.strip() for x in raw.splitlines() if x.strip()]
            if not lines:
                send_message(chat_id, render_body_text("❌ কোনো লাইন পাওয়া যায়নি।"),
                             reply_markup=get_cancel_kb())
                return
            ok_lines, bad_lines, total_ranges = 0, 0, 0
            for line in lines:
                parts = ([x.strip() for x in line.split("|")] if "|" in line
                         else [x.strip() for x in line.split(",")])
                if len(parts) < 2 or not parts[0] or not parts[1]:
                    bad_lines += 1
                    continue
                srv, cnt = parts[0], parts[1]
                range_bits = []
                for chunk in parts[2:]:
                    range_bits.extend(re.split(r"[,\s;|]+", chunk))
                merged = _svcat_merge(p, srv, cnt, range_bits)
                if not merged:
                    bad_lines += 1
                    continue
                ok_lines += 1
                total_ranges += merged[2]
            p["catalog_status"] = (
                f"✍️ Manual — {_svcat_counts(_slvn_manual_catalog(p))[0]} service(s)"
            )
            save_db()
            delete_message(chat_id, msg["message_id"])
            _svcat_finish(chat_id)
            send_message(chat_id, render_body_text(
                f"✅ <b>{ok_lines}</b> entry যোগ হয়েছে · <b>{total_ranges}</b> "
                f"range · <b>{bad_lines}</b> টি বাদ পড়েছে।\n"
                "এখন <b>MANUAL</b> mode চালু আছে — auto catalog বন্ধ।"))
            _svcat_rerender(chat_id, edit_id, _svcat_cb(idx, "root"))
            return

        elif state == "wait_for_add_wm" and text:
            bot_settings["w_methods"].append(text.strip())
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("💳 <b>WITHDRAWAL METHODS</b>\n\nManage your withdrawal methods below:"), reply_markup=w_methods_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_fj" and text:
            bot_settings["fj_channels"].append(parse_chat_id(text))
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("🔗 <b>FORCE JOIN SYSTEM</b>\nManage channels below:\n<i>(Note: For private links, use numeric IDs like -100...)</i>"), reply_markup=fj_settings_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return
            
        elif state == "wait_for_add_adm" and text:
            if text.isdigit():
                bot_settings["admins"].append(int(text))
                save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("👥 <b>ADMIN MANAGEMENT</b>\nManage your bot admins below:"), reply_markup=admin_settings_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_add_fw_id" and text:
            bot_settings["fw_groups"].append({"chat_id": text.strip(), "buttons": []})
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("🛡 <b>OTP GROUP MANAGEMENT</b>\nManage settings below:"), reply_markup=otp_groups_list_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return
            
        elif state == "wait_for_add_fw_btn" and text:
            fw_idx = temp_data[chat_id]["fw_idx"]
            if "-" in text:
                parts = text.split("-", 1)
                btn_text = parts[0].strip()
                btn_url = parts[1].strip()
                
                emoji_id = None
                emoji_char = ""
                for ent in msg.get("entities", []):
                    if ent.get("type") == "custom_emoji":
                        emoji_id = ent.get("custom_emoji_id")
                        offset = ent.get("offset", 0)
                        length = ent.get("length", 0)
                        b_text = text.encode('utf-16-le')
                        emoji_char = b_text[offset*2:(offset+length)*2].decode('utf-16-le')
                        break
                
                if emoji_char:
                    btn_text = btn_text.replace(emoji_char, "").strip()
                    
                btn_data = {"text": btn_text, "url": btn_url}
                if emoji_id:
                    btn_data["icon_custom_emoji_id"] = emoji_id
                    
                bot_settings["fw_groups"][fw_idx]["buttons"].append(btn_data)
                save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(f"🛡 <b>Manage Group:</b> {bot_settings['fw_groups'][fw_idx]['chat_id']}"), reply_markup=specific_fw_group_keyboard(fw_idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return
            
        elif state == "wait_for_otp_link" and text:
            bot_settings["otp_link"] = text.strip()
            save_db()
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text("🛡 <b>OTP GROUP MANAGEMENT</b>\nManage settings below:"), reply_markup=otp_groups_list_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_panel_name" and text:
            p_name = text.strip()
            t_key = temp_data[chat_id].get("add_type", "api")
            msg_id = temp_data[chat_id]["msg_id"]
            delete_message(chat_id, msg["message_id"])
            
            if t_key == "logc":
                user_states[chat_id] = "wait_for_cpanel_url"
                temp_data[chat_id] = {"msg_id": msg_id, "p_data": {
                    "name": p_name, "type": "Auto Captcha Panel", "status": "ON", "records": 0, "login_status": "⏳ Pending First Login"
                }}
                edit_message(chat_id, msg_id, render_body_text("1️⃣ <b>Login URL</b>\n➡️ Panel এর Login Link দিন:"), reply_markup=get_cancel_kb())
                return
            elif t_key == "json":
                bot_settings["panels"].append(new_json_panel(p_name))
                save_db()
                new_idx = len(bot_settings["panels"]) - 1
                user_states[chat_id] = "wait_for_j_url"
                temp_data[chat_id] = {"msg_id": msg_id, "p_idx": new_idx}
                edit_message(chat_id, msg_id, render_body_text(JSON_FIELD_PROMPTS["wait_for_j_url"]), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "conf_pnl_" + str(new_idx), "style": "danger"}]]})
                return
            else:
                bot_settings["panels"].append({
                    "name": p_name, "type": "API Panel", "status": "OFF", "api_url": "", "token": "", "records": 0
                })
                save_db()
                handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "manage_api_panels", "id": "internal"})
                if chat_id in user_states: del user_states[chat_id]
                if chat_id in temp_data: del temp_data[chat_id]
                return

        elif state == "wait_for_p_api" and text:
            idx = temp_data[chat_id]["p_idx"]
            bot_settings["panels"][idx]["api_url"] = text.strip()
            save_db()
            delete_message(chat_id, msg["message_id"])
            p = bot_settings["panels"][idx]
            ui_text = _panel_config_text(p)
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(ui_text), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_p_tok" and text:
            idx = temp_data[chat_id]["p_idx"]
            bot_settings["panels"][idx]["token"] = text.strip()
            save_db()
            delete_message(chat_id, msg["message_id"])
            p = bot_settings["panels"][idx]
            ui_text = _panel_config_text(p)
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(ui_text), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_p_fapi" and text:
            idx = temp_data[chat_id]["p_idx"]
            bot_settings["panels"][idx]["full_api_url"] = text.strip()
            save_db()
            delete_message(chat_id, msg["message_id"])
            p = bot_settings["panels"][idx]
            ui_text = _panel_config_text(p)
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(ui_text), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_p_rec" and text:
            if text.isdigit():
                idx = temp_data[chat_id]["p_idx"]
                bot_settings["panels"][idx]["records"] = int(text)
                save_db()
                delete_message(chat_id, msg["message_id"])
                p = bot_settings["panels"][idx]
                
                ui_text = _panel_config_text(p)
                edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(ui_text), reply_markup=panel_config_keyboard(idx))
            else:
                send_message(chat_id, render_body_text("❌ Please enter a valid number! Try again."), reply_markup=get_cancel_kb())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_j_charge" and text:
            idx = temp_data[chat_id].get("p_idx")
            raw = text.strip().replace("tk", "").replace("TK", "").strip()
            try:
                value = float(raw)
                ok = 0 <= value <= 1000
            except ValueError:
                ok = False
                value = 0.0
            if not ok:
                send_message(chat_id, render_body_text("❌ 0 থেকে 1000 এর মধ্যে একটা সংখ্যা দাও (0 = free)।"), reply_markup=get_cancel_kb())
                return
            if isinstance(idx, int) and 0 <= idx < len(bot_settings["panels"]):
                bot_settings["panels"][idx]["num_charge_tk"] = round(value, 2)
                save_db()
                delete_message(chat_id, msg["message_id"])
                p = bot_settings["panels"][idx]
                edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_j_hold" and text:
            idx = temp_data[chat_id].get("p_idx")
            if not text.strip().isdigit() or not (1 <= int(text.strip()) <= 180):
                send_message(chat_id, render_body_text("❌ 1 থেকে 180 এর মধ্যে একটা সংখ্যা দাও।"), reply_markup=get_cancel_kb())
                return
            if isinstance(idx, int) and 0 <= idx < len(bot_settings["panels"]):
                bot_settings["panels"][idx]["hold_minutes"] = int(text.strip())
                save_db()
                delete_message(chat_id, msg["message_id"])
                p = bot_settings["panels"][idx]
                edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_j_preset_token" and text:
            preset = JSON_PANEL_PRESETS.get(temp_data[chat_id].get("preset", ""))
            token = text.strip()
            if not preset or not token:
                send_message(chat_id, render_body_text("❌ Invalid input! আবার পাঠান।"), reply_markup=get_cancel_kb())
                return
            panel = new_json_panel(preset["label"])
            panel.update(preset["config"])
            panel["token"] = token
            _json_panel_uid(panel)
            bot_settings["panels"].append(panel)
            save_db()
            idx = len(bot_settings["panels"]) - 1
            delete_message(chat_id, msg["message_id"])
            edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(_panel_config_text(panel)), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state in JSON_STATE_FIELDS and text:
            idx = temp_data[chat_id].get("p_idx")
            field_key = JSON_STATE_FIELDS[state]
            value = text.strip()
            ok = True

            if state == "wait_for_j_method":
                value = value.upper()
                if value not in ("GET", "POST"):
                    ok = False
            elif state == "wait_for_j_auth":
                value = _normalize_json_auth(value) or ""
                if not value:
                    ok = False
            elif state in ("wait_for_j_path", "wait_for_j_numf", "wait_for_j_msgf", "wait_for_j_otpf"):
                if value.lower() in ("auto", "-", "none", "skip", "0", "no"):
                    value = ""
            elif state == "wait_for_j_url":
                if not value.lower().startswith("http") and "." not in value:
                    ok = False
                elif not value.lower().startswith("http"):
                    value = "http://" + value

            if not ok:
                send_message(chat_id, render_body_text("❌ Invalid value! আবার চেষ্টা করুন।"), reply_markup=get_cancel_kb())
                return

            if isinstance(idx, int) and 0 <= idx < len(bot_settings["panels"]):
                bot_settings["panels"][idx][field_key] = value
                save_db()
                delete_message(chat_id, msg["message_id"])
                p = bot_settings["panels"][idx]
                edit_message(chat_id, temp_data[chat_id]["msg_id"], render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "set_ariyan":
            msg_id = temp_data[chat_id]["msg_id"]
            key = temp_data[chat_id]["key"]
            try:
                if key in ["min_withdraw", "otp_reward", "refer_reward"]: bot_settings[key] = float(text)
                elif key in ["cooldown", "num_req", "num_share"]: bot_settings[key] = int(text)
                else: bot_settings[key] = text
                save_db()
                delete_message(chat_id, msg["message_id"])
                edit_message(chat_id, msg_id, render_body_text("🕹 <b>Ariyan Control Panel</b>"), reply_markup=ariyan_control_keyboard())
            except:
                delete_message(chat_id, msg["message_id"])
                edit_message(chat_id, msg_id, render_body_text("🕹 <b>Ariyan Control Panel</b>\n\n❌ Invalid value!"), reply_markup=ariyan_control_keyboard())
            del user_states[chat_id]
            del temp_data[chat_id]
            return

        elif state == "wait_for_search" and text:
            query = text.strip().replace("+", "")
            if not query.isdigit() or len(query) < 3 or len(query) > 9:
                send_message(chat_id, render_body_text("❌ Please enter a valid 3 to 9 digit number!"))
                return
                
            wait_msg = send_message(chat_id, render_body_text("⌛ <i>Processing... Finding Number...</i>"))
            wait_msg_id = wait_msg.get("result", {}).get("message_id")
            
            # 🌟 ১. প্রথমে Local থেকে নাম্বার খুঁজবে (যে কোনো দেশের জন্য)
            found_indices = []
            for b_id, b_data in number_batches.items():
                for idx, n_obj in enumerate(b_data["numbers"]):
                    if n_obj["num"].replace("+", "").startswith(query) and chat_id not in n_obj.get("used_by", []):
                        found_indices.append((b_id, idx))
            
            fetched_nums = []
            if not found_indices:
                # 🌟 ২. যদি Local এ না পায়, তখন চেক করবে Voltx বা StexSMS থেকে আনা যাবে কি না
                stex_allowed = bot_settings.get("search_countries", [])
                voltx_allowed = bot_settings.get("voltx_search_countries", [])
                
                # ফিক্স: অ্যাডমিন প্যানেলে দেশ এড না থাকলে অটোমেটিক Block করে দেবে
                is_stex_allowed = any(query.startswith(c) for c in stex_allowed) if stex_allowed else False
                is_voltx_allowed = any(query.startswith(c) for c in voltx_allowed) if voltx_allowed else False
                
                if not is_stex_allowed and not is_voltx_allowed:
                    if wait_msg_id: delete_message(chat_id, wait_msg_id)
                    send_message(chat_id, render_body_text("❌ This country code is not allowed!"), reply_markup=main_menu(chat_id))
                    del user_states[chat_id]
                    return
                    
                if wait_msg_id: edit_message(chat_id, wait_msg_id, render_body_text("⌛ <i>Processing... Finding Number via API...</i>"))
                
                is_voltx_used = False
                req_count = bot_settings.get("num_req", 1)
                
                # 🌟 প্রথমে Voltx চেক করবে
                if is_voltx_allowed:
                    voltx_keys = bot_settings.get("voltx_keys", [])
                    for _ in range(req_count):
                        if len(fetched_nums) >= req_count: break
                        for api_key in voltx_keys:
                            num_str = _legacy_panel_get_number("voltx", api_key, query)
                            if not num_str:
                                continue
                            fetched_nums.append(num_str)
                            voltx_assigned_numbers[num_str] = chat_id
                            is_voltx_used = True
                            global total_assigned_stats
                            total_assigned_stats += 1
                            break # শুধু api_key লুপ ব্রেক করবে, যাতে পরের নাম্বার আনতে পারে

                # 🌟 Voltx এ না পেলে বা আরও নাম্বার লাগলে StexSMS তে চেক করবে
                if len(fetched_nums) < req_count and is_stex_allowed:
                    stex_keys = bot_settings.get("stex_keys", [])
                    
                    for _ in range(req_count - len(fetched_nums)): 
                        for api_key in stex_keys:
                            num_str = _legacy_panel_get_number("stex", api_key, query)
                            if not num_str:
                                continue
                            fetched_nums.append(num_str)
                            stex_assigned_numbers[num_str] = chat_id
                            total_assigned_stats += 1
                            break
                        
                if not fetched_nums:
                    if wait_msg_id: delete_message(chat_id, wait_msg_id)
                    send_message(chat_id, render_body_text("❌ Number out of stock!"), reply_markup=main_menu(chat_id))
                    del user_states[chat_id]
                    return
                save_db()
            else:
                random.shuffle(found_indices)
                for b_id, idx in found_indices:
                    if len(fetched_nums) >= bot_settings.get("num_req", 1): break
                    n_obj = number_batches[b_id]["numbers"][idx]
                    num_str = n_obj["num"]
                    
                    fetched_nums.append(num_str)
                    
                    n_obj["shares"] += 1
                    n_obj["used_by"].append(chat_id)
                    total_assigned_stats += 1
                    
                    if n_obj["shares"] >= bot_settings.get("num_share", 1):
                        n_obj["to_remove"] = True
                        used_numbers_list.append(num_str)
                
                for b_id in number_batches:
                    number_batches[b_id]["numbers"] = [n for n in number_batches[b_id]["numbers"] if not n.get("to_remove")]
                save_db()
                
            kb = []
            flags_db = bot_settings.get("premium_flags", {})
            num_lines = []
            show_cc = bool(number_display_preferences.get(chat_id, True))
            for num in fetched_nums:
                _, iso = get_flag_and_code(num)
                display_num = _display_api_number(num, show_cc=show_cc)
                flag_html = get_flag_info_html(display_num)
                num_lines.append(f"{flag_html} <code>{display_num}</code>")
                emoji_id = "5780471598922337683"
                for flag_code, flag_data in flags_db.items():
                    if iso == flag_data.get("iso"):
                        if "id" in flag_data: emoji_id = flag_data["id"]
                        break
                kb.append([_number_copy_button(display_num, query)])

            vtx_ext = "_vtx" if 'is_voltx_used' in locals() and is_voltx_used else ""

            kb.append([{
                "text": "Remove CC" if show_cc else "Add CC",
                "icon_custom_emoji_id": "5422557736330106570" if show_cc else "5420396762189831222",
                "callback_data": "toggle_classic_cc",
                "style": "danger" if show_cc else "success",
            }])
            kb.append([{
                "text": "Change Number",
                "icon_custom_emoji_id": "5465368548702446780",
                "callback_data": f"c_n_s_{query}{vtx_ext}",
                "style": "success",
            }])
            kb.append([{
                "text": "Change Country",
                "icon_custom_emoji_id": "5336972142066047577",
                "callback_data": "get_number_menu",
                "style": "primary",
            }])
            kb.append([_otp_group_button()])

            c_btns = bot_settings["custom_messages"].get("search_number", {}).get("buttons", [])
            for c_b in c_btns:
                b_copy = c_b.copy()
                if "style" not in b_copy: b_copy["style"] = "primary"
                kb.append([b_copy])

            num_text = _imran_number_result_text(num_lines, numbers=fetched_nums)
            if wait_msg_id:
                edit_message(chat_id, wait_msg_id, num_text, reply_markup={"inline_keyboard": kb})
                user_active_sessions[chat_id] = {
                    "msg_id": wait_msg_id,
                    "nums": fetched_nums,
                    "show_cc": show_cc,
                    "service": query,
                    "country_callback": "get_number_menu",
                    "change_callback": f"c_n_s_{query}{vtx_ext}",
                }
            else:
                msg_res = send_message(chat_id, num_text, reply_markup={"inline_keyboard": kb})
                if msg_res and "result" in msg_res:
                    user_active_sessions[chat_id] = {
                        "msg_id": msg_res["result"]["message_id"],
                        "nums": fetched_nums,
                        "show_cc": show_cc,
                        "service": query,
                        "country_callback": "get_number_menu",
                        "change_callback": f"c_n_s_{query}{vtx_ext}",
                    }
            return
            
        elif state == "wait_for_withdraw_amount" and text:
            msg_id_to_edit = temp_data[chat_id].get("msg_id")
            try:
                amount = float(text.strip())
                bal = temp_data[chat_id]["balance"]
                min_w = bot_settings['min_withdraw']
                
                if amount < min_w:
                    if msg_id_to_edit: edit_message(chat_id, msg_id_to_edit, render_body_text(f"❌ Minimum withdrawal is {min_w} ৳!\n💰 Balance: {bal} ৳\n\n📝 Enter again:"), reply_markup=get_cancel_kb())
                    return
                if amount > bal:
                    if msg_id_to_edit: edit_message(chat_id, msg_id_to_edit, render_body_text(f"❌ You don't have enough balance!\n💰 Balance: {bal} ৳\n\n📝 Enter again:"), reply_markup=get_cancel_kb())
                    return
                    
                temp_data[chat_id]["amount"] = amount
                user_states[chat_id] = "wait_for_withdraw_number"
                if msg_id_to_edit:
                    edit_message(chat_id, msg_id_to_edit, render_body_text(f"✅ Amount: {amount} ৳\n\n📱 Now send your <b>{temp_data[chat_id]['method']}</b> account number:"), reply_markup=get_cancel_kb())
            except ValueError:
                if msg_id_to_edit: edit_message(chat_id, msg_id_to_edit, render_body_text("❌ Invalid amount!\n\n📝 Please send a valid number:"), reply_markup=get_cancel_kb())
            return
            
        elif state == "wait_for_2fa_key" and text:
            msg_id_to_edit = temp_data.get(chat_id, {}).get("msg_id")
            delete_message(chat_id, msg.get("message_id")) # ইউজারের মেসেজ ডিলিট

            if not msg_id_to_edit:
                send_message(chat_id, render_body_text("❌ Error: Message not found. Try again."))
                del user_states[chat_id]
                return

            try:
                secret = text.strip().replace(" ", "")
                totp = pyotp.TOTP(secret)
                code = totp.now()
                remaining_time = 30 - (int(time.time()) % 30)
                
                success_txt = (
                    f"━━━━━━━━━━━━━━━\n"
                    f"《 🔐 <b>2FA CODE</b> 》\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🔐 <b>CODE:</b> <code>{code}</code>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🕓 <b>EXPIRES IN:</b> {remaining_time}s\n"
                    f"━━━━━━━━━━━━━━━"
                )
                kb = [[{"text": f"Click to copy {code}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": code}, "style": "success"}],
                      [{"text": "Refresh", "icon_custom_emoji_id": "5420155432272438703", "callback_data": f"ref_2fa_{secret}", "style": "primary"},
                       {"text": "New Code", "icon_custom_emoji_id": "5352552689983067014", "callback_data": "gen_2fa", "style": "danger"}],
                      [{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}]]
                
                edit_message(chat_id, msg_id_to_edit, render_body_text(success_txt), reply_markup={"inline_keyboard": kb})
                del user_states[chat_id]
                if chat_id in temp_data: del temp_data[chat_id]
            except Exception:
                error_txt = "━━━━━━━━━━━━━━━\n《 🔑 <b>ENTER 2FA KEY</b> 》\n━━━━━━━━━━━━━━━\n📝 <b>SEND YOUR 2FA SECRET KEY</b>\n━━━━━━━━━━━━━━━\n❌ <b>Invalid Secret Key! Try again.</b>\n━━━━━━━━━━━━━━━"
                cancel_kb = {"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "cancel_2fa", "style": "danger"}]]}
                edit_message(chat_id, msg_id_to_edit, render_body_text(error_txt), reply_markup=cancel_kb)
            return

        elif state == "wait_for_withdraw_number":
            msg_id_to_edit = temp_data[chat_id].get("msg_id")
            
            method = temp_data[chat_id]["method"]
            amount = temp_data[chat_id]["amount"]
            number = text
            req_id = f"W_{str(uuid.uuid4())[:6].upper()}"
            
            first_name = msg.get("from", {}).get("first_name", "User")
            last_name = msg.get("from", {}).get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            
            update_balance(chat_id, -amount)
            pending_withdrawals[req_id] = {"user_id": chat_id, "amount": amount, "method": method, "number": number, "full_name": full_name}
            
            # Save to Local JSON DB for History
            if db:
                try:
                    db.collection('withdrawals').document(req_id).set({
                        "user_id": str(chat_id),
                        "amount": amount,
                        "method": method,
                        "status": "pending",
                        "timestamp": LOCAL_SERVER_TIMESTAMP
                    })
                except: pass
                
            if bot_settings["w_group"]:
                admin_msg = f"🎙 <b>NEW WITHDRAWAL REQUEST</b>\n\n👤 <b>USER:</b> <a href='tg://user?id={chat_id}'>{full_name}</a>\n💳 <b>WITHDRAWAL:</b> {amount} TK\n🍏 <b>NUMBER:</b> <code>{number}</code>\n🏦 <b>METHOD:</b> {method}\n\n🧾 <b>REQ ID:</b> {req_id}\n👨‍⚖️ <b>PROCESSED BY ADMIN</b>"
                kb = {"inline_keyboard": [[{"text": "APPROVE", "icon_custom_emoji_id": "5352694861990501856", "callback_data": f"wapp_{req_id}", "style": "success"}, {"text": "REJECT", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"wrej_{req_id}", "style": "danger"}]]}
                send_message(bot_settings["w_group"], render_body_text(admin_msg), reply_markup=kb)
            
            kb = {"inline_keyboard": [[{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}]]}
            success_text = f"{PEM['ok']} Your withdrawal request has been submitted!\n\n🧾 <b>Req ID:</b> {req_id}\n💰 <b>Amount:</b> {amount} ৳\n🏦 <b>Method:</b> {method}\n📱 <b>Number:</b> <code>{number}</code>"
            
            if msg_id_to_edit:
                edit_message(chat_id, msg_id_to_edit, render_body_text(success_text), reply_markup=kb)
            else:
                send_message(chat_id, render_body_text(success_text), reply_markup=kb)
                
            del user_states[chat_id]
            del temp_data[chat_id]
            return

    # --- Regular Commands ---
    if text.startswith("/start"):
        get_user(chat_id)
        
        # --- PROCESS PENDING REFERRAL ---
        if db:
            doc = db.collection('users').document(str(chat_id)).get()
            if doc.exists:
                u_data = doc.to_dict()
                if u_data.get("referred_by") and not u_data.get("ref_paid"):
                    inviter = u_data["referred_by"]
                    db.collection('users').document(str(chat_id)).update({"ref_paid": True})
                    reward = bot_settings.get("refer_reward", 0.2)
                    update_balance(inviter, reward)
                    db.collection('users').document(str(inviter)).update({"total_refers": local_increment(1)})
                    ref_msg = (
                        f"{PEM['gift']} <b>New Referral !</b>\n"
                        f"------------------\n"
                        f"🔥 <b>You Received {reward} TK</b>\n"
                        f"------------------\n"
                        f"{PEM['user']} <b>From User ID:</b> <code>{chat_id}</code>"
                    )
                    send_message(inviter, render_body_text(ref_msg))
                    
        c_msg = bot_settings["custom_messages"].get("start", {})
        txt = render_body_text(c_msg.get("text", f"{PEM['hi']} Welcome!"))
        kb = []
        for b in c_msg.get("buttons", []):
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
        
        if kb:
            send_message(chat_id, txt, reply_markup={"inline_keyboard": kb})
            send_message(chat_id, render_body_text(f"{PEM['gear']} Navigation Menu:"), reply_markup=main_menu(chat_id))
        else:
            send_message(chat_id, txt, reply_markup=main_menu(chat_id))
            
    elif text == "TRAFFIC":
        txt, markup = build_traffic_ui()
        send_message(chat_id, txt, reply_markup=markup)
        
    elif text == "Refer":
        u_data = get_user(chat_id)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={chat_id}"
        c_msg = bot_settings["custom_messages"].get("refer", {})
        
        raw_txt = c_msg.get("text", f"{PEM['gift']} Refer").replace("{ref_link}", ref_link).replace("{total_ref}", str(u_data.get('total_refers', 0))).replace("{ref_reward}", str(bot_settings['refer_reward']))
        txt = render_body_text(raw_txt)
        
        kb = [[{"text": "COPY LINK", "icon_custom_emoji_id": "5192739271886282680", "copy_text": {"text": ref_link}, "style": "success"}]]
        for b in c_msg.get("buttons", []): 
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
        kb.append([b_copy])
        kb.append([{"text": "CLOSE", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
        
        send_message(chat_id, txt, reply_markup={"inline_keyboard": kb})

    elif text == "WITHDRAWAL":
        if not bot_settings["withdraw_on"]:
            send_message(chat_id, render_body_text(f"{PEM['no']} Withdrawals are currently disabled."))
            return
        
        u_data = get_user(chat_id)
        bal = u_data.get('balance', 0.0)
        
        c_msg = bot_settings["custom_messages"].get("withdrawal", {})
        raw_txt = c_msg.get("text", "Withdrawal").replace("{bal}", str(bal)).replace("{total_otp}", str(u_data.get('total_otps', 0))).replace("{total_ref}", str(u_data.get('total_refers', 0))).replace("{min_w}", str(bot_settings['min_withdraw']))
        txt = render_body_text(raw_txt)
        
        kb = []
        for m in bot_settings["w_methods"]:
            kb.append([{"text": m.strip(), "icon_custom_emoji_id": "5190899075968441286", "callback_data": f"sel_wm_{m.strip()}", "style": "primary"}])
        
        for b in c_msg.get("buttons", []): 
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
        kb.append([{"text": "Cancel", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
        send_message(chat_id, txt, reply_markup={"inline_keyboard": kb})

    elif text == "Admin Panel" and is_admin(chat_id):
        send_message(chat_id, get_admin_text(chat_id), reply_markup=admin_panel_keyboard())

    elif text == "GET NUMBER":
        number_catalog = _unified_number_catalog()
        all_services = list(number_catalog.values())
        
        if not all_services:
            send_message(chat_id, render_body_text(f"{PEM['no']} No numbers or services available!"))
        else:
            c_msg = bot_settings["custom_messages"].get("get_number", {})
            txt = render_body_text(c_msg.get("text", f"{PEM['pin']} Select Service"))
            
            apps_db = bot_settings.get("premium_apps", {})
            kb = []
            for service_entry in sorted(all_services, key=lambda item: item["label"].casefold()):
                s = service_entry["label"]
                emoji_id = "5352694861990501856" # Default icon
                for app_key, app_data in apps_db.items():
                    if s.upper() == app_key or s.upper() in app_key or app_key in s.upper():
                        if "id" in app_data:
                            emoji_id = app_data["id"]
                            break
                kb.append([{
                    "text": f"{s}",
                    "icon_custom_emoji_id": emoji_id,
                    "callback_data": _number_choice_callback("service", s),
                    "style": "primary",
                }])
            
            for b in c_msg.get("buttons", []): 
                b_copy = b.copy()
                if "style" not in b_copy: b_copy["style"] = "primary"
                kb.append([b_copy])
            kb.append([{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
            
            send_message(chat_id, txt, reply_markup={"inline_keyboard": kb})

    elif text == "Search Number":
        user_states[chat_id] = "wait_for_search"
        c_msg = bot_settings["custom_messages"].get("search_number", {})
        txt = render_body_text(c_msg.get("text", f"{PEM['num']} Search Number"))
        kb = [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "cancel_state", "style": "danger"}]]
        for b in c_msg.get("buttons", []): 
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
        send_message(chat_id, txt, reply_markup={"inline_keyboard": kb})

    elif text == "2FA ONLINE" or text == "🔐 2FA ONLINE":
        txt = "━━━━━━━━━━━━━━━\n《 🔐 <b>2FA ONLINE</b> 》\n━━━━━━━━━━━━━━━\n<i>Generate your 2FA security code instantly using your secret key.</i>\n━━━━━━━━━━━━━━━"
        kb = [[{"text": "Generate 2fa code", "icon_custom_emoji_id": "5353022963132174959", "callback_data": "gen_2fa", "style": "success"}]]
        kb.append([{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
        send_message(chat_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif text == "SUPPORT":
        c_msg = bot_settings["custom_messages"].get("support", {})
        txt = render_body_text(c_msg.get("text", f"{PEM['msg']} Support"))
        if not txt.strip(): txt = render_body_text(f"{PEM['msg']} Support")
        kb = []
        for b in c_msg.get("buttons", []):
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
            
        append_support_button_rows(kb)
        kb.append([{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
        send_message(chat_id, txt, reply_markup={"inline_keyboard": kb} if kb else None)

def expire_previous_number(chat_id):
    if chat_id in user_active_sessions:
        prev_data = user_active_sessions[chat_id]
        prev_msg_id = prev_data["msg_id"]
        nums = prev_data["nums"]
        
        # API assignment maps থেকে remove করা যাতে expired number-এর OTP
        # আর user-এর inbox-এ না যায়।
        for num in nums:
            if num in stex_assigned_numbers:
                del stex_assigned_numbers[num]
            if num in voltx_assigned_numbers:
                del voltx_assigned_numbers[num]
        save_db()
        
        # আগের মেসেজ ইডিট করে Expired বাটন বসানো
        kb = [[{"text": "Number Expired", "icon_custom_emoji_id": "5336997731481193790", "callback_data": "ignore", "style": "danger"}]]
        try:
            edit_message(chat_id, prev_msg_id, "ㅤ\n", reply_markup={"inline_keyboard": kb})
        except:
            pass
        del user_active_sessions[chat_id]
    # A unified GET NUMBER request may also have allocated an NP/MK number.
    # Remove that session when the user's active number is replaced.
    with api_session_lock:
        api_number_sessions.pop(chat_id, None)

# ==========================================
# Callback Query Handler
# ==========================================
def handle_callback(call):
    global total_assigned_stats
    chat_id = call["message"]["chat"]["id"]
    chat_type = call["message"]["chat"].get("type", "private")
    data = call.get("data", "")

    # 🌟 Button Loading Fix: বাটন চাপার সাথে সাথেই টেলিগ্রামকে Response দিয়ে দেওয়া, যাতে বাটন আটকে না থাকে!
    if (
        not data.startswith("test_p_conn_")
        and not data.startswith("c_n_")
        and not data.startswith("g_c_")
        and not data.startswith("copy_otp:")
    ):
        try: threading.Thread(target=answer_callback, args=(call["id"],)).start()
        except: pass

    if data.startswith("copy_otp:"):
        encoded = data.split(":", 1)[1]
        try:
            padded = encoded + ("=" * (-len(encoded) % 4))
            otp_text = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        except Exception:
            otp_text = ""
        answer_callback(
            call["id"],
            f"OTP: {otp_text}" if otp_text else "OTP unavailable",
            show_alert=True,
        )
        return

    if chat_type != "private" and not (
        data.startswith("wapp_")
        or data.startswith("wrej_")
        or data.startswith("api_getnum:")
    ):
        return

    msg_id = call["message"]["message_id"]

    if chat_type == "private":
        if is_user_banned(chat_id):
            answer_callback(call["id"], "🚫 You are banned from using this bot!", show_alert=True)
            return

        if not check_force_join(chat_id) and data != "check_fj":
            send_force_join_msg(chat_id)
            return

    if data == "check_fj":
        if check_force_join(chat_id):
            delete_message(chat_id, msg_id)
            send_message(chat_id, render_body_text(f"{PEM['ok']} Thanks for joining! You can now use the bot."), reply_markup=main_menu(chat_id))
            
            # --- PROCESS PENDING REFERRAL ---
            if db:
                doc = db.collection('users').document(str(chat_id)).get()
                if doc.exists:
                    u_data = doc.to_dict()
                    if u_data.get("referred_by") and not u_data.get("ref_paid"):
                        inviter = u_data["referred_by"]
                        db.collection('users').document(str(chat_id)).update({"ref_paid": True})
                        reward = bot_settings.get("refer_reward", 0.2)
                        update_balance(inviter, reward)
                        db.collection('users').document(str(inviter)).update({"total_refers": local_increment(1)})
                        ref_msg = (
                            f"{PEM['gift']} <b>New Referral !</b>\n"
                            f"------------------\n"
                            f"🔥 <b>You Received {reward} TK</b>\n"
                            f"------------------\n"
                            f"{PEM['user']} <b>From User ID:</b> <code>{chat_id}</code>"
                        )
                        send_message(inviter, render_body_text(ref_msg))
            pending_token = pending_group_getnum.pop(chat_id, "")
            if pending_token:
                _process_group_get_number_token(chat_id, pending_token)
        else:
            answer_callback(call["id"], "❌ You haven't joined all channels yet!", show_alert=True)
        return

    if data == "close_msg":
        delete_message(chat_id, msg_id)
        
    elif data == "get_number_menu":
        # "Change Country" → একীভূত service selector দেখাও।
        number_catalog = _unified_number_catalog()
        all_services = list(number_catalog.values())
        if not all_services:
            answer_callback(call["id"], "❌ No services available!", show_alert=True)
            return
        c_msg = bot_settings["custom_messages"].get("get_number", {})
        txt = render_body_text(c_msg.get("text", f"{PEM['pin']} Select Service"))
        apps_db = bot_settings.get("premium_apps", {})
        kb = []
        for service_entry in sorted(all_services, key=lambda item: item["label"].casefold()):
            s = service_entry["label"]
            emoji_id = "5352694861990501856"
            for app_key, app_data in apps_db.items():
                if s.upper() == app_key or s.upper() in app_key or app_key in s.upper():
                    if "id" in app_data: emoji_id = app_data["id"]; break
            kb.append([{
                "text": f"{s}",
                "icon_custom_emoji_id": emoji_id,
                "callback_data": _number_choice_callback("service", s),
                "style": "primary",
            }])
        kb.append([{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}])
        edit_message(chat_id, msg_id, txt, reply_markup={"inline_keyboard": kb})
        answer_callback(call["id"])

    elif data == "cancel_state":
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        delete_message(chat_id, msg_id)

    elif data == "cancel_2fa":
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        txt = "━━━━━━━━━━━━━━━\n《 🔐 <b>2FA ONLINE</b> 》\n━━━━━━━━━━━━━━━\n<i>Generate your 2FA security code instantly using your secret key.</i>\n━━━━━━━━━━━━━━━"
        kb = [[{"text": "Generate 2fa code", "icon_custom_emoji_id": "5353022963132174959", "callback_data": "gen_2fa", "style": "success"}],
              [{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}]]
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})
        answer_callback(call["id"])

    elif data == "gen_2fa":
        user_states[chat_id] = "wait_for_2fa_key"
        temp_data[chat_id] = {"msg_id": msg_id}
        txt = "━━━━━━━━━━━━━━━\n《 🔑 <b>ENTER 2FA KEY</b> 》\n━━━━━━━━━━━━━━━\n📝 <b>SEND YOUR 2FA SECRET KEY</b>\n━━━━━━━━━━━━━━━"
        kb = {"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "cancel_2fa", "style": "danger"}]]}
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup=kb)
        answer_callback(call["id"])

    elif data.startswith("ref_2fa_"):
        secret = data.replace("ref_2fa_", "")
        try:
            totp = pyotp.TOTP(secret)
            code = totp.now()
            remaining_time = 30 - (int(time.time()) % 30)
            
            success_txt = (
                f"━━━━━━━━━━━━━━━\n"
                f"《 🔐 <b>2FA CODE</b> 》\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🔐 <b>CODE:</b> <code>{code}</code>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🕓 <b>EXPIRES IN:</b> {remaining_time}s\n"
                f"━━━━━━━━━━━━━━━"
            )
            kb = [[{"text": f"Click to copy {code}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": code}, "style": "success"}],
                  [{"text": "Refresh", "icon_custom_emoji_id": "5420155432272438703", "callback_data": f"ref_2fa_{secret}", "style": "primary"},
                   {"text": "New Code", "icon_custom_emoji_id": "5352552689983067014", "callback_data": "gen_2fa", "style": "danger"}],
                  [{"text": "Close", "icon_custom_emoji_id": "5420130255174145507", "callback_data": "close_msg", "style": "danger"}]]
            
            edit_message(chat_id, msg_id, render_body_text(success_txt), reply_markup={"inline_keyboard": kb})
        except:
            answer_callback(call["id"], "❌ Error refreshing code!", show_alert=True)

    elif data == "cancel_ariyan_edit":
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        edit_message(chat_id, msg_id, render_body_text("🕹 <b>Ariyan Control Panel</b>"), reply_markup=ariyan_control_keyboard())
        
    elif data == "dummy_alert":
        answer_callback(call["id"], "This feature will be added later!", show_alert=True)
        
    elif data == "refresh_traffic":
        txt, markup = build_traffic_ui()
        edit_message(chat_id, msg_id, txt, reply_markup=markup)
        answer_callback(call["id"], "✅ Traffic Refreshed!", show_alert=False)

    elif data == "traffic_main_menu":
        edit_message(chat_id, msg_id, render_body_text("🏠 <b>MAIN MENU</b>"))
        send_message(chat_id, render_body_text("✅ Main menu restored."), reply_markup=main_menu(chat_id))
        answer_callback(call["id"])

    elif data.startswith("exp_rng_"): 
        srv_query = data.replace("exp_rng_", "")
        
        country_stats = {}
        current_time = time.time()
        for t in recent_traffic:
            if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS:
                if t.get("service", "").startswith(srv_query):
                    iso = t.get("iso", "XX")
                    flag = t.get("flag", "🌍")
                    if iso not in country_stats:
                        country_stats[iso] = {"count": 0, "flag": flag}
                    country_stats[iso]["count"] += 1
        
        if not country_stats:
            answer_callback(call["id"], "❌ No recent traffic found for this service!", show_alert=True)
            return
            
        kb = []
        for iso, c_data in sorted(country_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            count = c_data["count"]
            country_info = _premium_flag_for_label(iso) or {}
            c_name = country_info.get("name") or DEFAULT_COUNTRY_NAMES.get(iso, iso)
            emoji_id = str(country_info.get("id", "") or "5780471598922337683")
            btn_text = f"{c_name} ({iso}) - {count} OTP"
            kb.append([{"text": btn_text, "icon_custom_emoji_id": emoji_id, "callback_data": f"exp_c_{srv_query}_{iso}", "style": "primary"}])
            
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "refresh_traffic", "style": "danger"}])
        
        app_full_name, prem_app_html = get_service_info_html(srv_query)
        edit_message(chat_id, msg_id, render_body_text(f"📊 <b>Explore Service: {prem_app_html} {app_full_name}</b>\n\nSelect a country to view available ranges:"), reply_markup={"inline_keyboard": kb})
        answer_callback(call["id"])

    elif data.startswith("exp_c_"):
        parts = data.split("_")
        srv_query = parts[2]
        iso_query = parts[3]
        
        nums = []
        current_time = time.time()
        for t in recent_traffic:
            if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS:
                if t.get("service", "").startswith(srv_query) and t.get("iso") == iso_query:
                    num = t.get("number", "").replace("+", "").strip()
                    if num: nums.append(num)
        
        if not nums:
            answer_callback(call["id"], "❌ No recent numbers found for this country!", show_alert=True)
            return
            
        # শুধুমাত্র StexSMS Services থেকে রেঞ্জ নিবো (Search Countries নিবো না, কারণ ওগুলোতে শুধু দেশের কোড থাকে)
        known_ranges = set()
        for s_name, c_dict in bot_settings.get("stex_services", {}).items():
            for c_name, r_list in c_dict.items():
                for r in r_list:
                    known_ranges.add(r)
                    
        sorted_known = sorted(list(known_ranges), key=len, reverse=True)
        
        r_counts = Counter()
        for num in nums:
            matched = False
            for r in sorted_known:
                if num.startswith(r):
                    r_counts[r] += 1
                    matched = True
                    break
            if not matched:
                if len(num) >= 7:
                    r_counts[num[:7]] += 1
                else:
                    r_counts[num] += 1
                    
        r_list = r_counts.most_common(12)
        
        kb = []
        for r, count in r_list:
            # এক লাইনে একটা করে বাটন
            kb.append([{"text": f"{r} ({count})", "icon_custom_emoji_id": "5352862640592949843", "copy_text": {"text": r}, "style": "primary"}])
            
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"exp_rng_{srv_query}", "style": "danger"}])
        
        app_full_name, prem_app_html = get_service_info_html(srv_query)
        prem_flag_html = get_flag_info_html(iso_query)
        
        edit_message(chat_id, msg_id, render_body_text(f"📊 <b>Ranges for {prem_app_html} {app_full_name} - {prem_flag_html} {iso_query}</b>\n\nClick on any range to copy it."), reply_markup={"inline_keyboard": kb})
        answer_callback(call["id"])

    # --- User Management Flows Integration ---
    elif data == "user_management":
        edit_message(chat_id, msg_id, get_user_management_text(), reply_markup=user_management_keyboard())

    elif data == "um_manage_balance":
        user_states[chat_id] = "wait_for_um_bal_uid"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the User ID to Manage Balance:"), reply_markup=get_cancel_kb())
        
    elif data == "um_ban_unban":
        user_states[chat_id] = "wait_for_um_ban_uid"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the User ID to Ban or Unban:"), reply_markup=get_cancel_kb())

    elif data == "um_user_profile":
        user_states[chat_id] = "wait_for_um_prof_uid"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the User ID to View Profile:"), reply_markup=get_cancel_kb())

    # --- Menu Design Integration ---
    elif data == "menu_design_list":
        edit_message(chat_id, msg_id, render_body_text(f"🎨 <b>Menu Design Editor</b>\n\nSelect a menu block to edit its Body Text and Inline Buttons. You can use Premium Emojis too!"), reply_markup=menu_design_list_keyboard())

    elif data == "md_reset_defaults":
        bot_settings["custom_messages"] = DEFAULT_CUSTOM_MESSAGES.copy()
        save_db()
        answer_callback(call["id"], "✅ Resetted to Premium Defaults!", show_alert=True)

    elif data.startswith("md_edit_"):
        answer_callback(call["id"])
        if chat_id in user_states: del user_states[chat_id]
        if chat_id in temp_data: del temp_data[chat_id]
        key = data.replace("md_edit_", "")
        cm_text = render_body_text(bot_settings["custom_messages"].get(key, {}).get("text", "..."))
        try:
            edit_message(chat_id, msg_id, render_body_text(f"🎨 <b>Editing: {key.upper()}</b>\n\nPreview of current Text:\n{cm_text}"), reply_markup=menu_edit_options_keyboard(key))
        except: pass

    elif data.startswith("md_text_"):
        key = data.replace("md_text_", "")
        user_states[chat_id] = "wait_for_menu_text"
        temp_data[chat_id] = {"msg_id": msg_id, "menu_key": key}
        edit_message(chat_id, msg_id, render_body_text(f"📝 <b>Edit Body: {key.upper()}</b>\n\nSend the new text. You can use Premium Emojis directly here.\n(Use standard HTML like <b>bold</b>, <i>italic</i> for formatting)"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"md_edit_{key}", "style": "danger"}]]})

    elif data.startswith("md_btns_"):
        answer_callback(call["id"]) 
        if chat_id in user_states: del user_states[chat_id] 
        if chat_id in temp_data: del temp_data[chat_id]
        key = data.replace("md_btns_", "")
        try:
            edit_message(chat_id, msg_id, render_body_text(f"⚙️ <b>Edit Inline Buttons: {key.upper()}</b>"), reply_markup=menu_buttons_list_keyboard(key))
        except: pass

    elif data.startswith("md_addbtn_"):
        key = data.replace("md_addbtn_", "")
        user_states[chat_id] = "wait_for_menu_btn"
        temp_data[chat_id] = {"msg_id": msg_id, "menu_key": key}
        edit_message(chat_id, msg_id, render_body_text(f"➕ <b>Add Button: {key.upper()}</b>\n\nSend custom button in this format:\n<code>Button Text - https://link.com</code>\n\n<i>(Only normal Emojis supported here!)</i>"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"md_btns_{key}", "style": "danger"}]]})

    elif data.startswith("md_delbtn_"):
        parts = data.split("_")
        key = parts[2]
        b_idx = int(parts[3])
        if b_idx < len(bot_settings["custom_messages"][key]["buttons"]):
            del bot_settings["custom_messages"][key]["buttons"][b_idx]
            save_db()
            answer_callback(call["id"], "✅ Button Deleted!", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text(f"⚙️ <b>Edit Inline Buttons: {key.upper()}</b>"), reply_markup=menu_buttons_list_keyboard(key))

    elif data.startswith("sel_wm_"):
        method = data.replace("sel_wm_", "")
        bal = get_user(chat_id).get('balance', 0.0)
        min_w = bot_settings['min_withdraw']
        
        if bal < min_w:
            answer_callback(call["id"], f"❌ আপনার ব্যালেন্স অপর্যাপ্ত! মিনিমাম {min_w} ৳ প্রয়োজন।", show_alert=True)
            return
            
        temp_data[chat_id] = {"method": method, "balance": bal, "msg_id": msg_id}
        user_states[chat_id] = "wait_for_withdraw_amount"
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['ok']} Method: {method}\n💰 Available Balance: {bal} ৳\n\n📝 Enter the amount you want to withdraw (Min: {min_w} ৳):"), reply_markup=get_cancel_kb())
        answer_callback(call["id"])

    elif data == "test_message_flow":
        user_states[chat_id] = "wait_for_test_service"
        temp_data[chat_id] = {}
        edit_message(chat_id, msg_id, render_body_text("🧪 <b>Test Mode</b>\n\n📝 Send the Service Name (e.g., IG):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}]]})

    elif data == "manage_emojis":
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['star']} <b>Premium Emoji Management</b>\n\nUpload your TXT files or manually add them below:"), reply_markup=emoji_settings_keyboard())

    elif data == "up_flags_txt":
        user_states[chat_id] = "wait_for_flag_txt"
        edit_message(chat_id, msg_id, render_body_text("📂 Please upload the <b>Flag Emojis</b> <code>.txt</code> file."), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_emojis", "style": "danger"}]]})

    elif data == "up_apps_txt":
        user_states[chat_id] = "wait_for_app_txt"
        edit_message(chat_id, msg_id, render_body_text("📂 Please upload the <b>Service Apps</b> <code>.txt</code> file."), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_emojis", "style": "danger"}]]})

    elif data == "add_single_emoji":
        user_states[chat_id] = "wait_for_emoji_extract"
        edit_message(chat_id, msg_id, render_body_text("📝 যেকোনো একটি Premium Emoji সেন্ড করুন (যেমন: 🇧🇩 বা 🚫):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_emojis", "style": "danger"}]]})

    elif data == "dl_flags_txt":
        content = generate_emoji_txt("flags")
        if content:
            send_document(chat_id, "Flag_Emojis.txt", content)
            answer_callback(call["id"], "✅ Downloaded!")
        else:
            answer_callback(call["id"], "❌ No Flag Emojis found!", show_alert=True)

    elif data == "dl_apps_txt":
        content = generate_emoji_txt("apps")
        if content:
            send_document(chat_id, "Service_Apps.txt", content)
            answer_callback(call["id"], "✅ Downloaded!")
        else:
            answer_callback(call["id"], "❌ No App Emojis found!", show_alert=True)

    elif data == "del_all_flags":
        bot_settings["premium_flags"] = {}
        save_db()
        answer_callback(call["id"], "✅ All Premium Flags Deleted Successfully!", show_alert=True)

    elif data == "broadcast_msg":
        user_states[chat_id] = "wait_for_broadcast"
        edit_message(chat_id, msg_id, render_body_text("📢 <b>Broadcast Mode</b>\n\nSend the message you want to broadcast (Text, Photo, Video, File etc)."), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]]})

    elif data == "upload_num":
        user_states[chat_id] = "wait_for_txt"
        edit_message(chat_id, msg_id, render_body_text("📂 Please upload the numbers in a <b>.txt</b> file."), reply_markup={"inline_keyboard": [[{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]]})

    elif data == "delete_files":
        kb = []
        for b_id, b_data in number_batches.items():
            kb.append([{"text": f"{b_data['filename']} ({len(b_data['numbers'])})", "icon_custom_emoji_id": "5422557736330106570", "callback_data": f"del_b_{b_id}", "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "primary"}])
        txt = "🗑 Select a file to delete:" if len(kb) > 1 else f"{PEM['no']} No files found."
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif data.startswith("del_b_"):
        b_id = data.split("del_b_")[1]
        if b_id in number_batches:
            del number_batches[b_id]
            save_db()
            answer_callback(call["id"], "✅ File deleted!", show_alert=True)
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "delete_files", "id": call["id"]})

    elif data == "show_used":
        kb = {"inline_keyboard": [[{"text": "Download TXT", "icon_custom_emoji_id": "5257969839313526622", "callback_data": "dl_used", "style": "primary"}], [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]]}
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['ok']} <b>Total Used Numbers:</b> {len(used_numbers_list)}"), reply_markup=kb)

    elif data == "show_unused":
        unused_count = sum(len(b["numbers"]) for b in number_batches.values())
        kb = {"inline_keyboard": [[{"text": "Download TXT", "icon_custom_emoji_id": "5257969839313526622", "callback_data": "dl_unused", "style": "primary"}], [{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]]}
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['rocket']} <b>Total Unused Numbers:</b> {unused_count}"), reply_markup=kb)

    elif data == "dl_used":
        if not used_numbers_list:
            answer_callback(call["id"], "❌ No used numbers found!", show_alert=True)
            return
        content = "\n".join(used_numbers_list).encode('utf-8')
        send_document(chat_id, "used_numbers.txt", content)
        answer_callback(call["id"])

    elif data == "dl_unused":
        unused_list = [n["num"] for b in number_batches.values() for n in b["numbers"]]
        if not unused_list:
            answer_callback(call["id"], "❌ No unused numbers found!", show_alert=True)
            return
        content = "\n".join(unused_list).encode('utf-8')
        send_document(chat_id, "unused_numbers.txt", content)
        answer_callback(call["id"])

    elif data == "lb_main":
        txt = f"━━━━━━━━━━━━━━━\n《 {PEM['admin']} <b>LEADER BOARD MENU</b> 》\n━━━━━━━━━━━━━━━\n<i>Select a category to view the top performers or history.</i>\n━━━━━━━━━━━━━━━"
        kb = [
            [{"text": "Top Referrers", "icon_custom_emoji_id": "5420145051336485498", "callback_data": "lb_top_refs", "style": "primary"}],
            [{"text": "Top OTP Receivers", "icon_custom_emoji_id": "5353001161878182134", "callback_data": "lb_top_otps", "style": "primary"}],
            [{"text": "Withdrawal History", "icon_custom_emoji_id": "5348469219761626211", "callback_data": "lb_w_history", "style": "success"}],
            [{"text": "Back to Admin", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]
        ]
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif data.startswith("lb_"):
        sub = data.replace("lb_", "")
        edit_message(chat_id, msg_id, render_body_text("⌛ <i>Fetching Data...</i>"))
        
        num_map = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣", "0": "0️⃣"}
        def get_p_num(n): return "".join([num_map.get(c, c) for c in str(n)])
        
        try:
            if sub == "top_refs":
                title, field, limit, icon = "TOP 5 REFERRERS", "total_refers", 5, PEM.get('user', '👥')
                users = db.collection('users').order_by(field, direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for u in users:
                    d = u.to_dict()
                    if d.get(field, 0) > 0:
                        p = "└" if count == limit else "├"
                        res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={u.id}'>{u.id}</a> ➔ <b>{d.get(field,0)}</b>\n"
                        count += 1
                if not res_txt: res_txt = "└ <i>No data found.</i>\n"

            elif sub == "top_otps":
                title, field, limit, icon = "TOP 5 OTP RECEIVERS", "total_otps", 5, PEM.get('msg', '📩')
                users = db.collection('users').order_by(field, direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for u in users:
                    d = u.to_dict()
                    if d.get(field, 0) > 0:
                        p = "└" if count == limit else "├"
                        res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={u.id}'>{u.id}</a> ➔ <b>{d.get(field,0)}</b>\n"
                        count += 1
                if not res_txt: res_txt = "└ <i>No data found.</i>\n"

            elif sub == "w_history":
                title, limit, icon = "LAST 10 WITHDRAWALS", 10, PEM.get('money', '💸')
                ws = db.collection('withdrawals').order_by('timestamp', direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for w in ws:
                    d = w.to_dict()
                    s = str(d.get('status','Pending')).lower()
                    stat_icon = PEM.get('ok','✅') if s in ["approved","success"] else PEM.get('no','❌') if s=="rejected" else "⏳"
                    uid = d.get('user_id','User')
                    p = "└" if count == limit else "├"
                    res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={uid}'>{uid}</a> ➔ <b>{d.get('amount',0)}৳</b> {stat_icon}\n"
                    count += 1
                if not res_txt: res_txt = "└ <i>No history found.</i>\n"

            final_msg = f"━━━━━━━━━━━━━━━\n{icon} <b>{title}</b>\n━━━━━━━━━━━━━━━\n{res_txt}━━━━━━━━━━━━━━━"
            kb = [[{"text": "Refresh", "icon_custom_emoji_id": "5420155432272438703", "callback_data": data, "style": "success"}, {"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "lb_main", "style": "danger"}]]
            edit_message(chat_id, msg_id, render_body_text(final_msg), reply_markup={"inline_keyboard": kb})

        except Exception as e:
            edit_message(chat_id, msg_id, render_body_text(f"❌ Error: {e}"), reply_markup={"inline_keyboard": [[{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "lb_main", "style": "danger"}]]})

    elif data == "lb_main":
        txt = f"━━━━━━━━━━━━━━━\n《 {PEM['admin']} <b>LEADER BOARD MENU</b> 》\n━━━━━━━━━━━━━━━\n<i>Select a category to view the top performers or history.</i>\n━━━━━━━━━━━━━━━"
        kb = [
            [{"text": "Top Referrers", "icon_custom_emoji_id": "5420145051336485498", "callback_data": "lb_top_refs", "style": "primary"}],
            [{"text": "Top OTP Receivers", "icon_custom_emoji_id": "5353001161878182134", "callback_data": "lb_top_otps", "style": "primary"}],
            [{"text": "Withdrawal History", "icon_custom_emoji_id": "5348469219761626211", "callback_data": "lb_w_history", "style": "success"}],
            [{"text": "Back to Admin", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "back_to_admin", "style": "danger"}]
        ]
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif data.startswith("lb_"):
        sub = data.replace("lb_", "")
        edit_message(chat_id, msg_id, render_body_text("⌛ <i>Fetching Data...</i>"))
        
        num_map = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣", "0": "0️⃣"}
        def get_p_num(n): return "".join([num_map.get(c, c) for c in str(n)])
        
        try:
            if sub == "top_refs":
                title, field, limit, icon = "TOP 5 REFERRERS", "total_refers", 5, PEM.get('user', '👥')
                users = db.collection('users').order_by(field, direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for u in users:
                    d = u.to_dict()
                    if d.get(field, 0) > 0:
                        p = "└" if count == limit else "├"
                        res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={u.id}'>{u.id}</a> ➔ <b>{d.get(field,0)}</b>\n"
                        count += 1
                if not res_txt: res_txt = "└ <i>No data found.</i>\n"

            elif sub == "top_otps":
                title, field, limit, icon = "TOP 5 OTP RECEIVERS", "total_otps", 5, PEM.get('msg', '📩')
                users = db.collection('users').order_by(field, direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for u in users:
                    d = u.to_dict()
                    if d.get(field, 0) > 0:
                        p = "└" if count == limit else "├"
                        res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={u.id}'>{u.id}</a> ➔ <b>{d.get(field,0)}</b>\n"
                        count += 1
                if not res_txt: res_txt = "└ <i>No data found.</i>\n"

            elif sub == "w_history":
                title, limit, icon = "LAST 10 WITHDRAWALS", 10, PEM.get('money', '💸')
                ws = db.collection('withdrawals').order_by('timestamp', direction="DESCENDING").limit(limit).stream()
                res_txt = ""
                count = 1
                for w in ws:
                    d = w.to_dict()
                    s = str(d.get('status','Pending')).lower()
                    stat_icon = PEM.get('ok','✅') if s in ["approved","success"] else PEM.get('no','❌') if s=="rejected" else "⏳"
                    uid = d.get('user_id','User')
                    p = "└" if count == limit else "├"
                    res_txt += f"{p} {get_p_num(count)} <a href='tg://user?id={uid}'>{uid}</a> ➔ <b>{d.get('amount',0)}৳</b> {stat_icon}\n"
                    count += 1
                if not res_txt: res_txt = "└ <i>No history found.</i>\n"

            final_msg = f"━━━━━━━━━━━━━━━\n{icon} <b>{title}</b>\n━━━━━━━━━━━━━━━\n{res_txt}━━━━━━━━━━━━━━━"
            kb = [[{"text": "Refresh", "icon_custom_emoji_id": "5420155432272438703", "callback_data": data, "style": "success"}, {"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "lb_main", "style": "danger"}]]
            edit_message(chat_id, msg_id, render_body_text(final_msg), reply_markup={"inline_keyboard": kb})

        except Exception as e:
            edit_message(chat_id, msg_id, render_body_text(f"❌ Error: {e}"), reply_markup={"inline_keyboard": [[{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "lb_main", "style": "danger"}]]})

    elif data == "back_to_admin":
        if chat_id in user_states: del user_states[chat_id]
        edit_message(chat_id, msg_id, get_admin_text(chat_id), reply_markup=admin_panel_keyboard())
        
    elif data == "system_settings":
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['gear']} <b>System Settings</b>\nManage advanced bot configurations below:"), reply_markup=system_settings_keyboard())

    elif data == "stex_control":
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        edit_message(chat_id, msg_id, render_body_text(
            f"🌐 <b>StexSMS Control Panel</b>\n\n"
            f"Total API Keys: {len(bot_settings.get('stex_keys', []))}\n"
            f"Base URL: <code>{html.escape(bot_settings.get('stex_base_url', '') or 'Not set')}</code>\n\n"
            "Manage your StexSMS API Keys below:"
        ), reply_markup=stex_control_keyboard())

    elif data == "set_stex_base":
        user_states[chat_id] = "wait_for_stex_base_url"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text(
            "🌐 <b>SET STEXSMS BASE URL</b>\n\n"
            "Provider-এর API root URL পাঠান। উদাহরণ: <code>https://provider.example/api</code>\n"
            "শেষে <code>/getnum</code> যোগ করবেন না।"
        ), reply_markup={"inline_keyboard": [[
            {"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "danger"}
        ]]})

    elif data == "add_stex_key":
        user_states[chat_id] = "wait_for_add_stex_key"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the new StexSMS API Key (e.g. nxa_...):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "danger"}]]})

    elif data == "view_stex_keys":
        kb = []
        for idx, key in enumerate(bot_settings.get("stex_keys", [])):
            safe_name = key[:10] + "..." if len(key)>10 else key
            kb.append([{"text": f"Delete {safe_name}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_nxa_{idx}", "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "primary"}])
        edit_message(chat_id, msg_id, render_body_text("🗑 <b>Select StexSMS Key to Delete:</b>"), reply_markup={"inline_keyboard": kb})

    elif data.startswith("del_nxa_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings.get("stex_keys", [])):
            del bot_settings["stex_keys"][idx]
            save_db()
            answer_callback(call["id"], "✅ StexSMS Key Deleted!", show_alert=True)
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "view_stex_keys", "id": call["id"]})

    elif data == "stex_search_country":
        kb = []
        for idx, c in enumerate(bot_settings.get("search_countries", [])):
            kb.append([{"text": f"Delete {c}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_sc_{idx}", "style": "danger"}])
        kb.append([{"text": "Add Country Code", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_search_country", "style": "success"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "primary"}])
        edit_message(chat_id, msg_id, render_body_text("🌍 <b>Allowed Search Countries:</b>\nOnly these country codes will be allowed in Search Number."), reply_markup={"inline_keyboard": kb})

    elif data == "add_search_country":
        user_states[chat_id] = "wait_for_add_sc"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the Country Code (e.g. 880 or 92):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_search_country", "style": "danger"}]]})

    elif data.startswith("del_sc_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings.get("search_countries", [])):
            del bot_settings["search_countries"][idx]
            save_db()
            answer_callback(call["id"], "✅ Country Deleted!", show_alert=True)
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "stex_search_country", "id": call["id"]})

    elif data == "manage_stex_srv":
        kb = []
        srvs = bot_settings.get("stex_services", {})
        apps_db = bot_settings.get("premium_apps", {})
        for srv in srvs:
            label, emoji_id = _catalog_button_label(srv, "service")
            button = {
                "text": label,
                "callback_data": _catalog_callback("nx_srv", srv),
                "style": "primary",
            }
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            kb.append([button])
        kb.append([{"text": "Add New Service", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "nx_add_srv", "style": "success"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "stex_control", "style": "danger"}])
        edit_message(chat_id, msg_id, render_body_text("📦 <b>StexSMS Services Manager</b>\nManage your API-based dynamic services below:"), reply_markup={"inline_keyboard": kb})

    elif data == "nx_add_srv":
        user_states[chat_id] = "wait_nx_srv_name"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Enter Service Name (e.g. TELEGRAM):"), reply_markup=get_cancel_kb())

    elif data.startswith("nx_srv_"):
        decoded = _catalog_callback_values(data, "nx_srv", 1)
        srv = decoded[0] if decoded else data.replace("nx_srv_", "")
        kb = []
        countries = bot_settings["stex_services"].get(srv, {})
        flags_db = bot_settings.get("premium_flags", {})
        country_buttons = []
        for c in countries:
            label, emoji_id = _catalog_button_label(c, "country")
            button = {
                "text": f"{label} ({len(countries[c])} Ranges)",
                "callback_data": _catalog_callback("nx_cnt", srv, c),
                "style": "primary",
            }
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            country_buttons.append(button)
        kb.extend(_two_column_inline_keyboard(country_buttons))
        kb.append([{"text": "Add Country", "icon_custom_emoji_id": "5420323438508155202", "callback_data": _catalog_callback("nx_add_cnt", srv), "style": "success"}])
        kb.append([{"text": "Delete Service", "icon_custom_emoji_id": "5422557736330106570", "callback_data": _catalog_callback("nx_del_srv", srv), "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_stex_srv", "style": "primary"}])
        service_label, _ = _catalog_button_label(srv, "service")
        edit_message(chat_id, msg_id, render_body_text(f"📂 <b>Service: {service_label}</b>\nManage countries for this service:"), reply_markup={"inline_keyboard": kb})

    elif data.startswith("nx_add_cnt_"):
        decoded = _catalog_callback_values(data, "nx_add_cnt", 1)
        srv = decoded[0] if decoded else data.replace("nx_add_cnt_", "")
        user_states[chat_id] = "wait_nx_cnt_name"
        temp_data[chat_id] = {"msg_id": msg_id, "srv": srv}
        service_label, _ = _catalog_button_label(srv, "service")
        edit_message(chat_id, msg_id, render_body_text(f"🌍 Enter Country Name for <b>{service_label}</b> (e.g. BD, INDIA):"), reply_markup=get_cancel_kb())

    elif data.startswith("nx_cnt_"):
        decoded = _catalog_callback_values(data, "nx_cnt", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 3)
            srv, cnt = parts[2], parts[3]
        ranges = bot_settings["stex_services"][srv].get(cnt, [])
        
        kb = []
        row = []
        for r in ranges:
            row.append({"text": f"Delete {r}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": _catalog_callback("nx_dr", srv, cnt, r), "style": "danger"})
            if len(row) == 2:
                kb.append(row)
                row = []
        if row: kb.append(row)
        
        kb.append([{"text": "Add Range", "icon_custom_emoji_id": "5420323438508155202", "callback_data": _catalog_callback("nx_addr", srv, cnt), "style": "success"}])
        kb.append([{"text": "Delete Entire Country", "icon_custom_emoji_id": "5422557736330106570", "callback_data": _catalog_callback("nx_del_cnt", srv, cnt), "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": _catalog_callback("nx_srv", srv), "style": "primary"}])
        
        service_label, _ = _catalog_button_label(srv, "service")
        country_label, _ = _catalog_button_label(cnt, "country")
        txt = f"📍 <b>Service: {service_label} | Country: {country_label}</b>\n\n<b>Total Ranges:</b> {len(ranges)}\n<i>Click on a range below to delete it, or add a new one.</i>"
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif data.startswith("nx_addr_"):
        decoded = _catalog_callback_values(data, "nx_addr", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 3)
            srv, cnt = parts[2], parts[3]
        user_states[chat_id] = "wait_nx_addr"
        temp_data[chat_id] = {"msg_id": msg_id, "srv": srv, "cnt": cnt}
        edit_message(chat_id, msg_id, render_body_text(f"📝 Send the new Range for <b>{cnt}</b> (e.g. 88017):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": _catalog_callback("nx_cnt", srv, cnt), "style": "danger"}]]})

    elif data.startswith("nx_dr_"):
        decoded = _catalog_callback_values(data, "nx_dr", 3)
        if decoded:
            srv, cnt, rng = decoded
        else:
            parts = data.split("_", 4)
            srv, cnt, rng = parts[2], parts[3], parts[4]
        if rng in bot_settings["stex_services"].get(srv, {}).get(cnt, []):
            bot_settings["stex_services"][srv][cnt].remove(rng)
            save_db()
            answer_callback(call["id"], f"✅ Range {rng} deleted!", show_alert=True)
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": _catalog_callback("nx_cnt", srv, cnt), "id": call["id"]})

    elif data.startswith("nx_del_srv_"):
        decoded = _catalog_callback_values(data, "nx_del_srv", 1)
        srv = decoded[0] if decoded else data.replace("nx_del_srv_", "")
        if srv in bot_settings["stex_services"]: del bot_settings["stex_services"][srv]
        save_db()
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "manage_stex_srv", "id": call["id"]})

    elif data.startswith("nx_del_cnt_"):
        decoded = _catalog_callback_values(data, "nx_del_cnt", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 4)
            srv, cnt = parts[3], parts[4]
        if cnt in bot_settings["stex_services"].get(srv, {}): del bot_settings["stex_services"][srv][cnt]
        save_db()
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": _catalog_callback("nx_srv", srv), "id": call["id"]})

    elif data == "voltx_control":
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        edit_message(chat_id, msg_id, render_body_text(
            f"⚡ <b>Voltx Control Panel</b>\n\n"
            f"Total API Keys: {len(bot_settings.get('voltx_keys', []))}\n"
            f"Base URL: <code>{html.escape(bot_settings.get('voltx_base_url', '') or 'Not set')}</code>\n\n"
            "Manage your Voltx API Keys below:"
        ), reply_markup=voltx_control_keyboard())

    elif data == "set_voltx_base":
        user_states[chat_id] = "wait_for_voltx_base_url"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text(
            "🌐 <b>SET VOLTX BASE URL</b>\n\n"
            "Provider-এর API root URL পাঠান। উদাহরণ: <code>https://provider.example/api</code>\n"
            "শেষে <code>/getnum</code> যোগ করবেন না।"
        ), reply_markup={"inline_keyboard": [[
            {"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_control", "style": "danger"}
        ]]})

    elif data == "add_voltx_key":
        user_states[chat_id] = "wait_for_add_voltx_key"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the new Voltx API Key:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_control", "style": "danger"}]]})

    elif data == "view_voltx_keys":
        kb = []
        for idx, key in enumerate(bot_settings.get("voltx_keys", [])):
            safe_name = key[:10] + "..." if len(key)>10 else key
            kb.append([{"text": f"Delete {safe_name}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_vtx_{idx}", "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_control", "style": "primary"}])
        edit_message(chat_id, msg_id, render_body_text("🗑 <b>Select Voltx Key to Delete:</b>"), reply_markup={"inline_keyboard": kb})

    elif data.startswith("del_vtx_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings.get("voltx_keys", [])):
            del bot_settings["voltx_keys"][idx]
            save_db()
            answer_callback(call["id"], "✅ Voltx Key Deleted!", show_alert=True)
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "view_voltx_keys", "id": call["id"]})

    elif data == "voltx_search_country":
        kb = []
        for idx, c in enumerate(bot_settings.get("voltx_search_countries", [])):
            kb.append([{"text": f"Delete {c}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"del_vsc_{idx}", "style": "danger"}])
        kb.append([{"text": "Add Country Code", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "add_voltx_search_country", "style": "success"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_control", "style": "primary"}])
        edit_message(chat_id, msg_id, render_body_text("🌍 <b>Voltx Allowed Ranges:</b>\nOnly these ranges/codes will be allowed in Voltx Search Number."), reply_markup={"inline_keyboard": kb})

    elif data == "add_voltx_search_country":
        user_states[chat_id] = "wait_for_add_vsc"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the Voltx Range Code (e.g. 26134):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_search_country", "style": "danger"}]]})

    elif data.startswith("del_vsc_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings.get("voltx_search_countries", [])):
            del bot_settings["voltx_search_countries"][idx]
            save_db()
            answer_callback(call["id"], "✅ Voltx Range Deleted!", show_alert=True)
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "voltx_search_country", "id": call["id"]})

    elif data == "manage_voltx_srv":
        kb = []
        srvs = bot_settings.get("voltx_services", {})
        apps_db = bot_settings.get("premium_apps", {})
        for srv in srvs:
            label, emoji_id = _catalog_button_label(srv, "service")
            button = {
                "text": label,
                "callback_data": _catalog_callback("vx_srv", srv),
                "style": "primary",
            }
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            kb.append([button])
        kb.append([{"text": "Add New Service", "icon_custom_emoji_id": "5420323438508155202", "callback_data": "vx_add_srv", "style": "success"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "voltx_control", "style": "danger"}])
        edit_message(chat_id, msg_id, render_body_text("⚡ <b>Voltx Services Manager</b>\nManage your API-based dynamic services below:"), reply_markup={"inline_keyboard": kb})

    elif data == "vx_add_srv":
        user_states[chat_id] = "wait_vx_srv_name"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Enter Service Name (e.g. TELEGRAM):"), reply_markup=get_cancel_kb())

    elif data.startswith("vx_srv_"):
        decoded = _catalog_callback_values(data, "vx_srv", 1)
        srv = decoded[0] if decoded else data.replace("vx_srv_", "")
        kb = []
        countries = bot_settings["voltx_services"].get(srv, {})
        flags_db = bot_settings.get("premium_flags", {})
        country_buttons = []
        for c in countries:
            label, emoji_id = _catalog_button_label(c, "country")
            button = {
                "text": f"{label} ({len(countries[c])} Ranges)",
                "callback_data": _catalog_callback("vx_cnt", srv, c),
                "style": "primary",
            }
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            country_buttons.append(button)
        kb.extend(_two_column_inline_keyboard(country_buttons))
        kb.append([{"text": "Add Country", "icon_custom_emoji_id": "5420323438508155202", "callback_data": _catalog_callback("vx_add_cnt", srv), "style": "success"}])
        kb.append([{"text": "Delete Service", "icon_custom_emoji_id": "5422557736330106570", "callback_data": _catalog_callback("vx_del_srv", srv), "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_voltx_srv", "style": "primary"}])
        service_label, _ = _catalog_button_label(srv, "service")
        edit_message(chat_id, msg_id, render_body_text(f"📂 <b>Service: {service_label}</b>\nManage countries for this service:"), reply_markup={"inline_keyboard": kb})

    elif data.startswith("vx_add_cnt_"):
        decoded = _catalog_callback_values(data, "vx_add_cnt", 1)
        srv = decoded[0] if decoded else data.replace("vx_add_cnt_", "")
        user_states[chat_id] = "wait_vx_cnt_name"
        temp_data[chat_id] = {"msg_id": msg_id, "srv": srv}
        service_label, _ = _catalog_button_label(srv, "service")
        edit_message(chat_id, msg_id, render_body_text(f"🌍 Enter Country Name for <b>{service_label}</b> (e.g. BD, INDIA):"), reply_markup=get_cancel_kb())

    elif data.startswith("vx_cnt_"):
        decoded = _catalog_callback_values(data, "vx_cnt", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 3)
            srv, cnt = parts[2], parts[3]
        ranges = bot_settings["voltx_services"][srv].get(cnt, [])
        kb = []
        row = []
        for r in ranges:
            row.append({"text": f"Delete {r}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": _catalog_callback("vx_dr", srv, cnt, r), "style": "danger"})
            if len(row) == 2:
                kb.append(row)
                row = []
        if row: kb.append(row)
        kb.append([{"text": "Add Range", "icon_custom_emoji_id": "5420323438508155202", "callback_data": _catalog_callback("vx_addr", srv, cnt), "style": "success"}])
        kb.append([{"text": "Delete Entire Country", "icon_custom_emoji_id": "5422557736330106570", "callback_data": _catalog_callback("vx_del_cnt", srv, cnt), "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": _catalog_callback("vx_srv", srv), "style": "primary"}])
        service_label, _ = _catalog_button_label(srv, "service")
        country_label, _ = _catalog_button_label(cnt, "country")
        txt = f"📍 <b>Service: {service_label} | Country: {country_label}</b>\n\n<b>Total Ranges:</b> {len(ranges)}\n<i>Click on a range below to delete it, or add a new one.</i>"
        edit_message(chat_id, msg_id, render_body_text(txt), reply_markup={"inline_keyboard": kb})

    elif data.startswith("vx_addr_"):
        decoded = _catalog_callback_values(data, "vx_addr", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 3)
            srv, cnt = parts[2], parts[3]
        user_states[chat_id] = "wait_vx_addr"
        temp_data[chat_id] = {"msg_id": msg_id, "srv": srv, "cnt": cnt}
        edit_message(chat_id, msg_id, render_body_text(f"📝 Send the new Range for <b>{cnt}</b> (e.g. 26134):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": _catalog_callback("vx_cnt", srv, cnt), "style": "danger"}]]})

    elif data.startswith("vx_dr_"):
        decoded = _catalog_callback_values(data, "vx_dr", 3)
        if decoded:
            srv, cnt, rng = decoded
        else:
            parts = data.split("_", 4)
            srv, cnt, rng = parts[2], parts[3], parts[4]
        if rng in bot_settings["voltx_services"].get(srv, {}).get(cnt, []):
            bot_settings["voltx_services"][srv][cnt].remove(rng)
            save_db()
            answer_callback(call["id"], f"✅ Range {rng} deleted!", show_alert=True)
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": _catalog_callback("vx_cnt", srv, cnt), "id": call["id"]})

    elif data.startswith("vx_del_srv_"):
        decoded = _catalog_callback_values(data, "vx_del_srv", 1)
        srv = decoded[0] if decoded else data.replace("vx_del_srv_", "")
        if srv in bot_settings["voltx_services"]: del bot_settings["voltx_services"][srv]
        save_db()
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": "manage_voltx_srv", "id": call["id"]})

    elif data.startswith("vx_del_cnt_"):
        decoded = _catalog_callback_values(data, "vx_del_cnt", 2)
        if decoded:
            srv, cnt = decoded
        else:
            parts = data.split("_", 4)
            srv, cnt = parts[3], parts[4]
        if cnt in bot_settings["voltx_services"].get(srv, {}): del bot_settings["voltx_services"][srv][cnt]
        save_db()
        handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": _catalog_callback("vx_srv", srv), "id": call["id"]})

    elif data == "manage_fj":
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['link']} <b>FORCE JOIN SYSTEM</b>\nManage channels below:"), reply_markup=fj_settings_keyboard())

    elif data == "toggle_fj":
        bot_settings["fj_on"] = not bot_settings["fj_on"]
        save_db()
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['link']} <b>FORCE JOIN SYSTEM</b>\nManage channels below:"), reply_markup=fj_settings_keyboard())

    elif data == "add_fj":
        user_states[chat_id] = "wait_for_add_fj"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send Channel Username or Invite Link:\n<i>(Note: For private channels, use the numeric ID like -100...)</i>"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_fj", "style": "danger"}]]})

    elif data.startswith("del_fj_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["fj_channels"]):
            del bot_settings["fj_channels"][idx]
            save_db()
            answer_callback(call["id"], "✅ Channel deleted!", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text(f"{PEM['link']} <b>FORCE JOIN SYSTEM</b>\nManage channels below:"), reply_markup=fj_settings_keyboard())

    elif data == "manage_admins":
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['user']} <b>ADMIN MANAGEMENT</b>\nManage your bot admins below:"), reply_markup=admin_settings_keyboard())

    elif data == "add_adm":
        user_states[chat_id] = "wait_for_add_adm"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the User ID of the new Admin:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_admins", "style": "danger"}]]})

    elif data.startswith("del_adm_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["admins"]):
            if bot_settings["admins"][idx] in OWNER_IDS:
                answer_callback(call["id"], "Owners cannot be deleted.", show_alert=True)
                return
            del bot_settings["admins"][idx]
            save_db()
            answer_callback(call["id"], "✅ Admin deleted!", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text(f"{PEM['user']} <b>ADMIN MANAGEMENT</b>\nManage your bot admins below:"), reply_markup=admin_settings_keyboard())

    elif data == "manage_otp_groups":
        edit_message(chat_id, msg_id, render_body_text("🛡 <b>OTP GROUP MANAGEMENT</b>\nManage settings below:"), reply_markup=otp_groups_list_keyboard())

    elif data == "add_fw":
        user_states[chat_id] = "wait_for_add_fw_id"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the Group ID/Username to forward messages to:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_otp_groups", "style": "danger"}]]})

    elif data.startswith("manage_fw_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["fw_groups"]):
            grp_id = bot_settings["fw_groups"][idx]["chat_id"]
            edit_message(chat_id, msg_id, render_body_text(f"🛡 <b>Manage Group:</b> {grp_id}"), reply_markup=specific_fw_group_keyboard(idx))

    elif data.startswith("add_fwbtn_"):
        idx = int(data.split("_")[2])
        user_states[chat_id] = "wait_for_add_fw_btn"
        temp_data[chat_id] = {"msg_id": msg_id, "fw_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("📝 Send Custom Inline Button format:\n<code>Button Text - https://link.com</code>"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"manage_fw_{idx}", "style": "danger"}]]})

    elif data.startswith("del_fwbtn_"):
        parts = data.split("_")
        idx, b_idx = int(parts[2]), int(parts[3])
        if 0 <= idx < len(bot_settings["fw_groups"]):
            if 0 <= b_idx < len(bot_settings["fw_groups"][idx]["buttons"]):
                del bot_settings["fw_groups"][idx]["buttons"][b_idx]
                save_db()
                answer_callback(call["id"], "✅ Button deleted!", show_alert=True)
                edit_message(chat_id, msg_id, render_body_text(f"🛡 <b>Manage Group:</b> {bot_settings['fw_groups'][idx]['chat_id']}"), reply_markup=specific_fw_group_keyboard(idx))

    elif data.startswith("del_fw_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["fw_groups"]):
            del bot_settings["fw_groups"][idx]
            save_db()
            answer_callback(call["id"], "✅ Group deleted!", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text("🛡 <b>OTP GROUP MANAGEMENT</b>\nManage settings below:"), reply_markup=otp_groups_list_keyboard())

    elif data == "edit_otp_link":
        user_states[chat_id] = "wait_for_otp_link"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the new OTP Group Link:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_otp_groups", "style": "danger"}]]})

    elif data == "manage_panels":
        api_count = len([p for p in bot_settings["panels"] if p.get("type") == "API Panel"])
        cpt_count = len([p for p in bot_settings["panels"] if p.get("type", "API Panel") == "Auto Captcha Panel"])
        json_count = len([p for p in bot_settings["panels"] if p.get("type") == JSON_PANEL_TYPE])
        text = f"{PEM['gear']} <b>Panel Management</b>\n\nSelect which type of panel system you want to manage:"
        kb = {"inline_keyboard": [
            [{"text": f"Manage API Panels ({api_count})", "icon_custom_emoji_id": "5336972142066047577", "callback_data": "manage_api_panels", "style": "primary"}],
            [{"text": f"Manage Auto Captcha Panels ({cpt_count})", "icon_custom_emoji_id": "5353022963132174959", "callback_data": "manage_cpt_panels", "style": "success"}],
            [{"text": f"Manage JSON API Panels ({json_count})", "icon_custom_emoji_id": "5420517437885943844", "callback_data": "manage_json_panels", "style": "primary"}],
            [{"text": "Back to System", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "system_settings", "style": "danger"}]
        ]}
        edit_message(chat_id, msg_id, render_body_text(text), reply_markup=kb)

    elif data in ["manage_api_panels", "manage_cpt_panels", "manage_json_panels"]:
        p_type = {"manage_cpt_panels": "Auto Captcha Panel",
                  "manage_json_panels": JSON_PANEL_TYPE}.get(data, "API Panel")
        p_list = [p for p in bot_settings["panels"] if p.get("type", "API Panel") == p_type]
        if p_type == 'API Panel':
            icon = f"{PEM['world']} API"
        elif p_type == 'Auto Captcha Panel':
            icon = f"{PEM['lock']} Auto Captcha"
        else:
            icon = f"{PEM['gear']} JSON API"
        
        text = f"{icon} <b>{p_type}s Management</b>\n\n👀 <b>Active Monitors:</b> {len(p_list)}\n\n🟢 <b>Available Providers:</b>\n"
        for p in p_list:
            status = "Monitoring" if p['status'] == 'ON' else "Stopped"
            login_state = p.get('login_status', '')
            if p['type'] == 'Auto Captcha Panel':
                conf = f" {login_state}" if login_state else f"{PEM['ok']} Configured"
            elif p['type'] == JSON_PANEL_TYPE:
                monitor_state = "Monitor ON" if p.get('status') == 'ON' else "Monitor OFF"
                source_state = "Source ON" if p.get('source_enabled') else "Source OFF"
                conf = (f"{PEM['ok'] if p.get('api_url') else PEM['no']} "
                        f"{monitor_state} | {source_state}")
            else:
                conf = f"{PEM['ok']} Configured" if p.get('api_url') else f"{PEM['no']} Not Configured"
            text += f"• {p['name']}: {PEM['ok'] if p['status']=='ON' else PEM['no']} {status} | {conf}\n"
        edit_message(chat_id, msg_id, render_body_text(text), reply_markup=typed_panels_list_keyboard(p_type))

    elif data in ["add_api_panel", "add_cpt_panel", "add_json_panel"]:
        user_states[chat_id] = "wait_for_panel_name"
        p_type = {"add_cpt_panel": "logc", "add_json_panel": "json"}.get(data, "api")
        back_cb = {"api": "manage_api_panels", "logc": "manage_cpt_panels", "json": "manage_json_panels"}[p_type]
        temp_data[chat_id] = {"msg_id": msg_id, "add_type": p_type}
        edit_message(chat_id, msg_id, render_body_text("📝 Please send the name of the New Provider:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": back_cb, "style": "danger"}]]})

    elif data.startswith("add_ptype_"):
        pass

    elif data in ["list_del_api", "list_del_cpt", "list_del_json"]:
        p_type = {"list_del_cpt": "Auto Captcha Panel", "list_del_json": JSON_PANEL_TYPE}.get(data, "API Panel")
        p_slug = "api" if p_type == "API Panel" else ("cpt" if p_type == "Auto Captcha Panel" else "json")
        kb = []
        for idx, p in enumerate(bot_settings["panels"]):
            if p.get("type", "API Panel") == p_type:
                kb.append([{"text": f"Delete {p['name']}", "icon_custom_emoji_id": "5420130255174145507", "callback_data": f"do_del_pnl_{idx}", "style": "danger"}])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"manage_{p_slug}_panels", "style": "primary"}])
        edit_message(chat_id, msg_id, render_body_text(f"{PEM['trash']} <b>Select a Provider to Delete:</b>"), reply_markup={"inline_keyboard": kb})

    elif data.startswith("do_del_pnl_"):
        idx = int(data.split("_")[3])
        if 0 <= idx < len(bot_settings["panels"]):
            p_type = bot_settings["panels"][idx].get("type", "API Panel")
            del bot_settings["panels"][idx]
            save_db()
            answer_callback(call["id"], "✅ Provider Deleted!", show_alert=True)
            p_slug = "api" if p_type == "API Panel" else ("cpt" if p_type == "Auto Captcha Panel" else "json")
            handle_callback({"message": {"chat": {"id": chat_id}, "message_id": msg_id}, "data": f"manage_{p_slug}_panels", "id": "internal"})

    elif data.startswith("tog_pnl_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            
            p["status"] = "ON" if p["status"] == "OFF" else "OFF"
            # OFF means the whole panel is off: stop monitoring AND give the
            # rented numbers back so nothing keeps running in the background.
            if p.get("type") == JSON_PANEL_TYPE and p["status"] == "OFF":
                released = 0
                for _number, _rental in list(slvn_rentals.items()):
                    if _rental.get("panel_uid") == _json_panel_uid(p):
                        if _slvn_release_number(_number, p):
                            released += 1
                if released:
                    p["login_status"] = f"🔴 OFF — {released} rental released"
            save_db()
            
            if p["type"] == "Auto Captcha Panel":
                text = _panel_config_text(p)
            else:
                text = _panel_config_text(p)
            edit_message(chat_id, msg_id, render_body_text(text), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("conf_pnl_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            if p["type"] == "Auto Captcha Panel":
                text = _panel_config_text(p)
            else:
                text = _panel_config_text(p)
            edit_message(chat_id, msg_id, render_body_text(text), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("set_p_api_"):
        idx = int(data.split("_")[3])
        user_states[chat_id] = "wait_for_p_api"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the API URL for this provider:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("set_p_tok_"):
        idx = int(data.split("_")[3])
        user_states[chat_id] = "wait_for_p_tok"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the Token for this provider:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("set_p_fapi_"):
        idx = int(data.split("_")[3])
        user_states[chat_id] = "wait_for_p_fapi"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the FULL API URL (Example: http://api.com/get?key=YOUR_TOKEN&start=0):"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("set_p_rec_"):
        idx = int(data.split("_")[3])
        user_states[chat_id] = "wait_for_p_rec"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the number of records to fetch (e.g. 10).\nType <code>0</code> for Unlimited:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("add_json_preset_"):
        preset_key = data.replace("add_json_preset_", "", 1)
        preset = JSON_PANEL_PRESETS.get(preset_key)
        if not preset:
            answer_callback(call["id"], "❌ Unknown preset", show_alert=True)
            return
        user_states[chat_id] = "wait_for_j_preset_token"
        temp_data[chat_id] = {"msg_id": msg_id, "preset": preset_key}
        edit_message(chat_id, msg_id, render_body_text(preset["token_prompt"]), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_json_panels", "style": "danger"}]]})

    elif data.startswith("tog_src_"):
        # 🌐 Number source switch (independent of the master panel switch)
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            p["source_enabled"] = not bool(p.get("source_enabled"))
            if p["source_enabled"]:
                p["status"] = "ON"          # source ON implies panel ON
                _json_panel_uid(p)
                try:
                    _slvn_catalog(p, force=True)
                except Exception:
                    pass
            save_db()
            state = "ON 🟢" if p["source_enabled"] else "OFF 🔴"
            answer_callback(call["id"], f"Number source {state}", show_alert=False)
            edit_message(chat_id, msg_id, render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("svc:"):
        # ✍️ Manual SLVN catalog: Service -> Country -> Range
        if not is_admin(chat_id):
            answer_callback(call["id"], "🚫 Admin only!", show_alert=True)
            return
        _parsed = _svcat_parse(data)
        if not _parsed:
            return
        idx, action, tokens = _parsed
        if action == "list":
            _svcat_render_list(chat_id, msg_id)
            return
        p = _svcat_panel(idx)
        if not p:
            answer_callback(call["id"], "❌ SLVN panel পাওয়া যায়নি!", show_alert=True)
            return
        catalog = _slvn_manual_catalog(p)

        if action == "root":
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "mode":
            new_mode = "auto" if _slvn_catalog_mode(p) == "manual" else "manual"
            _svcat_set_mode(p, new_mode)
            save_db()
            answer_callback(call["id"], f"Catalog mode: {new_mode.upper()}", show_alert=False)
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "src":
            p["source_enabled"] = not bool(p.get("source_enabled"))
            if p["source_enabled"]:
                p["status"] = "ON"
                _json_panel_uid(p)
                _slvn_catalog(p)
            save_db()
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "import":
            live = {}
            err = ""
            try:
                live = _slvn_live_catalog(p, force=True)
            except Exception as e:
                err = str(e)[:80]
            if not live:
                answer_callback(call["id"],
                                "❌ AUTO catalog খালি" + (f" — {err}" if err else ""),
                                show_alert=True)
            else:
                imported = 0
                for svc, countries in live.items():
                    for cnt, ranges in (countries or {}).items():
                        if _svcat_merge(p, svc, cnt, ranges or []):
                            imported += 1
                _svcat_set_mode(p, "manual")
                save_db()
                answer_callback(call["id"],
                                f"✅ {imported} country import হয়েছে — MANUAL ON",
                                show_alert=True)
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "clear":
            _svcat_render_clear(chat_id, msg_id, idx)

        elif action == "clearyes":
            p["catalog"] = {}
            _svcat_set_mode(p, "auto")
            save_db()
            answer_callback(call["id"], "🧹 Manual list cleared — AUTO mode", show_alert=True)
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "addsrv":
            _svcat_prompt(
                chat_id, msg_id, idx, "wait_svcat_service",
                "📝 <b>New Service name</b>\n➡️ যেমন: <code>TELEGRAM</code>, "
                "<code>WHATSAPP</code>\n\n<i>Service যোগ করলে catalog নিজেই "
                "MANUAL mode-এ চলে যাবে (auto catalog OFF)।</i>",
                _svcat_cb(idx, "root"),
            )

        elif action == "bulk":
            _svcat_prompt(
                chat_id, msg_id, idx, "wait_svcat_bulk",
                "📋 <b>Bulk Add</b>\nপ্রতি লাইনে একটা entry:\n"
                "<code>TELEGRAM | 🇧🇩 Bangladesh | 88017,88018</code>\n"
                "<code>WHATSAPP | BD | 88019</code>\n"
                "<code>FACEBOOK, INDIA, 9198</code>\n\n"
                "<i>Range না দিলেও চলবে — <code>SERVICE | COUNTRY</code> লিখলেই "
                "country যোগ হবে। দেশের নাম বা ISO code (BD/IN) দুটোই চলবে।</i>",
                _svcat_cb(idx, "root"),
            )

        elif action == "srv" and len(tokens) >= 1:
            _svcat_render_service(chat_id, msg_id, idx, tokens[0])

        elif action == "addcnt" and len(tokens) >= 1:
            srv = _svcat_resolve(catalog.keys(), tokens[0])
            if srv is None:
                answer_callback(call["id"], "❌ Service বদলে গেছে", show_alert=True)
                _svcat_render_root(chat_id, msg_id, idx)
            else:
                _svcat_prompt(
                    chat_id, msg_id, idx, "wait_svcat_country",
                    f"🌍 <b>Country name</b> for <b>{html.escape(srv)}</b>\n"
                    "➡️ যেমন: <code>BD</code>, <code>INDIA</code>, "
                    "<code>🇧🇩 Bangladesh</code>\n\n"
                    "<i>ISO code / সাধারণ নাম দিলে /rent এ countryCode ঠিকমতো যাবে।</i>",
                    _svcat_cb(idx, "srv", srv),
                    {"srv": srv},
                )

        elif action == "cnt" and len(tokens) >= 2:
            _svcat_render_country(chat_id, msg_id, idx, tokens[0], tokens[1])

        elif action == "addrng" and len(tokens) >= 2:
            srv = _svcat_resolve(catalog.keys(), tokens[0])
            cnt = None if srv is None else _svcat_resolve(catalog.get(srv, {}).keys(), tokens[1])
            if srv is None or cnt is None:
                answer_callback(call["id"], "❌ Entry বদলে গেছে", show_alert=True)
                _svcat_render_root(chat_id, msg_id, idx)
            else:
                _svcat_prompt(
                    chat_id, msg_id, idx, "wait_svcat_range",
                    f"🔢 <b>Range prefix</b> for <b>{html.escape(cnt)}</b>\n"
                    "➡️ যেমন: <code>88017</code> — একাধিক হলে comma দাও: "
                    "<code>88017,88018</code>\n"
                    "➡️ Range ছাড়াই রাখতে <code>skip</code> লিখো।\n\n"
                    "<i>এই prefix গুলো <code>/rent</code> API-তে rangePrefix হিসেবে যায়।</i>",
                    _svcat_cb(idx, "cnt", srv, cnt),
                    {"srv": srv, "cnt": cnt},
                )

        elif action == "delrng" and len(tokens) >= 3:
            srv = _svcat_resolve(catalog.keys(), tokens[0])
            cnt = None if srv is None else _svcat_resolve(catalog.get(srv, {}).keys(), tokens[1])
            rng = None if cnt is None else _svcat_resolve(catalog.get(srv, {}).get(cnt, []), tokens[2])
            if srv is None or cnt is None or rng is None:
                answer_callback(call["id"], "❌ Range বদলে গেছে", show_alert=True)
                _svcat_render_root(chat_id, msg_id, idx)
            else:
                catalog[srv][cnt] = [x for x in catalog[srv][cnt] if str(x) != str(rng)]
                p["catalog"] = catalog
                save_db()
                answer_callback(call["id"], f"✅ Range {rng} deleted", show_alert=False)
                _svcat_render_country(chat_id, msg_id, idx, srv, cnt)

        elif action == "delsrv" and len(tokens) >= 1:
            srv = _svcat_resolve(catalog.keys(), tokens[0])
            if srv is None:
                answer_callback(call["id"], "❌ Service বদলে গেছে", show_alert=True)
            else:
                catalog.pop(srv, None)
                p["catalog"] = catalog
                save_db()
                answer_callback(call["id"], f"✅ {srv} deleted", show_alert=False)
            _svcat_render_root(chat_id, msg_id, idx)

        elif action == "delcnt" and len(tokens) >= 2:
            srv = _svcat_resolve(catalog.keys(), tokens[0])
            cnt = None if srv is None else _svcat_resolve(catalog.get(srv, {}).keys(), tokens[1])
            if srv is None or cnt is None:
                answer_callback(call["id"], "❌ Country বদলে গেছে", show_alert=True)
                _svcat_render_root(chat_id, msg_id, idx)
            else:
                catalog.get(srv, {}).pop(cnt, None)
                p["catalog"] = catalog
                save_db()
                answer_callback(call["id"], f"✅ {cnt} deleted", show_alert=False)
                _svcat_render_service(chat_id, msg_id, idx, srv)

        else:
            answer_callback(call["id"], "⚠️ Unknown catalog action", show_alert=True)
        return

    elif data.startswith("slvn_cat_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            if _is_slvn_panel(p) and _slvn_catalog_mode(p) == "manual":
                _catalog_now = _slvn_catalog(p)
                _s, _c, _r = _svcat_counts(_catalog_now)
                save_db()
                send_message(chat_id, render_body_text(
                    "✍️ <b>MANUAL catalog mode</b>\n"
                    f"<b>{_s}</b> service · <b>{_c}</b> country · <b>{_r}</b> range\n\n"
                    "<i>live-console call করা হয়নি। নিচের বাটন দিয়ে list edit করো।</i>"
                ), reply_markup={"inline_keyboard": [[
                    {"text": "✍️ Manage Manual Catalog",
                     "icon_custom_emoji_id": "5192739271886282680",
                     "callback_data": _svcat_cb(idx, "root"), "style": "success"}
                ]]})
                edit_message(chat_id, msg_id, render_body_text(_panel_config_text(p)),
                             reply_markup=panel_config_keyboard(idx))
                return
            send_message(chat_id, render_body_text("⏳ Catalog লোড হচ্ছে..."))
            catalog = _slvn_catalog(p, force=True)
            save_db()
            if catalog:
                lines = []
                for svc, countries in list(catalog.items())[:12]:
                    lines.append(f"• <b>{html.escape(str(svc))}</b>: "
                                 + ", ".join(html.escape(str(c)) for c in list(countries)[:6]))
                send_message(chat_id, render_body_text(
                    f"✅ <b>Catalog loaded</b> — {len(catalog)} service(s)\n\n" + "\n".join(lines)
                    + "\n\n<i>Ei service/country gulo GET NUMBER menu তে দেখাবে.</i>"))
            else:
                send_message(chat_id, render_body_text(
                    f"❌ <b>Catalog খালি</b>\n{html.escape(str(p.get('catalog_status', '')))}\n\n"
                    "<i>API key ঠিক আছে কিনা দেখো, অথবা Test Connection চালাও.</i>"))
            edit_message(chat_id, msg_id, render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("slvn_cancel_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            done, total = _slvn_cancel_all(p)
            save_db()
            answer_callback(call["id"], f"Cancelled {done}/{total} rental(s)", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("set_charge_"):
        idx = int(data.split("_")[2])
        user_states[chat_id] = "wait_for_j_charge"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text(
            "💰 <b>Number Charge</b>\n➡️ প্রতি number এর জন্য user এর balance থেকে কত TK কাটবে?\n\n"
            "<code>0</code> = FREE (কিছু কাটবে না)\n<i>যেমন: 2 লিখলে প্রতি number এ 2 TK কাটবে.</i>"),
            reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("set_hold_"):
        idx = int(data.split("_")[2])
        user_states[chat_id] = "wait_for_j_hold"
        temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
        edit_message(chat_id, msg_id, render_body_text("⏳ <b>Hold Time</b>\n➡️ Number টা কত মিনিট user এর কাছে থাকবে? (1-180)\n\n<i>এর মধ্যে OTP না এলে janitor নিজেই number cancel করবে.</i>"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("clr_tok_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["panels"]):
            p = bot_settings["panels"][idx]
            p["token"] = ""
            p["source_enabled"] = False
            p["status"] = "OFF"
            p["login_status"] = "⏳ Not tested yet"
            save_db()
            answer_callback(call["id"], "API key removed — panel OFF", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text(_panel_config_text(p)), reply_markup=panel_config_keyboard(idx))

    elif data.startswith("set_j_"):
        # 🌟 JSON API Panel field editors
        parts = data.split("_")
        j_suffix = parts[2] if len(parts) > 2 else ""
        try:
            idx = int(parts[3])
        except (IndexError, ValueError):
            answer_callback(call["id"], "❌ Invalid panel index")
            return
        if 0 <= idx < len(bot_settings["panels"]) and j_suffix in JSON_CALLBACK_STATES:
            state_name = JSON_CALLBACK_STATES[j_suffix]
            user_states[chat_id] = state_name
            temp_data[chat_id] = {"msg_id": msg_id, "p_idx": idx}
            edit_message(chat_id, msg_id, render_body_text(JSON_FIELD_PROMPTS.get(state_name, "📝 Send the value:")), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": f"conf_pnl_{idx}", "style": "danger"}]]})

    elif data.startswith("test_p_conn_"):
        idx = int(data.split("_")[3])
        p = bot_settings["panels"][idx]
        wait_msg = send_message(chat_id, render_body_text("⏳ Testing connection. Please wait..."))
        wait_msg_id = wait_msg.get("result", {}).get("message_id") if wait_msg else None
        answer_callback(call["id"])
        
        try:
            parsed = []
            raw_text = ""
            
            if p["type"] == "Auto Captcha Panel":
                sess = panel_sessions.get(idx)
                if not sess:
                    success = attempt_auto_login(p, idx)
                    if not success:
                        if wait_msg_id: delete_message(chat_id, wait_msg_id)
                        send_message(chat_id, render_body_text(f"❌ <b>Auto Login Failed!</b>\nReason: {html.escape(str(p.get('login_status', 'Unknown')))}"))
                        return
                    sess = panel_sessions.get(idx)
                    
                login_url = p.get("login_url", "").strip()
                if not login_url.startswith("http"): login_url = "http://" + login_url
                msg_link = p.get("msg_link", "").strip()
                if not msg_link.startswith("http") and msg_link != "": msg_link = "http://" + msg_link
                check_url = msg_link if msg_link else f"{login_url.split('/login')[0]}/client/SMSCDRStats"
                
                # 🌟 test connection supports sAjaxSource & HTML table parser
                parsed, raw_text = fetch_cpt_panel_cdrs(p, sess, check_url)
                
            elif p.get("type") == JSON_PANEL_TYPE:
                # 🌟 JSON API Panel test: fetch + map using its own settings
                raw_text = fetch_json_panel_records(p)
                parsed = parse_json_api_panel(raw_text, p)
                p["login_status"] = "✅ Active & Fetching" if parsed else "⚠️ Connected, 0 records parsed"
                save_db()

            else:
                full_url = p.get("full_api_url", "").strip()
                url = p.get("api_url", "").strip()
                token = p.get("token", "").strip()
                if not full_url and not url:
                    if wait_msg_id: delete_message(chat_id, wait_msg_id)
                    send_message(chat_id, render_body_text("❌ Please Set API URL or Full API URL first!"))
                    return
                
                urls_to_try = []
                if full_url:
                    urls_to_try.append(full_url)
                else:
                    if "{token}" in url or "{key}" in url:
                        urls_to_try.append(url.replace("{token}", token).replace("{key}", token))
                    elif "token=" in url or "key=" in url:
                        urls_to_try.append(url)
                    else:
                        sep = '&' if '?' in url else '?'
                        urls_to_try.append(f"{url}{sep}token={token}")
                        urls_to_try.append(f"{url}{sep}key={token}&start=0")
                        urls_to_try.append(f"{url}{sep}key={token}")
                    
                parsed = []
                raw_text = ""
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                for try_url in urls_to_try:
                    try:
                        res = requests.get(try_url, headers=headers, timeout=10)
                        raw_text = res.text
                        parsed = parse_panel_response(raw_text, p)
                        if parsed:
                            if not full_url and try_url != url and token:
                                p["api_url"] = try_url.replace(token, "{token}")
                                save_db()
                            break
                    except: pass
                 
            if wait_msg_id: delete_message(chat_id, wait_msg_id)
                 
            if parsed:
                txt = f"✅ <b>Connection Successful!</b>\n\n🎯 <b>Parsed Data Sample (Max 3):</b>\n\n"
                
                for i, sample in enumerate(parsed[:3]):
                    num = sample['number']
                    msg = sample['message']
                    otp = sample['otp']
                    
                    detected_app = detect_service(msg)
                    app_name = detected_app if detected_app else p.get("name", "Unknown")
                    app_full_name, prem_app_html = get_service_info_html(app_name, msg)
                    
                    txt += f"<b>{i+1}.</b> {prem_app_html} <b>{app_full_name}</b>\n"
                    txt += f"📱 Number: <code>{num}</code>\n"
                    txt += f"📝 Full Msg: <code>{html.escape(msg)}</code>\n"
                    txt += f"🔐 OTP: <code>{otp}</code>\n"
                    txt += "➖" * 12 + "\n"
                    
                send_message(chat_id, render_body_text(txt))
            else:
                if p["type"] == "Auto Captcha Panel":
                    try:
                        soup = BeautifulSoup(raw_text, 'html.parser')
                        tables = soup.find_all('table')
                        if tables:
                            full_table_data = "🔍 FULL TABLE DATA (A-Z)\n" + "="*50 + "\n\n"
                            for t_idx, table in enumerate(tables):
                                full_table_data += f"--- Table {t_idx+1} ---\n"
                                rows = table.find_all('tr')
                                for r_idx, row in enumerate(rows):
                                    cols = row.find_all(['th', 'td'])
                                    col_texts = [f"[{c_idx+1}] {c.get_text(separator=' ', strip=True)}" for c_idx, c in enumerate(cols)]
                                    full_table_data += f"Row {r_idx+1}: {' | '.join(col_texts)}\n"
                                full_table_data += "\n" + "="*50 + "\n"
                            
                            send_document(chat_id, f"Full_Panel_Data_{idx}.txt", full_table_data.encode('utf-8'))
                            fail_txt = f"⚠️ <b>Connected, but couldn't parse OTP data!</b>\n\n<i>আমি ওই লিংকের সম্পূর্ণ (A-Z) ডাটা একটি Text File এ পাঠিয়েছি। ফাইলটি ওপেন করে সঠিক Column Number (যেমন: [1], [3]) চেক করে প্যানেলে আপডেট করে নাও।</i>"
                            send_message(chat_id, render_body_text(fail_txt))
                        else:
                            send_message(chat_id, render_body_text(f"⚠️ <b>Connected, but no HTML Table found!</b>\nMake sure the message link is correct."))
                    except Exception as e:
                        send_message(chat_id, render_body_text(f"❌ <b>Error parsing HTML:</b> {html.escape(str(e))}"))
                else:
                    safe_html = html.escape(str(raw_text)[:300])
                    send_message(chat_id, render_body_text(f"⚠️ <b>Connected, but couldn't find/parse OTP data.</b>\n\n<i>Make sure your API config is correct.</i>\n\nRaw HTML/Data (excerpt):\n<code>{safe_html}...</code>"))
        except Exception as e:
            if wait_msg_id: delete_message(chat_id, wait_msg_id)
            send_message(chat_id, render_body_text(f"❌ <b>Connection Failed!</b>\nError: {html.escape(str(e))}"))

    elif data == "ariyan_control":
        if chat_id in user_states: del user_states[chat_id]
        edit_message(chat_id, msg_id, render_body_text("🕹 <b>Ariyan Control Panel</b>"), reply_markup=ariyan_control_keyboard())

    elif data == "developer_info":
        callback_user_id = call.get("from", {}).get("id", chat_id)
        if not is_admin(callback_user_id):
            answer_callback(call["id"], "🚫 Admin only!", show_alert=True)
            return
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        edit_message(
            chat_id,
            msg_id,
            developer_info_text(),
            reply_markup=developer_info_keyboard(),
        )

    elif data == "ariyan_toggle_w":
        bot_settings["withdraw_on"] = not bot_settings["withdraw_on"]
        save_db()
        edit_message(chat_id, msg_id, render_body_text("🕹 <b>Ariyan Control Panel</b>"), reply_markup=ariyan_control_keyboard())

    elif data == "manage_w_methods":
        edit_message(chat_id, msg_id, render_body_text("💳 <b>WITHDRAWAL METHODS</b>\n\nManage your withdrawal methods below:"), reply_markup=w_methods_keyboard())

    elif data == "add_wm":
        user_states[chat_id] = "wait_for_add_wm"
        temp_data[chat_id] = {"msg_id": msg_id}
        edit_message(chat_id, msg_id, render_body_text("📝 Send the name of the new Withdrawal Method:"), reply_markup={"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "manage_w_methods", "style": "danger"}]]})

    elif data.startswith("del_wm_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(bot_settings["w_methods"]):
            del bot_settings["w_methods"][idx]
            save_db()
            answer_callback(call["id"], "✅ Method deleted!", show_alert=True)
            edit_message(chat_id, msg_id, render_body_text("💳 <b>WITHDRAWAL METHODS</b>\n\nManage your withdrawal methods below:"), reply_markup=w_methods_keyboard())

    elif data.startswith("ariyan_"):
        key = data.replace("ariyan_", "")
        key_map = {"min_w": "min_withdraw", "otp_r": "otp_reward", "ref_r": "refer_reward", "cool": "cooldown", "num_req": "num_req", "num_share": "num_share", "sup_link": "support_link", "w_group": "w_group"}
        if key in key_map:
            temp_data[chat_id] = {"msg_id": msg_id, "key": key_map[key]}
            user_states[chat_id] = "set_ariyan"
            cancel_kb = {"inline_keyboard": [[{"text": "Cancel", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "cancel_ariyan_edit", "style": "danger"}]]}
            edit_message(chat_id, msg_id, render_body_text(f"📝 Please send the new value for <code>{key_map[key]}</code>:"), reply_markup=cancel_kb)
            answer_callback(call["id"])

    elif data.startswith("g_s_") or data.startswith("num_service:"):
        if data.startswith("num_service:"):
            decoded = _decode_number_choice(data) or {}
            service = decoded.get("service", "")
        else:
            service = data.split("g_s_", 1)[1]

        service_entry = _unified_number_catalog().get(_number_catalog_key(service), {})
        service = service_entry.get("label", service)
        countries = service_entry.get("countries", {})
        
        c_msg = bot_settings["custom_messages"].get("select_country", {})
        raw_txt = c_msg.get("text", "📌 Select a country for {service}:").replace("{service}", service)
        txt = render_body_text(raw_txt)
        
        country_buttons = []
        for country_entry in sorted(countries.values(), key=lambda item: item["label"].casefold()):
            c = country_entry["label"]
            label, emoji_id = _catalog_button_label(c, "country")
            button = {
                "text": label,
                "callback_data": _number_choice_callback("country", service, c),
                "style": "success",
            }
            if emoji_id:
                button["icon_custom_emoji_id"] = emoji_id
            country_buttons.append(button)

        # Country buttons: exactly two per row; custom/action buttons stay on
        # their own rows below the country grid.
        kb = _two_column_inline_keyboard(country_buttons)
        for b in c_msg.get("buttons", []): 
            b_copy = b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
        kb.append([{"text": "Back", "icon_custom_emoji_id": "5267490665117275176", "callback_data": "close_msg", "style": "danger"}])
        edit_message(chat_id, msg_id, txt, reply_markup={"inline_keyboard": kb})

    elif (
        data.startswith("g_c_")
        or data.startswith("c_n_")
        or data.startswith("num_country:")
        or data.startswith("num_get:")
    ):
        # ১. গ্লোবাল কুলডাউন চেক (সকল নাম্বার মেথডের জন্য)
        now = time.time()
        if now - user_cooldowns.get(chat_id, 0) < bot_settings["cooldown"]:
            answer_callback(call["id"], f"⌛ Please wait {int(bot_settings['cooldown'] - (now - user_cooldowns.get(chat_id, 0)))}s.", show_alert=True)
            return
        
        # কুলডাউন আপডেট
        user_cooldowns[chat_id] = now
        
        # আগের নাম্বার এক্সপায়ার করা
        expire_previous_number(chat_id)

        # যদি সার্চ নাম্বার থেকে আসে
        if data.startswith("c_n_s_"):
            is_voltx_req = data.endswith("_vtx")
            clean_data = data[:-4] if is_voltx_req else data
            parts_s = clean_data.split("_", 4)
            
            query = parts_s[3] if len(parts_s) > 3 else ""
            service_from_cb = parts_s[4] if len(parts_s) > 4 else None
            
            allowed_countries = bot_settings.get("search_countries", [])
            voltx_allowed = bot_settings.get("voltx_search_countries", [])
            
            is_stex_allowed = any(query.startswith(c) for c in allowed_countries) if allowed_countries else False
            is_voltx_allowed = any(query.startswith(c) for c in voltx_allowed) if voltx_allowed else False
            
            if not is_voltx_req and not is_stex_allowed and not is_voltx_allowed:
                answer_callback(call["id"], "❌ This country code is not allowed for search!", show_alert=True)
                return
                
            edit_message(chat_id, msg_id, render_body_text("⌛ <i>Processing... Finding Number...</i>"))
            wait_msg_id = msg_id
            
            found_indices = []
            for b_id, b_data in number_batches.items():
                for idx, n_obj in enumerate(b_data["numbers"]):
                    if n_obj["num"].replace("+", "").startswith(query) and chat_id not in n_obj.get("used_by", []):
                        found_indices.append((b_id, idx))
            
            fetched_nums = []
            if not found_indices:
                api_found = False
                if is_voltx_req:
                    provider_order = ["voltx"]
                else:
                    provider_order = []
                    if is_stex_allowed:
                        provider_order.append("stex")
                    if is_voltx_allowed:
                        provider_order.append("voltx")

                # Try the selected provider first, then fall back to the
                # other configured provider instead of stopping after one
                # empty/error response.
                for provider in provider_order:
                    keys = bot_settings.get(
                        "voltx_keys" if provider == "voltx" else "stex_keys", []
                    )
                    for _ in range(bot_settings.get("num_req", 1) - len(fetched_nums)):
                        if len(fetched_nums) >= bot_settings.get("num_req", 1):
                            break
                        for api_key in keys:
                            num_str = _legacy_panel_get_number(provider, api_key, query)
                            if not num_str:
                                continue
                            fetched_nums.append(num_str)
                            if provider == "voltx":
                                voltx_assigned_numbers[num_str] = chat_id
                            else:
                                stex_assigned_numbers[num_str] = chat_id
                            api_found = True
                            global total_assigned_stats
                            total_assigned_stats += 1
                            break
                        if len(fetched_nums) >= bot_settings.get("num_req", 1):
                            break
                    if len(fetched_nums) >= bot_settings.get("num_req", 1):
                        break
                        
                if not api_found:
                    answer_callback(call["id"], "❌ Number out of stock!", show_alert=True)
                    delete_message(chat_id, wait_msg_id)
                    return
                save_db()
            else:
                random.shuffle(found_indices)
                for b_id, idx in found_indices:
                    if len(fetched_nums) >= bot_settings.get("num_req", 1): break
                    n_obj = number_batches[b_id]["numbers"][idx]
                    num_str = n_obj["num"]
                    fetched_nums.append(num_str)
                    n_obj["shares"] += 1
                    n_obj["used_by"].append(chat_id)
                    total_assigned_stats += 1
                    if n_obj["shares"] >= bot_settings.get("num_share", 1):
                        n_obj["to_remove"] = True
                        used_numbers_list.append(num_str)
                for b_id in number_batches:
                    number_batches[b_id]["numbers"] = [n for n in number_batches[b_id]["numbers"] if not n.get("to_remove")]
                save_db()
                
            flags_db = bot_settings.get("premium_flags", {})
            kb = []
            num_lines = []
            show_cc = bool(number_display_preferences.get(chat_id, True))
            srv_header = ""
            if service_from_cb:
                app_full_name, prem_app_html_h = get_service_info_html(service_from_cb)
                srv_header = f"{prem_app_html_h} <b>{app_full_name}</b>\n"

            for num in fetched_nums:
                _, iso = get_flag_and_code(num)
                display_num = _display_api_number(num, show_cc=show_cc)
                flag_html = get_flag_info_html(num)
                num_lines.append(f"{flag_html} <code>{display_num}</code>")
                emoji_id = "5780471598922337683"
                for flag_code, flag_data in flags_db.items():
                    if iso == flag_data.get("iso"):
                        if "id" in flag_data: emoji_id = flag_data["id"]; break
                kb.append([_number_copy_button(display_num, service_from_cb)])

            vtx_ext = "_vtx" if is_voltx_req else ""
            srv_ext = f"_{service_from_cb}" if service_from_cb else ""
            ch_cntry_cb = f"g_s_{service_from_cb}" if service_from_cb else "get_number_menu"

            kb.append([{
                "text": "Remove CC" if show_cc else "Add CC",
                "icon_custom_emoji_id": (
                    "5422557736330106570" if show_cc
                    else "5420396762189831222"
                ),
                "callback_data": "toggle_classic_cc",
                "style": "danger" if show_cc else "success",
            }])
            kb.append([{
                "text": "Change Number",
                "icon_custom_emoji_id": "5465368548702446780",
                "callback_data": f"c_n_s_{query}{srv_ext}{vtx_ext}",
                "style": "success",
            }])
            kb.append([{
                "text": "Change Country",
                "icon_custom_emoji_id": "5336972142066047577",
                "callback_data": ch_cntry_cb,
                "style": "primary",
            }])
            kb.append([_otp_group_button()])

            c_btns = bot_settings["custom_messages"].get("search_number", {}).get("buttons", [])
            for c_b in c_btns:
                b_copy = c_b.copy()
                if "style" not in b_copy: b_copy["style"] = "primary"
                kb.append([b_copy])
            

            num_text = _imran_number_result_text(num_lines, srv_header, numbers=fetched_nums)
            edit_message(chat_id, wait_msg_id, num_text, reply_markup={"inline_keyboard": kb})
            user_active_sessions[chat_id] = {
                "msg_id": wait_msg_id,
                "nums": fetched_nums,
                "show_cc": show_cc,
                "service": service_from_cb or app_full_name,
                "header": srv_header,
                "country_callback": ch_cntry_cb,
                "change_callback": f"c_n_s_{query}{srv_ext}{vtx_ext}",
            }
            return

        # Selected service/country-এর matching local stock বা panel থেকে
        # number নেওয়া হবে; একই country একাধিক source-এ থাকলে fallback হবে।
        if data.startswith("num_country:") or data.startswith("num_get:"):
            decoded = _decode_number_choice(data) or {}
            service = decoded.get("service", "")
            country = decoded.get("country", "")
        else:
            parts = data.split("_", 3)
            service = parts[2]
            country = parts[3]

        requested_count = max(1, int(bot_settings.get("num_req", 1)))
        fetched_nums = _fetch_priority_get_number_api_numbers(
            service, country, chat_id, requested_count
        )

        if not fetched_nums:
            _reason = globals().get("last_number_source_error", "")
            answer_callback(
                call["id"],
                "❌ Number out of stock or range missing!",
                show_alert=True,
            )
            if _reason:
                send_message(chat_id, render_body_text(_reason))
                globals()["last_number_source_error"] = ""
            if data.startswith("c_n_"): delete_message(chat_id, msg_id)
            return

        save_db()

        app_full_name, prem_app_html_loc = get_service_info_html(service)
        emoji_id = "5337302974806922068"
        apps_db = bot_settings.get("premium_apps", {})
        for app_key, app_data in apps_db.items():
            if service.upper() == app_key or service.upper() in app_key or app_key in service.upper():
                if "id" in app_data:
                    emoji_id = app_data["id"]
                    break

        flags_db = bot_settings.get("premium_flags", {})
        kb = []
        num_lines = []
        show_cc = bool(number_display_preferences.get(chat_id, True))
        selected_flag_html = (
            get_flag_info_html(country) if _premium_flag_for_label(country) else ""
        )
        for num in fetched_nums:
            _, iso = get_flag_and_code(num)
            display_num = _display_api_number(num, show_cc=show_cc)
            flag_html = selected_flag_html or get_flag_info_html(num)
            num_lines.append(f"{flag_html} <code>{display_num}</code>")
            emoji_id_f = "5780471598922337683"
            for flag_code, flag_data in flags_db.items():
                if iso == flag_data.get("iso"):
                    if "id" in flag_data: emoji_id_f = flag_data["id"]
                    break
            kb.append([_number_copy_button(display_num, service)])

        kb.append([{
            "text": "Remove CC" if show_cc else "Add CC",
            "icon_custom_emoji_id": (
                "5422557736330106570" if show_cc
                else "5420396762189831222"
            ),
            "callback_data": "toggle_classic_cc",
            "style": "danger" if show_cc else "success",
        }])
        kb.append([{
            "text": "Change Number",
            "icon_custom_emoji_id": "5465368548702446780",
            "callback_data": _number_choice_callback("get", service, country),
            "style": "success",
        }])
        kb.append([{
            "text": "Change Country",
            "icon_custom_emoji_id": "5336972142066047577",
            "callback_data": _number_choice_callback("service", service),
            "style": "primary",
        }])
        kb.append([_otp_group_button()])
                   
        c_btns = bot_settings["custom_messages"].get("get_number", {}).get("buttons", [])
        for c_b in c_btns: 
            b_copy = c_b.copy()
            if "style" not in b_copy: b_copy["style"] = "primary"
            kb.append([b_copy])
        text_numbers = _imran_number_result_text(
            num_lines,
            f"{prem_app_html_loc} <b>{app_full_name}</b>",
            numbers=fetched_nums,
            country=country,
        )
        # Always show the allocated number.  If Telegram rejects the edit,
        # send the result as a new message instead of leaving "Processing..."
        # without the Change Country / Change Number / OTP Group controls.
        _result, active_message_id = _deliver_number_result(
            chat_id,
            text_numbers,
            reply_markup={"inline_keyboard": kb},
            message_id=msg_id,
        )
        if active_message_id:
            user_active_sessions[chat_id] = {
                "msg_id": active_message_id,
                "nums": fetched_nums,
                "show_cc": show_cc,
                "service": service,
                "country": country,
                "header": f"{prem_app_html_loc} <b>{app_full_name}</b>\n",
                "country_callback": _number_choice_callback("service", service),
                "change_callback": _number_choice_callback("get", service, country),
            }

    elif data.startswith("wapp_") or data.startswith("wrej_"):
        # অ্যাডমিন চেক (User ID চেক করতে হবে)
        user_id_clicked = call["from"]["id"]
        if not is_admin(user_id_clicked):
            answer_callback(call["id"], "🚫 Only Bot Admins can process withdrawals!", show_alert=True)
            return
            
        action = "APPROVE" if data.startswith("wapp_") else "REJECT"
        req_id = data.replace("wapp_", "").replace("wrej_", "")
        
        if req_id in pending_withdrawals:
            req_data = pending_withdrawals[req_id]
            u_id, amt = req_data["user_id"], req_data["amount"]
            num = req_data["number"]
            full_name = req_data.get("full_name", u_id)
            
            if action == "APPROVE" and len(num) >= 7:
                masked_num = f"{num[:4]}❖Ariyan❖{num[-3:]}"
            else:
                masked_num = num
            
            status_text = "APPROVED" if action == "APPROVE" else "REJECTED"
            emoji_icon_id = "5352694861990501856" if action == "APPROVE" else "5420130255174145507"
            new_text = f"🎙 <b>WITHDRAWAL {status_text}</b>\n\n👤 <b>USER:</b> <a href='tg://user?id={u_id}'>{full_name}</a>\n💳 <b>WITHDRAWAL:</b> {amt} TK\n🍏 <b>NUMBER:</b> <code>{masked_num}</code>\n🏦 <b>METHOD:</b> {req_data['method']}\n\n🧾 <b>REQ ID:</b> {req_id}\n👨‍⚖️ <b>PROCESSED BY ADMIN</b>"
            
            kb = {"inline_keyboard": [[{"text": status_text, "icon_custom_emoji_id": emoji_icon_id, "callback_data": "ignore", "style": "success" if action == "APPROVE" else "danger"}]]}
            edit_message(chat_id, msg_id, render_body_text(new_text), reply_markup=kb)
            
            if action == "REJECT":
                update_balance(u_id, amt) 
                send_message(u_id, render_body_text(f"❌ Your {amt} TK withdrawal request was rejected. Balance refunded."))
            else:
                send_message(u_id, render_body_text(f"{PEM['ok']} Your {amt} TK withdrawal request has been paid successfully!"))
            
            if db:
                try: db.collection('withdrawals').document(req_id).update({"status": "approved" if action == "APPROVE" else "rejected"})
                except: pass
                
            del pending_withdrawals[req_id]
        else:
            answer_callback(call["id"], "❌ Request already processed!", show_alert=True)

# ==========================================
# Polling Loop
# ==========================================
def poll_otp_with_status(number_id, num_str, owner_id, api_key):
    headers = {"X-API-Key": api_key}
    for _ in range(150): # 150 * 4 seconds = 10 Minutes Polling
        try:
            stex_base = bot_settings.get("stex_base_url") or STEX_BASE_URL
            res = requests.get(f"{str(stex_base).rstrip('/')}/api/v1/numbers/{number_id}/sms", headers=headers, timeout=10)
            data = res.json()
            if data.get("success") and data.get("otp"):
                otp = str(data["otp"])
                msg_text = data.get("message", f"Your code is {otp}")
                
                # 🌟 সম্পূর্ণ মেসেজ থেকে ড্যাশসহ বা বড় OTP খোঁজার ফিক্স
                extracted_otp = extract_otp_code(msg_text)
                if extracted_otp and len(extracted_otp) > len(otp):
                    otp = extracted_otp
                    
                # 🌟 সম্পূর্ণ মেসেজ থেকে সার্ভিস/অ্যাপ চেনার ফিক্স
                app_name = data.get("service", "StexSMS Service")
                detected_app = detect_service(msg_text)
                if detected_app:
                    app_name = detected_app
                
                unique_id = f"POLL_{number_id}_{otp}"
                if unique_id not in processed_otps:
                    processed_otps.add(unique_id)
                    
                    char, iso = get_flag_and_code(num_str)
                    app_full_name, prem_app_html = get_service_info_html(app_name, msg_text)
                    
                    global recent_traffic
                    current_time = time.time()
                    if _number_has_get_number_owner(num_str):
                        recent_traffic = [t for t in recent_traffic if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS]
                        recent_traffic.append({"source": "GET NUMBER", "service": app_full_name, "iso": iso, "flag": char, "number": num_str, "time": current_time})
                        save_local_db()
                    
                    display_num = f"+{num_str}" if not str(num_str).startswith("+") else str(num_str)
                    masked = mask_number(display_num)
                    lang = detect_language(msg_text)
                    
                    display_msg = render_body_text(f"╔═══════════════╗\n║ {prem_app_html} {get_flag_info_html(display_num)} {masked} {lang}\n╚═══════════════╝")
                    
                    for fw in bot_settings.get("fw_groups", []):
                        kb = _legacy_group_keyboard(
                            fw, otp, num_str, "stex", app_name,
                            _country_code_from_number(num_str)
                        )
                        send_message(fw["chat_id"], display_msg, reply_markup={"inline_keyboard": kb})
                    
                    inbox_msg = _format_user_otp_inbox_message(display_num)
                    inbox_kb = [[{"text": f"{otp}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": otp}, "style": "success"}]]
                    
                    reward = float(bot_settings.get("otp_reward", 0.0))
                    if reward > 0:
                        update_balance(owner_id, reward)
                        inbox_kb.append([{"text": f"Added {reward} tk", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "ignore", "style": "primary"}])
                    
                    _record_user_history(owner_id, display_num, otp, reward, app_full_name, "GET NUMBER")
                    send_message(owner_id, inbox_msg, reply_markup={"inline_keyboard": inbox_kb})
                    
                    if db:
                        try: db.collection('users').document(str(owner_id)).update({"total_otps": local_increment(1)})
                        except: pass
                break
        except: pass
        time.sleep(4)

def voltx_sms_listener():
    global processed_otps, recent_traffic, voltx_assigned_numbers
    while True:
        try:
            voltx_keys = bot_settings.get("voltx_keys", [])
            for api_key in voltx_keys:
                try:
                    headers = {"mauthapi": api_key}
                    voltx_base = bot_settings.get("voltx_base_url") or VOLTX_BASE_URL
                    res = requests.get(f"{str(voltx_base).rstrip('/')}/success-otp", headers=headers, timeout=10)
                    resp_data = res.json()
                    
                    if resp_data.get("meta", {}).get("code") == 200 and "data" in resp_data and "otps" in resp_data["data"]:
                        for item in resp_data["data"]["otps"]:
                            num = str(item.get("number", "")).replace("+", "")
                            msg_text = str(item.get("message", ""))
                            otp = extract_otp_code(msg_text) or "CODE"
                            otp_id = str(item.get("otp_id", otp))
                            
                            app_name = "Voltx Service"
                            detected_app = detect_service(msg_text)
                            if detected_app: app_name = detected_app
                                
                            unique_id = f"VOLTX_{num}_{otp_id}"
                            
                            if unique_id not in processed_otps and num:
                                processed_otps.add(unique_id)
                                if len(processed_otps) > 5000: processed_otps.clear()
                                
                                char, iso = get_flag_and_code(num)
                                app_full_name, prem_app_html = get_service_info_html(app_name, msg_text)
                                current_time = time.time()
                                
                                if _number_has_get_number_owner(num):
                                    recent_traffic = [t for t in recent_traffic if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS]
                                    recent_traffic.append({"source": "GET NUMBER", "service": app_full_name, "iso": iso, "flag": char, "number": num, "time": current_time})
                                    save_local_db()
                                
                                display_num = f"+{num}" if not str(num).startswith("+") else str(num)
                                masked = mask_number(display_num)
                                lang = detect_language(msg_text)
                                
                                display_msg = render_body_text(f"╔═══════════════╗\n║ {prem_app_html} {get_flag_info_html(display_num)} {masked} {lang}\n╚═══════════════╝")
                                
                                for fw in bot_settings.get("fw_groups", []):
                                    kb = _legacy_group_keyboard(
                                        fw, otp, num, "voltx", app_name,
                                        _country_code_from_number(num)
                                    )
                                    send_message(fw["chat_id"], display_msg, reply_markup={"inline_keyboard": kb})
                                    
                                owner_id = None
                                clean_api_num = str(num).replace("+", "").replace(" ", "").replace("-", "").strip()
                                
                                for uid, session_data in user_active_sessions.items():
                                    for act_num in session_data.get("nums", []):
                                        act_clean = str(act_num).replace("+", "").replace(" ", "").replace("-", "").strip()
                                        if act_clean == clean_api_num or (len(act_clean) >= 8 and act_clean.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(act_clean[-8:])):
                                            owner_id = uid
                                            break
                                    if owner_id: break
                                    
                                if not owner_id:
                                    for vtx_n, n_owner in voltx_assigned_numbers.items():
                                        clean_vtx = str(vtx_n).replace("+", "").replace(" ", "").replace("-", "").strip()
                                        if clean_vtx == clean_api_num or (len(clean_vtx) >= 8 and clean_vtx.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(clean_vtx[-8:])):
                                            owner_id = n_owner
                                            break
                                        
                                if owner_id:
                                    inbox_msg = _format_user_otp_inbox_message(display_num)
                                    inbox_kb = [[{"text": f"{otp}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": otp}, "style": "success"}]]
                                    
                                    reward = float(bot_settings.get("otp_reward", 0.0))
                                    if reward > 0:
                                        update_balance(owner_id, reward)
                                        inbox_kb.append([{"text": f"Added {reward} tk", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "ignore", "style": "primary"}])
                                    
                                    _record_user_history(owner_id, display_num, otp, reward, app_full_name, "GET NUMBER")
                                    send_message(owner_id, inbox_msg, reply_markup={"inline_keyboard": inbox_kb})
                                    
                                    if db:
                                        try: db.collection('users').document(str(owner_id)).update({"total_otps": local_increment(1)})
                                        except: pass
                except: pass
        except: pass
        time.sleep(5)

def global_sms_listener():
    global processed_otps, recent_traffic, stex_assigned_numbers
    while True:
        try:
            stex_keys = bot_settings.get("stex_keys", [])
            for api_key in stex_keys:
                try:
                    headers = {"mauthapi": api_key}
                    stex_base = bot_settings.get("stex_base_url") or STEX_BASE_URL
                    res = requests.get(f"{str(stex_base).rstrip('/')}/success-otp", headers=headers, timeout=10)
                    resp_data = res.json()
                    
                    if resp_data.get("meta", {}).get("code") == 200 and "data" in resp_data and "otps" in resp_data["data"]:
                        for item in resp_data["data"]["otps"]:
                            num = str(item.get("number", "")).replace("+", "")
                            msg_text = str(item.get("message", ""))
                            otp = extract_otp_code(msg_text) or "CODE"
                            otp_id = str(item.get("otp_id", otp))
                            
                            app_name = "Stex Service"
                            detected_app = detect_service(msg_text)
                            if detected_app: app_name = detected_app
                                
                            unique_id = f"STEX_{num}_{otp_id}"
                            
                            if unique_id not in processed_otps and num:
                                processed_otps.add(unique_id)
                                if len(processed_otps) > 5000: processed_otps.clear()
                                
                                char, iso = get_flag_and_code(num)
                                app_full_name, prem_app_html = get_service_info_html(app_name, msg_text)
                                current_time = time.time()
                                
                                if _number_has_get_number_owner(num):
                                    recent_traffic = [t for t in recent_traffic if current_time - t.get("time", 0) <= TRAFFIC_WINDOW_SECONDS]
                                    recent_traffic.append({"source": "GET NUMBER", "service": app_full_name, "iso": iso, "flag": char, "number": num, "time": current_time})
                                    save_local_db()
                                
                                display_num = f"+{num}" if not str(num).startswith("+") else str(num)
                                masked = mask_number(display_num)
                                lang = detect_language(msg_text)
                                
                                display_msg = render_body_text(f"╔═══════════════╗\n║ {prem_app_html} {get_flag_info_html(display_num)} {masked} {lang}\n╚═══════════════╝")
                                
                                for fw in bot_settings.get("fw_groups", []):
                                    kb = _legacy_group_keyboard(
                                        fw, otp, num, "stex", app_name,
                                        _country_code_from_number(num)
                                    )
                                    send_message(fw["chat_id"], display_msg, reply_markup={"inline_keyboard": kb})
                                    
                                owner_id = None
                                clean_api_num = str(num).replace("+", "").replace(" ", "").replace("-", "").strip()
                                
                                for uid, session_data in user_active_sessions.items():
                                    for act_num in session_data.get("nums", []):
                                        act_clean = str(act_num).replace("+", "").replace(" ", "").replace("-", "").strip()
                                        if act_clean == clean_api_num or (len(act_clean) >= 8 and act_clean.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(act_clean[-8:])):
                                            owner_id = uid
                                            break
                                    if owner_id: break
                                    
                                if not owner_id:
                                    for stex_n, n_owner in stex_assigned_numbers.items():
                                        clean_stex = str(stex_n).replace("+", "").replace(" ", "").replace("-", "").strip()
                                        if clean_stex == clean_api_num or (len(clean_stex) >= 8 and clean_stex.endswith(clean_api_num[-8:])) or (len(clean_api_num) >= 8 and clean_api_num.endswith(clean_stex[-8:])):
                                            owner_id = n_owner
                                            break
                                        
                                if owner_id:
                                    inbox_msg = _format_user_otp_inbox_message(display_num)
                                    inbox_kb = [[{"text": f"{otp}", "icon_custom_emoji_id": "5353022963132174959", "copy_text": {"text": otp}, "style": "success"}]]
                                    
                                    reward = float(bot_settings.get("otp_reward", 0.0))
                                    if reward > 0:
                                        update_balance(owner_id, reward)
                                        inbox_kb.append([{"text": f"Added {reward} tk", "icon_custom_emoji_id": "5420396762189831222", "callback_data": "ignore", "style": "primary"}])
                                    
                                    _record_user_history(owner_id, display_num, otp, reward, app_full_name, "GET NUMBER")
                                    send_message(owner_id, inbox_msg, reply_markup={"inline_keyboard": inbox_kb})
                                    
                                    if db:
                                        try: db.collection('users').document(str(owner_id)).update({"total_otps": local_increment(1)})
                                        except: pass
                except: pass
        except: pass
        time.sleep(5)


# ==========================================
# API NUMBER + MK ONLINE SMS CONTROL
# ==========================================
# The existing DXnumbers flow remains unchanged. The old "Search Number"
# button is replaced in the menu by "API Number". API Number uses only
# authorized providers configured by the owner and the provider contract:
#   GET  {base_url}/api/liveaccess
#   POST {base_url}/api/getnum
#   GET  {base_url}/api/success-otp-info

API_RANGE_FILE = "api_ranges.json"
MK_PANEL_FILE = "mk_api_panels.json"
API_SESSION_TIMEOUT = 3600
api_range_lock = threading.RLock()
api_session_lock = threading.RLock()
api_number_sessions = {}
api_number_display_preferences = {}
api_range_cache = {}
api_seen_otps = set()
# Short-lived references used by the permanent GET NUMBER button that is
# attached to API OTP messages in forwarding groups.  The range and panel
# stay server-side instead of being exposed in Telegram callback_data.
api_group_getnum_tokens = {}
mk_panel_http = requests.Session()


def _legacy_panel_get_number(provider, api_key, range_id):
    """Request one number from the legacy StexSMS/Voltx contract."""
    provider = str(provider).lower()
    setting_key = "stex_base_url" if provider == "stex" else "voltx_base_url"
    configured_url = bot_settings.get(setting_key, "")
    base_url = configured_url or (STEX_BASE_URL if provider == "stex" else VOLTX_BASE_URL)
    base_url = str(base_url or "").rstrip("/")
    if not base_url:
        print(f"[{provider.upper()}] base URL is not configured")
        return ""
    try:
        response = requests.post(
            f"{base_url}/getnum",
            json={"rid": str(range_id)},
            headers={"mauthapi": str(api_key)},
            timeout=10,
        )
        payload = response.json()
        if response.ok and payload.get("meta", {}).get("code") == 200 and payload.get("data"):
            data = payload["data"]
            number = str(data.get("no_plus_number", "")).replace("+", "")
            return number or str(data.get("national_number", "")).replace("+", "")
        print(f"[{provider.upper()}] getnum returned HTTP {response.status_code}")
    except Exception as exc:
        print(f"[{provider.upper()}] getnum error: {type(exc).__name__}")
    return ""


def _safe_panel_id(value):
    clean = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value).strip()).strip("-")
    return (clean[:30] or "mk-panel")


def _normalise_mk_panel(raw, index=0):
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or f"MK Panel {index + 1}").strip()[:60]
    base_url = str(raw.get("base_url") or raw.get("url") or "").strip().rstrip("/")
    api_key = str(raw.get("api_key") or raw.get("token") or "").strip()
    if not base_url:
        return None
    protocol = str(raw.get("protocol") or raw.get("type") or "").strip().lower()
    # Existing MK records remain compatible.  NP Network records can also be
    # recognised during migration when the provider URL is self-describing.
    if protocol not in {"mk", "npnetwork"}:
        protocol = "npnetwork" if (
            "npsmsnetwork" in base_url.lower() or "route=user" in base_url.lower()
        ) else "mk"
    routes = []
    for route in raw.get("routes", []) if isinstance(raw.get("routes", []), list) else []:
        if not isinstance(route, dict):
            continue
        service = str(route.get("service") or "").strip().upper()
        country = str(route.get("country") or "").strip().upper()
        ranges = route.get("ranges", [])
        if isinstance(ranges, str):
            ranges = re.split(r"[,;\n]+", ranges)
        ranges = [str(value).strip().upper() for value in (ranges or []) if str(value).strip()]
        if service and country and ranges:
            routes.append({
                "service": service,
                "country": country,
                "ranges": list(dict.fromkeys(ranges)),
            })
    return {
        "id": _safe_panel_id(raw.get("id") or name),
        "name": name,
        "base_url": base_url,
        "api_key": api_key,
        "protocol": protocol,
        "enabled": bool(raw.get("enabled", True)),
        # Optional admin routing rules. When present for a service/country,
        # these ranges are used instead of the panel's liveaccess ranges.
        "routes": routes,
        "created_at": raw.get("created_at") or datetime.now().isoformat(),
    }


def _save_mk_panels(panels):
    cleaned, seen = [], set()
    for i, raw in enumerate(panels or []):
        p = _normalise_mk_panel(raw, i)
        if p and p["id"] not in seen:
            seen.add(p["id"])
            cleaned.append(p)
    temp = MK_PANEL_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)
    os.replace(temp, MK_PANEL_FILE)
    try:
        os.chmod(MK_PANEL_FILE, 0o600)
    except OSError:
        pass


def _load_mk_panels():
    if not os.path.exists(MK_PANEL_FILE):
        # Optional migration from environment variables. No credentials are
        # included in source code.
        panels = []
        env_base = os.environ.get("MK_API_BASE_URL", "").strip().rstrip("/")
        env_key = os.environ.get("MK_API_KEY", "").strip()
        if env_base:
            panels.append({"id": "mk-primary", "name": "MK Primary", "base_url": env_base, "api_key": env_key, "protocol": "mk", "enabled": True})
        np_base = os.environ.get("NP_API_BASE_URL", "").strip().rstrip("/")
        np_key = os.environ.get("NP_API_KEY", "").strip()
        if np_base:
            panels.append({"id": "np-primary", "name": "NP Network Primary", "base_url": np_base, "api_key": np_key, "protocol": "npnetwork", "enabled": True})
        _save_mk_panels(panels)
        return panels
    try:
        with open(MK_PANEL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [_normalise_mk_panel(x, i) for i, x in enumerate(data or []) if _normalise_mk_panel(x, i)]
    except Exception as e:
        print(f"[MK panels] load error: {e}")
        return []


def _mk_panels(enabled_only=False):
    panels = _load_mk_panels()
    return [p for p in panels if p["enabled"]] if enabled_only else panels


def _mk_panel(panel_id):
    return next((p for p in _mk_panels() if p["id"] == str(panel_id)), None)


def _mk_headers(panel):
    headers = {"Accept": "application/json"}
    if panel.get("api_key"):
        if panel.get("protocol") == "npnetwork":
            headers["mauthapi"] = panel["api_key"]
        else:
            headers["X-API-Key"] = panel["api_key"]
    return headers


def _mk_endpoint(panel, path):
    base = panel["base_url"].rstrip("/")
    clean_path = "/" + path.lstrip("/")
    # Accept either a site root or a base URL that already ends in /api.
    if base.lower().endswith("/api") and clean_path.lower().startswith("/api/"):
        clean_path = clean_path[4:]
    return f"{base}{clean_path}"


def _np_user_endpoint(panel, action=None):
    """Build the NP Network user API URL from root, /api, or route=user input."""
    base = str(panel.get("base_url", "")).strip().rstrip("/")
    lower = base.lower()
    if "route=user" in lower:
        endpoint = base
        separator = "&" if "?" in endpoint else "?"
    elif re.search(r"/api/(?:index\.php|user)$", lower):
        endpoint = base
        separator = "&" if "?" in endpoint else "?"
    elif lower.endswith("/api"):
        endpoint = f"{base}/index.php?route=user"
        separator = "&"
    else:
        endpoint = f"{base}/api/index.php?route=user"
        separator = "&"
    if action:
        return f"{endpoint}{separator}action={action}"
    return endpoint


def _api_liveaccess_services(payload):
    """Accept the MK response and the NP Network response shapes."""
    if not isinstance(payload, dict):
        return []
    candidates = []
    if isinstance(payload.get("services"), list):
        candidates.append(payload["services"])
    if isinstance(payload.get("result"), dict) and isinstance(payload["result"].get("services"), list):
        candidates.append(payload["result"]["services"])
    if isinstance(payload.get("liveaccess"), list):
        candidates.append(payload["liveaccess"])
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("services"), list):
        candidates.append(data["services"])
    if isinstance(data, dict) and isinstance(data.get("liveaccess"), list):
        candidates.append(data["liveaccess"])
    if isinstance(data, list):
        candidates.append(data)
    for services in candidates:
        result = []
        for service in services:
            if not isinstance(service, dict):
                continue
            ranges = service.get("ranges")
            if ranges is None and service.get("range") is not None:
                ranges = [service.get("range")]
            result.append({
                **service,
                "ranges": [str(x) for x in (ranges or []) if str(x).strip()],
            })
        if result:
            return result
    return []


def _api_service_name(item):
    if not isinstance(item, dict):
        return ""
    for key in (
        "service",
        "service_name",
        "service_id",
        "sid",
        "name",
        "app",
        "application",
    ):
        value = item.get(key)
        if isinstance(value, dict):
            value = (
                value.get("name")
                or value.get("service")
                or value.get("service_id")
                or value.get("sid")
                or value.get("id")
            )
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _api_country_values(item, range_text):
    """Return possible country labels for a liveaccess service record."""
    values = []
    for key in ("country", "country_name", "country_code", "iso", "iso_code"):
        value = item.get(key) if isinstance(item, dict) else None
        if isinstance(value, dict):
            value = value.get("name") or value.get("iso") or value.get("code")
        if value is not None and str(value).strip():
            values.append(str(value).strip())
    # Some NP liveaccess responses expose only a range.  Keeping that range as
    # the country selector still makes the number available from GET NUMBER.
    if not values and str(range_text).strip():
        values.append(str(range_text).strip())
    return values


def _api_catalog():
    """Build service -> country/range options from every enabled API panel."""
    catalog = {}
    for panel in _mk_panels(enabled_only=True):
        for route in panel.get("routes", []) or []:
            service = str(route.get("service", "")).strip()
            country = str(route.get("country", "")).strip()
            for range_text in route.get("ranges", []) or []:
                if service and country and str(range_text).strip():
                    catalog.setdefault(service, {}).setdefault(country, [])
                    if str(range_text) not in catalog[service][country]:
                        catalog[service][country].append(str(range_text))
        services = _api_liveaccess_services(_mk_json_get(panel, "/api/liveaccess") or {})
        for item in services:
            service = _api_service_name(item)
            if not service:
                continue
            for range_text in item.get("ranges", []) or []:
                for country in _api_country_values(item, range_text):
                    catalog.setdefault(service, {}).setdefault(country, [])
                    if str(range_text) not in catalog[service][country]:
                        catalog[service][country].append(str(range_text))
    return catalog


def _number_catalog_key(value):
    """Use one case-insensitive key for services and countries."""
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _catalog_callback(prefix, *values):
    """Encode service/country names so emoji and long names fit callbacks."""
    encoded = []
    for value in values:
        token = base64.urlsafe_b64encode(
            str(value).encode("utf-8")
        ).decode("ascii").rstrip("=")
        encoded.append(token)
    return f"{prefix}_e_" + ".".join(encoded)


def _catalog_callback_values(data, prefix, count):
    """Decode a new catalog callback, while old raw callbacks remain valid."""
    marker = f"{prefix}_e_"
    if not str(data).startswith(marker):
        return None
    values = str(data)[len(marker):].split(".")
    if len(values) != count:
        return None
    decoded = []
    try:
        for value in values:
            padded = value + ("=" * (-len(value) % 4))
            decoded.append(
                base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            )
    except Exception:
        return None
    return decoded


def _unified_number_catalog():
    """Merge local stock and every configured provider into one catalog.

    The user should see one service button even when that service exists in
    several panels and in uploaded stock. Countries are also de-duplicated,
    while the source list is retained so the allocator can still use the
    correct provider after a country is selected.
    """
    catalog = {}

    def add(service, country, source):
        service = str(service or "").strip()
        country = str(country or "").strip()
        if not service or not country:
            return
        service_key = _number_catalog_key(service)
        country_key = _number_catalog_key(country)
        service_entry = catalog.setdefault(
            service_key, {"label": service, "countries": {}}
        )
        country_entry = service_entry["countries"].setdefault(
            country_key, {"label": country, "sources": []}
        )
        if source not in country_entry["sources"]:
            country_entry["sources"].append(source)

    # Uploaded local files.
    for batch_id, batch in number_batches.items():
        if not batch.get("numbers"):
            continue
        add(
            batch.get("service"),
            batch.get("country"),
            {"kind": "local", "batch_id": str(batch_id)},
        )

    # Legacy StexSMS/Voltx service maps.
    for provider, settings_key in (
        ("stex", "stex_services"),
        ("voltx", "voltx_services"),
    ):
        for service, countries in (bot_settings.get(settings_key, {}) or {}).items():
            for country, ranges in (countries or {}).items():
                if ranges:
                    add(
                        service,
                        country,
                        {"kind": provider, "provider": provider},
                    )

    # JSON API panels that also act as a number source (e.g. SL Virtual Number).
    for _idx, panel in _slvn_source_panels():
        panel_source = {
            "kind": "slvn",
            "panel_uid": _json_panel_uid(panel),
            "panel_name": str(panel.get("name", "JSON API Panel")),
        }
        for service, countries in (_slvn_catalog(panel) or {}).items():
            for country, prefixes in (countries or {}).items():
                if prefixes or country:
                    add(service, country, panel_source)

    # NP/MK panels: include both explicitly configured routes and liveaccess.
    for panel in _mk_panels(enabled_only=True):
        panel_source = {
            "kind": "panel",
            "panel_id": str(panel.get("id", "")),
            "panel_name": str(panel.get("name", "API Panel")),
        }
        for route in panel.get("routes", []) or []:
            if route.get("ranges"):
                add(route.get("service"), route.get("country"), panel_source)
        # Once an admin has configured explicit routes for a panel, those
        # routes are the public catalogue for that panel.  Do not also expose
        # every service/range returned by liveaccess; that made the user see
        # the provider's entire inventory instead of the intended selection.
        if not panel.get("routes"):
            for item in _api_liveaccess_services(
                _mk_json_get(panel, "/api/liveaccess") or {}
            ):
                service = _api_service_name(item)
                for range_text in item.get("ranges", []) or []:
                    for country in _api_country_values(item, range_text):
                        add(service, country, panel_source)
    return catalog


def _number_choice_callback(kind, service, country=None):
    """Build compact callbacks that are safe for spaces/underscores."""
    payload = json.dumps(
        [str(service), str(country)] if country is not None else [str(service)],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"num_{kind}:{token}"


def _decode_number_choice(data):
    match = re.match(r"^num_(service|country|get):(.+)$", str(data or ""))
    if not match:
        return None
    token = match.group(2)
    token += "=" * (-len(token) % 4)
    try:
        values = json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
        if not isinstance(values, list):
            return None
        if match.group(1) == "service" and len(values) >= 1:
            return {"kind": "service", "service": str(values[0])}
        if match.group(1) == "country" and len(values) >= 2:
            return {
                "kind": "country",
                "service": str(values[0]),
                "country": str(values[1]),
            }
        if match.group(1) == "get" and len(values) >= 2:
            return {
                "kind": "get",
                "service": str(values[0]),
                "country": str(values[1]),
            }
    except Exception:
        pass
    return None


def _api_service_names():
    return set(_api_catalog().keys())


def _api_ranges_for_service_country(panel, service, country):
    """Find ranges for a selected GET NUMBER service/country on one panel."""
    wanted_service = str(service).strip().upper()
    wanted_country = str(country).strip().upper()
    configured = []
    for route in panel.get("routes", []) or []:
        if (
            str(route.get("service", "")).strip().upper() == wanted_service
            and str(route.get("country", "")).strip().upper() == wanted_country
        ):
            configured.extend(str(value).strip() for value in route.get("ranges", []) if str(value).strip())
    # An explicit route is authoritative. This lets an admin choose a range
    # even when liveaccess is slow, incomplete, or unavailable.
    if configured:
        return list(dict.fromkeys(configured))
    result = []
    services = _api_liveaccess_services(_mk_json_get(panel, "/api/liveaccess") or {})
    for item in services:
        name = _api_service_name(item)
        if name.upper() != wanted_service:
            continue
        for range_text in item.get("ranges", []) or []:
            countries = _api_country_values(item, range_text)
            if (
                wanted_country == str(range_text).strip().upper()
                or not countries
                or any(wanted_country == str(x).upper() for x in countries)
            ):
                if str(range_text) not in result:
                    result.append(str(range_text))
    return result


def _number_source_candidates():
    panels = _mk_panels(enabled_only=True)
    slvn_sources = [f"slvn:{_json_panel_uid(p)}" for _, p in _slvn_source_panels()]
    return (
        ["stex", "voltx"] + slvn_sources
        + [
            f"{'np' if p.get('protocol') == 'npnetwork' else 'mk'}:{p['id']}"
            for p in panels
        ]
        + ["local"]
    )


def _number_source_order():
    """Return all available sources in a stable fallback order.

    Source priority is intentionally no longer an admin setting. The selected
    service/country determines which source is eligible; this order is only a
    fallback when the same country was accidentally configured more than once.
    """
    candidates = _number_source_candidates()
    # Uploaded stock is checked first for an uploaded country, then legacy
    # providers, then the configured panels. Matching is still case-insensitive
    # and only a source containing the selected service/country is used.
    slvn_sources = [source for source in candidates if source.startswith("slvn:")]
    preferred = ["local", "stex", "voltx"] + slvn_sources
    return (
        [source for source in preferred if source in candidates]
        + [source for source in candidates if source not in preferred]
    )


def _number_source_help_text():
    candidates = _number_source_candidates()
    return (
        "বর্তমান priority:\n"
        f"<code>{html.escape(' → '.join(_number_source_order()))}</code>\n\n"
        "লিখুন comma-separated order, উদাহরণ:\n"
        "<code>np:panel-a, voltx, stex, local</code>\n\n"
        "Available source IDs:\n"
        f"<code>{html.escape(', '.join(candidates))}</code>\n\n"
        "এখানে আগে থাকা source আগে চেষ্টা হবে; ব্যর্থ/কম number হলে পরের source চলবে।"
    )


def _parse_number_source_priority(text):
    candidates = _number_source_candidates()
    tokens = [x.strip().lower() for x in re.split(r"[,\n]+", str(text)) if x.strip()]
    resolved = []
    invalid = []
    for token in tokens:
        if token in {"np", "npnetwork"}:
            matches = [x for x in candidates if x.startswith("np:")]
        elif token in {"mk", "api", "other", "others"}:
            matches = [x for x in candidates if x.startswith("mk:")]
        elif token in {"stex", "stexsms", "setex"}:
            matches = ["stex"]
        elif token in {"voltx", "voltex"}:
            matches = ["voltx"]
        elif token in {"local", "stock", "uploaded"}:
            matches = ["local"]
        elif token in {"slvn", "sl", "slvirtualnumber", "json"}:
            matches = [x for x in candidates if x.startswith("slvn:")]
        else:
            matches = [
                x for x in candidates
                if x.lower() == token or x.lower().endswith(f":{token}")
            ]
        if not matches:
            invalid.append(token)
        for source in matches:
            if source not in resolved:
                resolved.append(source)
    return resolved, invalid


def _fetch_priority_get_number_api_numbers(service, country, owner_id, limit):
    """Fetch GET NUMBER stock in the admin-selected source priority."""
    global total_assigned_stats, stex_assigned_numbers, voltx_assigned_numbers
    global legacy_assignment_meta

    fetched = []
    seen = set()
    np_assignments = []
    limit = max(1, int(limit or 1))

    for source in _number_source_order():
        if len(fetched) >= limit:
            break

        if source == "local":
            candidates = []
            for batch_id, batch in number_batches.items():
                if _number_catalog_key(batch.get("service")) != _number_catalog_key(service):
                    continue
                if _number_catalog_key(batch.get("country")) != _number_catalog_key(country):
                    continue
                for index, item in enumerate(batch.get("numbers", [])):
                    if owner_id not in item.get("used_by", []):
                        candidates.append((batch_id, index))
            random.shuffle(candidates)
            for batch_id, index in candidates:
                if len(fetched) >= limit:
                    break
                item = number_batches[batch_id]["numbers"][index]
                number = re.sub(r"\D", "", str(item.get("num", "")))
                if not number or number in seen:
                    continue
                seen.add(number)
                fetched.append(number)
                item["shares"] = int(item.get("shares", 0)) + 1
                item.setdefault("used_by", []).append(owner_id)
                legacy_assignment_meta[number] = {
                    "provider": "local", "service": str(service),
                    "country": str(country), "range": str(country),
                }
                total_assigned_stats += 1
                if item["shares"] >= bot_settings.get("num_share", 1):
                    item["to_remove"] = True
                    used_numbers_list.append(item.get("num", number))
            for batch_id in number_batches:
                number_batches[batch_id]["numbers"] = [
                    x for x in number_batches[batch_id]["numbers"]
                    if not x.get("to_remove")
                ]
            continue

        if source in {"stex", "voltx"}:
            services_key = "stex_services" if source == "stex" else "voltx_services"
            keys_key = "stex_keys" if source == "stex" else "voltx_keys"
            service_map = bot_settings.get(services_key, {}) or {}
            service_entry = next(
                (
                    value for key, value in service_map.items()
                    if _number_catalog_key(key) == _number_catalog_key(service)
                ),
                {},
            )
            country_entry = next(
                (
                    value for key, value in (service_entry or {}).items()
                    if _number_catalog_key(key) == _number_catalog_key(country)
                ),
                [],
            )
            ranges = country_entry or []
            keys = [str(x).strip() for x in bot_settings.get(keys_key, []) if str(x).strip()]
            if not ranges or not keys:
                continue
            for _ in range(limit - len(fetched)):
                found = ""
                range_id = random.choice(ranges)
                for api_key in keys:
                    found = _legacy_panel_get_number(source, api_key, range_id)
                    clean = re.sub(r"\D", "", str(found))
                    if clean and clean not in seen:
                        found = clean
                        break
                    found = ""
                if not found:
                    break
                seen.add(found)
                fetched.append(found)
                (voltx_assigned_numbers if source == "voltx" else stex_assigned_numbers)[found] = owner_id
                legacy_assignment_meta[found] = {
                    "provider": source, "service": str(service),
                    "country": str(country), "range": str(range_id),
                }
                total_assigned_stats += 1
            continue

        if source.startswith("slvn:"):
            panel_uid = source.split(":", 1)[1]
            panel = _json_panel_by_uid(panel_uid)
            if not panel or panel.get("status") != "ON" or not panel.get("source_enabled"):
                continue
            rented_numbers = _slvn_rent_for_user(
                service, country, owner_id, limit - len(fetched), panel
            )
            for number in rented_numbers:
                if number in seen:
                    continue
                seen.add(number)
                fetched.append(number)
            continue

        if ":" not in source:
            continue
        protocol, panel_id = source.split(":", 1)
        panel = _mk_panel(panel_id)
        if not panel or not panel.get("enabled"):
            continue
        ranges = _api_ranges_for_service_country(panel, service, country)
        for range_id in ranges:
            while len(fetched) < limit:
                item = _mk_get_number(panel, range_id)
                number = re.sub(r"\D", "", str((item or {}).get("number", "")))
                if not number or number in seen:
                    break
                seen.add(number)
                fetched.append(number)
                np_assignments.append({
                    "number": number, "panel_id": panel["id"],
                    "panel_name": panel["name"], "range": str(range_id),
                })
                total_assigned_stats += 1
            if len(fetched) >= limit:
                break

    if np_assignments:
        with api_session_lock:
            api_number_sessions[owner_id] = {
                "user_id": owner_id,
                "range": np_assignments[0]["range"],
                "panel_id": np_assignments[0]["panel_id"],
                "panel_name": np_assignments[0]["panel_name"],
                "assignments": np_assignments,
                "numbers": [x["number"] for x in np_assignments],
                "created": time.time(),
            }
    return fetched


def _mk_json_get(panel, path):
    try:
        if panel.get("protocol") == "npnetwork":
            action = {
                "liveaccess": "liveaccess",
                "success-otp-info": "otp",
                "otp": "otp",
                "console": "console",
            }.get(str(path).strip("/").split("/")[-1].lower())
            endpoint = _np_user_endpoint(panel, action)
        else:
            endpoint = _mk_endpoint(panel, path)
        res = mk_panel_http.get(endpoint, headers=_mk_headers(panel), timeout=12)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[{panel.get('protocol', 'mk').upper()}:{panel.get('name')}] GET error: {type(e).__name__}")
        return None


def _mk_json_post(panel, path, payload):
    try:
        request_payload = dict(payload or {})
        if panel.get("protocol") == "npnetwork":
            endpoint = _np_user_endpoint(panel)
            # NP Network's contract accepts exactly the action/range pair.
            request_payload = {
                "action": "getnum",
                "range": str(request_payload.get("range", "")),
            }
        else:
            endpoint = _mk_endpoint(panel, path)
        res = mk_panel_http.post(endpoint, headers=_mk_headers(panel), json=request_payload, timeout=12)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[{panel.get('protocol', 'mk').upper()}:{panel.get('name')}] POST error: {type(e).__name__}")
        return None


def _load_api_ranges():
    if not os.path.exists(API_RANGE_FILE):
        return {}
    try:
        with open(API_RANGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[API ranges] load error: {e}")
        return {}


def _save_api_ranges(data):
    temp = API_RANGE_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp, API_RANGE_FILE)
    try:
        os.chmod(API_RANGE_FILE, 0o600)
    except OSError:
        pass


def _get_user_api_ranges(user_id):
    """Return only the user's latest saved range.

    The local JSON database is primary; the API-range file is a fallback.
    """
    with api_range_lock:
        if db:
            try:
                doc = db.collection("users").document(str(user_id)).get()
                latest = doc.to_dict().get("api_last_range") if doc.exists else None
                if isinstance(latest, dict) and latest.get("range"):
                    return [latest]
            except Exception as e:
                print(f"[API ranges] Local DB read error: {type(e).__name__}")
        data = _load_api_ranges()
        values = data.get(str(user_id), [])
        if isinstance(values, list) and values:
            return [values[-1]]
        return []


def _add_user_api_range(user_id, range_text, panel):
    with api_range_lock:
        data = _load_api_ranges()
        key = str(user_id)
        existing = data.get(key, [])
        if not isinstance(existing, list):
            existing = []
        if not any(str(x.get("range", "")).upper() == str(range_text).upper() and x.get("panel_id") == panel["id"] for x in existing if isinstance(x, dict)):
            existing.append({
                "range": str(range_text).upper(),
                "panel_id": panel["id"],
                "panel_name": panel["name"],
                "saved_at": datetime.now().isoformat(),
            })
        data[key] = existing
        _save_api_ranges(data)
        return existing


def _range_is_listed(panel, range_text):
    """Validate a range without allocating/consuming a phone number."""
    wanted = re.sub(r"\s+", "", str(range_text).upper())
    configured_ranges = [
        str(value)
        for route in (panel.get("routes", []) or [])
        for value in (route.get("ranges", []) or [])
    ]
    if any(re.sub(r"\s+", "", value.upper()) == wanted for value in configured_ranges):
        return True
    data = _mk_json_get(panel, "/api/liveaccess") or {}
    services = _api_liveaccess_services(data)
    for service in services:
        for candidate in service.get("ranges", []) or []:
            if re.sub(r"\s+", "", str(candidate).upper()) == wanted:
                return True
    return False


def _find_panel_for_range(range_text):
    for panel in _mk_panels(enabled_only=True):
        if _range_is_listed(panel, range_text):
            return panel
    return None


_PANEL_NUMBER_KEYS = (
    "full_number",
    "fullNumber",
    "no_plus_number",
    "noPlusNumber",
    "national_number",
    "nationalNumber",
    "phone_number",
    "phoneNumber",
    "mobile_number",
    "mobileNumber",
    "assigned_number",
    "assignedNumber",
    "selected_number",
    "selectedNumber",
    "msisdn",
    "phone",
    "phone_no",
    "phoneNo",
    "mobile",
    "mobile_no",
    "mobileNo",
    "telephone",
    "tel",
    "sim_number",
    "simNumber",
    "number",
)


def _number_from_text(value):
    """Extract a plausible phone number from a scalar panel value.

    Different panels return the allocated number in slightly different
    shapes: a plain string, ``Your number is +...`` or a value containing
    spaces/dashes.  The old parser only accepted a string when the whole
    value was the number, so a successful allocation could be discarded.
    """
    if not isinstance(value, (str, int, float)):
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    # Prefer a number with an international ``+`` because it is less likely
    # to be a request id, status code, or range value.
    candidates = re.findall(r"\+\d[\d\s().-]{7,}\d", raw)
    candidates += re.findall(r"(?<!\d)\d[\d\s().-]{7,}\d(?!\d)", raw)
    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)
        if 8 <= len(digits) <= 16:
            return digits

    # Finally accept a scalar that is already just a phone number.
    digits = re.sub(r"\D", "", raw)
    if 8 <= len(digits) <= 16 and (
        raw.startswith("+") or raw.replace(".", "").isdigit()
    ):
        return digits
    return ""


def _extract_panel_number(payload):
    """Extract a phone number from the different NP/MK response envelopes."""
    if isinstance(payload, dict):
        # Prefer explicit phone-number fields before the generic `number` key.
        for key in _PANEL_NUMBER_KEYS:
            value = payload.get(key)
            found = _number_from_text(value)
            if found:
                return found
        for value in payload.values():
            found = _extract_panel_number(value)
            if found:
                return found
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found = _extract_panel_number(value)
            if found:
                return found
    elif isinstance(payload, (str, int, float)):
        return _number_from_text(payload)
    return ""


def _numbers_match(first, second):
    """Match full and country-code-stripped forms of the same phone number."""
    left = re.sub(r"\D", "", str(first or ""))
    right = re.sub(r"\D", "", str(second or ""))
    if left.startswith("00"):
        left = left[2:]
    if right.startswith("00"):
        right = right[2:]
    if not left or not right:
        return False
    if left == right:
        return True
    # NP Network's getnum response includes the country code while its OTP
    # endpoint returns the same number without it. Require a substantial phone
    # suffix to avoid matching short IDs or range values accidentally.
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 8 and longer.endswith(shorter)


def _mk_get_number(panel, range_text):
    data = _mk_json_post(panel, "/api/getnum", {"range": str(range_text), "is_national": False}) or {}
    number = _extract_panel_number(data)
    if not number:
        # Some panels put the assigned phone in a human-readable message or
        # in a generic ``result`` string.  Scan all scalar values, not only a
        # fixed set of message keys.
        scalar_values = []
        def collect_scalars(value):
            if isinstance(value, dict):
                for child in value.values():
                    collect_scalars(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collect_scalars(child)
            elif isinstance(value, (str, int, float)):
                scalar_values.append(value)

        collect_scalars(data)
        for value in scalar_values:
            number = _number_from_text(value)
            if number:
                break
    if not number:
        return None
    body = data.get("data", {}) if isinstance(data, dict) else {}
    if not isinstance(body, dict):
        body = data if isinstance(data, dict) else {}
    return {
        "number": number,
        "otp_now": bool(body.get("otp_now", False)),
        "otp": body.get("otp"),
        "sms": body.get("sms"),
        "panel_id": panel["id"],
        "panel_name": panel["name"],
        "service": body.get("service") or body.get("app") or panel.get("name", ""),
        "app": body.get("service") or body.get("app") or panel.get("name", ""),
        "range": str(range_text),
    }


def _api_button_config(key):
    defaults = {
        "save_range": {"label": "SAVE RANGE", "char": "💾", "id": "5352721946054268944", "style": "primary"},
        "api_number": {"label": "API NUMBER", "char": "📞", "id": "5337132498965010628", "style": "primary"},
        "main_menu": {"label": "MAIN MENU", "char": "🏠", "id": "5267490665117275176", "style": "danger"},
        "cancel": {"label": "CANCEL", "char": "❌", "id": "5267490665117275176", "style": "danger"},
        "otp_group": {"label": "OTP GROUP", "char": "🛡", "id": "5190447043545438788", "style": "primary"},
        "change_number": {"label": "CHANGE NUMBER", "char": "🔄", "id": "5465368548702446780", "style": "danger"},
        "provider": {"label": "PROVIDER", "char": "🛰", "id": "5336879280578138635", "style": "primary"},
    }
    configured = bot_settings.setdefault("api_buttons", {}).get(key, {})
    item = dict(defaults.get(key, {"label": key.upper(), "char": "🔘", "style": "primary"}))
    if isinstance(configured, dict):
        item.update({k: v for k, v in configured.items() if v is not None})
    return item


def _api_button(key, callback_data=None, url=None, text=None):
    """Build an API button with style and optional Premium Emoji icon."""
    item = _api_button_config(key)
    button = {
        "text": str(text if text is not None else f"{item.get('char', '')} {item.get('label', key.upper())}").strip(),
        "style": item.get("style", "primary"),
    }
    icon_id = str(item.get("id") or "").strip()
    if icon_id.isdigit():
        button["icon_custom_emoji_id"] = icon_id
    if callback_data is not None:
        button["callback_data"] = callback_data
    if url is not None:
        button["url"] = url
    return button


def _api_button_matches(text, key):
    """Accept a button after its leading normal/custom emoji was changed."""
    value = str(text or "").strip()
    item = _api_button_config(key)
    label = str(item.get("label", "")).strip()
    return value == _api_button(key).get("text") or value.upper().endswith(label.upper())


def _strip_number_country_code(number):
    """Return the national part using the configured premium country codes."""
    clean = re.sub(r"\D", "", str(number or ""))
    if clean.startswith("00"):
        clean = clean[2:]
    for raw_code in sorted(
        bot_settings.get("premium_flags", {}).keys(),
        key=lambda value: len(str(value)),
        reverse=True,
    ):
        code = re.sub(r"\D", "", str(raw_code))
        if code and clean.startswith(code) and len(clean) - len(code) >= 7:
            return clean[len(code):]
    return clean


def _display_api_number(number, show_cc=True):
    clean = re.sub(r"\D", "", str(number or ""))
    if show_cc:
        return f"+{clean}" if clean else str(number or "")
    return _strip_number_country_code(clean)


def _imran_number_result_text(number_lines, header="", numbers=None, country=""):
    """Render the screenshot-style number result message."""
    numbers = list(numbers or [])
    first_number = numbers[0] if numbers else ""
    if not first_number and number_lines:
        match = re.search(r"\+?\d{7,}", "\n".join(str(line) for line in number_lines))
        first_number = match.group(0) if match else ""
    return render_body_text(
        f"{_country_display_html(first_number, country)}\n\n"
        "🔵 <b>Waiting for OTP</b>"
    )


def _classic_number_ui(session):
    """Build the Imran OTP-style number message and its CC toggle controls."""
    show_cc = bool(session.get("show_cc", True))
    numbers = session.get("nums", []) or []
    service_text = session.get("service", "") or session.get("header", "")
    lines = []
    keyboard = []
    for number in numbers:
        display_number = _display_api_number(number, show_cc=show_cc)
        lines.append(
            f"{get_flag_info_html(number)} <code>{display_number}</code>"
        )
        keyboard.append([_number_copy_button(display_number, service_text)])

    country_callback = session.get("country_callback") or "get_number_menu"
    change_callback = session.get("change_callback") or "get_number_menu"
    keyboard.append([{
        "text": "Remove CC" if show_cc else "Add CC",
        "icon_custom_emoji_id": (
            "5422557736330106570" if show_cc
            else "5420396762189831222"
        ),
        "callback_data": "toggle_classic_cc",
        "style": "danger" if show_cc else "success",
    }])
    keyboard.append([{
        "text": "Change Number",
        "icon_custom_emoji_id": "5465368548702446780",
        "callback_data": change_callback,
        "style": "success",
    }])
    keyboard.append([{
        "text": "Change Country",
        "icon_custom_emoji_id": "5336972142066047577",
        "callback_data": country_callback,
        "style": "primary",
    }])
    otp_link = str(bot_settings.get("otp_link", "") or "").strip()
    otp_button = {
        "text": "OTP Group",
        "icon_custom_emoji_id": "5190447043545438788",
        "style": "success",
    }
    if otp_link:
        otp_button["url"] = otp_link
    else:
        otp_button["callback_data"] = "api_open_group"
    keyboard.append([otp_button])

    header = str(session.get("header", "") or "")
    return _imran_number_result_text(
        lines,
        header,
        numbers=numbers,
        country=session.get("country", ""),
    ), {"inline_keyboard": keyboard}


def api_button_settings_keyboard():
    labels = {
        "save_range": "SAVE RANGE",
        "api_number": "API NUMBER",
        "main_menu": "MAIN MENU",
        "cancel": "CANCEL",
        "otp_group": "OTP GROUP",
        "change_number": "CHANGE NUMBER",
        "provider": "PROVIDER",
    }
    kb = []
    for key, label in labels.items():
        item = _api_button_config(key)
        shown = f"{item.get('char', '')} {label}".strip()
        kb.append([{
            "text": f"Change {shown}",
            "icon_custom_emoji_id": item.get("id", ""),
            "callback_data": f"api_btn_emoji:{key}",
            "style": item.get("style", "primary"),
        }])
    kb.append([{
        "text": "Back",
        "icon_custom_emoji_id": "5267490665117275176",
        "callback_data": "system_settings",
        "style": "danger",
    }])
    return {"inline_keyboard": kb}


def _api_number_keyboard():
    """Persistent API reply keyboard; it changes only when MAIN MENU is pressed."""
    return {"keyboard": [
        [_api_button("save_range"), _api_button("api_number")],
        [_api_button("main_menu")],
    ], "resize_keyboard": True, "one_time_keyboard": False}


def _api_cancel_keyboard():
    return {"keyboard": [[_api_button("cancel")]], "resize_keyboard": True, "one_time_keyboard": False}


def _api_cancel_inline_keyboard():
    return {"inline_keyboard": [[_api_button("cancel", callback_data="api_cancel_range")]]}


def _api_result_inline_keyboard(link="", items=None, show_cc=True):
    """Build result controls and make each fetched number copyable."""
    link = str(link or "").strip()
    # A Telegram URL button opens the configured group immediately. There is
    # no callback/message hop when the admin has configured OTP_GROUP_LINK or
    # the Admin Panel OTP Group link.
    otp_button = _api_button("otp_group", callback_data="api_open_group")
    if link:
        otp_button = _api_button("otp_group", url=link)
    otp_button["text"] = "OTP Group"
    rows = []
    for item in items or []:
        number = re.sub(r"\D", "", str(item.get("number", "")))
        if number:
            display_number = _display_api_number(number, show_cc=show_cc)
            rows.append([_number_copy_button(
                display_number,
                item.get("service") or item.get("app") or item.get("panel_name", ""),
            )])
    rows.extend([
        [{
            "text": "Remove CC" if show_cc else "Add CC",
            "icon_custom_emoji_id": (
                "5422557736330106570" if show_cc
                else "5420396762189831222"
            ),
            "callback_data": "api_toggle_cc",
            "style": "danger" if show_cc else "success",
        }],
        [{
            "text": "Change Number",
            "icon_custom_emoji_id": "5465368548702446780",
            "callback_data": "api_change_number",
            "style": "success",
        }],
        [{
            "text": "Change Country",
            "icon_custom_emoji_id": "5336972142066047577",
            "callback_data": "api_change_country",
            "style": "primary",
        }],
        [otp_button],
    ])
    return {"inline_keyboard": rows}


def _show_api_number_menu(chat_id, message_id=None):
    saved = _get_user_api_ranges(chat_id)
    latest = saved[-1].get("range", "") if saved and isinstance(saved[-1], dict) else ""
    text = (
        "📞 <b>API NUMBER</b>\n\n"
        "💾 SAVE RANGE — আপনার সর্বশেষ অনুমোদিত range save করুন।\n"
        "📞 API NUMBER — saved range-এর matched provider বাছাই করুন।\n\n"
        f"📋 LAST SAVED RANGE: <code>{html.escape(latest or 'Not saved')}</code>"
    )
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text))
    send_message(chat_id, render_body_text(text), reply_markup=_api_number_keyboard())


def _show_api_provider_menu(chat_id, message_id=None):
    """Show matching providers with a bottom reply keyboard."""
    saved = _get_user_api_ranges(chat_id)
    latest = saved[-1] if saved and isinstance(saved[-1], dict) else None
    range_text = str(latest.get("range", "")).upper() if latest else ""
    if not range_text:
        user_states.pop(chat_id, None)
        text = "⚠️ আগে SAVE RANGE থেকে একটি valid range save করুন।"
        markup = _api_number_keyboard()
    else:
        matches = _find_matching_mk_panels(range_text)
        if matches:
            user_states[chat_id] = "api_choose_provider"
            text = (
                "🔹 <b>PLEASE SELECT PROVIDER</b>\n\n"
                f"📋 RANGE: <code>{html.escape(range_text)}</code>\n"
                "নিচের provider button-এ ক্লিক করুন; নির্বাচিত provider থেকে ২টি number নেওয়া হবে।"
            )
            rows = [[_api_button(
                "provider",
                callback_data=f"api_provider:{panel['id']}",
                text=f"{_api_button_config('provider').get('char', '🛰')} {panel['name']}",
            )] for panel in matches]
            markup = {"inline_keyboard": rows}
        else:
            user_states.pop(chat_id, None)
            text = (
                "❌ saved range-এর সাথে কোনো enabled API provider-এর live range মেলেনি।\n\n"
                f"RANGE: <code>{html.escape(range_text)}</code>"
            )
            markup = None
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text), reply_markup=markup)
    else:
        send_message(chat_id, render_body_text(text), reply_markup=markup)


def _api_number_result_text(items):
    lines = []
    for item in items:
        flag_html = get_flag_info_html(item["number"])
        lines.append(f"{flag_html} <code>+{item['number']}</code>")
    return _imran_number_result_text(
        lines,
        "🛰 <b>API Number</b>",
        numbers=[item.get("number", "") for item in items],
    )


def _api_number_action(chat_id, message_id=None, preferred=None):
    saved = _get_user_api_ranges(chat_id)
    if not saved:
        _show_api_number_menu(chat_id, message_id)
        send_message(chat_id, render_body_text("⚠️ আগে SAVE API RANGE থেকে অন্তত একটি valid range save করুন."))
        return
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(x for x in saved if x not in candidates)
    fetched = []
    chosen = None
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        panel = _mk_panel(entry.get("panel_id"))
        if not panel or not panel["enabled"]:
            continue
        chosen = (entry, panel)
        for _ in range(2 - len(fetched)):
            item = _mk_get_number(panel, entry.get("range", ""))
            if item and item["number"] not in {x["number"] for x in fetched}:
                fetched.append(item)
        if len(fetched) >= 2:
            break
    if not fetched:
        msg = "❌ saved range-এ বর্তমানে কোনো number পাওয়া যায়নি।"
        if message_id:
            edit_message(chat_id, message_id, render_body_text(msg), reply_markup=_api_number_keyboard())
        else:
            send_message(chat_id, render_body_text(msg), reply_markup=_api_number_keyboard())
        return
    if chosen:
        entry, panel = chosen
        session = {
            "user_id": chat_id,
            "range": entry.get("range", ""),
            "panel_id": panel["id"],
            "panel_name": panel["name"],
            "numbers": [x["number"] for x in fetched],
            "created": time.time(),
        }
        with api_session_lock:
            api_number_sessions[chat_id] = session
    text = _api_number_result_text(fetched)
    result_markup = _api_result_inline_keyboard(
        bot_settings.get("otp_link", ""), fetched
    )
    _result, active_message_id = _deliver_number_result(
        chat_id,
        render_body_text(text),
        reply_markup=result_markup,
        message_id=message_id,
    )
    if active_message_id and chat_id in api_number_sessions:
        with api_session_lock:
            api_number_sessions[chat_id]["message_id"] = active_message_id


def _api_monitor_thread():
    while True:
        try:
            now = time.time()
            with api_session_lock:
                for uid in list(api_number_sessions):
                    if now - api_number_sessions[uid].get("created", now) > API_SESSION_TIMEOUT:
                        del api_number_sessions[uid]
                sessions = list(api_number_sessions.values())
            for panel in _mk_panels(enabled_only=True):
                owners = [s for s in sessions if s.get("panel_id") == panel["id"]]
                if not owners:
                    continue
                data = _mk_json_get(panel, "/api/success-otp-info") or {}
                items = _api_otp_items(data)
                for item in items:
                    number = re.sub(r"\D", "", str(item.get("number", "")))
                    owner_session = next((s for s in owners if number in s.get("numbers", [])), None)
                    if not owner_session:
                        continue
                    sms = item.get("message") or item.get("otp") or item.get("sms") or "No Content"
                    code = extract_otp_code(str(sms)) or "N/A"
                    otp_id = str(item.get("otp_id") or f"{number}_{code}")
                    unique = f"{panel['id']}::{number}::{otp_id}"
                    if unique in api_seen_otps:
                        continue
                    api_seen_otps.add(unique)
                    if len(api_seen_otps) > 10000:
                        api_seen_otps.clear()
                    reward = float(bot_settings.get("otp_reward", 0.0))
                    if reward > 0:
                        update_balance(owner_session["user_id"], reward)
                    send_message(owner_session["user_id"], render_body_text(
                        f"✅ <b>API OTP RECEIVED</b>\n\n🛰 PANEL: {html.escape(panel['name'])}\n"
                        f"📞 <code>+{number}</code>\n🔑 <code>{html.escape(str(code))}</code>\n\n"
                        f"<blockquote>📩 {html.escape(str(sms))}</blockquote>\n\n"
                        f"💵 ADDED: {reward:.2f} TK"
                    ), reply_markup=main_menu(owner_session["user_id"]))
        except Exception as e:
            print(f"[API Number] monitor error: {e}")
        time.sleep(max(3, int(os.environ.get("MK_CHECK_INTERVAL", "5"))))


# Zero Trace style navigation.
# The old business logic is intentionally kept behind these labels, so the
# redesign changes navigation without removing any existing feature.
_original_dx_main_menu = main_menu

def main_menu(user_id):
    # Only PREMIUM emoji (icon_custom_emoji_id) is shown; the plain emoji in the
    # label text is removed so each button shows a single large premium icon.
    kb = {
        "keyboard": [
            [
                {"text": "Get Number", "icon_custom_emoji_id": "5337132498965010628", "style": "primary"},
            ],
            [
                {"text": "Profile", "icon_custom_emoji_id": "5352861489541714456", "style": "primary"},
                {"text": "Live Traffic", "icon_custom_emoji_id": "5352877703043258544", "style": "primary"},
            ],
            [
                {"text": "2FA ONLINE", "icon_custom_emoji_id": "5353022963132174959", "style": "success"},
                {"text": "Leaderboard", "icon_custom_emoji_id": "5353032893096567467", "style": "success"},
            ],
            [
                {"text": "SUPPORT", "icon_custom_emoji_id": "5420145051336485498", "style": "primary"},
            ],
        ],
        "resize_keyboard": True,
    }
    if is_admin(user_id):
        kb["keyboard"].append([
            {"text": "Admin Panel", "icon_custom_emoji_id": "5420155432272438703", "style": "danger"}
        ])
    return kb


def _zerotrace_profile_screen(chat_id):
    user = get_user(chat_id)
    name = user.get("first_name") or user.get("name") or "User"
    balance = float(user.get("balance", 0.0) or 0.0)
    total_otps = int(user.get("total_otps", 0) or 0)
    total_refers = int(user.get("total_refers", 0) or 0)
    text = (
        "╔═══════════════╗\n"
        "║ 🐵 <b>PROFILE DETAILS</b>\n"
        "╚═══════════════╝\n\n"
        f"👤 Name: <b>{html.escape(str(name))}</b>\n"
        f"🆔 UID: <code>{chat_id}</code>\n"
        f"💰 Balance: <b>{balance:g}৳</b>\n\n"
        f"📅 Total OTP: <b>{total_otps}</b>\n"
        f"🤝 Total Refer: <b>{total_refers}</b>"
    )
    markup = {
        "inline_keyboard": [
            [
                {"text": "🏧 Withdraw", "callback_data": "zt_profile_withdrawal", "style": "primary"},
                {"text": "🤝 Refer", "callback_data": "zt_profile_refer", "style": "success"},
            ],
            [{"text": "📜 History", "callback_data": "zt_profile_history", "style": "primary"}],
        ]
    }
    send_message(chat_id, render_body_text(text), reply_markup=markup)


def _zerotrace_user_leaderboard(chat_id, message_id=None):
    rows = []
    if db:
        try:
            users = db.collection("users").order_by(
                "total_otps", direction="DESCENDING"
            ).limit(10).stream()
            for index, doc in enumerate(users, 1):
                item = doc.to_dict() or {}
                display_name = item.get("first_name") or item.get("name") or doc.id
                otp_count = int(item.get("total_otps", 0) or 0)
                rows.append(
                    f"{index}. <b>{html.escape(str(display_name)[:24])}</b> — "
                    f"{otp_count} OTP ({float(item.get('balance', 0) or 0):g}৳)"
                )
        except Exception as exc:
            print(f"[leaderboard] {exc}")
    if not rows:
        rows.append("এখনো কোনো leaderboard data নেই।")
    text = (
        "🏆 <b>TOP LEADERBOARD</b>\n\n"
        + "\n".join(rows)
        + "\n\n"
        "আপনার OTP ও আয়ের ভিত্তিতে ranking আপডেট হয়।"
    )
    markup = {
        "inline_keyboard": [
            [{"text": "🔄 Refresh", "callback_data": "zt_leaderboard", "style": "success"}],
            [{"text": "🏠 Main Menu", "callback_data": "traffic_main_menu", "style": "danger"}],
        ]
    }
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text), reply_markup=markup)
    else:
        send_message(chat_id, render_body_text(text), reply_markup=markup)


def _zerotrace_history_screen(chat_id):
    entries = user_history.get(str(chat_id), [])[:20]
    lines = []
    for entry in entries:
        when = datetime.fromtimestamp(float(entry.get("time", 0))).strftime("%d/%m %H:%M")
        number = mask_number(str(entry.get("number", "")))
        reward = float(entry.get("reward", 0.0) or 0.0)
        lines.append(
            f"• {html.escape(str(entry.get('service', 'OTP'))[:18])} "
            f"{html.escape(number)} → <code>{html.escape(str(entry.get('otp', '')))}</code> "
            f"+{reward:g}৳ ({when})"
        )
    if not lines:
        lines.append("এখনো কোনো OTP history নেই।")
    text = (
        "📜 <b>HISTORY</b>\n\n"
        + "\n".join(lines)
    )
    markup = {
        "inline_keyboard": [
            [{"text": "🔙 Profile", "callback_data": "zt_profile", "style": "danger"}],
        ]
    }
    send_message(chat_id, render_body_text(text), reply_markup=markup)


# Add an MK provider-management shortcut to the existing System Settings menu.
_original_system_settings_keyboard = system_settings_keyboard

def system_settings_keyboard():
    markup = _original_system_settings_keyboard()
    rows = markup.get("inline_keyboard", [])
    rows.insert(0, [{"text": "API PANELS (MK / NP)", "icon_custom_emoji_id": "5336879280578138635", "callback_data": "mk_manage_panels", "style": "primary"}])
    return markup


def _mk_admin_keyboard():
    rows = []
    for p in _mk_panels():
        state = "ON" if p["enabled"] else "OFF"
        provider_tag = "NP" if p.get("protocol") == "npnetwork" else "MK"
        rows.append([
            {"text": f"{'🟢' if p['enabled'] else '🔴'} [{provider_tag}] {p['name']} [{state}]", "callback_data": f"mks_toggle:{p['id']}", "style": "primary"},
            {"text": "TEST", "callback_data": f"mks_test:{p['id']}", "style": "success"},
        ])
        rows.append([{
            "text": f"🧭 ROUTES ({len(p.get('routes', []) or [])})",
            "callback_data": f"mks_routes:{p['id']}",
            "style": "primary",
        }])
        rows.append([{ "text": "DELETE", "callback_data": f"mks_delete:{p['id']}", "style": "danger" }])
    rows.append([{ "text": "➕ ADD NP NETWORK PANEL", "callback_data": "nps_add", "style": "success" }])
    rows.append([{ "text": "➕ ADD GENERIC MK PANEL", "callback_data": "mks_add", "style": "primary" }])
    rows.append([{ "text": "BACK TO SYSTEM", "callback_data": "mks_back", "style": "primary" }])
    return {"inline_keyboard": rows}


def _mk_routes_keyboard(panel):
    """Show and edit admin-owned service/country/range routing rules."""
    pid = str(panel.get("id", ""))
    rows = []
    routes = panel.get("routes", []) or []
    for index, route in enumerate(routes):
        label = (
            f"{route.get('service', '?')} / {route.get('country', '?')} — "
            f"{', '.join(route.get('ranges', []) or [])}"
        )
        rows.append([{
            "text": f"🗑 {label[:52]}",
            "callback_data": f"mks_route_delete:{pid}:{index}",
            "style": "danger",
        }])
    rows.append([{
        "text": "➕ ADD COUNTRY + RANGE",
        "callback_data": f"mks_route_add:{pid}",
        "style": "success",
    }])
    rows.append([{
        "text": "BACK TO PANELS",
        "callback_data": "mks_back",
        "style": "primary",
    }])
    return {"inline_keyboard": rows}


def _show_mk_routes(chat_id, panel_id, message_id=None):
    panel = _mk_panel(panel_id)
    if not panel:
        return
    routes = panel.get("routes", []) or []
    if routes:
        route_lines = "\n".join(
            f"• <b>{html.escape(str(route.get('service', '')))}</b> / "
            f"<b>{html.escape(str(route.get('country', '')))}</b> → "
            f"<code>{html.escape(', '.join(route.get('ranges', []) or []))}</code>"
            for route in routes
        )
    else:
        route_lines = "<i>কোনো custom route নেই। Panel-এর liveaccess ranges ব্যবহার হবে।</i>"
    text = (
        f"🧭 <b>{html.escape(panel['name'])} ROUTING</b>\n\n"
        "এখানে service + country অনুযায়ী এই panel-এর preferred range ঠিক করুন।\n"
        "Custom route থাকলে সেটিই আগে ব্যবহার হবে; number না পেলে একই country-এর অন্য configured source-এ fallback হবে।\n\n"
        f"{route_lines}\n\n"
        "Format: <code>SERVICE | COUNTRY | RANGE1,RANGE2</code>"
    )
    markup = _mk_routes_keyboard(panel)
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text), reply_markup=markup)
    else:
        send_message(chat_id, render_body_text(text), reply_markup=markup)


def _show_mk_admin(chat_id, message_id=None):
    text = (
        "🛰 <b>API PANEL CONTROL</b>\n\n"
        "একাধিক authorized MK বা NP Network panel যোগ করুন।\n"
        "NP contract: mauthapi header, getnum, otp, liveaccess, console"
    )
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text), reply_markup=_mk_admin_keyboard())
    else:
        send_message(chat_id, render_body_text(text), reply_markup=_mk_admin_keyboard())


_original_dx_handle_message = handle_message

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    admin = is_admin(chat_id)

    # Zero Trace labels route to the original feature handlers.
    if text in ("🦚 Get Number", "Get Number"):
        msg = dict(msg)
        msg["text"] = "GET NUMBER"
        _original_dx_handle_message(msg)
        return
    if text in ("🐵 Profile", "Profile", "PROFILE"):
        _zerotrace_profile_screen(chat_id)
        return
    if text in ("📈 Live Traffic", "Live Traffic"):
        msg = dict(msg)
        msg["text"] = "TRAFFIC"
        _original_dx_handle_message(msg)
        return
    if text in ("🔐 2FA ONLINE", "2FA ONLINE"):
        msg = dict(msg)
        msg["text"] = "2FA ONLINE"
        _original_dx_handle_message(msg)
        return
    if text in ("🏆 Leaderboard", "Leaderboard", "LEADERBOARD"):
        _zerotrace_user_leaderboard(chat_id)
        return
    if text in ("🛠 Admin Panel", "Admin Panel"):
        msg = dict(msg)
        msg["text"] = "Admin Panel"
        _original_dx_handle_message(msg)
        return

    if _api_button_matches(text, "main_menu"):
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        send_message(chat_id, render_body_text("✅ Main menu restored."), reply_markup=main_menu(chat_id))
        return
    if _api_button_matches(text, "otp_group"):
        link = bot_settings.get("otp_link", "")
        if link:
            send_message(chat_id, render_body_text("🛡 <b>OTP GROUP</b>"), reply_markup={
                "inline_keyboard": [[_api_button("otp_group", url=link, text=f"{_api_button_config('otp_group').get('char', '🛡')} OPEN OTP GROUP")]]
            })
        else:
            send_message(chat_id, render_body_text("⚠️ Admin has not configured an OTP group."))
        return
    if _api_button_matches(text, "change_number"):
        if not _dual_api_allowed(chat_id):
            return
        with api_session_lock:
            current_session = dict(api_number_sessions.get(chat_id, {}))
        if current_session.get("panel_id") and current_session.get("range"):
            preferred = {
                "range": current_session.get("range"),
                "panel_id": current_session.get("panel_id"),
                "panel_name": current_session.get("panel_name", ""),
            }
            # Change Number stays on the provider selected by the user.
            _api_number_action(
                chat_id,
                preferred=preferred,
                provider_id=current_session.get("panel_id"),
            )
        else:
            send_message(chat_id, render_body_text("⚠️ আগে API NUMBER থেকে একটি provider select করুন."), reply_markup=_api_number_keyboard())
        return
    if text in ("🔄 CHANGE PROVIDER", "CHANGE PROVIDER"):
        if not _dual_api_allowed(chat_id):
            return
        # Provider changes only through API NUMBER → provider selection.
        _show_api_provider_menu(chat_id)
        return
    if _api_button_matches(text, "save_range") or text == "SAVE API RANGE":
        if not _dual_api_allowed(chat_id):
            return
        user_states[chat_id] = "api_wait_range"
        send_message(chat_id, render_body_text("💾 <b>SAVE RANGE</b>\n\nআপনার অনুমোদিত range পাঠান। উদাহরণ: <code>234XXX</code>"), reply_markup=_api_cancel_inline_keyboard())
        return

    if user_states.get(chat_id) == "api_choose_provider" and text.startswith("🛰 "):
        saved = _get_user_api_ranges(chat_id)
        latest = saved[-1] if saved and isinstance(saved[-1], dict) else None
        provider_name = text.removeprefix("🛰 ").strip()
        matches = _find_matching_mk_panels(str(latest.get("range", ""))) if latest else []
        panel = next((p for p in matches if p.get("name") == provider_name), None)
        if not panel:
            send_message(chat_id, render_body_text("❌ Provider আর available নেই। আবার API NUMBER চাপুন."), reply_markup=_api_number_keyboard())
            return
        user_states.pop(chat_id, None)
        _api_number_action(chat_id, preferred=latest, provider_id=panel["id"])
        return

    if user_states.get(chat_id) == "api_wait_range":
        if text == "Cancel" or _api_button_matches(text, "cancel"):
            user_states.pop(chat_id, None)
            send_message(chat_id, render_body_text("❌ Range save cancelled."), reply_markup=_api_number_keyboard())
            return
        if not re.match(r"^[0-9]+[0-9Xx]*$", text) or not re.search(r"\d", text):
            send_message(chat_id, render_body_text("❌ Invalid range. উদাহরণ: <code>234XXX</code>"), reply_markup=_api_cancel_inline_keyboard())
            return
        range_text = text.upper().replace(" ", "")
        user_states.pop(chat_id, None)
        send_message(chat_id, render_body_text("⌛ MK Online SMS panel-এ range যাচাই করা হচ্ছে..."))
        panel = _find_panel_for_range(range_text)
        if panel:
            saved = _add_user_api_range(chat_id, range_text, panel)
            send_message(chat_id, render_body_text(
                f"✅ <b>RANGE SAVED</b>\n\n📶 RANGE: <code>{html.escape(range_text)}</code>\n"
                f"🛰 MATCHED PROVIDERS: <b>{html.escape(panel['name'])}</b>\n"
                "📋 শুধু সর্বশেষ range-টি database-এ রাখা হয়েছে।"
            ), reply_markup=_api_number_keyboard())
        else:
            send_message(chat_id, render_body_text(
                "❌ এই range MK Online SMS-এর liveaccess তালিকায় নেই।\n"
                "Provider-এর official live range ব্যবহার করুন।"
            ), reply_markup=_api_number_keyboard())
        return

    if admin and user_states.get(chat_id) in {"wait_for_stex_base_url", "wait_for_voltx_base_url"}:
        if text in ("Cancel", "❌ CANCEL"):
            state = user_states.pop(chat_id, "")
            temp_data.pop(chat_id, None)
            callback = "stex_control" if state == "wait_for_stex_base_url" else "voltx_control"
            handle_callback({
                "message": {"chat": {"id": chat_id}, "message_id": msg.get("message_id", 0)},
                "data": callback,
                "id": "internal",
            })
            return
        if not re.match(r"^https://[^\s]+$", text, re.I) or any(
            host in text.lower() for host in ("localhost", "127.0.0.1", "0.0.0.0")
        ):
            send_message(
                chat_id,
                render_body_text("❌ একটি valid public HTTPS Base URL দিন। শেষে /getnum যোগ করবেন না।"),
            )
            return
        state = user_states.pop(chat_id)
        temp_data.pop(chat_id, None)
        key = "stex_base_url" if state == "wait_for_stex_base_url" else "voltx_base_url"
        bot_settings[key] = text.rstrip("/")
        save_db()
        provider_title = "StexSMS" if key == "stex_base_url" else "Voltx"
        send_message(
            chat_id,
            render_body_text(f"✅ {provider_title} Base URL saved.\n<code>{html.escape(bot_settings[key])}</code>"),
            reply_markup=stex_control_keyboard() if key == "stex_base_url" else voltx_control_keyboard(),
        )
        return

    if admin and user_states.get(chat_id) == "wait_api_button_emoji":
        if text == "Cancel" or _api_button_matches(text, "cancel"):
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            send_message(chat_id, render_body_text("❌ API button emoji change cancelled."), reply_markup=main_menu(chat_id))
            return
        emoji_char, emoji_id = extract_custom_emoji(msg)
        if not emoji_id:
            send_message(
                chat_id,
                render_body_text("❌ একটি Telegram Premium Emoji পাঠান। সাধারণ emoji নয়।"),
                reply_markup=_api_cancel_keyboard(),
            )
            return
        key = temp_data.get(chat_id, {}).get("api_button_key")
        if not key:
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            send_message(chat_id, render_body_text("❌ Button setting পাওয়া যায়নি।"))
            return
        item = _api_button_config(key)
        bot_settings.setdefault("api_buttons", {})[key] = {
            "label": item.get("label", key.upper()),
            "char": emoji_char,
            "id": emoji_id,
            "style": item.get("style", "primary"),
        }
        save_db()
        admin_msg_id = temp_data.get(chat_id, {}).get("msg_id")
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        try:
            delete_message(chat_id, msg.get("message_id"))
        except Exception:
            pass
        if admin_msg_id:
            edit_message(
                chat_id,
                admin_msg_id,
                render_body_text("🎨 <b>API BUTTON EMOJIS</b>\n\nযে button-এর emoji বদলাতে চান সেটি নির্বাচন করুন।"),
                reply_markup=api_button_settings_keyboard(),
            )
        else:
            send_message(
                chat_id,
                render_body_text("✅ API button-এর Premium Emoji আপডেট হয়েছে।"),
                reply_markup=api_button_settings_keyboard(),
            )
        return

    # Admin panel-management input flow
    admin_mode = user_states.get(chat_id)
    if admin and admin_mode == "mks_route":
        panel_id = temp_data.get(chat_id, {}).get("panel_id")
        if text in ("Cancel", "❌ CANCEL"):
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            if panel_id:
                _show_mk_routes(chat_id, panel_id)
            else:
                send_message(chat_id, render_body_text("❌ Routing setup cancelled."), reply_markup=main_menu(chat_id))
            return

        parts = [part.strip() for part in text.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            send_message(
                chat_id,
                render_body_text(
                    "❌ Format ভুল। এভাবে পাঠান:\n"
                    "<code>FACEBOOK | BD | 88017,88018</code>"
                ),
                reply_markup=get_cancel_kb(),
            )
            return
        service, country, raw_ranges = parts
        ranges = [
            value.strip().upper()
            for value in re.split(r"[,;\s]+", raw_ranges)
            if value.strip()
        ]
        if (
            not re.match(r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,59}$", service)
            or not re.match(r"^[A-Za-z0-9][A-Za-z0-9 _./+-]{0,39}$", country)
            or not ranges
            or any(
                not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.*+#/-]{0,39}$", value)
                for value in ranges
            )
        ):
            send_message(
                chat_id,
                render_body_text(
                    "❌ Service, country বা range সঠিক নয়। উদাহরণ:\n"
                    "<code>WHATSAPP | IN | 9198,9199</code>"
                ),
                reply_markup=get_cancel_kb(),
            )
            return

        panel = _mk_panel(panel_id)
        if not panel:
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            send_message(chat_id, render_body_text("❌ Panel পাওয়া যায়নি।"))
            return

        duplicate_route = any(
            _number_catalog_key(route.get("service")) == _number_catalog_key(service)
            and _number_catalog_key(route.get("country")) == _number_catalog_key(country)
            for route in (panel.get("routes", []) or [])
        )
        if duplicate_route:
            send_message(
                chat_id,
                render_body_text(
                    f"{PEM['no']} এই panel-এ Service/Country আগে থেকেই আছে:\n"
                    f"<b>{html.escape(service)}</b> / <b>{html.escape(country)}</b>\n\n"
                    "একই নামের বড়/ছোট হাতের রূপ যোগ করা যাবে না। "
                    "Number, Letter বা Emoji যোগ করে নতুন নাম ব্যবহার করুন।"
                ),
                reply_markup=get_cancel_kb(),
            )
            return

        new_route = {
            "service": service.upper(),
            "country": country.upper(),
            "ranges": list(dict.fromkeys(ranges)),
        }
        routes = [
            route for route in (panel.get("routes", []) or [])
            if not (
                _number_catalog_key(route.get("service")) == _number_catalog_key(new_route["service"])
                and _number_catalog_key(route.get("country")) == _number_catalog_key(new_route["country"])
            )
        ]
        routes.append(new_route)
        panel["routes"] = routes
        _save_mk_panels([
            panel if item.get("id") == panel["id"] else item
            for item in _mk_panels()
        ])
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        send_message(
            chat_id,
            render_body_text(
                f"✅ Route saved: <b>{html.escape(new_route['service'])}</b> / "
                f"<b>{html.escape(new_route['country'])}</b> → "
                f"<code>{html.escape(', '.join(new_route['ranges']))}</code>\n\n"
                "এই country-তে আগে এই panel/range চেষ্টা হবে; খালি হলে পরের configured panel-এ যাবে."
            ),
        )
        _show_mk_routes(chat_id, panel["id"])
        return

    if admin and admin_mode in ("mks_name", "mks_url", "mks_key", "nps_name", "nps_url", "nps_key"):
        if text in ("Cancel", "❌ CANCEL"):
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            send_message(chat_id, render_body_text("❌ Panel setup cancelled."), reply_markup=main_menu(chat_id))
            return
        if admin_mode in ("mks_name", "nps_name"):
            temp_data[chat_id] = {"name": text[:60]}
            next_state = "nps_url" if admin_mode == "nps_name" else "mks_url"
            user_states[chat_id] = next_state
            example = "https://npsmsnetwork.com/api/index.php?route=user" if next_state == "nps_url" else "https://provider.example/api"
            send_message(chat_id, render_body_text(f"🌐 Panel base URL দিন:\n<code>{example}</code>"), reply_markup=get_cancel_kb())
            return
        if admin_mode in ("mks_url", "nps_url"):
            url = text.rstrip("/")
            if not re.match(r"^https://[^\s]+$", url, re.I) or any(x in url.lower() for x in ["localhost", "127.0.0.1", "0.0.0.0"]):
                send_message(chat_id, render_body_text("❌ Public HTTPS URL দিন।"), reply_markup=get_cancel_kb())
                return
            temp_data[chat_id]["base_url"] = url
            user_states[chat_id] = "nps_key" if admin_mode == "nps_url" else "mks_key"
            send_message(chat_id, render_body_text("🔐 API key দিন। Message পাঠানোর পরে delete করার চেষ্টা করা হবে."), reply_markup=get_cancel_kb())
            return
        if admin_mode in ("mks_key", "nps_key"):
            key = text.strip()
            try:
                delete_message(chat_id, msg.get("message_id"))
            except Exception:
                pass
            if len(key) < 4:
                send_message(chat_id, "❌ API key invalid.", reply_markup=get_cancel_kb())
                return
            data = temp_data.get(chat_id, {})
            name = data.get("name", "MK Panel")
            panels = _mk_panels()
            pid_base = _safe_panel_id(name)
            pid = pid_base
            i = 2
            while any(p["id"] == pid for p in panels):
                pid = f"{pid_base}-{i}"; i += 1
            panels.append({
                "id": pid,
                "name": name,
                "base_url": data["base_url"],
                "api_key": key,
                "protocol": "npnetwork" if admin_mode == "nps_key" else "mk",
                "enabled": True,
            })
            _save_mk_panels(panels)
            user_states.pop(chat_id, None)
            temp_data.pop(chat_id, None)
            title = "NP Network" if admin_mode == "nps_key" else "MK"
            send_message(chat_id, render_body_text(f"✅ {title} API panel added. এখন TEST চাপুন."), reply_markup=main_menu(chat_id))
            return

    # Existing DXnumbers behavior
    _original_dx_handle_message(msg)


_original_dx_handle_callback = handle_callback

def handle_callback(call):
    chat_id = call["message"]["chat"]["id"]
    data = call.get("data", "")
    if data in {
        "zt_profile_refer",
        "zt_profile_withdrawal",
        "zt_profile_history",
        "zt_profile",
        "zt_leaderboard",
        "zt_search_number",
    }:
        answer_callback(call["id"])
        if data == "zt_leaderboard":
            _zerotrace_user_leaderboard(chat_id, call["message"]["message_id"])
            return
        if data == "zt_profile":
            _zerotrace_profile_screen(chat_id)
            return
        if data == "zt_profile_history":
            _zerotrace_history_screen(chat_id)
            return
        routed_text = {
            "zt_profile_refer": "Refer",
            "zt_profile_withdrawal": "WITHDRAWAL",
            "zt_search_number": "Search Number",
        }[data]
        routed_message = {
            "chat": {"id": chat_id, "type": "private"},
            "text": routed_text,
        }
        _original_dx_handle_message(routed_message)
        return
    if data == "toggle_classic_cc":
        session = user_active_sessions.get(chat_id)
        if not session:
            answer_callback(call["id"], "Number session expired.", show_alert=True)
            return
        show_cc = not bool(session.get("show_cc", True))
        session["show_cc"] = show_cc
        number_display_preferences[chat_id] = show_cc
        text, markup = _classic_number_ui(session)
        edit_message(
            chat_id,
            call["message"]["message_id"],
            text,
            reply_markup=markup,
        )
        answer_callback(call["id"])
        return
    if not (data.startswith("mks_") or data.startswith("nps_") or data.startswith("np_") or data.startswith("api_") or data == "mk_manage_panels"):
        return _original_dx_handle_callback(call)
    callback_user_id = call.get("from", {}).get("id", chat_id)
    access_id = callback_user_id if data.startswith("api_getnum:") else chat_id
    if not is_admin(access_id) and not check_force_join(access_id):
        send_force_join_msg(access_id)
        return
    msg_id = call["message"]["message_id"]
    if not data.startswith("api_getnum:"):
        answer_callback(call["id"])

    if data.startswith("api_getnum:"):
        # This callback originates in a forwarding group.  Telegram's
        # message chat is the group, while the callback actor is the person
        # who should receive the newly allocated number.
        user_id = call.get("from", {}).get("id")
        token = data.split(":", 1)[1]
        with api_session_lock:
            request = dict(api_group_getnum_tokens.get(token, {}))
        if not user_id or not request or time.time() - request.get("created", 0) > API_SESSION_TIMEOUT:
            answer_callback(call["id"], "This GET NUMBER button has expired.", show_alert=True)
            return
        if not _dual_api_allowed(user_id):
            return
        if request.get("kind") == "legacy":
            answer_callback(call["id"], "Number is being fetched…")
            _legacy_group_get_number(user_id, request)
            return
        panel_id = request.get("panel_id")
        range_text = request.get("range")
        if not panel_id or not range_text:
            answer_callback(call["id"], "Panel/range information is unavailable.", show_alert=True)
            return
        answer_callback(call["id"], "Number is being fetched…")
        _api_number_action(
            user_id,
            preferred={
                "range": range_text,
                "panel_id": panel_id,
                "panel_name": request.get("panel_name", ""),
            },
            provider_id=panel_id,
            count=1,
        )
        return

    if data in {"mk_manage_panels", "np_manage_panels"}:
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can manage panels", show_alert=True)
            return
        _show_mk_admin(chat_id, msg_id)
        return
    if data == "mks_back":
        edit_message(chat_id, msg_id, render_body_text("⚙️ <b>SYSTEM SETTINGS</b>"), reply_markup=system_settings_keyboard())
        return
    if data.startswith("mks_routes:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can manage routes", show_alert=True)
            return
        panel_id = data.split(":", 1)[1]
        if not _mk_panel(panel_id):
            answer_callback(call["id"], "Panel not found", show_alert=True)
            return
        user_states.pop(chat_id, None)
        temp_data.pop(chat_id, None)
        _show_mk_routes(chat_id, panel_id, msg_id)
        return
    if data.startswith("mks_route_add:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can manage routes", show_alert=True)
            return
        panel_id = data.split(":", 1)[1]
        if not _mk_panel(panel_id):
            answer_callback(call["id"], "Panel not found", show_alert=True)
            return
        user_states[chat_id] = "mks_route"
        temp_data[chat_id] = {"msg_id": msg_id, "panel_id": panel_id}
        edit_message(
            chat_id,
            msg_id,
            render_body_text(
                "🧭 <b>ADD PANEL ROUTE</b>\n\n"
                "এক লাইনে পাঠান:\n"
                "<code>SERVICE | COUNTRY | RANGE1,RANGE2</code>\n\n"
                "উদাহরণ:\n"
                "<code>FACEBOOK | BD | 88017,88018</code>\n"
                "<code>WHATSAPP | IN | 9198</code>\n\n"
                "এই panel-এর custom route liveaccess-এর চেয়ে অগ্রাধিকার পাবে।"
            ),
            reply_markup=get_cancel_kb(),
        )
        return
    if data.startswith("mks_route_delete:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can manage routes", show_alert=True)
            return
        parts = data.split(":")
        if len(parts) != 3:
            answer_callback(call["id"], "Invalid route", show_alert=True)
            return
        panel_id, raw_index = parts[1], parts[2]
        try:
            route_index = int(raw_index)
        except ValueError:
            answer_callback(call["id"], "Invalid route", show_alert=True)
            return
        panel = _mk_panel(panel_id)
        routes = panel.get("routes", []) if panel else []
        if not panel or not 0 <= route_index < len(routes):
            answer_callback(call["id"], "Route not found", show_alert=True)
            return
        deleted = routes.pop(route_index)
        panel["routes"] = routes
        _save_mk_panels([
            panel if item.get("id") == panel_id else item
            for item in _mk_panels()
        ])
        answer_callback(call["id"], "✅ Route deleted", show_alert=True)
        _show_mk_routes(chat_id, panel_id, msg_id)
        return
    if data == "api_button_style":
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can change API button emojis", show_alert=True)
            return
        edit_message(
            chat_id,
            msg_id,
            render_body_text("🎨 <b>API BUTTON EMOJIS</b>\n\nযে button-এর Premium Emoji বদলাতে চান সেটি নির্বাচন করুন।"),
            reply_markup=api_button_settings_keyboard(),
        )
        return
    if data.startswith("api_btn_emoji:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin can change API button emojis", show_alert=True)
            return
        key = data.split(":", 1)[1]
        if key not in {"save_range", "api_number", "main_menu", "cancel", "otp_group", "change_number", "provider"}:
            answer_callback(call["id"], "Unknown API button", show_alert=True)
            return
        item = _api_button_config(key)
        user_states[chat_id] = "wait_api_button_emoji"
        temp_data[chat_id] = {"api_button_key": key, "msg_id": msg_id}
        edit_message(
            chat_id,
            msg_id,
            render_body_text(
                f"🎨 <b>CHANGE {item.get('label', key.upper())} EMOJI</b>\n\n"
                "এখন একটি Telegram Premium Emoji পাঠান।\n"
                "শুধু button-এর emoji বদলাবে; button-এর কাজ ও label একই থাকবে।"
            ),
            reply_markup=_api_cancel_inline_keyboard(),
        )
        return
    if data in {"mks_add", "nps_add"}:
        user_states[chat_id] = "nps_name" if data == "nps_add" else "mks_name"
        temp_data[chat_id] = {"msg_id": msg_id}
        title = "NP NETWORK" if data == "nps_add" else "GENERIC MK / FAST SMS"
        edit_message(chat_id, msg_id, render_body_text(f"➕ <b>ADD API PANEL ({title})</b>\n\nPanel name পাঠান:"), reply_markup=get_cancel_kb())
        return
    if data.startswith("mks_toggle:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin", show_alert=True); return
        pid = data.split(":", 1)[1]
        panels = _mk_panels()
        for p in panels:
            if p["id"] == pid:
                p["enabled"] = not p["enabled"]
        _save_mk_panels(panels)
        _show_mk_admin(chat_id, msg_id)
        return
    if data.startswith("mks_delete:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin", show_alert=True); return
        pid = data.split(":", 1)[1]
        _save_mk_panels([p for p in _mk_panels() if p["id"] != pid])
        _show_mk_admin(chat_id, msg_id)
        return
    if data.startswith("mks_test:"):
        if not is_admin(chat_id):
            answer_callback(call["id"], "Only admin", show_alert=True); return
        pid = data.split(":", 1)[1]
        panel = _mk_panel(pid)
        result = _mk_json_get(panel, "/api/liveaccess") if panel else None
        services = _api_liveaccess_services(result)
        send_message(chat_id, render_body_text(
            f"🧪 <b>{html.escape(panel['name'] if panel else pid)}</b>\n"
            + (f"✅ {len(services)} service(s) available" if services else "❌ Test failed or no service returned")
        ))
        return
    if data == "api_cancel_range":
        user_states.pop(chat_id, None)
        if temp_data.get(chat_id, {}).get("api_button_key"):
            temp_data.pop(chat_id, None)
            edit_message(
                chat_id,
                msg_id,
                render_body_text("🎨 <b>API BUTTON EMOJIS</b>\n\nযে button-এর emoji বদলাতে চান সেটি নির্বাচন করুন।"),
                reply_markup=api_button_settings_keyboard(),
            )
            return
        edit_message(chat_id, msg_id, render_body_text("❌ Range save cancelled."), reply_markup=_api_number_keyboard())
        return
    if data == "api_save_range":
        user_states[chat_id] = "api_wait_range"
        edit_message(chat_id, msg_id, render_body_text("💾 <b>SAVE API RANGE</b>\n\nRange পাঠান। উদাহরণ: <code>234XXX</code>"), reply_markup=_api_cancel_inline_keyboard())
        return
    if data == "api_main_menu":
        edit_message(chat_id, msg_id, render_body_text("🏠 <b>MAIN MENU</b>"))
        send_message(chat_id, render_body_text("✅ Main menu restored."), reply_markup=main_menu(chat_id))
        return
    if data == "api_get_numbers":
        _show_api_provider_menu(chat_id, msg_id)
        return
    if data.startswith("api_provider:"):
        provider_id = data.split(":", 1)[1]
        saved = _get_user_api_ranges(chat_id)
        preferred = saved[-1] if saved else None
        _api_number_action(chat_id, msg_id, preferred=preferred, provider_id=provider_id)
        return
    if data == "api_change_country":
        # Return to the same service/country selector used by GET NUMBER.
        # This keeps API results from trapping the user in the saved-range
        # flow and provides the expected Change Country action.
        return _original_dx_handle_callback({**call, "data": "get_number_menu"})
    if data == "api_toggle_cc":
        with api_session_lock:
            current_session = api_number_sessions.get(chat_id)
            if not current_session:
                current_session = None
            else:
                show_cc = not bool(current_session.get("show_cc", True))
                current_session["show_cc"] = show_cc
                api_number_display_preferences[chat_id] = show_cc
                items = list(current_session.get("items", []) or [])
                if not items:
                    items = [{
                        "number": assignment.get("number", ""),
                        "panel_name": current_session.get("panel_name", "API Panel"),
                        "range": assignment.get("range", current_session.get("range", "")),
                    } for assignment in current_session.get("assignments", [])]
                active_message_id = current_session.get("message_id") or msg_id
        if not current_session:
            answer_callback(call["id"], "API number session expired.", show_alert=True)
            return
        edit_message(
            chat_id,
            active_message_id,
            render_body_text(_api_number_result_text(items, show_cc=show_cc)),
            reply_markup=_api_result_inline_keyboard(
                bot_settings.get("otp_link", ""),
                items,
                show_cc=show_cc,
            ),
        )
        return
    if data == "api_change_number":
        with api_session_lock:
            current_session = dict(api_number_sessions.get(chat_id, {}))
        if not current_session.get("panel_id") or not current_session.get("range"):
            answer_callback(call["id"], "API number session expired. Press API NUMBER again.", show_alert=True)
            send_message(chat_id, render_body_text("⚠️ API session শেষ হয়েছে। নতুন provider বাছাই করতে আবার 📞 API NUMBER চাপুন."), reply_markup=_api_number_keyboard())
            return
        preferred = {
            "range": current_session.get("range"),
            "panel_id": current_session.get("panel_id"),
            "panel_name": current_session.get("panel_name", ""),
        }
        _api_number_action(
            chat_id,
            message_id=msg_id,
            preferred=preferred,
            provider_id=current_session.get("panel_id"),
        )
        return
    if data in ("api_no_group", "api_open_group"):
        answer_callback(call["id"], "Admin has not configured an OTP group", show_alert=True)
        return


def _dual_api_allowed(chat_id):
    if is_admin(chat_id):
        return True
    if is_user_banned(chat_id):
        send_message(chat_id, render_body_text("🚫 <b>You are banned from using this bot!</b>"))
        return False
    if not check_force_join(chat_id):
        send_force_join_msg(chat_id)
        return False
    return True


# ==========================================
# API NUMBER V2: MULTI-PROVIDER + DX FORWARD GROUPS
# ==========================================
# API Number checks all enabled API providers against the user's last saved
# range, shows the matching providers, and takes two numbers from the provider
# selected by the user. OTPs are sent to the user and to the same groups/buttons
# configured in the DX admin panel.


def _find_matching_mk_panels(range_text):
    matches = []
    wanted = re.sub(r"\s+", "", str(range_text).upper())
    for panel in _mk_panels(enabled_only=True):
        # Explicit routes are authoritative when present, including routes
        # that are not currently returned by the provider's liveaccess feed.
        configured_ranges = [
            str(value)
            for route in (panel.get("routes", []) or [])
            for value in (route.get("ranges", []) or [])
        ]
        if any(re.sub(r"\s+", "", value.upper()) == wanted for value in configured_ranges):
            matches.append(panel)
            continue
        data = _mk_json_get(panel, "/api/liveaccess") or {}
        services = _api_liveaccess_services(data)
        if any(re.sub(r"\s+", "", str(r).upper()) == wanted
               for service in services for r in (service.get("ranges") or [])):
            matches.append(panel)
    return matches


def _find_panel_for_range(range_text):
    matches = _find_matching_mk_panels(range_text)
    if not matches:
        return None
    return {
        "id": "multi-match", "name": ", ".join(p["name"] for p in matches)[:120],
        "base_url": "", "api_key": "", "enabled": True,
        "matched_panel_ids": [p["id"] for p in matches],
    }


def _add_user_api_range(user_id, range_text, panel=None):
    """Save exactly one latest range in the local JSON database and fallback file."""
    matches = _find_matching_mk_panels(range_text)
    if not matches and panel and panel.get("id") != "multi-match":
        matches = [panel]
    if not matches:
        return []
    ids = [p["id"] for p in matches]
    names = [p["name"] for p in matches]
    record = {
        "range": str(range_text).upper(),
        "panel_ids": ids,
        "panel_names": names,
        "saved_at": datetime.now().isoformat(),
    }
    with api_range_lock:
        data = _load_api_ranges()
        # User requirement: only the newest range is retained.
        data[str(user_id)] = [record]
        _save_api_ranges(data)
        if db:
            try:
                db.collection("users").document(str(user_id)).set(
                    {"api_last_range": record}, merge=True
                )
            except Exception as e:
                print(f"[API ranges] Local DB write error: {type(e).__name__}")
    return [record]


def _api_sources_for_user(chat_id, preferred_range=None, provider_id=None):
    saved = _get_user_api_ranges(chat_id)
    # A user clicking GET NUMBER from an OTP group may not have saved an API
    # range yet.  In that case the callback's exact panel/range is trusted
    # only after it has been looked up from the short-lived server token.
    if not saved and not preferred_range:
        return []
    entry = saved[-1] if saved else {}
    range_text = str(preferred_range or entry.get("range", "")).upper()
    if not range_text:
        return []
    sources = []
    for panel in _mk_panels(enabled_only=True):
        if provider_id and panel["id"] != str(provider_id):
            continue
        sources.append((panel, range_text))
    return sources


def _fetch_api_numbers(chat_id, preferred_range=None, provider_id=None, count=2):
    sources = _api_sources_for_user(chat_id, preferred_range, provider_id)
    fetched, successful = [], []
    count = max(1, int(count or 1))
    # A selected provider supplies the requested number of numbers. Provider/
    # range validity is checked before this function is called by the normal
    # inline-button flow; group callbacks already carry the exact range.
    for panel, range_text in sources:
        for _ in range(count):
            item = _mk_get_number(panel, range_text)
            if item and item["number"] not in {x["number"] for x in fetched}:
                fetched.append(item)
        if fetched:
            successful.append((panel, range_text))
        if len(fetched) >= count:
            break
    return fetched[:count], successful


def _fetch_two_api_numbers(chat_id, preferred_range=None, provider_id=None):
    return _fetch_api_numbers(chat_id, preferred_range, provider_id, count=2)


def _api_number_result_text(items, show_cc=True):
    lines = []
    for item in items:
        display_number = _display_api_number(item["number"], show_cc=show_cc)
        lines.append(
            f"🌍 <code>{display_number}</code> "
            f"<i>({html.escape(str(item.get('panel_name', 'Fast OTP')))})</i>"
        )
    return _imran_number_result_text(
        lines,
        "🛰 <b>API Number</b>",
        numbers=[item.get("number", "") for item in items],
    )


def _api_otp_items(payload):
    """Accept common MK/NP OTP response envelopes."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    if any(
        payload.get(key) is not None
        for key in _PANEL_NUMBER_KEYS
    ) and any(payload.get(key) is not None for key in ("message", "otp", "sms", "code", "text")):
        return [payload]
    for key in ("otps", "sms", "messages", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    for key in ("data", "result", "response"):
        value = payload.get(key)
        found = _api_otp_items(value)
        if found:
            return found
    return []


def _format_api_group_message(panel, number, sms, otp, range_text=""):
    """Backward-compatible alias for the API OTP group formatter."""
    return _format_api_dx_group_message(panel, number, sms, otp, range_text)


def _format_user_otp_inbox_message(number, reward=None):
    """Build the compact inbox OTP message used by every number source."""
    if reward is None:
        reward = float(bot_settings.get("otp_reward", 0.0))
    clean = re.sub(r"\D", "", str(number))
    display = f"+{clean}" if clean else str(number)
    return render_body_text(
        f"☎️ <code>{html.escape(display)}</code>\n"
        f"👛 <b>{float(reward):+.4f}$</b>"
    )


def _format_api_user_otp_message(panel, number, sms, otp, range_text, reward):
    """Build the compact API-number inbox message.

    The OTP itself is deliberately supplied as a Telegram copy button by the
    caller, matching the normal inbox experience.
    """
    return _format_user_otp_inbox_message(number, reward)


def _format_api_dx_group_message(panel, number, sms, otp, range_text=""):
    """Build the screenshot-style API OTP card for forwarding groups.

    API NUMBER group messages never expose the allocated phone number; only
    the exact range used for that OTP is shown.
    """
    shown_range = str(range_text or "").strip() or "Unknown range"
    service = detect_service(str(sms)) or panel.get("name", "API Service")
    app_name, app_html = get_service_info_html(service, str(sms))
    # Show the service's premium emoji (e.g. the Instagram camera icon) next to
    # its name so the header card looks big and bold, matching the design.
    service_label = html.escape(str(app_name).upper())
    language = detect_language(str(sms)).lstrip("#")
    range_flag = get_flag_info_html(shown_range)
    return render_body_text(
        f"╔═══════════════╗\n"
        f"║ {range_flag} <code>{html.escape(shown_range)}</code> | "
        f"{app_html} {service_label} | 🔊 {html.escape(language)}\n"
        f"╚═══════════════╝\n\n"
        f"💬 {html.escape(str(sms))}"
    )


def _register_api_group_getnum(panel, range_text):
    """Register the panel/range behind a permanent group GET NUMBER button."""
    token = uuid.uuid4().hex[:12]
    with api_session_lock:
        api_group_getnum_tokens[token] = {
            "panel_id": panel.get("id", ""),
            "panel_name": panel.get("name", "API Panel"),
            "range": str(range_text or "").strip(),
            "created": time.time(),
        }
    return _group_get_number_link(token)


def _country_code_from_number(number):
    clean = re.sub(r"\D", "", str(number))
    for code in sorted(bot_settings.get("premium_flags", {}).keys(), key=len, reverse=True):
        if clean.startswith(str(code)):
            return str(code)
    return ""


def _register_legacy_group_getnum(provider, number, service="", country=""):
    """Register the source behind a GET NUMBER OTP group's button."""
    clean = re.sub(r"\D", "", str(number))
    meta = dict(legacy_assignment_meta.get(clean, {}))
    provider = str(meta.get("provider") or provider or "").lower()
    service = str(meta.get("service") or service or "").strip()
    country = str(meta.get("country") or country or _country_code_from_number(clean)).strip()
    range_id = str(meta.get("range") or country).strip()
    token = uuid.uuid4().hex[:12]
    with api_session_lock:
        api_group_getnum_tokens[token] = {
            "kind": "legacy",
            "provider": provider,
            "service": service,
            "country": country,
            "range": range_id,
            "created": time.time(),
        }
    return _group_get_number_link(token)


def _group_get_number_link(token):
    """Return a bot deep link that routes the user into private chat first."""
    username = str(BOT_USERNAME or os.environ.get("BOT_USERNAME", "")).strip().lstrip("@")
    if not username:
        # The production process populates BOT_USERNAME via getMe before any
        # OTP group message is sent. Keep a safe fallback for local startup.
        return f"https://t.me/?start=gn_{token}"
    return f"https://t.me/{username}?start=gn_{token}"


def _normalize_inline_url(value):
    """Turn common admin-entered links into Telegram-valid button URLs."""
    url = str(value or "").strip()
    if not url:
        return ""
    if url.startswith("t.me/"):
        return "https://" + url
    if url.startswith("@"):
        return "https://t.me/" + url[1:]
    if not re.match(r"^(?:https?|tg)://", url, re.I):
        return "https://" + url
    return url


def _process_group_get_number_token(user_id, token):
    """Resolve a group deep-link and deliver the number in private chat."""
    token = str(token or "").strip()
    with api_session_lock:
        request = dict(api_group_getnum_tokens.get(token, {}))
    if (
        not token
        or not request
        or time.time() - request.get("created", 0) > API_SESSION_TIMEOUT
    ):
        send_message(
            user_id,
            render_body_text(
                "⚠️ এই GET NUMBER link-এর মেয়াদ শেষ হয়েছে। "
                "OTP Group থেকে নতুন link চাপুন।"
            ),
        )
        return
    if not _dual_api_allowed(user_id):
        return
    if request.get("kind") == "legacy":
        send_message(
            user_id,
            render_body_text("⌛ <i>Processing... Finding Number...</i>"),
        )
        _legacy_group_get_number(user_id, request)
        return
    panel_id = request.get("panel_id")
    range_text = request.get("range")
    if not panel_id or not range_text:
        send_message(
            user_id,
            render_body_text("❌ Panel/range information is unavailable."),
        )
        return
    # Same number count the admin set for the normal GET NUMBER flow
    # (NUM/REQ), so the OTP-group button gives as many numbers as the menu.
    requested_count = max(1, int(bot_settings.get("num_req", 1)))
    _api_number_action(
        user_id,
        preferred={
            "range": range_text,
            "panel_id": panel_id,
            "panel_name": request.get("panel_name", ""),
        },
        provider_id=panel_id,
        count=requested_count,
    )


def _legacy_group_get_number(user_id, request):
    """Allocate the same number count as the normal GET NUMBER flow."""
    global total_assigned_stats, legacy_assignment_meta

    provider = str(request.get("provider") or "").lower()
    service = str(request.get("service") or "").strip()
    country = str(request.get("country") or "").strip()
    preferred_range = str(request.get("range") or "").strip()
    requested_count = max(1, int(bot_settings.get("num_req", 1)))
    fetched_numbers = []
    seen = set()

    # A provider-specific OTP keeps the same provider. If the source is
    # unknown, use the normal GET NUMBER priority. If the original provider
    # cannot fill the configured count, the other API provider is used as the
    # normal GET NUMBER fallback.
    providers = [provider] if provider in {"stex", "voltx"} else (
        [] if provider == "local" else ["stex", "voltx"]
    )
    if provider in {"stex", "voltx"}:
        other = "voltx" if provider == "stex" else "stex"
        providers.append(other)

    for source in providers:
        if len(fetched_numbers) >= requested_count:
            break
        services_key = "stex_services" if source == "stex" else "voltx_services"
        keys_key = "stex_keys" if source == "stex" else "voltx_keys"
        service_map = bot_settings.get(services_key, {})
        service_key = next(
            (key for key in service_map if str(key).upper() == service.upper()),
            service,
        )
        country_map = service_map.get(service_key, {}) if isinstance(service_map, dict) else {}
        country_key = next(
            (key for key in country_map if str(key) == country),
            country,
        )
        ranges = list(country_map.get(country_key, []) or []) if isinstance(country_map, dict) else []
        if preferred_range in ranges:
            ranges = [preferred_range] + [r for r in ranges if r != preferred_range]
        keys = [str(key).strip() for key in bot_settings.get(keys_key, []) if str(key).strip()]
        if not ranges or not keys:
            continue

        # Repeat the provider request until NUM_REQ is filled, while avoiding
        # duplicate numbers returned by a panel.
        for _ in range(requested_count - len(fetched_numbers)):
            found = False
            for range_id in ranges:
                for api_key in keys:
                    candidate = _legacy_panel_get_number(source, api_key, range_id)
                    clean = re.sub(r"\D", "", str(candidate))
                    if not clean or clean in seen:
                        continue
                    seen.add(clean)
                    fetched_numbers.append(clean)
                    assignments = (
                        stex_assigned_numbers
                        if source == "stex"
                        else voltx_assigned_numbers
                    )
                    assignments[clean] = user_id
                    legacy_assignment_meta[clean] = {
                        "provider": source,
                        "service": str(service_key),
                        "country": str(country_key),
                        "range": str(range_id),
                    }
                    total_assigned_stats += 1
                    found = True
                    break
                if found:
                    break
            if not found:
                break

    # Uploaded stock fills any remaining slots, just like the normal GET
    # NUMBER fallback after both API providers.
    if len(fetched_numbers) < requested_count:
        candidates = []
        for batch_id, batch in number_batches.items():
            if str(batch.get("service", "")).upper() != service.upper():
                continue
            if str(batch.get("country", "")) != country:
                continue
            for index, item in enumerate(batch.get("numbers", [])):
                if user_id not in item.get("used_by", []):
                    candidates.append((batch_id, index))
        random.shuffle(candidates)
        for batch_id, index in candidates:
            if len(fetched_numbers) >= requested_count:
                break
            item = number_batches[batch_id]["numbers"][index]
            number = re.sub(r"\D", "", str(item.get("num", "")))
            if not number or number in seen:
                continue
            seen.add(number)
            fetched_numbers.append(number)
            item["shares"] = int(item.get("shares", 0)) + 1
            item.setdefault("used_by", []).append(user_id)
            legacy_assignment_meta[number] = {
                "provider": "local",
                "service": service,
                "country": country,
                "range": country,
            }
            total_assigned_stats += 1
            if item["shares"] >= bot_settings.get("num_share", 1):
                item["to_remove"] = True
                used_numbers_list.append(item.get("num", number))
        for batch_id in number_batches:
            number_batches[batch_id]["numbers"] = [
                x for x in number_batches[batch_id]["numbers"] if not x.get("to_remove")
            ]

    if not fetched_numbers:
        send_message(
            user_id,
            render_body_text("❌ এই country/range-এর নতুন number বর্তমানে পাওয়া যাচ্ছে না।"),
        )
        return

    current = dict(user_active_sessions.get(user_id, {}))
    numbers = list(current.get("nums", []))
    for number in fetched_numbers:
        if number not in numbers:
            numbers.append(number)
    user_active_sessions[user_id] = {"msg_id": current.get("msg_id"), "nums": numbers}
    save_db()
    app_name, _ = get_service_info_html(service or "GET NUMBER")
    number_lines = []
    number_buttons = []
    for number in fetched_numbers:
        display_number = f"+{number}"
        number_lines.append(f"{get_flag_info_html(display_number)} <code>{display_number}</code>")
        number_buttons.append([_number_copy_button(display_number, service)])
    send_message(
        user_id,
        render_body_text(
            "╔═══════════════╗\n"
            "║ 📱 <b>YOUR NUMBERS</b>\n"
            "╚═══════════════╝\n"
            f"{html.escape(app_name)}\n"
            + "\n".join(number_lines)
        ),
        reply_markup={"inline_keyboard": number_buttons},
    )


def _legacy_group_keyboard(fw, otp, number, provider, service="", country=""):
    """Build the shared OTP-group keyboard for legacy GET NUMBER messages.

    Uses only standard Telegram inline button fields (text/text/url and
    text/callback_data) so the GET NUMBER and OTP buttons are always shown,
    even on older Bot API versions that reject Premium fields (style,
    icon_custom_emoji_id, copy_text).
    """
    get_number_token = _register_legacy_group_getnum(
        provider, number, service, country
    )
    return _otp_group_inline_keyboard(
        otp, get_number_token, extra_buttons=fw.get("buttons", [])
    )


def _forward_api_otp_to_dx_groups(panel, number, sms, otp, range_text=""):
    # Uses the exact fw_groups list and buttons maintained by DX Admin Panel.
    for fw in bot_settings.get("fw_groups", []):
        try:
            get_number_token = _register_api_group_getnum(panel, range_text)
            # Admin buttons + OTP copy on top rows, full-width GET NUMBER below.
            keyboard = _otp_group_inline_keyboard(
                otp, get_number_token, extra_buttons=fw.get("buttons", [])
            )
            send_message(
                fw["chat_id"],
                _format_api_dx_group_message(panel, number, sms, otp, range_text),
                reply_markup={"inline_keyboard": keyboard}
            )
        except Exception as e:
            print(f"[API Number] group forward error: {e}")

def _api_number_action(chat_id, message_id=None, preferred=None, provider_id=None, count=2):
    preferred_range = preferred.get("range") if isinstance(preferred, dict) else None
    items, successful = _fetch_api_numbers(chat_id, preferred_range, provider_id, count=count)
    if not items:
        quantity = "১টি" if int(count or 1) == 1 else f"{int(count or 1)}টি"
        text = f"❌ নির্বাচিত provider-এ এই range-এর {quantity} number বর্তমানে পাওয়া যায়নি।"
        _deliver_number_result(
            chat_id,
            render_body_text(text),
            reply_markup=_api_number_keyboard(),
            message_id=message_id,
        )
        return
    user_states.pop(chat_id, None)
    default_range = items[0].get("range", preferred_range or "")
    assignments = [{"number": x["number"], "panel_id": x["panel_id"],
                    "panel_name": x["panel_name"], "range": x.get("range", default_range)} for x in items]
    selected_panel_id = items[0].get("panel_id", provider_id or "")
    show_cc = bool(api_number_display_preferences.get(chat_id, True))
    with api_session_lock:
        api_number_sessions[chat_id] = {
            "user_id": chat_id, "range": default_range,
            "panel_id": selected_panel_id, "panel_name": items[0].get("panel_name", "API Panel"),
            "assignments": assignments, "items": items,
            "numbers": [x["number"] for x in items],
            "show_cc": show_cc, "created": time.time()
        }
    text = _api_number_result_text(items, show_cc=show_cc)
    result_markup = _api_result_inline_keyboard(
        bot_settings.get("otp_link", ""), items, show_cc=show_cc
    )
    _result, active_message_id = _deliver_number_result(
        chat_id,
        render_body_text(text),
        reply_markup=result_markup,
        message_id=message_id,
    )
    if active_message_id:
        with api_session_lock:
            api_number_sessions[chat_id]["message_id"] = active_message_id


def _api_monitor_thread():
    while True:
        try:
            now = time.time()
            with api_session_lock:
                for uid in list(api_number_sessions):
                    if now - api_number_sessions[uid].get("created", now) > API_SESSION_TIMEOUT:
                        del api_number_sessions[uid]
                for token in list(api_group_getnum_tokens):
                    if now - api_group_getnum_tokens[token].get("created", now) > API_SESSION_TIMEOUT:
                        del api_group_getnum_tokens[token]
                sessions = list(api_number_sessions.values())
            for panel in _mk_panels(enabled_only=True):
                panel_sessions = [s for s in sessions if any(
                    a.get("panel_id") == panel["id"] for a in s.get("assignments", []))]
                if not panel_sessions:
                    continue
                data = _mk_json_get(panel, "/api/success-otp-info") or {}
                items = _api_otp_items(data)
                for item in items:
                    number = _extract_panel_number(item)
                    matched_sessions = [s for s in panel_sessions if any(
                        a.get("panel_id") == panel["id"]
                        and _numbers_match(a.get("number"), number)
                        for a in s.get("assignments", [])
                    )]
                    if len(matched_sessions) != 1:
                        if len(matched_sessions) > 1:
                            print(
                                f"[API Number] ambiguous OTP mapping skipped: "
                                f"panel={panel['id']} number={number}"
                            )
                        continue
                    session = matched_sessions[0]
                    assignment = next((
                        a for a in session.get("assignments", [])
                        if a.get("panel_id") == panel["id"]
                        and _numbers_match(a.get("number"), number)
                    ), {})
                    range_text = assignment.get("range") or session.get("range", "")
                    sms = item.get("message") or item.get("otp") or item.get("sms") or "No Content"
                    code = extract_otp_code(str(sms)) or "N/A"
                    oid = str(item.get("otp_id") or f"{number}_{code}")
                    unique = f"{panel['id']}::{number}::{oid}"
                    if unique in api_seen_otps:
                        continue
                    api_seen_otps.add(unique)
                    if len(api_seen_otps) > 10000: api_seen_otps.clear()
                    owner_id = session["user_id"]
                    reward = float(bot_settings.get("otp_reward", 0.0))
                    if reward > 0:
                        update_balance(owner_id, reward)

                    # Keep API OTPs included in the same user statistics and
                    # two-hour traffic view as the existing DX listeners.
                    char, iso = get_flag_and_code(number)
                    detected_service = detect_service(str(sms)) or panel.get("name", "API Service")
                    service_name, _ = get_service_info_html(detected_service, str(sms))
                    recent_traffic.append({
                        "source": "API Number",
                        "service": service_name,
                        "iso": iso,
                        "flag": char,
                        "number": number,
                        "range": range_text,
                        "time": time.time(),
                    })
                    if owner_id in user_cache:
                        user_cache[owner_id]["total_otps"] = int(user_cache[owner_id].get("total_otps", 0)) + 1
                    if db:
                        try:
                            db.collection("users").document(str(owner_id)).update({
                                "total_otps": local_increment(1),
                                "verified": True,
                            })
                        except Exception as e:
                            print(f"[API Number] stats update error: {e}")
                    save_local_db()

                    _record_user_history(
                        owner_id, f"+{number}", code, reward, service_name, "API NUMBER"
                    )
                    send_message(
                        owner_id,
                        _format_api_user_otp_message(
                            panel, number, str(sms), code,
                            range_text, reward
                        ),
                        reply_markup={"inline_keyboard": [[{
                            "text": str(code),
                            "icon_custom_emoji_id": "5353022963132174959",
                            "copy_text": {"text": str(code)},
                            "style": "success",
                        }]]}
                    )
                    # Group message remains in the existing DX forward-group style.
                    _forward_api_otp_to_dx_groups(panel, number, str(sms), code, range_text)
        except Exception as e:
            print(f"[API Number] multi-panel monitor error: {e}")
        time.sleep(max(3, int(os.environ.get("MK_CHECK_INTERVAL", "5"))))


def _show_mk_admin(chat_id, message_id=None):
    text = (
        "🛰 <b>API PANEL CONTROL</b>\n\n"
        "MK Online SMS, Fast SMS বা অন্য authorized API provider যোগ করুন।\n"
        "Admin এখানে panel add, ON/OFF, test, delete এবং প্রতি panel-এর "
        "service/country/range ROUTES ঠিক করতে পারবে।"
    )
    if message_id:
        edit_message(chat_id, message_id, render_body_text(text), reply_markup=_mk_admin_keyboard())
    else:
        send_message(chat_id, render_body_text(text), reply_markup=_mk_admin_keyboard())

def _notify_owner_on_start():
    """Send the bot username to the owner's group as soon as the bot starts.

    This lets you know instantly that THIS code is running somewhere, and gives
    you the exact bot username.  Target group is taken from the STARTUP_ALERT_GROUP
    env variable, or falls back to the first configured OTP forward group.
    The owner id itself is never printed anywhere.
    """
    if not BOT_USERNAME:
        return
    # Prefer STARTUP_ALERT_GROUP from the environment; fall back to a
    # built-in default so the startup notification always reaches your group.
    target = os.environ.get("STARTUP_ALERT_GROUP", "").strip()
    if not target:
        target = "-1004462806501"
    if not target and bot_settings.get("fw_groups"):
        target = bot_settings["fw_groups"][0].get("chat_id", "")
    if not target:
        return
    try:
        send_message(
            target,
            render_body_text(
                f"{PEM['rocket']} <b>BOT IS LIVE!</b>\n"
                f"{PEM['user']} Username: <code>@{BOT_USERNAME}</code>\n"
                f"{PEM['gear']} Code started successfully."
            ),
        )
    except Exception as e:
        print(f"[startup notify] error: {type(e).__name__}: {e}")


def main():
    global BOT_USERNAME
    res = api_call("getMe")
    if res.get("ok"): BOT_USERNAME = res["result"]["username"]
    print(f"🤖 Bot is starting... @{BOT_USERNAME}")
    
    threading.Thread(target=panel_monitor_thread, daemon=True).start()
    threading.Thread(target=global_sms_listener, daemon=True).start()
    threading.Thread(target=voltx_sms_listener, daemon=True).start()
    threading.Thread(target=_api_monitor_thread, daemon=True).start()
    threading.Thread(target=slvn_rental_janitor_thread, daemon=True).start()
    print("📡 Background APIs, Global SMS Listener & API Number Monitor Started!")

    # 🔔 Tell the owner's group we are live (with the bot username).
    try:
        _notify_owner_on_start()
    except Exception as e:
        print(f"[startup notify] error: {type(e).__name__}: {e}")
    
    # 🌟 PRO-LEVEL FAST SYSTEM: 500 Workers Pool
    executor = ThreadPoolExecutor(max_workers=500)
    
    offset = None
    while True:
        try:
            updates = api_call(f"getUpdates?timeout=50&offset={offset}")
            if updates and "result" in updates:
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update: 
                        executor.submit(handle_message, update["message"])
                    elif "callback_query" in update: 
                        executor.submit(handle_callback, update["callback_query"])
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()
