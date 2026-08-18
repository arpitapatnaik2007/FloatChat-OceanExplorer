"""Supported speech/UI locales, mirroring the frontend language selector."""

LANGUAGES: list[dict[str, str]] = [
    {"code": "en-IN", "label": "English", "placeholder": "Ask about ARGO floats, salinity, BGC parameters..."},
    {"code": "hi-IN", "label": "हिन्दी", "placeholder": "आर्गो फ्लोट, लवणता या BGC मापदंडों के बारे में पूछें..."},
    {"code": "or-IN", "label": "ଓଡ଼ିଆ", "placeholder": "ଆର୍ଗୋ ଫ୍ଲୋଟ, ଲବଣତା କିମ୍ବା BGC ବିଷୟରେ ପଚାରନ୍ତୁ..."},
    {"code": "bn-IN", "label": "বাংলা", "placeholder": "আর্গো ফ্লোট, লবণাক্ততা বা BGC সম্পর্কে জিজ্ঞাসা করুন..."},
    {"code": "te-IN", "label": "తెలుగు", "placeholder": "ఆర్గో ఫ్లోట్లు, లవణీయత గురించి అడగండి..."},
    {"code": "ta-IN", "label": "தமிழ்", "placeholder": "ஆர்கோ மிதவைகள், உப்புத்தன்மை பற்றி கேளுங்கள்..."},
    {"code": "mr-IN", "label": "मराठी", "placeholder": "आर्गो फ्लोट्स, क्षारता विषयी विचारा..."},
    {"code": "kn-IN", "label": "ಕನ್ನಡ", "placeholder": "ಆರ್ಗೊ ಫ್ಲೋಟ್‌ಗಳ ಬಗ್ಗೆ ಕೇಳಿ..."},
    {"code": "ml-IN", "label": "മലയാളം", "placeholder": "ആർഗോ ഫ്ലോട്ടുകളെക്കുറിച്ച് ചോദിക്കുക..."},
    {"code": "gu-IN", "label": "ગુજરાતી", "placeholder": "આર્ગો ફ્લોટ વિશે પૂછો..."},
    {"code": "pa-IN", "label": "ਪੰਜਾਬੀ", "placeholder": "ਆਰਗੋ ਫਲੋਟਸ ਬਾਰੇ ਪੁੱਛੋ..."},
    {"code": "as-IN", "label": "অসমীয়া", "placeholder": "আৰ্গো ফ্লʼটৰ বিষয়ে সোধক..."},
    {"code": "ur-IN", "label": "اردو", "placeholder": "آرگو فلوٹس کے بارے میں پوچھیں..."},
    {"code": "fr-FR", "label": "Français", "placeholder": "Posez une question sur les flotteurs ARGO..."},
    {"code": "es-ES", "label": "Español", "placeholder": "Pregunta sobre los flotadores ARGO..."},
    {"code": "ja-JP", "label": "日本語", "placeholder": "ARGOフロートについて質問してください..."},
]

BY_CODE = {item["code"]: item for item in LANGUAGES}


def resolve(code: str) -> dict[str, str]:
    return BY_CODE.get(code, BY_CODE["en-IN"])
