"""The interview Kaam conducts, in each supported language.

Questions are short and conversational because Timbre reads them aloud and the
worker answers by voice. Translations other than English and Hindi should be
checked by a native speaker before recording demos.
"""

# id → what the answer is used for in the resume
QUESTION_IDS = ["intro", "work", "history", "strengths", "preferences", "languages"]

LANGUAGES = {
    "hi-IN": {"label": "हिन्दी", "name": "Hindi"},
    "en-IN": {"label": "English", "name": "English"},
    "ta-IN": {"label": "தமிழ்", "name": "Tamil"},
    "bn-IN": {"label": "বাংলা", "name": "Bengali"},
    "mr-IN": {"label": "मराठी", "name": "Marathi"},
}

QUESTIONS = {
    "hi-IN": [
        "नमस्ते! आपका नाम क्या है, और आप कहाँ से हैं?",
        "आप कौन सा काम करते हैं, और कितने साल से कर रहे हैं?",
        "अब तक आपने कहाँ-कहाँ काम किया है? थोड़ा बताइए।",
        "आप किस काम में सबसे अच्छे हैं? कोई ऐसी बात बताइए जिस पर आपको गर्व हो।",
        "आप किस इलाके में काम करना चाहते हैं, और कितनी तनख़्वाह की उम्मीद रखते हैं?",
        "आप कौन-कौन सी भाषाएँ बोल लेते हैं?",
    ],
    "en-IN": [
        "Hello! What's your name, and where are you from?",
        "What work do you do, and for how many years have you done it?",
        "Where have you worked so far? Tell me a little about it.",
        "What are you best at? Tell me about something you're proud of.",
        "Which area would you like to work in, and what salary do you expect?",
        "Which languages can you speak?",
    ],
    "ta-IN": [
        "வணக்கம்! உங்கள் பெயர் என்ன, நீங்கள் எந்த ஊர்?",
        "நீங்கள் என்ன வேலை செய்கிறீர்கள், எத்தனை வருடங்களாக செய்கிறீர்கள்?",
        "இதுவரை எங்கெல்லாம் வேலை செய்திருக்கிறீர்கள்? கொஞ்சம் சொல்லுங்கள்.",
        "எந்த வேலையில் நீங்கள் மிகவும் திறமையானவர்? உங்களுக்குப் பெருமையான ஒரு விஷயம் சொல்லுங்கள்.",
        "எந்தப் பகுதியில் வேலை செய்ய விரும்புகிறீர்கள், எவ்வளவு சம்பளம் எதிர்பார்க்கிறீர்கள்?",
        "நீங்கள் எந்தெந்த மொழிகள் பேசுவீர்கள்?",
    ],
    "bn-IN": [
        "নমস্কার! আপনার নাম কী, আর আপনি কোথা থেকে এসেছেন?",
        "আপনি কী কাজ করেন, আর কত বছর ধরে করছেন?",
        "এখন পর্যন্ত কোথায় কোথায় কাজ করেছেন? একটু বলুন।",
        "কোন কাজে আপনি সবচেয়ে দক্ষ? এমন কিছু বলুন যা নিয়ে আপনি গর্বিত।",
        "আপনি কোন এলাকায় কাজ করতে চান, আর কত মাইনে আশা করেন?",
        "আপনি কোন কোন ভাষা বলতে পারেন?",
    ],
    "mr-IN": [
        "नमस्कार! तुमचं नाव काय, आणि तुम्ही कुठले आहात?",
        "तुम्ही कोणतं काम करता, आणि किती वर्षांपासून करताय?",
        "आत्तापर्यंत तुम्ही कुठे कुठे काम केलं आहे? थोडं सांगा.",
        "कोणत्या कामात तुम्ही सगळ्यात जास्त हुशार आहात? ज्याचा तुम्हाला अभिमान आहे असं काहीतरी सांगा.",
        "तुम्हाला कोणत्या भागात काम करायचं आहे, आणि किती पगाराची अपेक्षा आहे?",
        "तुम्ही कोणकोणत्या भाषा बोलता?",
    ],
}

# Everything the worker sees or hears around the questions, in their language.
# `intro` is also spoken aloud, because not everyone can read a consent notice.
UI = {
    "en-IN": {
        "intro_title": "Just 6 questions. Answer by speaking.",
        "intro": "Your answers go to speech and AI services to make your resume. Kaam doesn't save your recording. Anyone with your card's link can see your card.",
        "start": "Start", "speak": "Speak now", "listen": "Listen", "wait": "One moment…",
        "next": "Next", "finish": "Finish", "skip": "Skip", "again": "Say Again", "fix": "Fix",
        "voice_q": "Which voice should introduce you?", "female": "Female Voice", "male": "Male Voice",
        "building": "Making your resume…", "build_error": "Couldn't make your resume. Try again.", "retry": "Try Again",
        "mic_blocked": "The microphone is off. Allow it in your browser settings, then try again.",
        "speech_error": "Can't hear right now. Try again.",
        "quit": "Start over? Your answers will be lost.",
        "ready": "Your card is ready", "whatsapp": "Send on WhatsApp", "copy": "Copy Link",
        "copied": "Copied", "image": "Save Image", "print": "Print",
    },
    "hi-IN": {
        "intro_title": "बस 6 सवाल। बोलकर जवाब दीजिए।",
        "intro": "आपके जवाब रिज़्यूमे बनाने के लिए आवाज़ और AI सेवाओं को भेजे जाते हैं। काम आपकी रिकॉर्डिंग सेव नहीं करता। आपके कार्ड का लिंक जिसके पास होगा, वह आपका कार्ड देख सकता है।",
        "start": "शुरू करें", "speak": "अब बोलिए", "listen": "सुनिए", "wait": "एक पल…",
        "next": "आगे", "finish": "पूरा करें", "skip": "छोड़ें", "again": "फिर से बोलें", "fix": "ठीक करें",
        "voice_q": "आपका परिचय किस आवाज़ में हो?", "female": "महिला की आवाज़", "male": "पुरुष की आवाज़",
        "building": "आपका रिज़्यूमे बन रहा है…", "build_error": "रिज़्यूमे नहीं बन पाया। फिर कोशिश कीजिए।", "retry": "फिर कोशिश करें",
        "mic_blocked": "माइक बंद है। ब्राउज़र की सेटिंग में माइक की अनुमति दीजिए, फिर कोशिश कीजिए।",
        "speech_error": "अभी सुनाई नहीं दे रहा। फिर कोशिश कीजिए।",
        "quit": "दोबारा शुरू करें? आपके जवाब मिट जाएँगे।",
        "ready": "आपका कार्ड तैयार है", "whatsapp": "WhatsApp पर भेजें", "copy": "लिंक कॉपी करें",
        "copied": "कॉपी हो गया", "image": "फ़ोटो सेव करें", "print": "प्रिंट करें",
    },
    "ta-IN": {
        "intro_title": "ஆறு கேள்விகள் மட்டும். பேசி பதில் சொல்லுங்கள்.",
        "intro": "உங்கள் ரெஸ்யூமே தயாரிக்க, உங்கள் பதில்கள் குரல் மற்றும் AI சேவைகளுக்கு அனுப்பப்படும். காம் உங்கள் பதிவைச் சேமிக்காது. உங்கள் கார்டின் லிங்க் உள்ள யாரும் உங்கள் கார்டைப் பார்க்கலாம்.",
        "start": "தொடங்குங்கள்", "speak": "இப்போது பேசுங்கள்", "listen": "கேளுங்கள்", "wait": "ஒரு நிமிடம்…",
        "next": "அடுத்து", "finish": "முடிக்கவும்", "skip": "தவிர்க்கவும்", "again": "மீண்டும் சொல்லுங்கள்", "fix": "திருத்தவும்",
        "voice_q": "எந்தக் குரலில் உங்களை அறிமுகப்படுத்தலாம்?", "female": "பெண் குரல்", "male": "ஆண் குரல்",
        "building": "உங்கள் ரெஸ்யூமே தயாராகிறது…", "build_error": "ரெஸ்யூமே தயாரிக்க முடியவில்லை. மீண்டும் முயலுங்கள்.", "retry": "மீண்டும் முயலுங்கள்",
        "mic_blocked": "மைக் ஆஃப் ஆக உள்ளது. பிரவுசர் செட்டிங்ஸில் அனுமதி கொடுத்து மீண்டும் முயலுங்கள்.",
        "speech_error": "இப்போது கேட்கவில்லை. மீண்டும் முயலுங்கள்.",
        "quit": "மீண்டும் தொடங்கவா? உங்கள் பதில்கள் அழிந்துவிடும்.",
        "ready": "உங்கள் கார்டு தயார்", "whatsapp": "WhatsApp-ல் அனுப்பவும்", "copy": "லிங்க் காப்பி",
        "copied": "காப்பி ஆனது", "image": "படத்தைச் சேமிக்கவும்", "print": "பிரிண்ட்",
    },
    "bn-IN": {
        "intro_title": "মাত্র ৬টি প্রশ্ন। বলে উত্তর দিন।",
        "intro": "আপনার রেজিউমে তৈরি করতে আপনার উত্তর ভয়েস ও AI পরিষেবায় পাঠানো হয়। কাম আপনার রেকর্ডিং সেভ করে না। আপনার কার্ডের লিংক যার কাছে থাকবে, সে আপনার কার্ড দেখতে পাবে।",
        "start": "শুরু করুন", "speak": "এবার বলুন", "listen": "শুনুন", "wait": "এক মুহূর্ত…",
        "next": "পরের", "finish": "শেষ করুন", "skip": "বাদ দিন", "again": "আবার বলুন", "fix": "ঠিক করুন",
        "voice_q": "কোন কণ্ঠে আপনার পরিচয় দেওয়া হবে?", "female": "মহিলা কণ্ঠ", "male": "পুরুষ কণ্ঠ",
        "building": "আপনার রেজিউমে তৈরি হচ্ছে…", "build_error": "রেজিউমে তৈরি করা যায়নি। আবার চেষ্টা করুন।", "retry": "আবার চেষ্টা করুন",
        "mic_blocked": "মাইক বন্ধ আছে। ব্রাউজারের সেটিংসে অনুমতি দিয়ে আবার চেষ্টা করুন।",
        "speech_error": "এখন শোনা যাচ্ছে না। আবার চেষ্টা করুন।",
        "quit": "আবার শুরু করবেন? আপনার উত্তর মুছে যাবে।",
        "ready": "আপনার কার্ড তৈরি", "whatsapp": "WhatsApp-এ পাঠান", "copy": "লিংক কপি করুন",
        "copied": "কপি হয়েছে", "image": "ছবি সেভ করুন", "print": "প্রিন্ট করুন",
    },
    "mr-IN": {
        "intro_title": "फक्त ६ प्रश्न. बोलून उत्तर द्या.",
        "intro": "तुमचा रेझ्युमे बनवण्यासाठी तुमची उत्तरे आवाज आणि AI सेवांकडे पाठवली जातात. काम तुमचे रेकॉर्डिंग सेव्ह करत नाही. तुमच्या कार्डची लिंक ज्याच्याकडे असेल, त्याला तुमचे कार्ड दिसू शकते.",
        "start": "सुरू करा", "speak": "आता बोला", "listen": "ऐका", "wait": "एक क्षण…",
        "next": "पुढे", "finish": "पूर्ण करा", "skip": "वगळा", "again": "पुन्हा बोला", "fix": "दुरुस्त करा",
        "voice_q": "तुमची ओळख कोणत्या आवाजात करून द्यायची?", "female": "महिलेचा आवाज", "male": "पुरुषाचा आवाज",
        "building": "तुमचा रेझ्युमे तयार होत आहे…", "build_error": "रेझ्युमे तयार करता आला नाही. पुन्हा प्रयत्न करा.", "retry": "पुन्हा प्रयत्न करा",
        "mic_blocked": "माइक बंद आहे. ब्राउझरच्या सेटिंग्जमध्ये परवानगी देऊन पुन्हा प्रयत्न करा.",
        "speech_error": "आत्ता ऐकू येत नाही. पुन्हा प्रयत्न करा.",
        "quit": "पुन्हा सुरू करायचे? तुमची उत्तरे पुसली जातील.",
        "ready": "तुमचे कार्ड तयार आहे", "whatsapp": "WhatsApp वर पाठवा", "copy": "लिंक कॉपी करा",
        "copied": "कॉपी झाले", "image": "फोटो सेव्ह करा", "print": "प्रिंट करा",
    },
}

assert all(len(qs) == len(QUESTION_IDS) for qs in QUESTIONS.values())
assert QUESTIONS.keys() == LANGUAGES.keys() == UI.keys()
assert all(t.keys() == UI["en-IN"].keys() for t in UI.values())


def questions_for(lang: str) -> list[dict]:
    return [{"id": qid, "text": text} for qid, text in zip(QUESTION_IDS, QUESTIONS[lang])]


def stt_lang_for(lang: str) -> str:
    """Prisma language setting for answers in `lang`.

    Workers mix English trade words into every language ("AC repair",
    "four-wheeler"). Prisma handles that within a single locale and keeps those
    words in Latin script, and it rejects comma-separated lists in `lang_code`.
    """
    return lang
