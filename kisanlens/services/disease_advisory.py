"""General crop-care information for the classes the model can predict.

IMPORTANT
- This is educational background, kept separate from the model prediction.
- It deliberately names NO pesticides and gives NO doses. Treatment decisions
  must come from a local agriculture officer / Krishi Vigyan Kendra (KVK).
- The text was drafted from general agronomy knowledge and must be reviewed
  against the reference sources listed in REFERENCE_SOURCES before being
  presented as "verified" (see README, "Content review").
"""
from model.common import canonical_key, crop_of

REFERENCE_SOURCES = [
    {"name": "ICAR – Central Potato Research Institute (CPRI), Shimla", "url": "https://cpri.icar.gov.in"},
    {"name": "TNAU Agritech Portal – Crop Protection", "url": "https://agritech.tnau.ac.in"},
    {"name": "UC IPM – Tomato Pest Management Guidelines", "url": "https://ipm.ucanr.edu"},
    {"name": "Cornell Vegetable MD Online", "url": "https://www.vegetables.cornell.edu/pest-management/disease-factsheets/"},
    {"name": "Your nearest Krishi Vigyan Kendra (KVK) / State Agriculture Department", "url": "https://kvk.icar.gov.in"},
]


def _entry(crop, name_en, name_hi, visual, kind, sym, prev, mgmt, urgent=False):
    return {
        "crop": crop,
        "name": {"en": name_en, "hi": name_hi},
        "visual": visual,          # drives the generic leaf illustration
        "kind": kind,              # fungal / oomycete / bacterial / viral / pest / healthy
        "symptoms": {"en": sym[0], "hi": sym[1]},
        "prevention": {"en": prev[0], "hi": prev[1]},
        "management": {"en": mgmt[0], "hi": mgmt[1]},
        "urgent": urgent,
    }


_BLIGHT_PREV = (
    [
        "Rotate with non-potato/non-tomato crops for 2–3 seasons.",
        "Use certified, disease-free seed or healthy seedlings.",
        "Avoid overhead watering late in the day; give plants space for airflow.",
    ],
    [
        "2–3 मौसम तक आलू/टमाटर के बजाय दूसरी फसलें लगाएँ।",
        "प्रमाणित, रोग-मुक्त बीज या स्वस्थ पौध का उपयोग करें।",
        "शाम को ऊपर से सिंचाई न करें; पौधों के बीच हवा के लिए जगह रखें।",
    ],
)

ADVISORY = {
    # ------------------------------------------------------------ POTATO
    "potato_early_blight": _entry(
        "potato", "Early Blight", "अगेती झुलसा (अर्ली ब्लाइट)", "target_spots", "fungal",
        (
            ["Dark brown spots with ring-like (target) patterns, usually on older lower leaves first.",
             "Yellowing around the spots; badly affected leaves dry up and fall.",
             "Plants under stress or low nutrition are often hit harder."],
            ["गहरे भूरे धब्बे जिनमें छल्ले जैसी रेखाएँ होती हैं, आमतौर पर पहले नीचे की पुरानी पत्तियों पर।",
             "धब्बों के आसपास पीलापन; ज़्यादा प्रभावित पत्तियाँ सूखकर गिर जाती हैं।",
             "कमज़ोर या पोषण की कमी वाले पौधों पर असर ज़्यादा होता है।"],
        ),
        _BLIGHT_PREV,
        (
            ["Remove and destroy badly affected leaves and crop residue away from the field.",
             "Keep plants well fed and watered. Ask your agriculture officer which treatment, if any, is approved locally."],
            ["ज़्यादा प्रभावित पत्तियों और फसल-अवशेष को खेत से दूर नष्ट करें।",
             "पौधों को संतुलित पोषण और पानी दें। स्थानीय कृषि अधिकारी से पूछें कि कौन-सा उपचार (यदि ज़रूरी हो) मान्य है।"],
        ),
    ),
    "potato_late_blight": _entry(
        "potato", "Late Blight", "पछेती झुलसा (लेट ब्लाइट)", "water_blight", "oomycete",
        (
            ["Pale green or dark water-soaked patches on leaves that quickly turn brown or black.",
             "In humid weather, white fuzzy growth may appear on the underside of leaves.",
             "Can spread very fast in cool, cloudy, wet weather and may rot the tubers."],
            ["पत्तियों पर हल्के हरे या गहरे, पानी से भीगे धब्बे जो जल्दी भूरे या काले हो जाते हैं।",
             "नमी वाले मौसम में पत्ती के नीचे की तरफ़ सफ़ेद रुई जैसी परत दिख सकती है।",
             "ठंडे, बादल वाले, गीले मौसम में बहुत तेज़ी से फैलता है और कंद सड़ सकते हैं।"],
        ),
        (
            ["Plant certified disease-free seed tubers; destroy cull piles and volunteer potato plants.",
             "Improve drainage and avoid dense planting.",
             "Watch local weather and disease alerts during cool, humid spells."],
            ["प्रमाणित रोग-मुक्त बीज कंद लगाएँ; बेकार कंदों के ढेर और अपने-आप उगे आलू के पौधे नष्ट करें।",
             "जल-निकास ठीक रखें और घनी बुवाई से बचें।",
             "ठंडे, नम मौसम में स्थानीय मौसम व रोग-चेतावनी पर नज़र रखें।"],
        ),
        (
            ["This disease can destroy a field quickly. Contact your KVK or agriculture department promptly.",
             "Do not store tubers from heavily affected plants without inspecting them."],
            ["यह रोग खेत को जल्दी बर्बाद कर सकता है। तुरंत अपने KVK या कृषि विभाग से संपर्क करें।",
             "ज़्यादा प्रभावित पौधों के कंद बिना जाँचे भंडारण में न रखें।"],
        ),
        urgent=True,
    ),
    "potato_healthy": _entry(
        "potato", "Healthy", "स्वस्थ पत्ती", "healthy", "healthy",
        (
            ["Even green colour and no obvious spots, lesions or mould.",
             "No curling, wilting or unusual yellowing."],
            ["एक समान हरा रंग; कोई स्पष्ट धब्बा, घाव या फफूँद नहीं।",
             "पत्तियाँ मुड़ी, मुरझाई या असामान्य रूप से पीली नहीं हैं।"],
        ),
        (
            ["Keep rotating crops and using clean seed.",
             "Inspect plants every few days, especially after rain or humid weather."],
            ["फसल-चक्र अपनाते रहें और साफ़ बीज इस्तेमाल करें।",
             "खासकर बारिश या नमी के बाद, हर कुछ दिन में पौधों की जाँच करें।"],
        ),
        (
            ["A healthy result applies only to the leaf in the photo. Other leaves or plants may differ."],
            ["स्वस्थ परिणाम सिर्फ़ फ़ोटो वाली पत्ती के लिए है। दूसरी पत्तियाँ या पौधे अलग हो सकते हैं।"],
        ),
    ),
    # ------------------------------------------------------------ TOMATO
    "tomato_bacterial_spot": _entry(
        "tomato", "Bacterial Spot", "जीवाणु धब्बा रोग (बैक्टीरियल स्पॉट)", "small_spots", "bacterial",
        (
            ["Small, dark, water-soaked spots on leaves that turn brown or black, sometimes with a yellow halo.",
             "Rough, scab-like spots can appear on fruit.",
             "Heavily affected leaves may drop."],
            ["पत्तियों पर छोटे, गहरे, पानी से भीगे धब्बे जो भूरे या काले हो जाते हैं, कभी-कभी पीले घेरे के साथ।",
             "फलों पर खुरदरे, पपड़ी जैसे धब्बे आ सकते हैं।",
             "ज़्यादा प्रभावित पत्तियाँ गिर सकती हैं।"],
        ),
        (
            ["Start with disease-free seed and healthy seedlings.",
             "Avoid working among wet plants; clean tools between plants.",
             "Prefer drip irrigation and rotate crops."],
            ["रोग-मुक्त बीज और स्वस्थ पौध से शुरुआत करें।",
             "गीले पौधों के बीच काम न करें; औज़ार साफ़ करके इस्तेमाल करें।",
             "टपक सिंचाई अपनाएँ और फसल-चक्र रखें।"],
        ),
        (
            ["Remove and destroy badly infected plant parts and residue.",
             "Ask an agriculture officer about locally approved options; bacterial diseases are hard to control once established."],
            ["ज़्यादा संक्रमित पौध-भाग और अवशेष नष्ट करें।",
             "स्थानीय रूप से मान्य उपायों के बारे में कृषि अधिकारी से पूछें; जीवाणु रोग एक बार फैलने पर नियंत्रित करना कठिन होता है।"],
        ),
    ),
    "tomato_early_blight": _entry(
        "tomato", "Early Blight", "अगेती झुलसा (अर्ली ब्लाइट)", "target_spots", "fungal",
        (
            ["Brown spots with ring-like (target) patterns, usually on older lower leaves first.",
             "Yellowing around spots; dark sunken spots can appear near the fruit stem or on the stem.",
             "Severe cases cause leaf drop and sun-scald on fruit."],
            ["भूरे धब्बे जिनमें छल्ले जैसी रेखाएँ होती हैं, आमतौर पर पहले नीचे की पुरानी पत्तियों पर।",
             "धब्बों के आसपास पीलापन; फल के डंठल या तने के पास गहरे दबे धब्बे आ सकते हैं।",
             "गंभीर स्थिति में पत्तियाँ गिरती हैं और फल धूप से झुलस सकते हैं।"],
        ),
        _BLIGHT_PREV,
        (
            ["Remove and destroy badly affected leaves and plant residue.",
             "Mulch and stake plants to keep leaves off wet soil. Ask your agriculture officer about locally approved treatment."],
            ["ज़्यादा प्रभावित पत्तियों और अवशेष को नष्ट करें।",
             "मल्च और सहारा देकर पत्तियों को गीली मिट्टी से दूर रखें। मान्य उपचार के लिए कृषि अधिकारी से पूछें।"],
        ),
    ),
    "tomato_late_blight": _entry(
        "tomato", "Late Blight", "पछेती झुलसा (लेट ब्लाइट)", "water_blight", "oomycete",
        (
            ["Large, irregular, greasy-looking grey-green patches on leaves that turn brown.",
             "White fuzzy growth may appear underneath in humid conditions.",
             "Firm brown patches on fruit; stems can also be affected. Spreads fast in cool, wet weather."],
            ["पत्तियों पर बड़े, बेढंगे, चिकने-से धूसर-हरे धब्बे जो भूरे हो जाते हैं।",
             "नमी में नीचे की तरफ़ सफ़ेद रुई जैसी परत दिख सकती है।",
             "फलों पर कठोर भूरे धब्बे; तना भी प्रभावित हो सकता है। ठंडे, गीले मौसम में तेज़ी से फैलता है।"],
        ),
        _BLIGHT_PREV,
        (
            ["This disease can spread within days. Contact your KVK or agriculture department promptly.",
             "Remove and destroy infected plants as advised locally; do not compost them."],
            ["यह रोग कुछ ही दिनों में फैल सकता है। तुरंत अपने KVK या कृषि विभाग से संपर्क करें।",
             "संक्रमित पौधों को स्थानीय सलाह के अनुसार नष्ट करें; उनसे खाद न बनाएँ।"],
        ),
        urgent=True,
    ),
    "tomato_leaf_mold": _entry(
        "tomato", "Leaf Mold", "पत्ती फफूँद (लीफ मोल्ड)", "mold", "fungal",
        (
            ["Pale green or yellow patches on the upper leaf surface.",
             "Olive-green to brownish velvety mould on the underside of the same patches.",
             "Most common in humid, poorly ventilated conditions such as greenhouses and dense crops."],
            ["पत्ती की ऊपरी सतह पर हल्के हरे या पीले धब्बे।",
             "उन्हीं धब्बों के नीचे जैतूनी-हरी से भूरी मख़मली फफूँद।",
             "नमी वाली, कम हवादार जगहों जैसे ग्रीनहाउस और घनी फसल में ज़्यादा होता है।"],
        ),
        (
            ["Improve ventilation and plant spacing; avoid wetting leaves.",
             "Avoid long periods of high humidity; water in the morning.",
             "Use resistant varieties where available."],
            ["हवा का आवागमन और पौधों की दूरी बढ़ाएँ; पत्तियों को गीला न करें।",
             "लंबे समय तक अधिक नमी से बचें; सुबह सिंचाई करें।",
             "जहाँ उपलब्ध हों, रोग-प्रतिरोधी किस्में लगाएँ।"],
        ),
        (
            ["Remove affected leaves and clean up residue after harvest.",
             "Ask an agriculture officer about locally approved options."],
            ["प्रभावित पत्तियाँ हटाएँ और कटाई के बाद अवशेष साफ़ करें।",
             "मान्य उपायों के लिए कृषि अधिकारी से पूछें।"],
        ),
    ),
    "tomato_septoria_leaf_spot": _entry(
        "tomato", "Septoria Leaf Spot", "सेप्टोरिया पत्ती धब्बा", "small_spots", "fungal",
        (
            ["Many small round spots with dark borders and lighter grey or tan centres.",
             "Tiny dark dots may be visible in the centre of spots.",
             "Starts on lower leaves and moves upward; heavily spotted leaves yellow and drop."],
            ["कई छोटे गोल धब्बे जिनके किनारे गहरे और बीच का हिस्सा हल्का धूसर या भूरा होता है।",
             "धब्बों के बीच में छोटे काले बिंदु दिख सकते हैं।",
             "नीचे की पत्तियों से शुरू होकर ऊपर बढ़ता है; बहुत धब्बों वाली पत्तियाँ पीली होकर गिरती हैं।"],
        ),
        (
            ["Avoid splashing water on leaves; use mulch and stake plants.",
             "Rotate crops and remove old plant debris.",
             "Keep weeds in the nightshade family out of the field."],
            ["पत्तियों पर पानी के छींटे न पड़ने दें; मल्च और सहारा दें।",
             "फसल-चक्र अपनाएँ और पुराने पौध-अवशेष हटाएँ।",
             "खेत में टमाटर-कुल के खरपतवार न रहने दें।"],
        ),
        (
            ["Remove the lowest affected leaves early.",
             "Ask an agriculture officer about locally approved options."],
            ["सबसे नीचे की प्रभावित पत्तियाँ जल्दी हटा दें।",
             "मान्य उपायों के लिए कृषि अधिकारी से पूछें।"],
        ),
    ),
    "tomato_spider_mites": _entry(
        "tomato", "Spider Mites (Two-spotted)", "लाल मकड़ी (स्पाइडर माइट)", "stippling", "pest",
        (
            ["Fine pale stippling or speckles on leaves; leaves may look bronzed or dry.",
             "Very fine webbing, usually on the underside of leaves.",
             "Worse in hot, dry, dusty conditions. This is a pest, not a germ-caused disease."],
            ["पत्तियों पर बारीक हल्के बिंदु या चित्तियाँ; पत्तियाँ काँसे जैसी या सूखी दिख सकती हैं।",
             "आमतौर पर पत्ती के नीचे बहुत बारीक जाला।",
             "गर्म, सूखे, धूल भरे मौसम में ज़्यादा। यह कीट है, रोगाणु से होने वाला रोग नहीं।"],
        ),
        (
            ["Check the underside of leaves regularly, especially in hot dry spells.",
             "Reduce dust and avoid water stress.",
             "Avoid unnecessary spraying that kills natural enemies of mites."],
            ["खासकर गर्म-सूखे दौर में पत्तियों के नीचे की सतह नियमित देखें।",
             "धूल कम करें और पौधों को पानी की कमी से बचाएँ।",
             "बेवजह छिड़काव से बचें, इससे मकड़ी के प्राकृतिक दुश्मन भी मर जाते हैं।"],
        ),
        (
            ["On a small scale, a strong spray of plain water on leaf undersides can reduce numbers.",
             "For larger infestations, ask an agriculture officer which control is approved locally."],
            ["छोटे स्तर पर पत्तियों के नीचे सादे पानी की तेज़ धार से संख्या कम हो सकती है।",
             "ज़्यादा प्रकोप में कृषि अधिकारी से पूछें कि कौन-सा नियंत्रण स्थानीय रूप से मान्य है।"],
        ),
    ),
    "tomato_target_spot": _entry(
        "tomato", "Target Spot", "टारगेट स्पॉट (लक्ष्य धब्बा)", "target_spots", "fungal",
        (
            ["Brown spots with ring-like patterns and often a yellow halo; can look similar to early blight.",
             "Spots can appear on leaves, stems and fruit.",
             "Favoured by warm, humid weather and dense foliage."],
            ["भूरे धब्बे जिनमें छल्ले जैसी रेखाएँ और अक्सर पीला घेरा होता है; अगेती झुलसा जैसे दिख सकते हैं।",
             "धब्बे पत्तियों, तने और फलों पर आ सकते हैं।",
             "गर्म, नम मौसम और घनी पत्तियों में ज़्यादा फैलता है।"],
        ),
        (
            ["Improve airflow with spacing and pruning of lower leaves.",
             "Rotate crops and remove crop residue after harvest.",
             "Avoid overhead irrigation."],
            ["दूरी रखकर और नीचे की पत्तियाँ छाँटकर हवा का आवागमन बढ़ाएँ।",
             "फसल-चक्र अपनाएँ और कटाई के बाद अवशेष हटाएँ।",
             "ऊपर से सिंचाई से बचें।"],
        ),
        (
            ["Because it resembles early blight, get the diagnosis confirmed by an expert before choosing any treatment."],
            ["अगेती झुलसा जैसा दिखने के कारण, कोई भी उपचार चुनने से पहले विशेषज्ञ से पुष्टि करवाएँ।"],
        ),
    ),
    "tomato_yellow_leaf_curl_virus": _entry(
        "tomato", "Yellow Leaf Curl Virus", "पीला पत्ती मोड़क विषाणु (येलो लीफ कर्ल)", "curl", "viral",
        (
            ["Leaves curl upward and cup, with yellowing edges.",
             "Plants look stunted; flowers may drop and fruit set is poor.",
             "Spread by whiteflies. There is no cure for an infected plant."],
            ["पत्तियाँ ऊपर की ओर मुड़कर कटोरी जैसी हो जाती हैं, किनारे पीले पड़ते हैं।",
             "पौधे बौने दिखते हैं; फूल झड़ सकते हैं और फल कम लगते हैं।",
             "सफ़ेद मक्खी से फैलता है। संक्रमित पौधे का कोई इलाज नहीं है।"],
        ),
        (
            ["Raise seedlings under insect-proof net and check for whiteflies often.",
             "Remove weeds that host whiteflies; use yellow sticky traps for monitoring.",
             "Use tolerant varieties recommended for your area."],
            ["पौध कीट-रोधी जाली में तैयार करें और सफ़ेद मक्खी की नियमित जाँच करें।",
             "सफ़ेद मक्खी को आश्रय देने वाले खरपतवार हटाएँ; निगरानी के लिए पीले चिपचिपे जाल लगाएँ।",
             "अपने क्षेत्र के लिए अनुशंसित सहनशील किस्में लगाएँ।"],
        ),
        (
            ["Remove infected plants early so the virus does not spread to healthy ones.",
             "Ask your agriculture officer about whitefly management suited to your area."],
            ["संक्रमित पौधों को जल्दी हटा दें ताकि विषाणु स्वस्थ पौधों में न फैले।",
             "अपने क्षेत्र के अनुसार सफ़ेद मक्खी प्रबंधन के लिए कृषि अधिकारी से पूछें।"],
        ),
        urgent=True,
    ),
    "tomato_mosaic_virus": _entry(
        "tomato", "Mosaic Virus", "मोज़ेक विषाणु", "mosaic", "viral",
        (
            ["Mottled light and dark green pattern on leaves; leaves may be narrow or distorted.",
             "Stunted growth and lower yield.",
             "Spreads through hands, tools, contaminated seed and plant sap. No cure for infected plants."],
            ["पत्तियों पर हल्के और गहरे हरे रंग की चितकबरी बनावट; पत्तियाँ पतली या टेढ़ी हो सकती हैं।",
             "बौनापन और कम उपज।",
             "हाथों, औज़ारों, दूषित बीज और पौधे के रस से फैलता है। संक्रमित पौधे का इलाज नहीं है।"],
        ),
        (
            ["Use clean seed and healthy seedlings.",
             "Wash hands and disinfect tools; avoid handling plants after handling tobacco without washing.",
             "Remove infected plants and rotate crops."],
            ["साफ़ बीज और स्वस्थ पौध लें।",
             "हाथ धोएँ और औज़ार कीटाणु-रहित करें; तंबाकू छूने के बाद बिना हाथ धोए पौधे न छुएँ।",
             "संक्रमित पौधे हटाएँ और फसल-चक्र अपनाएँ।"],
        ),
        (
            ["Remove and destroy infected plants (do not compost).",
             "Ask an agriculture officer to confirm the virus before removing many plants."],
            ["संक्रमित पौधे हटाकर नष्ट करें (उनसे खाद न बनाएँ)।",
             "बहुत से पौधे हटाने से पहले कृषि अधिकारी से विषाणु की पुष्टि करवाएँ।"],
        ),
        urgent=True,
    ),
    "tomato_healthy": _entry(
        "tomato", "Healthy", "स्वस्थ पत्ती", "healthy", "healthy",
        (
            ["Even green colour and no obvious spots, lesions, mould or curling.",
             "No unusual yellowing or distortion."],
            ["एक समान हरा रंग; कोई स्पष्ट धब्बा, घाव, फफूँद या मुड़ाव नहीं।",
             "असामान्य पीलापन या टेढ़ापन नहीं।"],
        ),
        (
            ["Keep rotating crops, using clean seed and giving plants airflow.",
             "Inspect plants every few days, especially after rain or humid weather."],
            ["फसल-चक्र, साफ़ बीज और हवा के आवागमन का ध्यान रखते रहें।",
             "खासकर बारिश या नमी के बाद, हर कुछ दिन में पौधों की जाँच करें।"],
        ),
        (
            ["A healthy result applies only to the leaf in the photo. Other leaves or plants may differ."],
            ["स्वस्थ परिणाम सिर्फ़ फ़ोटो वाली पत्ती के लिए है। दूसरी पत्तियाँ या पौधे अलग हो सकते हैं।"],
        ),
    ),
}

SUPPORTED_DATASET_CLASSES = list(ADVISORY.keys())


def get_advisory(class_key):
    """Advisory dict for a class key (raw dataset names are normalised), or None."""
    entry = ADVISORY.get(class_key) or ADVISORY.get(canonical_key(class_key))
    if entry is None:
        return None
    key = class_key if class_key in ADVISORY else canonical_key(class_key)
    return {"class_key": key, **entry}


def list_advisories(class_keys=None, crop=None):
    """Advisories for the given class keys (default: every documented class)."""
    keys = class_keys if class_keys is not None else SUPPORTED_DATASET_CLASSES
    out = []
    for k in keys:
        item = get_advisory(k)
        if item and (not crop or item["crop"] == crop):
            out.append(item)
    return out


def class_label(class_key):
    item = get_advisory(class_key)
    if item:
        return {"en": f"{item['crop'].title()} – {item['name']['en']}",
                "hi": f"{_CROP_HI.get(item['crop'], item['crop'])} – {item['name']['hi']}"}
    pretty = class_key.replace("_", " ").title()
    return {"en": pretty, "hi": pretty}


_CROP_HI = {"tomato": "टमाटर", "potato": "आलू"}

__all__ = ["ADVISORY", "SUPPORTED_DATASET_CLASSES", "REFERENCE_SOURCES",
           "get_advisory", "list_advisories", "class_label", "crop_of"]
