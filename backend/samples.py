"""Sample workers for the one-tap demo.

Each is a fictional person answering Kaam's six questions the way people
actually talk: filler words, self-corrections, English trade words mixed into
their own language, and a background that matches where they'd be speaking.

The audio is synthesized with Timbre and mixed with background noise by
`scripts/make_samples.py`, then decoded in the browser and streamed through
the live pipeline (Prisma →
LLM → Timbre) exactly like a microphone, so the demo shows real results.
Everything here is made up; the UI labels these as synthetic voices.
"""

SAMPLES = [
    {
        "id": "sunita-cook",
        "gender": "female",
        "language": "hi-IN",
        "name": "Sunita Devi",
        "trade": "Cook",
        "place": "Darbhanga → Gurgaon",
        "scene": "kitchen",
        "scene_label": "In a kitchen, pressure cooker on",
        "voice": "Chitra",
        "model": "timbre-v2.5",
        "speed": 0.95,
        "answers": [
            "जी, नमस्ते। मेरा नाम सुनीता है... सुनीता देवी। बिहार से हूँ, दरभंगा ज़िला। अभी गुड़गाँव में रहती हूँ, सेक्टर चालीस के पास।",
            "खाना बनाती हूँ, cook का काम करती हूँ घरों में। करीब छह साल... नहीं, सात साल हो गए, दो हज़ार उन्नीस से कर रही हूँ।",
            "पहले DLF फेज़ टू में एक family के यहाँ चार साल रही। उनके दो बच्चे थे तो उनका tiffin भी मैं ही बनाती थी। फिर एक PG में लगी, वहाँ पंद्रह लड़कियों का सुबह-शाम का खाना बनाती थी।",
            "North Indian खाना बहुत अच्छा बनता है, दाल मखनी, पनीर, रोटी। और सफ़ाई का मैं बहुत ध्यान रखती हूँ। PG वाली मैडम बोलती थीं कि सुनीता के आने के बाद कोई लड़की बीमार नहीं पड़ी।",
            "गुड़गाँव में ही चाहिए, सेक्टर चालीस के आस-पास हो तो अच्छा है। दो घर मिल जाएँ तो... एक घर का आठ-नौ हज़ार।",
            "हिंदी बोलती हूँ, मैथिली भी। English थोड़ा-थोड़ा समझ लेती हूँ, बोल नहीं पाती।",
        ],
    },
    {
        "id": "joseph-guard",
        "gender": "male",
        "language": "en-IN",
        "name": "Joseph Mathew",
        "trade": "Security guard",
        "place": "Kottayam → Bengaluru",
        "scene": "street_night",
        "scene_label": "At a gate at night, traffic passing",
        "voice": "Shlok",
        "model": "timbre-v2.5",
        "speed": 0.95,
        "answers": [
            "Good evening madam. My name is Joseph, Joseph Mathew. I am from Kottayam, Kerala. Now I am staying in Bangalore, near Hebbal.",
            "Security guard job I am doing. Eleven years total. First three years in Kerala itself, then I came to Bangalore.",
            "First I was in one jewellery shop in Kottayam. Then in Bangalore, in one apartment complex in Hebbal, six years, night shift mostly. After that two years in a tech park, but that contract got over last month.",
            "I am very strict with the visitor register and CCTV checking. One time at night I found a short circuit in the meter room and I switched off the main, so no fire came. The association gave me a certificate for that.",
            "North Bangalore only, Hebbal or Yelahanka side. Day shift or night shift, both okay. Salary I am expecting around twenty two thousand.",
            "Malayalam is my mother tongue. English and Hindi I can speak. Kannada also little bit, enough for talking with delivery boys.",
        ],
    },
    {
        "id": "murugan-electrician",
        "gender": "male",
        "language": "ta-IN",
        "name": "Murugan",
        "trade": "Electrician",
        "place": "Tirunelveli → Chennai",
        "scene": "roadside_phone",
        "scene_label": "On a phone by a busy road",
        "voice": "Yashraj",
        "model": "timbre-v3.0",
        "speed": 1.0,
        "answers": [
            "வணக்கம் சார். என் பேரு முருகன். சொந்த ஊரு திருநெல்வேலி. இப்போ சென்னையில, தாம்பரம் பக்கத்துல இருக்கேன்.",
            "நான் electrician வேலை பாக்கறேன். ஒரு பன்னிரண்டு வருஷமா பண்றேன். முதல்ல helper-ஆ சேர்ந்தேன், அப்புறம் தனியா வேலை எடுக்க ஆரம்பிச்சேன்.",
            "முதல்ல ஒரு contractor கிட்ட அஞ்சு வருஷம் இருந்தேன், புது வீடுகளுக்கு full wiring. அப்புறம் ஒரு apartment-ல maintenance electrician-ஆ மூணு வருஷம். இப்போ தனியா வீட்டு வேலைங்க பண்றேன்.",
            "Wiring, fan, light fitting, inverter எல்லாம் பண்ணுவேன். Fault கண்டுபிடிக்கறதுல நான் ரொம்ப fast. போன மழையில ஒரு apartment-ல current போயிடுச்சு, ராத்திரியே சரி பண்ணி கொடுத்தேன்.",
            "தாம்பரம், குரோம்பேட்டை பக்கம் இருந்தா நல்லது. மாசம் இருபத்தஞ்சு ஆயிரம் எதிர்பாக்கறேன். இல்லன்னா ஒரு நாளைக்கு ஆயிரம் ரூபாய்.",
            "தமிழ் தான் சார். கொஞ்சம் English புரியும். Hindi... ரெண்டு மூணு வார்த்தை தான் தெரியும்.",
        ],
    },
    {
        "id": "rina-nanny",
        "gender": "female",
        "language": "bn-IN",
        "name": "Rina Das",
        "trade": "Nanny and caregiver",
        "place": "Canning → Kolkata",
        "scene": "home_tv",
        "scene_label": "At home, TV and ceiling fan on",
        "voice": "Kirra",
        "model": "timbre-v2.5",
        "speed": 0.95,
        "answers": [
            "নমস্কার দিদি। আমার নাম রিনা, রিনা দাস। বাড়ি দক্ষিণ চব্বিশ পরগনা, ক্যানিং। এখন কলকাতায় থাকি, যাদবপুরে।",
            "আমি বাচ্চা দেখাশোনার কাজ করি, আয়ার কাজ। আট বছর হল এই কাজ করছি।",
            "প্রথমে সল্টলেকে এক বাড়িতে পাঁচ বছর ছিলাম, যমজ বাচ্চা ছিল, জন্ম থেকে দেখেছি। তারপর বালিগঞ্জে এক বয়স্ক মাসিমার দেখাশোনা করতাম, তিন বছর। মাসিমা মারা যাওয়ার পর থেকে কাজ খুঁজছি।",
            "বাচ্চাদের খুব ভালো সামলাতে পারি। খাওয়ানো, স্নান করানো, ঘুম পাড়ানো, সব। আর রাতে জেগে থাকতে পারি। যমজ বাচ্চাদের মা বলতেন, রিনা না থাকলে আমরা পারতাম না।",
            "যাদবপুর, গড়িয়াহাট এদিকে হলে ভালো হয়। থাকা-খাওয়া সহ হলে বারো হাজার, না হলে চোদ্দো হাজার।",
            "বাংলা বলি। হিন্দি বলতে পারি, কাজ চলে যায়। ইংরেজি একটু একটু বুঝি।",
        ],
    },
    {
        "id": "santosh-driver",
        "gender": "male",
        "language": "mr-IN",
        "name": "Santosh Pawar",
        "trade": "Driver",
        "place": "Satara → Pune",
        "scene": "traffic",
        "scene_label": "On the street, traffic and horns",
        "voice": "Ishaan",
        "model": "timbre-v2.5",
        "speed": 1.0,
        "answers": [
            "नमस्कार साहेब. माझं नाव संतोष, संतोष पवार. मी साताऱ्याचा आहे, कोरेगाव तालुका. आता पुण्यात राहतो, हडपसरला.",
            "मी ड्रायव्हर आहे, फोर-व्हीलर चालवतो. नऊ वर्षं झाली, म्हणजे... दोन हजार सतरापासून.",
            "आधी एका travels कंपनीत होतो, तीन वर्षं. Innova आणि Ertiga चालवायचो, मुंबई, पुणे, गोवा trips. नंतर एका डॉक्टर साहेबांकडे personal driver म्हणून पाच वर्षं होतो. ते आता बाहेरगावी shift झाले.",
            "माझं driving एकदम safe आहे. नऊ वर्षांत एकही accident नाही, एकही challan नाही. Highway आणि city दोन्ही चालवतो. Google Map पण वापरता येतो.",
            "हडपसर, मगरपट्टा, खराडी कडे मिळालं तर बरं. पगार अठरा ते वीस हजार अपेक्षित आहे. रात्रीचं काम असेल तर थोडं जास्त.",
            "मराठी, हिंदी बोलतो. इंग्रजी थोडं थोडं समजतं. आणि driving license आहे, commercial badge पण आहे.",
        ],
    },
]

BY_ID = {s["id"]: s for s in SAMPLES}


def public_manifest() -> list[dict]:
    """What the UI needs: who each sample is, plus the script for comparison."""
    from .questions import QUESTION_IDS

    return [
        {
            "id": s["id"],
            "language": s["language"],
            "name": s["name"],
            "trade": s["trade"],
            "place": s["place"],
            "scene_label": s["scene_label"],
            "gender": s["gender"],
            "audio": [f"/samples/{s['id']}/{qid}.m4a" for qid in QUESTION_IDS],
            "script": s["answers"],
        }
        for s in SAMPLES
    ]
