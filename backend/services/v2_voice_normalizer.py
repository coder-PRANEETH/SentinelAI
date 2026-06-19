from difflib import SequenceMatcher
import re


EVENT_TYPE_DATASET = {
    "accident": ["accident", "axident", "crash", "collision"],
    "congestion": ["congestion", "traffic", "traffic jam", "jam", "slow moving"],
    "road_block": ["road block", "roadblock", "road blocked", "blocked"],
    "vehicle_breakdown": ["breakdown", "vehicle breakdown"],
    "fire": ["fire"],
    "medical_emergency": ["medical", "ambulance", "injured"],
}

TRAFFIC_CONDITION_DATASET = {
    "blocked": ["blocked", "road blocked", "road block", "not moving", "stopped"],
    "slow_moving": ["slow", "slow moving", "heavy traffic", "jam", "congestion"],
    "normal": ["normal", "clear", "okay", "moving"],
}

SEVERITY_DATASET = {
    "high": ["high", "hai", "height", "serious", "major", "emergency", "critical"],
    "medium": ["medium", "mediam", "median", "moderate", "normal severity", "not too serious"],
    "low": ["low", "lo", "love", "hello", "hi", "minor", "small", "not serious"],
}

LOCATION_DATASET = {
    "Silk Board Junction": [
        "silk board", "silk board junction", "silkboard", "silk board signal",
        "central silk board", "silk board flyover", "silk board traffic",
        "silk board road", "silkboard junction", "silkboard signal"
    ],
    "Electronic City": [
        "electronic city", "electronics city", "electronic city phase one",
        "electronic city phase 1", "electronic city phase two",
        "electronic city phase 2", "ecity", "e city", "electronic city toll",
        "electronic city flyover", "infosys electronic city", "wipro electronic city"
    ],
    "Hosur Road": [
        "hosur road", "osur road", "hosur main road", "bangalore hosur road",
        "electronic city road", "bommanahalli hosur road", "madivala hosur road"
    ],
    "Outer Ring Road": [
        "outer ring road", "orr", "o r r", "outer ring", "ring road",
        "bellandur outer ring road", "marathahalli outer ring road",
        "kadubeesanahalli outer ring road", "ecospace outer ring road",
        "manyata outer ring road"
    ],
    "Marathahalli": [
        "marathahalli", "marathalli", "maratahalli", "marathahalli bridge",
        "marathahalli junction", "marathahalli signal", "marathahalli flyover",
        "marathahalli market", "marathahalli main road"
    ],
    "Bellandur": [
        "bellandur", "belandur", "bellandur lake", "bellandur signal",
        "bellandur junction", "bellandur gate", "bellandur outer ring road",
        "ecospace bellandur"
    ],
    "Sarjapur Road": [
        "sarjapur road", "sarjapur", "sarjapura road", "sarjapur main road",
        "wipro sarjapur", "doddakannelli sarjapur road", "carmelaram sarjapur road"
    ],
    "Whitefield": [
        "whitefield", "white field", "whitefield main road", "whitefield road",
        "whitefield signal", "whitefield metro", "hope farm whitefield",
        "itpl whitefield", "kadugodi whitefield"
    ],
    "ITPL": [
        "itpl", "i t p l", "international tech park", "itpl road",
        "itpl main road", "itpl whitefield", "itpl bus stop", "itpl signal"
    ],
    "KR Puram": [
        "kr puram", "k r puram", "krishnarajapuram", "kr puram railway station",
        "kr puram bridge", "kr puram hanging bridge", "kr puram junction",
        "kr puram signal", "kr puram metro"
    ],
    "Tin Factory": [
        "tin factory", "tin factory junction", "tin factory signal",
        "tin factory bus stop", "tin factory kr puram", "tin factory bridge"
    ],
    "Old Madras Road": [
        "old madras road", "omr bangalore", "madras road", "bengaluru old madras road",
        "kr puram old madras road", "indiranagar old madras road"
    ],
    "Indiranagar": [
        "indiranagar", "indira nagar", "indiranagar metro", "100 feet road indiranagar",
        "hundred feet road indiranagar", "cmh road", "12th main indiranagar",
        "indiranagar signal"
    ],
    "MG Road": [
        "mg road", "m g road", "mahatma gandhi road", "mg road metro",
        "brigade road mg road", "trinity mg road", "mg road signal"
    ],
    "Brigade Road": [
        "brigade road", "brigade", "brigade road junction", "brigade road signal",
        "mg road brigade road"
    ],
    "Church Street": [
        "church street", "church road", "church street bangalore", "church street mg road"
    ],
    "Cubbon Park": [
        "cubbon park", "cubbon park metro", "cubbon road", "cubbon park road",
        "vidhana soudha cubbon park"
    ],
    "Vidhana Soudha": [
        "vidhana soudha", "vidhana soudha metro", "vidhana soudha road",
        "high court bangalore", "attara kacheri"
    ],
    "Majestic": [
        "majestic", "kempegowda bus station", "kempegowda bus stand",
        "majestic bus stand", "majestic metro", "kempegowda metro",
        "kg bus stand", "ksrtc majestic", "bmtc majestic"
    ],
    "KSR Bengaluru Railway Station": [
        "ksr railway station", "ksr bengaluru railway station",
        "bangalore city railway station", "bengaluru city station",
        "city railway station", "majestic railway station", "sbc railway station"
    ],
    "Yeshwanthpur": [
        "yeshwanthpur", "yesvantpur", "yeshwanthpur railway station",
        "yesvantpur railway station", "yeshwanthpur metro",
        "yeshwanthpur market", "yeshwanthpur flyover"
    ],
    "Tumkur Road": [
        "tumkur road", "tumakuru road", "tumkur main road",
        "yeshwanthpur tumkur road", "nelamangala road", "peenya tumkur road"
    ],
    "Peenya": [
        "peenya", "peenya industrial area", "peenya metro",
        "peenya 1st stage", "peenya second stage", "peenya signal",
        "peenya flyover", "peenya junction"
    ],
    "Goraguntepalya": [
        "goraguntepalya", "goragunte palya", "goraguntepalya junction",
        "goraguntepalya metro", "goraguntepalya signal", "parle g toll"
    ],
    "Hebbal": [
        "hebbal", "hebbal flyover", "hebbal junction", "hebbal signal",
        "hebbal bridge", "hebbal lake", "hebbal ring road", "hebbal airport road"
    ],
    "Airport Road": [
        "airport road", "kempegowda airport road", "bengaluru airport road",
        "kia road", "devanahalli road", "hebbal airport road", "international airport road"
    ],
    "Manyata Tech Park": [
        "manyata tech park", "manyata", "manyata embassy business park",
        "manyata gate", "manyata entrance", "manyata nagawara", "manyata tech park road"
    ],
    "Nagawara": [
        "nagawara", "nagavara", "nagawara junction", "nagawara signal",
        "nagawara ring road", "nagawara lake", "manyata nagawara"
    ],
    "Hennur Road": [
        "hennur road", "hennur main road", "hennur", "hennur cross",
        "hennur junction", "hennur signal"
    ],
    "Thanisandra": [
        "thanisandra", "thanisandra main road", "thanisandra road",
        "thanisandra signal", "thanisandra junction"
    ],
    "Jakkur": ["jakkur", "jakkur road", "jakkur aerodrome", "jakkur junction", "jakkur signal"],
    "Yelahanka": [
        "yelahanka", "yelahanka new town", "yelahanka old town",
        "yelahanka railway station", "yelahanka signal", "yelahanka junction",
        "yelahanka airport road"
    ],
    "Devanahalli": [
        "devanahalli", "devanahalli road", "devanahalli toll",
        "airport toll", "kempegowda airport toll"
    ],
    "Banashankari": [
        "banashankari", "bsk", "banashankari bus stand", "banashankari metro",
        "banashankari signal", "bsk 2nd stage", "bsk 3rd stage", "bsk 6th stage"
    ],
    "Jayanagar": [
        "jayanagar", "jayanagar 4th block", "jayanagar fourth block",
        "jayanagar metro", "jayanagar signal", "jayanagar 9th block",
        "south end circle"
    ],
    "JP Nagar": [
        "jp nagar", "j p nagar", "jayaprakash nagar", "jp nagar metro",
        "jp nagar 6th phase", "jp nagar 7th phase", "jp nagar signal",
        "sarakki signal"
    ],
    "BTM Layout": [
        "btm layout", "btm", "btm 1st stage", "btm 2nd stage",
        "btm signal", "btm water tank", "btm lake"
    ],
    "Bannerghatta Road": [
        "bannerghatta road", "bannerghatta main road", "bannerghatta",
        "bg road", "b g road", "arekere bannerghatta road",
        "iim bangalore road", "apollo bannerghatta road"
    ],
    "Koramangala": [
        "koramangala", "koramangla", "koramangala 1st block",
        "koramangala 4th block", "koramangala 5th block",
        "koramangala 6th block", "koramangala 7th block",
        "koramangala 8th block", "koramangala sony signal",
        "sony world signal", "koramangala forum mall"
    ],
    "Ejipura": ["ejipura", "egipura", "ejipura signal", "ejipura flyover", "ejipura main road"],
    "Domlur": ["domlur", "domlur flyover", "domlur signal", "domlur bridge", "domlur inner ring road", "domlur layout"],
    "HAL Road": [
        "hal road", "h a l road", "old airport road", "airport road hal",
        "hal main road", "murugeshpalya old airport road"
    ],
    "Murugeshpalya": [
        "murugeshpalya", "murugesh palya", "murugeshpalya signal",
        "murugeshpalya old airport road", "manipal hospital old airport road"
    ],
    "CV Raman Nagar": ["cv raman nagar", "c v raman nagar", "cv raman road", "bagmane tech park", "bagmane", "drdo township"],
    "Kaggadasapura": ["kaggadasapura", "kaggadaspura", "kaggadasapura main road", "kaggadasapura railway gate"],
    "Basavanagudi": ["basavanagudi", "basavanagudi road", "gandhi bazaar", "bull temple road", "basavanagudi signal"],
    "Lalbagh": ["lalbagh", "lalbagh road", "lalbagh main gate", "lalbagh west gate", "lalbagh metro", "lalbagh botanical garden"],
    "Richmond Road": ["richmond road", "richmond circle", "residency road", "richmond town", "richmond signal"],
    "Shivajinagar": ["shivajinagar", "shivaji nagar", "shivajinagar bus stand", "shivajinagar market", "commercial street", "russell market"],
    "Commercial Street": ["commercial street", "commercial road", "commercial street junction", "shivajinagar commercial street"],
    "Ulsoor": ["ulsoor", "ulsoor lake", "ulsoor road", "halasuru", "halasuru metro", "ulsoor signal"],
    "Frazer Town": ["frazer town", "fraser town", "mosque road", "coleshill road", "frazer town signal"],
    "RT Nagar": ["rt nagar", "r t nagar", "rt nagar main road", "rt nagar signal", "rabindranath tagore nagar"],
    "Sanjay Nagar": ["sanjay nagar", "sanjaynagar", "sanjay nagar main road", "sanjay nagar signal"],
    "Malleshwaram": [
        "malleshwaram", "malleswaram", "malleshwaram 8th cross",
        "malleshwaram 18th cross", "sampige road", "mantri mall", "malleshwaram metro"
    ],
    "Rajajinagar": ["rajajinagar", "rajaji nagar", "rajajinagar metro", "rajajinagar entrance", "rajajinagar signal", "navrang signal", "navrang theatre"],
    "Basaveshwaranagar": ["basaveshwaranagar", "basaveshwara nagar", "basaveshwar nagar", "basaveshwaranagar main road"],
    "Vijayanagar": ["vijayanagar", "vijaya nagar", "vijayanagar metro", "vijayanagar bus stand", "vijayanagar signal"],
    "Mysore Road": ["mysore road", "mysuru road", "mysore main road", "nayandahalli mysore road", "kengeri mysore road", "satellite bus stand mysore road"],
    "Nayandahalli": ["nayandahalli", "nayanda halli", "nayandahalli junction", "nayandahalli metro", "nayandahalli flyover"],
    "Kengeri": ["kengeri", "kengeri satellite town", "kengeri bus terminal", "kengeri metro", "kengeri railway station", "kengeri junction"],
    "RR Nagar": ["rr nagar", "r r nagar", "rajarajeshwari nagar", "rajarajeshwari nagar metro", "rr nagar arch", "global village tech park"],
    "Magadi Road": ["magadi road", "magadi main road", "magadi road metro", "sunkadakatte magadi road"],
    "Kanakapura Road": ["kanakapura road", "kanakapura main road", "kanakpura road", "konanakunte kanakapura road", "doddakallasandra", "talaghattapura"],
    "Kanakapura Road Metro": ["konanakunte cross", "doddakallasandra metro", "vajrahalli metro", "talaghattapura metro", "silk institute metro"],
    "Wilson Garden": ["wilson garden", "wilson garden road", "wilson garden signal", "shantinagar wilson garden"],
    "Shantinagar": ["shantinagar", "shanti nagar", "shantinagar bus stand", "shantinagar bus station", "double road shantinagar"],
    "Lakkasandra": ["lakkasandra", "lakkasandra signal", "nimhans lakkasandra"],
    "NIMHANS": ["nimhans", "nimhans hospital", "nimhans signal", "nimhans junction"],
    "Dairy Circle": ["dairy circle", "dairy circle flyover", "dairy circle signal", "christ university dairy circle"],
    "Christ University": ["christ university", "christ college", "christ university hosur road", "christ college road"],
    "Bommanahalli": ["bommanahalli", "bommanahalli signal", "bommanahalli junction", "bommanahalli hosur road"],
    "Madivala": ["madivala", "madiwala", "madivala market", "madivala police station", "madivala lake", "madivala signal"],
    "HSR Layout": ["hsr layout", "h s r layout", "hsr", "hsr bda complex", "hsr signal", "hsr 27th main", "hsr 14th main", "agara hsr layout"],
    "Agara": ["agara", "agara lake", "agara flyover", "agara signal", "agara junction", "agara hsr"],
    "Kadubeesanahalli": ["kadubeesanahalli", "kadubeesanahalli bridge", "kadubeesanahalli signal", "kadubeesanahalli outer ring road"],
    "Devarabisanahalli": ["devarabisanahalli", "devarabeesanahalli", "devarabisanahalli flyover", "devarabisanahalli outer ring road"],
    "Ecospace": ["ecospace", "embassy tech village", "etv bellandur", "ecospace bellandur", "ecospace outer ring road"],
    "Bagmane Tech Park": ["bagmane tech park", "bagmane", "bagmane constellation", "bagmane world technology center", "bagmane cv raman nagar"],
    "Manyata Embassy Business Park": ["manyata embassy business park", "manyata tech park", "manyata", "manyata back gate", "manyata main gate"],
    "Phoenix Marketcity": ["phoenix marketcity", "phoenix mall", "phoenix whitefield", "phoenix mall mahadevapura"],
    "Mahadevapura": ["mahadevapura", "mahadevpura", "mahadevapura ring road", "mahadevapura signal", "mahadevapura flyover"],
    "Banaswadi": ["banaswadi", "bana swadi", "banaswadi railway station", "banaswadi main road", "banaswadi signal"],
    "Kalyan Nagar": ["kalyan nagar", "kalyannagar", "kalyan nagar ring road", "hrbr layout", "kammanahalli kalyan nagar"],
    "Kammanahalli": ["kammanahalli", "kammanahalli main road", "kammanahalli signal", "kamanahalli"],
    "Horamavu": ["horamavu", "horamavu main road", "horamavu signal", "horamavu agara"],
    "Ramamurthy Nagar": ["ramamurthy nagar", "ram murthy nagar", "ramamurthy nagar signal", "ramamurthy nagar main road"],
    "Kasturi Nagar": ["kasturi nagar", "kasturinagar", "kasturi nagar main road"],
    "HBR Layout": ["hbr layout", "h b r layout", "hbr", "hbr signal", "hbr ring road"],
    "HRBR Layout": ["hrbr layout", "h r b r layout", "hrbr", "hrbr kalyan nagar"],
    "Jeevan Bima Nagar": ["jeevan bima nagar", "jeevanbheema nagar", "j b nagar", "jbnagar", "jeevan bima nagar main road"],
    "KR Market": ["kr market", "k r market", "city market", "kr market flyover", "kr market bus stand", "kalasipalya market"],
    "Kalasipalya": ["kalasipalya", "kalasipalyam", "kalasipalya bus stand", "kalasipalya market"],
    "Mekhri Circle": ["mekhri circle", "mekhri", "mekri circle", "mekhri signal", "palace grounds mekhri circle"],
    "Palace Grounds": ["palace grounds", "palace ground", "bangalore palace", "palace road"],
    "Seshadripuram": ["seshadripuram", "sheshadripuram", "seshadripuram road", "seshadripuram college"],
    "Sadashivanagar": ["sadashivanagar", "sadashiva nagar", "sankey tank", "bashyam circle"],
    "Sankey Road": ["sankey road", "sankey tank road", "sankey tank"],
    "Cunningham Road": ["cunningham road", "cunningham", "cunningham road signal"],
    "Queens Road": ["queens road", "queen's road", "queens circle"],
    "St Marks Road": ["st marks road", "saint marks road", "st mark road", "st marks"],
    "Residency Road": ["residency road", "residency", "residency road signal"],
    "Lavelle Road": ["lavelle road", "lavelle", "lavelle road junction"],
    "Double Road": ["double road", "kh road", "k h road", "shantinagar double road"],
    "Mission Road": ["mission road", "mission", "mission road junction"],
    "JC Road": ["jc road", "j c road", "jc road signal", "town hall jc road"],
    "SP Road": ["sp road", "s p road", "sadar patrappa road", "sp road market"],
    "Avenue Road": ["avenue road", "avenue", "avenue road market"],
    "Chickpet": ["chickpet", "chikpet", "chickpet metro", "chickpet market"],
    "Cottonpet": ["cottonpet", "cotton pet", "cottonpet main road"],
    "Malleswaram 18th Cross": ["18th cross malleshwaram", "eighteenth cross malleshwaram", "malleshwaram 18th cross", "malleswaram 18th cross"],
    "Sampige Road": ["sampige road", "sampige", "mantri mall road", "sampige road metro"],
    "Orion Mall": ["orion mall", "orion", "orion mall rajajinagar", "orion mall brigade gateway"],
    "World Trade Center": ["world trade center", "wtc", "w t c", "wtc bangalore", "brigade gateway"],
    "Nagarbhavi": ["nagarbhavi", "nagar bhavi", "nagarbhavi circle", "nagarbhavi main road"],
    "Ullal": ["ullal", "ullal main road", "ullal junction"],
    "Varthur": ["varthur", "varthur road", "varthur kodi", "varthur lake", "varthur main road"],
    "Gunjur": ["gunjur", "gunjur road", "gunjur palya"],
    "Carmelaram": ["carmelaram", "carmelaram railway station", "carmelaram road"],
    "Doddakannelli": ["doddakannelli", "doddakannelli road", "doddakannelli sarjapur"],
    "Kaikondrahalli": ["kaikondrahalli", "kaikondrahalli lake", "kaikondrahalli sarjapur road"],
    "Kudlu Gate": ["kudlu gate", "kudlu", "kudlu gate junction", "kudlu gate signal", "hosur road kudlu gate"],
    "Harlur": ["harlur", "harlur road", "haralur", "haralur road"],
    "Begur": ["begur", "begur road", "begur junction"],
    "Arekere": ["arekere", "arekere gate", "arekere signal", "arekere bannerghatta road"],
    "Hulimavu": ["hulimavu", "hulimavu gate", "hulimavu signal", "hulimavu bannerghatta road"],
    "Gottigere": ["gottigere", "gottigere road", "gottigere junction"],
    "Kumaraswamy Layout": ["kumaraswamy layout", "kumaraswamy", "ks layout", "kumaraswamy layout signal"],
    "Padmanabhanagar": ["padmanabhanagar", "padmanabha nagar", "padmanabhanagar signal"],
    "Uttarahalli": ["uttarahalli", "uttarahalli main road", "uttarahalli junction"],
    "Vajarahalli": ["vajrahalli", "vajarahalli", "vajrahalli metro", "kanakapura road vajrahalli"],
}

MISHEARD_LOCATION_MAP = {
    "silk boat": "Silk Board Junction",
    "silk board": "Silk Board Junction",
    "electronic city": "Electronic City",
    "electronics city": "Electronic City",
    "marathalli": "Marathahalli",
    "marathahalli": "Marathahalli",
    "tin factor": "Tin Factory",
    "tin factory": "Tin Factory",
    "k r puram": "KR Puram",
    "majestic": "Majestic",
    "hebbal": "Hebbal",
    "manyata": "Manyata Tech Park",
    "white field": "Whitefield",
    "whitefield": "Whitefield",
    "yesvantpur": "Yeshwanthpur",
    "indra nagar": "Indiranagar",
    "indira nagar": "Indiranagar",
}

TEXT_NORMALIZATION_MAP = {
    "play over": "flyover",
    "fly over": "flyover",
}

BENGALURU_LOCATION_COORDS = {
    "Silk Board Junction": {"lat": 12.9177, "lng": 77.6238},
    "Electronic City": {"lat": 12.8452, "lng": 77.6602},
    "Hosur Road": {"lat": 12.8957, "lng": 77.6327},
    "Outer Ring Road": {"lat": 12.9279, "lng": 77.6271},
    "Marathahalli": {"lat": 12.9569, "lng": 77.7011},
    "Bellandur": {"lat": 12.9304, "lng": 77.6784},
    "Sarjapur Road": {"lat": 12.8996, "lng": 77.6837},
    "Whitefield": {"lat": 12.9698, "lng": 77.7499},
    "ITPL": {"lat": 12.9871, "lng": 77.7374},
    "KR Puram": {"lat": 13.0076, "lng": 77.6957},
    "Tin Factory": {"lat": 13.0026, "lng": 77.6696},
    "Old Madras Road": {"lat": 12.9952, "lng": 77.6663},
    "Indiranagar": {"lat": 12.9784, "lng": 77.6408},
    "MG Road": {"lat": 12.9756, "lng": 77.6067},
    "Majestic": {"lat": 12.9767, "lng": 77.5713},
    "KSR Bengaluru Railway Station": {"lat": 12.9781, "lng": 77.5697},
    "Yeshwanthpur": {"lat": 13.0238, "lng": 77.5500},
    "Tumkur Road": {"lat": 13.0280, "lng": 77.5400},
    "Peenya": {"lat": 13.0285, "lng": 77.5197},
    "Hebbal": {"lat": 13.0358, "lng": 77.5970},
    "Airport Road": {"lat": 13.1986, "lng": 77.7066},
    "Manyata Tech Park": {"lat": 13.0420, "lng": 77.6200},
    "Nagawara": {"lat": 13.0450, "lng": 77.6220},
    "Banashankari": {"lat": 12.9255, "lng": 77.5468},
    "Jayanagar": {"lat": 12.9250, "lng": 77.5938},
    "JP Nagar": {"lat": 12.9063, "lng": 77.5857},
    "BTM Layout": {"lat": 12.9166, "lng": 77.6101},
    "Bannerghatta Road": {"lat": 12.8877, "lng": 77.5975},
    "Koramangala": {"lat": 12.9352, "lng": 77.6245},
    "Domlur": {"lat": 12.9608, "lng": 77.6387},
    "HAL Road": {"lat": 12.9585, "lng": 77.6510},
    "Lalbagh": {"lat": 12.9507, "lng": 77.5848},
    "Shivajinagar": {"lat": 12.9857, "lng": 77.6057},
    "Malleshwaram": {"lat": 13.0031, "lng": 77.5643},
    "Rajajinagar": {"lat": 12.9915, "lng": 77.5554},
    "Mysore Road": {"lat": 12.9469, "lng": 77.5300},
    "Kengeri": {"lat": 12.9177, "lng": 77.4838},
    "RR Nagar": {"lat": 12.9259, "lng": 77.5175},
    "Kanakapura Road": {"lat": 12.8875, "lng": 77.5577},
    "Dairy Circle": {"lat": 12.9369, "lng": 77.6025},
    "Christ University": {"lat": 12.9344, "lng": 77.6069},
    "Bommanahalli": {"lat": 12.9081, "lng": 77.6236},
    "Madivala": {"lat": 12.9226, "lng": 77.6174},
    "HSR Layout": {"lat": 12.9116, "lng": 77.6474},
    "Agara": {"lat": 12.9224, "lng": 77.6514},
    "Kadubeesanahalli": {"lat": 12.9415, "lng": 77.6953},
    "Ecospace": {"lat": 12.9279, "lng": 77.6815},
    "Phoenix Marketcity": {"lat": 12.9960, "lng": 77.6963},
    "Mahadevapura": {"lat": 12.9916, "lng": 77.6926},
    "KR Market": {"lat": 12.9635, "lng": 77.5770},
}

LOCATION_ENTITY_WORDS = [
    "Flyover", "Junction", "Circle", "Signal", "Metro", "Bus Stand",
    "Railway Station", "Tech Park", "Mall", "Lake", "Market",
    "Hospital", "University", "College",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def location_payload(location_key: str) -> dict:
    coords = BENGALURU_LOCATION_COORDS.get(location_key, {})
    if "Road" in location_key:
        payload = {"road_name": location_key}
    elif any(word in location_key for word in LOCATION_ENTITY_WORDS):
        payload = {"location_name": location_key}
    else:
        payload = {"location_name": location_key}

    if coords:
        payload["lat"] = coords["lat"]
        payload["lng"] = coords["lng"]
    return payload


def phrase_in_text(phrase: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def extract_location_from_text(text: str, fuzzy_threshold: float = 0.78) -> dict:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return {}
    for source, target in TEXT_NORMALIZATION_MAP.items():
        normalized_text = re.sub(rf"\b{re.escape(source)}\b", target, normalized_text)

    for phrase, location_key in MISHEARD_LOCATION_MAP.items():
        if phrase_in_text(normalize_text(phrase), normalized_text):
            return location_payload(location_key)

    alias_pairs = []
    for location_key, aliases in LOCATION_DATASET.items():
        alias_pairs.append((location_key, normalize_text(location_key)))
        alias_pairs.extend((location_key, normalize_text(alias)) for alias in aliases)

    for location_key, alias in sorted(alias_pairs, key=lambda item: len(item[1]), reverse=True):
        if alias and phrase_in_text(alias, normalized_text):
            return location_payload(location_key)

    best_key = None
    best_score = 0
    for location_key, alias in alias_pairs:
        if not alias:
            continue
        score = SequenceMatcher(None, alias, normalized_text).ratio()
        if score > best_score:
            best_key = location_key
            best_score = score

    if best_key and best_score >= fuzzy_threshold:
        return location_payload(best_key)

    return {}
