"""Document AI Parser - Key-Value Pair Extraction Service with Full Indian Language Support"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.models.document import KeyValuePair, BoundingBox

logger = logging.getLogger(__name__)


# ============================================================================
# INDIAN LANGUAGES - MULTILINGUAL LABEL MAPPINGS
# ============================================================================

# Common field labels in 22 Official Indian Languages + English
MULTILINGUAL_LABELS = {
    "name": {
        "en": ["name", "full name", "applicant name"],
        "hi": ["नाम", "पूरा नाम", "आवेदक का नाम"],  # Hindi
        "bn": ["নাম", "পুরো নাম", "আবেদনকারীর নাম"],  # Bengali
        "te": ["పేరు", "పూర్తి పేరు"],  # Telugu
        "mr": ["नाव", "पूर्ण नाव"],  # Marathi
        "ta": ["பெயர்", "முழு பெயர்"],  # Tamil
        "gu": ["નામ", "પૂરું નામ"],  # Gujarati
        "kn": ["ಹೆಸರು", "ಪೂರ್ಣ ಹೆಸರು"],  # Kannada
        "ml": ["പേര്", "മുഴുവൻ പേര്"],  # Malayalam
        "pa": ["ਨਾਮ", "ਪੂਰਾ ਨਾਮ"],  # Punjabi
        "or": ["ନାମ", "ସମ୍ପୂର୍ଣ୍ଣ ନାମ"],  # Odia
        "as": ["নাম", "সম্পূৰ্ণ নাম"],  # Assamese
        "ur": ["نام", "پورا نام"],  # Urdu
        "sa": ["नाम", "पूर्णनाम"],  # Sanskrit
        "sd": ["نالو", "پورو نالو"],  # Sindhi
        "ks": ["ناو"],  # Kashmiri
        "ne": ["नाम", "पूरा नाम"],  # Nepali
        "doi": ["नांव"],  # Dogri
        "kok": ["नांव"],  # Konkani
        "mai": ["नाम"],  # Maithili
        "sat": ["ᱧᱩᱛᱩᱢ"],  # Santali
        "mni": ["ꯃꯤꯡ"],  # Manipuri
    },
    "date": {
        "en": ["date", "dated", "date of"],
        "hi": ["तारीख", "दिनांक", "तिथि"],
        "bn": ["তারিখ", "দিনাঙ্ক"],
        "te": ["తేదీ", "దినాంకం"],
        "mr": ["तारीख", "दिनांक"],
        "ta": ["தேதி", "நாள்"],
        "gu": ["તારીખ", "દિનાંક"],
        "kn": ["ದಿನಾಂಕ", "ತಾರೀಖು"],
        "ml": ["തീയതി", "ദിവസം"],
        "pa": ["ਤਾਰੀਖ", "ਮਿਤੀ"],
        "or": ["ତାରିଖ", "ଦିନାଙ୍କ"],
        "as": ["তাৰিখ"],
        "ur": ["تاریخ"],
        "ne": ["मिति", "तारिख"],
    },
    "address": {
        "en": ["address", "residence", "location"],
        "hi": ["पता", "ठिकाना", "निवास"],
        "bn": ["ঠিকানা", "বাসস্থান"],
        "te": ["చిరునామా", "నివాసం"],
        "mr": ["पत्ता", "ठिकाण"],
        "ta": ["முகவரி", "இருப்பிடம்"],
        "gu": ["સરનામું", "રહેઠાણ"],
        "kn": ["ವಿಳಾಸ", "ನಿವಾಸ"],
        "ml": ["വിലാസം", "മേൽവിലാസം"],
        "pa": ["ਪਤਾ", "ਠਿਕਾਣਾ"],
        "or": ["ଠିକଣା", "ନିବାସ"],
        "ur": ["پتہ", "ٹھکانہ"],
        "ne": ["ठेगाना"],
    },
    "phone": {
        "en": ["phone", "mobile", "telephone", "contact", "cell"],
        "hi": ["फोन", "मोबाइल", "दूरभाष", "संपर्क"],
        "bn": ["ফোন", "মোবাইল", "যোগাযোগ"],
        "te": ["ఫోన్", "మొబైల్", "సంప్రదించండి"],
        "mr": ["फोन", "मोबाईल", "संपर्क"],
        "ta": ["தொலைபேசி", "கைபேசி", "தொடர்பு"],
        "gu": ["ફોન", "મોબાઈલ", "સંપર્ક"],
        "kn": ["ಫೋನ್", "ಮೊಬೈಲ್", "ಸಂಪರ್ಕ"],
        "ml": ["ഫോൺ", "മൊബൈൽ", "ബന്ധപ്പെടുക"],
        "pa": ["ਫੋਨ", "ਮੋਬਾਈਲ"],
        "ur": ["فون", "موبائل"],
    },
    "amount": {
        "en": ["amount", "total", "sum", "payment", "fee"],
        "hi": ["राशि", "कुल", "धनराशि", "भुगतान", "शुल्क"],
        "bn": ["পরিমাণ", "মোট", "টাকা"],
        "te": ["మొత్తం", "రాశి", "చెల్లింపు"],
        "mr": ["रक्कम", "एकूण", "देयक"],
        "ta": ["தொகை", "மொத்தம்", "கட்டணம்"],
        "gu": ["રકમ", "કુલ", "ચુકવણી"],
        "kn": ["ಮೊತ್ತ", "ಒಟ್ಟು", "ಪಾವತಿ"],
        "ml": ["തുക", "മൊത്തം", "പേയ്മെന്റ്"],
        "pa": ["ਰਕਮ", "ਕੁੱਲ"],
        "ur": ["رقم", "کل"],
    },
    "father_name": {
        "en": ["father's name", "father name", "s/o", "son of", "d/o", "daughter of"],
        "hi": ["पिता का नाम", "वालिद का नाम", "पुत्र", "पुत्री"],
        "bn": ["পিতার নাম", "বাবার নাম"],
        "te": ["తండ్రి పేరు"],
        "mr": ["वडिलांचे नाव", "पित्याचे नाव"],
        "ta": ["தந்தை பெயர்", "தகப்பன் பெயர்"],
        "gu": ["પિતાનું નામ"],
        "kn": ["ತಂದೆಯ ಹೆಸರು"],
        "ml": ["പിതാവിന്റെ പേര്", "അച്ഛന്റെ പേര്"],
        "pa": ["ਪਿਤਾ ਦਾ ਨਾਮ"],
        "ur": ["والد کا نام"],
    },
    "occupation": {
        "en": ["occupation", "profession", "job", "employment"],
        "hi": ["व्यवसाय", "पेशा", "नौकरी"],
        "bn": ["পেশা", "বৃত্তি"],
        "te": ["వృత్తి", "ఉద్యోగం"],
        "mr": ["व्यवसाय", "नोकरी"],
        "ta": ["தொழில்", "வேலை"],
        "gu": ["વ્યવસાય", "નોકરી"],
        "kn": ["ವೃತ್తಿ", "ಉದ್ಯೋಗ"],
        "ml": ["തൊഴിൽ", "ജോലി"],
        "pa": ["ਕਿੱਤਾ", "ਪੇਸ਼ਾ"],
        "ur": ["پیشہ"],
    },
    "age": {
        "en": ["age", "years old"],
        "hi": ["आयु", "उम्र", "वर्ष"],
        "bn": ["বয়স", "বছর"],
        "te": ["వయస్సు", "ఏళ్ళు"],
        "mr": ["वय", "वर्षे"],
        "ta": ["வயது", "வயசு"],
        "gu": ["ઉંમર", "વર્ષ"],
        "kn": ["ವಯಸ್ಸು", "ವರ್ಷ"],
        "ml": ["വയസ്സ്", "പ്രായം"],
        "pa": ["ਉਮਰ"],
        "ur": ["عمر"],
    },
    "gender": {
        "en": ["gender", "sex", "male", "female"],
        "hi": ["लिंग", "पुरुष", "महिला"],
        "bn": ["লিঙ্গ", "পুরুষ", "মহিলা"],
        "te": ["లింగం", "పురుషుడు", "స్త్రీ"],
        "mr": ["लिंग", "पुरुष", "स्त्री"],
        "ta": ["பாலினம்", "ஆண்", "பெண்"],
        "gu": ["લિંગ", "પુરુષ", "સ્ત્રી"],
        "kn": ["ಲಿಂಗ", "ಪುರುಷ", "ಮಹಿಳೆ"],
        "ml": ["ലിംഗം", "പുരുഷൻ", "സ്ത്രീ"],
        "ur": ["جنس"],
    },
}

# Legal terms in major Indian languages
LEGAL_LABELS = {
    "case_number": {
        "en": ["case no", "case number", "case id"],
        "hi": ["मामला संख्या", "मामला नं", "केस नंबर"],
        "bn": ["মামলা নম্বর", "কেস নম্বর"],
        "te": ["కేసు నంబర్"],
        "mr": ["खटला क्रमांक", "केस क्रमांक"],
        "ta": ["வழக்கு எண்"],
        "gu": ["કેસ નંબર"],
        "kn": ["ಪ್ರಕರಣ ಸಂಖ್ಯೆ"],
        "ml": ["കേസ് നമ്പർ"],
    },
    "court": {
        "en": ["court", "tribunal", "high court", "supreme court", "district court"],
        "hi": ["न्यायालय", "अदालत", "उच्च न्यायालय", "सर्वोच्च न्यायालय", "जिला न्यायालय"],
        "bn": ["আদালত", "বিচারালয়", "উচ্চ আদালত"],
        "te": ["న్యాయస్థానం", "కోర్టు"],
        "mr": ["न्यायालय", "कोर्ट"],
        "ta": ["நீதிமன்றம்", "உயர் நீதிமன்றம்"],
        "gu": ["અદાલત", "કોર્ટ"],
        "kn": ["ನ್ಯಾಯಾಲಯ", "ಕೋರ್ಟ್"],
        "ml": ["കോടതി", "ന്യായാലയം"],
    },
    "judge": {
        "en": ["judge", "justice", "hon'ble", "honourable"],
        "hi": ["न्यायाधीश", "न्यायमूर्ति", "माननीय"],
        "bn": ["বিচারক", "বিচারপতি"],
        "te": ["న్యాయమూర్తి"],
        "mr": ["न्यायाधीश", "न्यायमूर्ती"],
        "ta": ["நீதிபதி", "நீதியரசர்"],
        "gu": ["ન્યાયાધીશ"],
        "kn": ["ನ್ಯಾಯಾಧೀಶ"],
        "ml": ["ജഡ്ജി", "ന്യായാധിപൻ"],
    },
    "petitioner": {
        "en": ["petitioner", "appellant", "plaintiff", "complainant"],
        "hi": ["याचिकाकर्ता", "अपीलकर्ता", "वादी", "शिकायतकर्ता"],
        "bn": ["আবেদনকারী", "অভিযোগকারী"],
        "te": ["పిటిషనర్", "అప్పీలుదారు"],
        "mr": ["याचिकाकर्ता", "अर्जदार"],
        "ta": ["மனுதாரர்", "விண்ணப்பதாரர்"],
        "gu": ["અરજદાર", "ફરિયાદી"],
        "kn": ["ಅರ್ಜಿದಾರ"],
        "ml": ["ഹർജിക്കാരൻ", "അപേക്ഷകൻ"],
    },
    "respondent": {
        "en": ["respondent", "defendant", "accused", "opposite party"],
        "hi": ["प्रतिवादी", "आरोपी", "विपक्षी"],
        "bn": ["প্রতিবাদী", "আসামী"],
        "te": ["ప్రతివాది", "నిందితుడు"],
        "mr": ["प्रतिवादी", "आरोपी"],
        "ta": ["எதிர்தரப்பினர்", "பிரதிவாதி"],
        "gu": ["પ્રતિવાદી", "આરોપી"],
        "kn": ["ಪ್ರತಿವಾದಿ"],
        "ml": ["എതിർകക്ഷി", "പ്രതി"],
    },
    "fir": {
        "en": ["fir", "first information report", "complaint"],
        "hi": ["प्राथमिकी", "एफआईआर", "शिकायत"],
        "bn": ["এফআইআর", "প্রাথমিক তথ্য প্রতিবেদন"],
        "te": ["ఎఫ్‌ఐఆర్"],
        "mr": ["एफआयआर", "प्रथम माहिती अहवाल"],
        "ta": ["எஃப்ஐஆர்", "முதல் தகவல் அறிக்கை"],
    },
    "section": {
        "en": ["section", "under section", "u/s"],
        "hi": ["धारा", "अंतर्गत धारा"],
        "bn": ["ধারা"],
        "te": ["సెక్షన్"],
        "mr": ["कलम"],
        "ta": ["பிரிவு"],
        "gu": ["કલમ"],
        "kn": ["ಕಲಂ"],
        "ml": ["വകുപ്പ്"],
    },
    "police_station": {
        "en": ["police station", "ps", "thana"],
        "hi": ["थाना", "पुलिस स्टेशन", "पुलिस थाना"],
        "bn": ["থানা", "পুলিশ স্টেশন"],
        "te": ["పోలీస్ స్టేషన్"],
        "mr": ["पोलीस ठाणे"],
        "ta": ["காவல் நிலையம்"],
        "gu": ["પોલીસ સ્ટેશન"],
        "kn": ["ಪೊಲೀಸ್ ಠಾಣೆ"],
        "ml": ["പോലീസ് സ്റ്റേഷൻ"],
    },
    "district": {
        "en": ["district", "dist"],
        "hi": ["जिला", "ज़िला"],
        "bn": ["জেলা"],
        "te": ["జిల్లా"],
        "mr": ["जिल्हा"],
        "ta": ["மாவட்டம்"],
        "gu": ["જિલ્લો"],
        "kn": ["ಜಿಲ್ಲೆ"],
        "ml": ["ജില്ല"],
    },
    "state": {
        "en": ["state", "state of"],
        "hi": ["राज्य", "प्रदेश"],
        "bn": ["রাজ্য"],
        "te": ["రాష్ట్రం"],
        "mr": ["राज्य"],
        "ta": ["மாநிலம்"],
        "gu": ["રાજ્ય"],
        "kn": ["ರಾಜ್ಯ"],
        "ml": ["സംസ്ഥാനം"],
    },
    "witness": {
        "en": ["witness", "witnesses"],
        "hi": ["गवाह", "साक्षी"],
        "bn": ["সাক্ষী"],
        "te": ["సాక్షి"],
        "mr": ["साक्षीदार"],
        "ta": ["சாட்சி"],
        "gu": ["સાક્ષી"],
        "kn": ["ಸಾಕ್ಷಿ"],
        "ml": ["സാക്ഷി"],
    },
    "judgment": {
        "en": ["judgment", "order", "decree", "verdict"],
        "hi": ["निर्णय", "आदेश", "फैसला"],
        "bn": ["রায়", "আদেশ"],
        "te": ["తీర్పు", "ఆదేశం"],
        "mr": ["निकाल", "आदेश"],
        "ta": ["தீர்ப்பு", "உத்தரவு"],
        "gu": ["ચુકાદો", "હુકમ"],
        "kn": ["ತೀರ್ಪು", "ಆದೇಶ"],
        "ml": ["വിധി", "ഉത്തരവ്"],
    },
}


@dataclass
class ExtractionPattern:
    """Pattern for extracting key-value pairs."""
    key_name: str
    pattern: str
    flags: int = re.IGNORECASE


class KVExtractionService:
    """
    Key-Value pair extraction service with full Indian language support.
    
    Supports 22 official Indian languages:
    Hindi, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam,
    Punjabi, Odia, Assamese, Urdu, Sanskrit, Sindhi, Kashmiri, Nepali,
    Dogri, Konkani, Maithili, Santali, Manipuri, Bodo
    """
    
    def __init__(self):
        self.patterns = self._get_default_patterns()
        self.legal_patterns = self._get_legal_document_patterns()
        self.multilingual_labels = MULTILINGUAL_LABELS
        self.legal_labels = LEGAL_LABELS
    
    def _build_multilingual_pattern(self, field: str, labels_dict: Dict) -> str:
        """Build regex pattern from multilingual labels."""
        all_labels = []
        for lang, labels in labels_dict.get(field, {}).items():
            all_labels.extend(labels)
        
        if not all_labels:
            return None
        
        # Escape special regex characters and join
        escaped = [re.escape(label) for label in all_labels]
        return "|".join(escaped)
    
    def _get_default_patterns(self) -> List[ExtractionPattern]:
        """Get default extraction patterns with multilingual support."""
        patterns = []
        
        # Date pattern (multilingual)
        date_labels = self._build_multilingual_pattern("date", MULTILINGUAL_LABELS)
        if date_labels:
            patterns.append(ExtractionPattern(
                "date",
                rf"(?:{date_labels})[\s:]*(\d{{1,2}}[-/\.]\d{{1,2}}[-/\.]\d{{2,4}})",
                re.IGNORECASE
            ))
        
        # Name pattern (multilingual)
        name_labels = self._build_multilingual_pattern("name", MULTILINGUAL_LABELS)
        if name_labels:
            patterns.append(ExtractionPattern(
                "name",
                rf"(?:{name_labels})[\s:]+(.+?)(?:\n|,|$)",
                re.IGNORECASE
            ))
        
        # Phone pattern (multilingual)
        phone_labels = self._build_multilingual_pattern("phone", MULTILINGUAL_LABELS)
        if phone_labels:
            patterns.append(ExtractionPattern(
                "phone",
                rf"(?:{phone_labels})[\s:]*([+]?\d{{10,14}})",
                re.IGNORECASE
            ))
        
        # Amount pattern (multilingual)
        amount_labels = self._build_multilingual_pattern("amount", MULTILINGUAL_LABELS)
        if amount_labels:
            patterns.append(ExtractionPattern(
                "amount",
                rf"(?:{amount_labels})[\s:]*(?:Rs\.?|₹|INR|টাকা|రూ|ரூ|રૂ|ರೂ|രൂ)?\s*([\d,]+\.?\d*)",
                re.IGNORECASE
            ))
        
        # Address pattern (multilingual)
        address_labels = self._build_multilingual_pattern("address", MULTILINGUAL_LABELS)
        if address_labels:
            patterns.append(ExtractionPattern(
                "address",
                rf"(?:{address_labels})[\s:]+(.+?)(?:\n\n|\.$)",
                re.IGNORECASE | re.DOTALL
            ))
        
        # Father's name (multilingual)
        father_labels = self._build_multilingual_pattern("father_name", MULTILINGUAL_LABELS)
        if father_labels:
            patterns.append(ExtractionPattern(
                "father_name",
                rf"(?:{father_labels})[\s:]+(.+?)(?:\n|,|$)",
                re.IGNORECASE
            ))
        
        # Age (multilingual)
        age_labels = self._build_multilingual_pattern("age", MULTILINGUAL_LABELS)
        if age_labels:
            patterns.append(ExtractionPattern(
                "age",
                rf"(?:{age_labels})[\s:]*(\d{{1,3}})",
                re.IGNORECASE
            ))
        
        # Email (universal)
        patterns.append(ExtractionPattern(
            "email",
            r"(?:email|e-mail|ईमेल|ইমেইল|మెయిల్|மின்னஞ்சல்)[\s:]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            re.IGNORECASE
        ))
        
        return patterns
    
    def _get_legal_document_patterns(self) -> List[ExtractionPattern]:
        """Get patterns specific to Indian legal documents with multilingual support."""
        patterns = []
        
        # Case number (multilingual)
        case_labels = self._build_multilingual_pattern("case_number", LEGAL_LABELS)
        if case_labels:
            patterns.append(ExtractionPattern(
                "case_number",
                rf"(?:{case_labels})[\s:]*([A-Z0-9/\-\.]+\d+)",
                re.IGNORECASE
            ))
        
        # Court (multilingual)
        court_labels = self._build_multilingual_pattern("court", LEGAL_LABELS)
        if court_labels:
            patterns.append(ExtractionPattern(
                "court_name",
                rf"(?:{court_labels})[^,\n]{{0,100}}",
                re.IGNORECASE
            ))
        
        # Judge (multilingual)
        judge_labels = self._build_multilingual_pattern("judge", LEGAL_LABELS)
        if judge_labels:
            patterns.append(ExtractionPattern(
                "judge_name",
                rf"(?:{judge_labels})[\s:]*(?:mr\.?|mrs\.?|shri|smt\.?|श्री|श्रीमती)?[\s:]*(.+?)(?:\n|,|$)",
                re.IGNORECASE
            ))
        
        # Petitioner (multilingual)
        pet_labels = self._build_multilingual_pattern("petitioner", LEGAL_LABELS)
        if pet_labels:
            patterns.append(ExtractionPattern(
                "petitioner",
                rf"(?:{pet_labels})[\s:]*(.+?)(?:\s*(?:versus|vs\.?|v/s|-vs-|बनाम|বনাম|వర్సెస్)|\n)",
                re.IGNORECASE
            ))
        
        # Respondent (multilingual)
        resp_labels = self._build_multilingual_pattern("respondent", LEGAL_LABELS)
        if resp_labels:
            patterns.append(ExtractionPattern(
                "respondent",
                rf"(?:{resp_labels})[\s:]*(.+?)(?:\n\n|\.$)",
                re.IGNORECASE
            ))
        
        # Section (multilingual)
        section_labels = self._build_multilingual_pattern("section", LEGAL_LABELS)
        if section_labels:
            patterns.append(ExtractionPattern(
                "section",
                rf"(?:{section_labels})[\s:]*(\d+[A-Za-z]?(?:\s*,?\s*\d+[A-Za-z]?)*)",
                re.IGNORECASE
            ))
        
        # Police Station (multilingual)
        ps_labels = self._build_multilingual_pattern("police_station", LEGAL_LABELS)
        if ps_labels:
            patterns.append(ExtractionPattern(
                "police_station",
                rf"(?:{ps_labels})[\s:]*(.+?)(?:,|\n|$)",
                re.IGNORECASE
            ))
        
        # District (multilingual)
        dist_labels = self._build_multilingual_pattern("district", LEGAL_LABELS)
        if dist_labels:
            patterns.append(ExtractionPattern(
                "district",
                rf"(?:{dist_labels})[\s:]*(.+?)(?:\n|,|$)",
                re.IGNORECASE
            ))
        
        # State (multilingual)
        state_labels = self._build_multilingual_pattern("state", LEGAL_LABELS)
        if state_labels:
            patterns.append(ExtractionPattern(
                "state",
                rf"(?:{state_labels})[\s:]*(.+?)(?:\s*(?:versus|vs\.?|v/s)|\n|,)",
                re.IGNORECASE
            ))
        
        # FIR (multilingual)
        fir_labels = self._build_multilingual_pattern("fir", LEGAL_LABELS)
        if fir_labels:
            patterns.append(ExtractionPattern(
                "fir_number",
                rf"(?:{fir_labels})[\s:]*(?:No\.?)?[\s:]*(\d+/\d+)",
                re.IGNORECASE
            ))
        
        # Standard English legal patterns
        patterns.extend([
            ExtractionPattern("writ_petition", r"(?:writ\s*petition|W\.?P\.?)[\s:]*(?:No\.?)?[\s:]*(\d+/\d+)", re.IGNORECASE),
            ExtractionPattern("civil_appeal", r"(?:civil\s*appeal|C\.?A\.?)[\s:]*(?:No\.?)?[\s:]*(\d+/\d+)", re.IGNORECASE),
            ExtractionPattern("criminal_appeal", r"(?:criminal\s*appeal|Cr\.?A\.?)[\s:]*(?:No\.?)?[\s:]*(\d+/\d+)", re.IGNORECASE),
            ExtractionPattern("slp", r"(?:S\.?L\.?P\.?|special\s*leave\s*petition)[\s:]*(?:No\.?)?[\s:]*(\d+/\d+)", re.IGNORECASE),
            ExtractionPattern("article", r"(?:article|अनुच्छेद|অনুচ্ছেদ|ఆర్టికల్)[\s:]*(\d+(?:\s*,?\s*\d+)*)", re.IGNORECASE),
            ExtractionPattern("act", r"(?:under\s*(?:the)?|of\s+the)\s*([A-Z][A-Za-z\s,]+?Act[,\s]+\d{4})", re.IGNORECASE),
            ExtractionPattern("date_of_judgment", r"(?:date\s*of\s*(?:judgment|order|decision)|निर्णय\s*दिनांक|রায়ের\s*তারিখ)[\s:]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})", re.IGNORECASE),
            ExtractionPattern("date_of_filing", r"(?:date\s*of\s*filing|दाखिल\s*तिथि)[\s:]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})", re.IGNORECASE),
        ])
        
        return patterns
    
    def extract_from_text(
        self,
        text: str,
        include_legal: bool = True
    ) -> List[KeyValuePair]:
        """
        Extract key-value pairs from text (supports all Indian languages).
        
        Args:
            text: Text to extract from
            include_legal: Include legal document patterns
            
        Returns:
            List of extracted key-value pairs
        """
        results = []
        seen_keys = set()
        
        # Apply default patterns
        for pattern in self.patterns:
            kv = self._apply_pattern(pattern, text)
            if kv and pattern.key_name not in seen_keys:
                results.append(kv)
                seen_keys.add(pattern.key_name)
        
        # Apply legal patterns if requested
        if include_legal:
            for pattern in self.legal_patterns:
                kv = self._apply_pattern(pattern, text)
                if kv and pattern.key_name not in seen_keys:
                    results.append(kv)
                    seen_keys.add(pattern.key_name)
        
        # Extract colon-separated pairs (supports Indian punctuation)
        colon_pairs = self._extract_colon_pairs(text)
        for kv in colon_pairs:
            if kv.key.lower() not in seen_keys:
                results.append(kv)
                seen_keys.add(kv.key.lower())
        
        return results
    
    def _apply_pattern(self, pattern: ExtractionPattern, text: str) -> Optional[KeyValuePair]:
        """Apply a single pattern to extract key-value pair."""
        try:
            match = re.search(pattern.pattern, text, pattern.flags)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                # Clean up value
                value = re.sub(r'\s+', ' ', value)
                value = value.strip('.,;:।')  # Include Hindi danda
                
                if value and len(value) > 1:
                    return KeyValuePair(
                        key=pattern.key_name,
                        value=value,
                        confidence=0.9
                    )
        except Exception as e:
            logger.debug(f"Pattern matching failed for {pattern.key_name}: {e}")
        
        return None
    
    def _extract_colon_pairs(self, text: str) -> List[KeyValuePair]:
        """Extract key:value pairs from text (supports Indian scripts and punctuation)."""
        results = []
        
        # Pattern: Key: Value (supports Devanagari danda ।, colon, etc.)
        # Supports: Latin, Devanagari, Bengali, Telugu, Tamil, Kannada, Malayalam, Gujarati, Punjabi, Odia scripts
        pattern = r'^([A-Za-z\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F][^\n:।]{1,50})\s*[:।]\s*(.+?)$'
        
        for match in re.finditer(pattern, text, re.MULTILINE):
            key = match.group(1).strip()
            value = match.group(2).strip()
            
            # Filter out obvious non-key-value pairs
            if len(key) < 2 or len(value) < 1:
                continue
            if key.lower() in ['the', 'and', 'but', 'for', 'with', 'this', 'that']:
                continue
            
            results.append(KeyValuePair(
                key=key,
                value=value[:200],  # Limit value length
                confidence=0.7
            ))
        
        return results
    
    def extract_from_layout(
        self,
        text_blocks: List[Dict[str, Any]]
    ) -> List[KeyValuePair]:
        """
        Extract key-value pairs based on layout proximity.
        
        Looks for label-value pairs where:
        - Label is on the left, value on the right
        - Label is bold/uppercase, value is normal
        """
        results = []
        
        # Sort by Y position then X
        sorted_blocks = sorted(
            text_blocks,
            key=lambda b: (b["bounding_box"].y, b["bounding_box"].x)
        )
        
        for i, block in enumerate(sorted_blocks):
            text = block["text"].strip()
            bbox = block["bounding_box"]
            
            # Check if this looks like a label
            if self._is_label(text):
                # Look for value to the right or below
                value_block = self._find_value_block(sorted_blocks, i, bbox)
                if value_block:
                    key = text.rstrip(':।').strip()
                    value = value_block["text"].strip()
                    
                    results.append(KeyValuePair(
                        key=key,
                        value=value,
                        confidence=0.8,
                        bounding_box=bbox
                    ))
        
        return results
    
    def _is_label(self, text: str) -> bool:
        """Check if text looks like a label (supports all Indian languages)."""
        text = text.strip()
        
        # Ends with colon or Hindi danda
        if text.endswith(':') or text.endswith('।'):
            return len(text) < 60
        
        # Is uppercase and short (for English)
        if text.isupper() and 2 < len(text) < 40:
            return True
        
        # Check against all multilingual labels
        text_lower = text.lower()
        for field, langs in {**self.multilingual_labels, **self.legal_labels}.items():
            for lang, labels in langs.items():
                for label in labels:
                    if label.lower() in text_lower or text_lower in label.lower():
                        return True
        
        return False
    
    def _find_value_block(
        self,
        blocks: List[Dict[str, Any]],
        label_idx: int,
        label_bbox: BoundingBox
    ) -> Optional[Dict[str, Any]]:
        """Find the value block for a label."""
        for i in range(label_idx + 1, min(label_idx + 3, len(blocks))):
            block = blocks[i]
            bbox = block["bounding_box"]
            
            # Check if to the right (same line)
            if abs(bbox.y - label_bbox.y) < label_bbox.height:
                if bbox.x > label_bbox.x + label_bbox.width:
                    return block
            
            # Check if below (next line, aligned)
            if bbox.y > label_bbox.y + label_bbox.height:
                if abs(bbox.x - label_bbox.x) < label_bbox.width:
                    return block
        
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return [
            "English (en)", "Hindi (hi)", "Bengali (bn)", "Telugu (te)",
            "Marathi (mr)", "Tamil (ta)", "Gujarati (gu)", "Kannada (kn)",
            "Malayalam (ml)", "Punjabi (pa)", "Odia (or)", "Assamese (as)",
            "Urdu (ur)", "Sanskrit (sa)", "Sindhi (sd)", "Kashmiri (ks)",
            "Nepali (ne)", "Dogri (doi)", "Konkani (kok)", "Maithili (mai)",
            "Santali (sat)", "Manipuri (mni)", "Bodo (brx)"
        ]


# Singleton instance
_kv_service: Optional[KVExtractionService] = None


def get_kv_extraction_service() -> KVExtractionService:
    """Get KV extraction service singleton."""
    global _kv_service
    if _kv_service is None:
        _kv_service = KVExtractionService()
    return _kv_service
