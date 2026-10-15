"""
MARAPOLI (மரபொலி) — Automatic Region Identification Service
Analyzes Tamil oral transcripts to identify villages, towns, districts, states,
and cultural regions with evidence extraction, role disambiguation, and
anti-hallucination guarantees.
"""

import os
import re
import json
import requests

# ---------------------------------------------------------------------------
# 1. Comprehensive Tamil Geographic Knowledge Base (Gazetteer)
# ---------------------------------------------------------------------------

TAMIL_REGIONS = {
    "KONGU": "கொங்கு மண்டலம் (மேற்கு தமிழ்நாடு)",
    "PANDYA": "பாண்டி நாடு (தென் மண்டலம்)",
    "CHOLA": "சோழ நாடு (டெல்டா மண்டலம்)",
    "THONDAI": "தொண்டை மண்டலம் (வட மண்டலம்)",
    "NADU_NADU": "நடுநாடு (மத்திய மண்டலம்)",
    "NANJIL": "நாஞ்சில் நாடு (தென்கோடி குமரி)",
}

# All 38 Districts of Tamil Nadu + standard variants and cultural regions
TN_DISTRICTS = {
    "சென்னை": {"district": "சென்னை", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["சென்னை", "மதராஸ்", "சென்னபட்டினம்"]},
    "மதுரை": {"district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["மதுரை", "கூடல்", "நான்மாடக்கூடல்"]},
    "கோயம்புத்தூர்": {"district": "கோயம்புத்தூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["கோயம்புத்தூர்", "கோவை", "கோயமுத்தூர்"]},
    "திருநெல்வேலி": {"district": "திருநெல்வேலி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["திருநெல்வேலி", "நெல்லை", "வேணுவனம்"]},
    "தஞ்சாவூர்": {"district": "தஞ்சாவூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["தஞ்சாவூர்", "தஞ்சை"]},
    "திருச்சிராப்பள்ளி": {"district": "திருச்சிராப்பள்ளி", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["திருச்சிராப்பள்ளி", "திருச்சி", "திரிசிரபுரம்"]},
    "சேலம்": {"district": "சேலம்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["சேலம்", "சைலம்"]},
    "ஈரோடு": {"district": "ஈரோடு", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["ஈரோடு"]},
    "திருப்பூர்": {"district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["திருப்பூர்"]},
    "திண்டுக்கல்": {"district": "திண்டுக்கல்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["திண்டுக்கல்"]},
    "கன்னியாகுமரி": {"district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு", "variants": ["கன்னியாகுமரி", "குமரி"]},
    "தூத்துக்குடி": {"district": "தூத்துக்குடி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["தூத்துக்குடி", "முத்துநகர்", "டுட்டிகொரின்"]},
    "தென்காசி": {"district": "தென்காசி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["தென்காசி"]},
    "சிவகங்கை": {"district": "சிவகங்கை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["சிவகங்கை", "சிவகங்கைச் சீமை"]},
    "இராமநாதபுரம்": {"district": "இராமநாதபுரம்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["இராமநாதபுரம்", "ராமநாதபுரம்", "முகவை"]},
    "விருதுநகர்": {"district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["விருதுநகர்", "விருதுபட்டி"]},
    "தேனி": {"district": "தேனி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["தேனி"]},
    "கரூர்": {"district": "கரூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["கரூர்", "கருவூர்"]},
    "நாமக்கல்": {"district": "நாமக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["நாமக்கல்"]},
    "நீலகிரி": {"district": "நீலகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["நீலகிரி", "உதகை", "ஊட்டி"]},
    "தருமபுரி": {"district": "தருமபுரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["தருமபுரி", "தர்மபுரி", "தகடூர்"]},
    "கிருஷ்ணகிரி": {"district": "கிருஷ்ணகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["கிருஷ்ணகிரி"]},
    "வேலூர்": {"district": "வேலூர்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["வேலூர்"]},
    "திருப்பத்தூர்": {"district": "திருப்பத்தூர்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["திருப்பத்தூர்"]},
    "ராணிப்பேட்டை": {"district": "ராணிப்பேட்டை", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["ராணிப்பேட்டை"]},
    "திருவண்ணாமலை": {"district": "திருவண்ணாமலை", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["திருவண்ணாமலை", "அண்ணாமலை"]},
    "காஞ்சிபுரம்": {"district": "காஞ்சிபுரம்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["காஞ்சிபுரம்", "காஞ்சி"]},
    "செங்கல்பட்டு": {"district": "செங்கல்பட்டு", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["செங்கல்பட்டு"]},
    "திருவள்ளூர்": {"district": "திருவள்ளூர்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["திருவள்ளூர்"]},
    "விழுப்புரம்": {"district": "விழுப்புரம்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு", "variants": ["விழுப்புரம்"]},
    "கள்ளக்குறிச்சி": {"district": "கள்ளக்குறிச்சி", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு", "variants": ["கள்ளக்குறிச்சி"]},
    "கடலூர்": {"district": "கடலூர்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு", "variants": ["கடலூர்"]},
    "நாகப்பட்டினம்": {"district": "நாகப்பட்டினம்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["நாகப்பட்டினம்", "நாகை"]},
    "மயிலாடுதுறை": {"district": "மயிலாடுதுறை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["மயிலாடுதுறை", "மாயவரம்"]},
    "திருவாரூர்": {"district": "திருவாரூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["திருவாரூர்", "ஆரூர்"]},
    "புதுக்கோட்டை": {"district": "புதுக்கோட்டை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["புதுக்கோட்டை"]},
    "அரியலூர்": {"district": "அரியலூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["அரியலூர்"]},
    "பெரம்பலூர்": {"district": "பெரம்பலூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["பெரம்பலூர்"]}
}

# Major Tamil Nadu Towns, Taluks, Pilgrimage sites, and Villages
TN_LOCALITIES = {
    # Kongu
    "பொள்ளாச்சி": {"town": "பொள்ளாச்சி", "district": "கோயம்புத்தூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "ஆனைமலை": {"town": "ஆனைமலை", "district": "கோயம்புத்தூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "மேட்டுப்பாளையம்": {"town": "மேட்டுப்பாளையம்", "district": "கோயம்புத்தூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "பவானி": {"town": "பவானி", "district": "ஈரோடு", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "அந்தியூர்": {"town": "அந்தியூர்", "district": "ஈரோடு", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "கோபிசெட்டிபாளையம்": {"town": "கோபிசெட்டிபாளையம்", "district": "ஈரோடு", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["கோபி"]},
    "பழனி": {"town": "பழனி", "district": "திண்டுக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "கொடைக்கானல்": {"town": "கொடைக்கானல்", "district": "திண்டுக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["கொடை"]},
    "தாராபுரம்": {"town": "தாராபுரம்", "district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "காங்கேயம்": {"town": "காங்கேயம்", "district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "உடுமலைப்பேட்டை": {"town": "உடுமலைப்பேட்டை", "district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு", "variants": ["உடுமலை"]},
    "அவினாசி": {"town": "அவினாசி", "district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "பல்லடம்": {"town": "பல்லடம்", "district": "திருப்பூர்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "மேட்டூர்": {"town": "மேட்டூர்", "district": "சேலம்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "எடப்பாடி": {"town": "எடப்பாடி", "district": "சேலம்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "ஆத்தூர்": {"town": "ஆத்தூர்", "district": "சேலம்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "திருச்செங்கோடு": {"town": "திருச்செங்கோடு", "district": "நாமக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "குமாரபாளையம்": {"town": "குமாரபாளையம்", "district": "நாமக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "ராசிபுரம்": {"town": "ராசிபுரம்", "district": "நாமக்கல்", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "குன்னூர்": {"town": "குன்னூர்", "district": "நீலகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "கோத்தகிரி": {"town": "கோத்தகிரி", "district": "நீலகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "கூடலூர்": {"town": "கூடலூர்", "district": "நீலகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "ஓசூர்": {"town": "ஓசூர்", "district": "கிருஷ்ணகிரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},
    "அரூர்": {"town": "அரூர்", "district": "தருமபுரி", "region": TAMIL_REGIONS["KONGU"], "state": "தமிழ்நாடு"},

    # Pandya
    "அழகர்கோவில்": {"town": "அழகர்கோவில்", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "திருப்பரங்குன்றம்": {"town": "திருப்பரங்குன்றம்", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "சோழவந்தான்": {"town": "சோழவந்தான்", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "மேலூர்": {"town": "மேலூர்", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "உசிலம்பட்டி": {"town": "உசிலம்பட்டி", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "வாடிப்பட்டி": {"town": "வாடிப்பட்டி", "district": "மதுரை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "சாத்தூர்": {"town": "சாத்தூர்", "district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "சிவகாசி": {"town": "சிவகாசி", "district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "அருப்புக்கோட்டை": {"town": "அருப்புக்கோட்டை", "district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "ராஜபாளையம்": {"town": "ராஜபாளையம்", "district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "ஸ்ரீவில்லிபுத்தூர்": {"town": "ஸ்ரீவில்லிபுத்தூர்", "district": "விருதுநகர்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "கோவில்பட்டி": {"town": "கோவில்பட்டி", "district": "தூத்துக்குடி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "திருச்செந்தூர்": {"town": "திருச்செந்தூர்", "district": "தூத்துக்குடி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "உடன்குடி": {"town": "உடன்குடி", "district": "தூத்துக்குடி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "குற்றாலம்": {"town": "குற்றாலம்", "district": "தென்காசி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "சங்கரன்கோவில்": {"town": "சங்கரன்கோவில்", "district": "தென்காசி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "அம்பாசமுத்திரம்": {"town": "அம்பாசமுத்திரம்", "district": "திருநெல்வேலி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "பாபநாசம்": {"town": "பாபநாசம்", "district": "திருநெல்வேலி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "காரைக்குடி": {"town": "காரைக்குடி", "district": "சிவகங்கை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "தேவகோட்டை": {"town": "தேவகோட்டை", "district": "சிவகங்கை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "மானாமதுரை": {"town": "மானாமதுரை", "district": "சிவகங்கை", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "பரமக்குடி": {"town": "பரமக்குடி", "district": "இராமநாதபுரம்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "இராமேஸ்வரம்": {"town": "இராமேஸ்வரம்", "district": "இராமநாதபுரம்", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["ராமேஸ்வரம்"]},
    "போடிநாயக்கனூர்": {"town": "போடிநாயக்கனூர்", "district": "தேனி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு", "variants": ["போடி"]},
    "பெரியகுளம்": {"town": "பெரியகுளம்", "district": "தேனி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},
    "கம்பம்": {"town": "கம்பம்", "district": "தேனி", "region": TAMIL_REGIONS["PANDYA"], "state": "தமிழ்நாடு"},

    # Chola / Delta
    "கும்பகோணம்": {"town": "கும்பகோணம்", "district": "தஞ்சாவூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["குடந்தை"]},
    "திருவையாறு": {"town": "திருவையாறு", "district": "தஞ்சாவூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "பட்டுக்கோட்டை": {"town": "பட்டுக்கோட்டை", "district": "தஞ்சாவூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "மன்னார்குடி": {"town": "மன்னார்குடி", "district": "திருவாரூர்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "வேதாரண்யம்": {"town": "வேதாரண்யம்", "district": "நாகப்பட்டினம்", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "சீர்காழி": {"town": "சீர்காழி", "district": "மயிலாடுதுறை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "பூம்புகார்": {"town": "பூம்புகார்", "district": "மயிலாடுதுறை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு", "variants": ["காவேரிப்பூம்பட்டினம்"]},
    "தரங்கம்பாடி": {"town": "தரங்கம்பாடி", "district": "மயிலாடுதுறை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "ஸ்ரீரங்கம்": {"town": "ஸ்ரீரங்கம்", "district": "திருச்சிராப்பள்ளி", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "மணப்பாறை": {"town": "மணப்பாறை", "district": "திருச்சிராப்பள்ளி", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},
    "அறந்தாங்கி": {"town": "அறந்தாங்கி", "district": "புதுக்கோட்டை", "region": TAMIL_REGIONS["CHOLA"], "state": "தமிழ்நாடு"},

    # Thondai & Nadu Nadu
    "மாமல்லபுரம்": {"town": "மாமல்லபுரம்", "district": "செங்கல்பட்டு", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு", "variants": ["மகாபலிபுரம்"]},
    "தாம்பரம்": {"town": "தாம்பரம்", "district": "செங்கல்பட்டு", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "மதுராந்தகம்": {"town": "மதுராந்தகம்", "district": "செங்கல்பட்டு", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "ஸ்ரீபெரும்புதூர்": {"town": "ஸ்ரீபெரும்புதூர்", "district": "காஞ்சிபுரம்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "ஆரணி": {"town": "ஆரணி", "district": "திருவண்ணாமலை", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "வந்தவாசி": {"town": "வந்தவாசி", "district": "திருவண்ணாமலை", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "ஆம்பூர்": {"town": "ஆம்பூர்", "district": "திருப்பத்தூர்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "வாணியம்பாடி": {"town": "வாணியம்பாடி", "district": "திருப்பத்தூர்", "region": TAMIL_REGIONS["THONDAI"], "state": "தமிழ்நாடு"},
    "செஞ்சி": {"town": "செஞ்சி", "district": "விழுப்புரம்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு"},
    "திண்டிவனம்": {"town": "திண்டிவனம்", "district": "விழுப்புரம்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு"},
    "சிதம்பரம்": {"town": "சிதம்பரம்", "district": "கடலூர்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு"},
    "விருத்தாசலம்": {"town": "விருத்தாசலம்", "district": "கடலூர்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு"},
    "பண்ருட்டி": {"town": "பண்ருட்டி", "district": "கடலூர்", "region": TAMIL_REGIONS["NADU_NADU"], "state": "தமிழ்நாடு"},

    # Nanjil
    "நாகர்கோவில்": {"town": "நாகர்கோவில்", "district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு"},
    "பத்மநாபபுரம்": {"town": "பத்மநாபபுரம்", "district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு"},
    "தக்கலை": {"town": "தக்கலை", "district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு"},
    "மார்த்தாண்டம்": {"town": "மார்த்தாண்டம்", "district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு"},
    "குழித்துறை": {"town": "குழித்துறை", "district": "கன்னியாகுமரி", "region": TAMIL_REGIONS["NANJIL"], "state": "தமிழ்நாடு"}
}

# Major Non-TN Interstate Locations frequently mentioned in Tamil Oral History
INTERSTATE_LOCATIONS = {
    "விஜயவாடா": {"town": "விஜயவாடா", "district": "விஜயவாடா (என்டிஆர் மாவட்டம்)", "region": "ஆந்திரப் பிரதேசம்", "state": "ஆந்திரப் பிரதேசம்", "variants": ["விஜயவாடா", "பெசவாடா"]},
    "பெங்களூரு": {"town": "பெங்களூரு", "district": "பெங்களூரு", "region": "கர்நாடகா", "state": "கர்நாடகா", "variants": ["பெங்களூரு", "பெங்களூர்", "பெங்களூரு நகரம்"]},
    "மைசூர்": {"town": "மைசூர்", "district": "மைசூர்", "region": "கர்நாடகா", "state": "கர்நாடகா", "variants": ["மைசூர்", "மைசூரு"]},
    "பாலக்காடு": {"town": "பாலக்காடு", "district": "பாலக்காடு", "region": "கேரளா", "state": "கேரளா", "variants": ["பாலக்காடு"]},
    "திருவனந்தபுரம்": {"town": "திருவனந்தபுரம்", "district": "திருவனந்தபுரம்", "region": "கேரளா", "state": "கேரளா", "variants": ["திருவனந்தபுரம்", "ட்ரிவாண்ட்ரம்"]},
    "மும்பை": {"town": "மும்பை", "district": "மும்பை", "region": "மகாராஷ்டிரா", "state": "மகாராஷ்டிரா", "variants": ["மும்பை", "பம்பாய்"]},
    "ஹைதராபாத்": {"town": "ஹைதராபாத்", "district": "ஹைதராபாத்", "region": "தெலங்கானா", "state": "தெலங்கானா", "variants": ["ஹைதராபாத்", "பாக்யநகரம்"]},
    "டெல்லி": {"town": "டெல்லி", "district": "புது தில்லி", "region": "தேசியத் தலைநகர் மண்டலம்", "state": "தில்லி", "variants": ["டெல்லி", "புது தில்லி"]},
    "கொல்கத்தா": {"town": "கொல்கத்தா", "district": "கொல்கத்தா", "region": "மேற்கு வங்கம்", "state": "மேற்கு வங்கம்", "variants": ["கொல்கத்தா", "கல்கத்தா"]}
}

# ---------------------------------------------------------------------------
# 2. Tamil Suffix & Postposition Matcher
# ---------------------------------------------------------------------------
# Suffixes that attach to place names in Tamil oral discourse
TAMIL_SUFFIX_PATTERNS = [
    r'வில்\b', r'யில்\b', r'இல்\b', r'ல்\b', r'ல\b',               # Locative (in / at)
    r'வில்\s*இருந்து', r'யில்\s*இருந்து', r'இல்\s*இருந்து',         # Ablative (from)
    r'லிருந்து\b', r'ல\s*இருந்து', r'இருந்து\b',
    r'வுக்கு\b', r'யிற்கு\b', r'விற்கு\b', r'க்கு\b', r'கு\b',     # Dative (to / toward)
    r'காரன்\b', r'காரி\b', r'காரங்க\b',                           # Inhabitant (resident of)
    r'பக்கம்\b', r'பக்கத்துல\b', r'சுற்றுவட்டாரம்\b',             # Vicinity
    r'மாவட்டம்\b', r'நகரம்\b', r'கிராமம்\b', r'ஊர்\b'             # Administrative suffix
]


def extract_sentences(text):
    """Split Tamil text into meaningful sentences while preserving punctuations."""
    cleaned = text.replace('\r', ' ').strip()
    raw_sentences = re.split(r'[\.\?\!\n]+', cleaned)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    if not sentences and cleaned:
        sentences = [cleaned]
    return sentences


def find_place_mentions(transcript):
    """
    Scans transcript for all known place names, variants, and morphological suffixes.
    Returns list of match dictionaries:
    {
        'name': canonical_name,
        'matched_token': token_in_text,
        'type': 'locality' | 'district' | 'interstate',
        'details': dict,
        'sentence': sentence,
        'sentence_index': int
    }
    """
    sentences = extract_sentences(transcript)
    all_matches = []
    seen_names_per_sentence = set()

    # Build master search list: (variant_regex, canonical_key, match_type, details)
    search_catalog = []

    # Localities
    for loc_name, details in TN_LOCALITIES.items():
        variants = [loc_name] + details.get("variants", [])
        for v in variants:
            search_catalog.append((v, loc_name, "locality", details))

    # Interstate
    for loc_name, details in INTERSTATE_LOCATIONS.items():
        variants = [loc_name] + details.get("variants", [])
        for v in variants:
            search_catalog.append((v, loc_name, "interstate", details))

    # Districts
    for dist_name, details in TN_DISTRICTS.items():
        variants = details.get("variants", [dist_name])
        for v in variants:
            search_catalog.append((v, dist_name, "district", details))

    # Suffixes regex alternation
    suffix_regex = r'(?:' + '|'.join(TAMIL_SUFFIX_PATTERNS) + r')?'

    for s_idx, sentence in enumerate(sentences):
        for pattern_text, canonical_name, match_type, details in search_catalog:
            # Pattern matching with Tamil word boundary / morphological suffix
            p = re.compile(rf'(?:\b|\s|^)({re.escape(pattern_text)}{suffix_regex})(?:\b|\s|[,\.\?!]|$)', re.IGNORECASE)
            match = p.search(sentence)
            if match:
                matched_token = match.group(1).strip()
                match_key = (s_idx, canonical_name)
                if match_key not in seen_names_per_sentence:
                    seen_names_per_sentence.add(match_key)
                    all_matches.append({
                        "name": canonical_name,
                        "matched_token": matched_token,
                        "type": match_type,
                        "details": details,
                        "sentence": sentence,
                        "sentence_index": s_idx
                    })

    return all_matches


# ---------------------------------------------------------------------------
# 3. Contextual Role Disambiguation (Residence vs Setting vs Destination)
# ---------------------------------------------------------------------------
def classify_location_roles(matches):
    """
    Disambiguates multiple location mentions into:
    - Storyteller's Origin / Residence (சொந்த ஊர் / பூர்வீகம்)
    - Destination / Work Migration (வந்த இடம் / பணி இடம்)
    - Story Setting (களம் / திருவிழா / நிகழ்விடம்)
    - General Mention (குறிப்பிடப்பட்ட இடம்)
    """
    residence_markers = [
        r'(?:என்\s*பெயர்|என்\s*பேரு|நான்|நாங்க|எங்க\s*குடும்பம்)',
        r'(?:எங்க\s*ஊரு|எங்கள்\s*ஊர்|சொந்த\s*ஊர்|பூர்வீகம்|பூர்வீக\s*ஊர்)',
        r'(?:பிறந்து|வளர்ந்து|பிறந்தது|வாழ்கிறேன்|வசிக்கிறேன்)',
        r'(?:காரன்|காரி|காரங்க)'
    ]
    
    origin_ablative_markers = [
        r'(?:இல்\s*இருந்து|லிருந்து|ல\s*இருந்து|இருந்து)'
    ]

    destination_markers = [
        r'(?:க்கு\s*ஒரு\s*வேலை|க்கு\s*வேலை|க்கு\s*வந்தேன்|க்கு\s*சென்றேன்|க்கு\s*போனேன்)',
        r'(?:க்கு\s*இடம்\s*பெயர்ந்தோம்|க்கு\s*வந்து\s*இருக்கேன்|க்கு\s*குடியேறினோம்)'
    ]

    setting_markers = [
        r'(?:கோவில்|கோயில்|திருவிழா|சடங்கு|முளைப்பாரி|நடைபெற்றது|நடக்கும்)',
        r'(?:பக்கத்துல\s*தான்|பக்கம்\s*தான்|வாழ்ந்தாங்க|இருந்தாங்க|சம்பவம்)'
    ]

    classified = []
    for m in matches:
        sentence = m["sentence"]
        matched_token = m["matched_token"]
        role = "general_mention"
        role_desc = "குறிப்பிடப்பட்ட இடம்"
        role_priority = 10

        # Check for Storyteller Residence / Origin (e.g. "நான் விஜயவாடாவில் இருந்து")
        is_from_origin = any(re.search(re.escape(matched_token) + r'.*?' + om, sentence) or
                            re.search(om, matched_token) for om in origin_ablative_markers)
        has_self_ref = any(re.search(rm, sentence) for rm in residence_markers)

        if is_from_origin and has_self_ref:
            role = "storyteller_residence"
            role_desc = "கதைசொல்லியின் பூர்வீகம் / சொந்த இடம்"
            role_priority = 100
        elif has_self_ref and ("பிறந்து" in sentence or "சொந்த" in sentence or "பூர்வீகம்" in sentence):
            role = "storyteller_residence"
            role_desc = "கதைசொல்லியின் பூர்வீகம்"
            role_priority = 90
        elif any(re.search(dm, sentence) for dm in destination_markers):
            role = "destination_or_work"
            role_desc = "பணி இடம் / இடம் பெயர்ந்த பகுதி"
            role_priority = 70
        elif any(re.search(sm, sentence) for sm in setting_markers):
            role = "story_setting"
            role_desc = "கதை நிகழ்ந்த களம் / வரலாற்று நிகழ்விடம்"
            role_priority = 80

        classified.append({
            **m,
            "role": role,
            "role_desc": role_desc,
            "role_priority": role_priority
        })

    # Sort matches by priority descending, then occurrence order
    classified.sort(key=lambda x: (-x["role_priority"], x["sentence_index"]))
    return classified


# ---------------------------------------------------------------------------
# 4. Contextual Dialect Inferences (When no explicit place name exists)
# ---------------------------------------------------------------------------
DIALECT_CLUSTERS = {
    "KONGU": {
        "region": TAMIL_REGIONS["KONGU"],
        "state": "தமிழ்நாடு",
        "district": "கொங்கு மண்டலம் (கோவை/ஈரோடு/திருப்பூர்/சேலம்)",
        "markers": ["ஏனுங்க", "சொல்லுங்க", "போனுங்க", "வருவாங்கோ", "செரிங்க", "அம்பிடுது", "கெழக்கு", "வக்கணையாய்", "முளைப்பாரி", "கழனி", "சோளக்காடு", "குப்பறை", "பில்லு", "கோயம்புத்தூர்", "பொள்ளாச்சி"]
    },
    "NELLAI": {
        "region": TAMIL_REGIONS["PANDYA"],
        "state": "தமிழ்நாடு",
        "district": "திருநெல்வேலி / தென்காசி பகுதி (பாண்டி நாடு)",
        "markers": ["மக்கா", "அண்ணாச்சி", "இம்புட்டு", "அம்புட்டு", "செத்த நேரம்", "போயி வாரேன்", "சாரல்", "எலே", "ஏல", "கம்மா", "கண்மாய்", "தாமிரபரணி", "ஊருணி"]
    },
    "MADURAI": {
        "region": TAMIL_REGIONS["PANDYA"],
        "state": "தமிழ்நாடு",
        "district": "மதுரை மற்றும் தென் மாவட்டங்கள்",
        "markers": ["வைகை", "சித்திரை திருவிழா", "மீனாட்சி", "மல்லி", "செல்லம்", "அங்கட்டு", "இங்கட்டு", "என்னத்த", "மாப்ள", "கொட்டாம்பட்டி", "மேலூர்"]
    },
    "DELTA": {
        "region": TAMIL_REGIONS["CHOLA"],
        "state": "தமிழ்நாடு",
        "district": "தஞ்சாவூர் / காவிரி டெல்டா பகுதி (சோழ நாடு)",
        "markers": ["காவிரி", "காவேரி", "குறுவை", "சம்பா", "மதகு", "கல்லணை", "வாய்க்கால்", "கொள்ளிடம்", "தஞ்சாவூரு", "குடந்தை"]
    },
    "MADRAS": {
        "region": TAMIL_REGIONS["THONDAI"],
        "state": "தமிழ்நாடு",
        "district": "சென்னை / வட மண்டலம் (தொண்டை நாடு)",
        "markers": ["கஸ்மாலம்", "நைனா", "பேஜார்", "டவுசர்", "கபால்னு", "அப்பாலிக்கா", "காசா", "குசும்பு", "மெட்ராஸ்"]
    },
    "NANJIL": {
        "region": TAMIL_REGIONS["NANJIL"],
        "state": "தமிழ்நாடு",
        "district": "நாஞ்சில் நாடு (கன்னியாகுமரி மாவட்டம்)",
        "markers": ["அண்ணாவி", "கொழுந்து", "சத்தம்", "முந்திரி", "குமரி", "குளச்சல்", "பத்மநாபபுரம்"]
    }
}


def infer_dialectal_region(transcript):
    """
    Examines transcript for distinct regional dialect markers when no explicit
    geographical names are mentioned. Detects dialect markers sensitively.
    """
    sentences = extract_sentences(transcript)
    best_candidate = None
    max_hits = 0

    for cluster_key, data in DIALECT_CLUSTERS.items():
        found_tokens = []
        supporting_sentence = ""
        for s in sentences:
            for marker in data["markers"]:
                if re.search(r'\b' + re.escape(marker) + r'\b', s, re.IGNORECASE):
                    if marker not in found_tokens:
                        found_tokens.append(marker)
                    if not supporting_sentence:
                        supporting_sentence = s

        # Sensitive detection: 1 or more tokens
        if len(found_tokens) >= 1 and len(found_tokens) > max_hits:
            max_hits = len(found_tokens)
            best_candidate = {
                "village_or_town": "வட்டார வழக்கு அடிப்படையில்",
                "district": data["district"],
                "state": data["state"],
                "region": data["region"],
                "_evidence": f"வட்டார வழக்குச் சான்று ({', '.join(found_tokens)}): '{supporting_sentence}'",
                "confidence": "high" if len(found_tokens) >= 2 else "medium",
                "identification_method": "inferred",
                "formatted_location": f"{data['district']}",
                "dialect_markers": found_tokens,
                "alternatives": []
            }

    return best_candidate


# ---------------------------------------------------------------------------
# 5. Core Identification Entrypoint
# ---------------------------------------------------------------------------
def identify_region_from_transcript(transcript):
    """
    Main function to analyze Tamil transcript and extract region metadata.
    
    Returns structured dict:
    {
        "village_or_town": str,
        "district": str,
        "state": str,
        "region": str,
        "_evidence": str,
        "confidence": "high" | "medium" | "low" | "none",
        "identification_method": "explicitly_mentioned" | "inferred" | "unknown",
        "formatted_location": str,
        "storyteller_residence": dict or None,
        "story_setting": dict or None,
        "destination_or_work": dict or None,
        "alternatives": list of dicts,
        "all_detected_locations": list of dicts
    }
    """
    if not transcript or not transcript.strip():
        return {
            "village_or_town": "unknown",
            "district": "unknown",
            "state": "unknown",
            "region": "unknown",
            "_evidence": "எழுத்தாக்க உரை காலியாக உள்ளது.",
            "confidence": "none",
            "identification_method": "unknown",
            "formatted_location": "",
            "storyteller_residence": None,
            "story_setting": None,
            "destination_or_work": None,
            "alternatives": [],
            "all_detected_locations": []
        }

    # Step A: Find all explicit mentions
    explicit_matches = find_place_mentions(transcript)

    if explicit_matches:
        classified = classify_location_roles(explicit_matches)
        primary = classified[0]

        # Extract roles
        residence = next((c for c in classified if c["role"] == "storyteller_residence"), None)
        setting = next((c for c in classified if c["role"] == "story_setting"), None)
        destination = next((c for c in classified if c["role"] == "destination_or_work"), None)

        details = primary["details"]
        village_or_town = details.get("town", details.get("district", primary["name"]))
        district = details.get("district", primary["name"])
        state = details.get("state", "தமிழ்நாடு")
        region = details.get("region", "தமிழ்நாடு")

        # Create structured alternatives if multiple distinct places were found
        unique_alternatives = []
        seen_alt_keys = set()
        for c in classified:
            c_det = c["details"]
            c_town = c_det.get("town", c_det.get("district", c["name"]))
            c_dist = c_det.get("district", c["name"])
            c_st = c_det.get("state", "தமிழ்நாடு")
            c_reg = c_det.get("region", "தமிழ்நாடு")
            alt_key = f"{c_town}_{c_dist}"
            
            # Formatted option text
            if c_town != c_dist:
                opt_label = f"{c_town}, {c_dist} ({c['role_desc']})"
            else:
                opt_label = f"{c_dist} ({c['role_desc']})"

            if alt_key not in seen_alt_keys:
                seen_alt_keys.add(alt_key)
                unique_alternatives.append({
                    "village_or_town": c_town,
                    "district": c_dist,
                    "state": c_st,
                    "region": c_reg,
                    "label": opt_label,
                    "role": c["role"],
                    "role_desc": c["role_desc"],
                    "_evidence": c["sentence"]
                })

        # Build clean formatted location string
        if residence and destination and residence["name"] != destination["name"]:
            formatted_location = f"{residence['details'].get('town', residence['name'])} (பூர்வீகம்) / {destination['details'].get('town', destination['name'])} (பணி இடம்)"
        elif village_or_town != district:
            formatted_location = f"{village_or_town}, {district} மாவட்டம்"
        else:
            formatted_location = f"{district} மாவட்டம்"

        return {
            "village_or_town": village_or_town,
            "district": district,
            "state": state,
            "region": region,
            "_evidence": primary["sentence"],
            "confidence": "high",
            "identification_method": "explicitly_mentioned",
            "formatted_location": formatted_location,
            "storyteller_residence": {
                "name": residence["name"],
                "formatted": f"{residence['details'].get('town', residence['name'])}, {residence['details'].get('district', '')}",
                "evidence": residence["sentence"]
            } if residence else None,
            "story_setting": {
                "name": setting["name"],
                "formatted": f"{setting['details'].get('town', setting['name'])}, {setting['details'].get('district', '')}",
                "evidence": setting["sentence"]
            } if setting else None,
            "destination_or_work": {
                "name": destination["name"],
                "formatted": f"{destination['details'].get('town', destination['name'])}, {destination['details'].get('district', '')}",
                "evidence": destination["sentence"]
            } if destination else None,
            "alternatives": unique_alternatives,
            "all_detected_locations": unique_alternatives
        }

    # Step B: If no explicit places, attempt contextual dialect inference
    dialect_result = infer_dialectal_region(transcript)
    if dialect_result:
        return dialect_result

    # Step C: Anti-hallucination return — Unknown location
    return {
        "village_or_town": "unknown",
        "district": "unknown",
        "state": "unknown",
        "region": "unknown",
        "_evidence": "பதிவில் குறிப்பிட்ட ஊர் அல்லது வட்டாரக் குறிப்பு எதுவும் கண்டறியப்படவில்லை.",
        "confidence": "none",
        "identification_method": "unknown",
        "formatted_location": "",
        "storyteller_residence": None,
        "story_setting": None,
        "destination_or_work": None,
        "alternatives": [],
        "all_detected_locations": []
    }


# ---------------------------------------------------------------------------
# 6. Comprehensive Metadata & Entity Extractor (Speaker, Date, Region, Topic)
# ---------------------------------------------------------------------------
TAMIL_WORD_NUMBERS = {
    "பத்து": 10, "இருபது": 20, "முப்பது": 30, "நாற்பது": 40, "ஐம்பது": 50,
    "அறுபது": 60, "அறுபத்தைந்து": 65, "எழுபது": 70, "எழுபத்திரண்டு": 72,
    "எழுபத்தைந்து": 75, "எழுபத்தெட்டு": 78, "எண்பது": 80, "எண்பத்தைந்து": 85,
    "தொண்ணூறு": 90, "நூறு": 100
}

def extract_full_metadata(transcript):
    """
    Intelligently extracts all archival metadata fields from spoken Tamil transcript:
    - Speaker / Storyteller name, age, and role
    - Geographic region / district / village
    - Mentioned dates, years, and historical timelines
    - Topic / domain classification
    - Synthesized authentic Tamil story title
    - Concise archival summary / description
    """
    from datetime import datetime

    if not transcript or not transcript.strip():
        return {
            "storyteller": "",
            "region": "",
            "topic": "வாய்மொழி வரலாறு",
            "date": datetime.now().strftime('%Y-%m-%d'),
            "timeline": "",
            "title": "",
            "description": "",
            "location_details": None
        }

    # 1. Geographic Location Analysis
    loc_info = identify_region_from_transcript(transcript)
    formatted_region = ""
    if loc_info and loc_info.get("identification_method") != "unknown":
        if loc_info.get("formatted_location"):
            formatted_region = loc_info["formatted_location"]
        elif loc_info.get("district") and loc_info.get("district") != "unknown":
            cultural = loc_info.get("region", "")
            formatted_region = f"{loc_info['district']} ({cultural})" if cultural else loc_info['district']

    # Fallback regional landscape analysis if no explicit place or dialect was found
    if not formatted_region:
        if re.search(r'(காவிரி|காவேரி|டெல்டா|சம்பா|குறுவை|வாய்க்கால்|மதகு|கொள்ளிடம்)', transcript):
            formatted_region = "காவிரி டெல்டா பகுதி (சோழ நாடு)"
        elif re.search(r'(வைகை|தாமிரபரணி|கரிசல்|கண்மாய்|ஊருணி|சாரல்|தென்)', transcript):
            formatted_region = "தென் மண்டலம் (பாண்டி நாடு)"
        elif re.search(r'(பொள்ளாச்சி|கோவை|பில்லு|சோளக்காடு|குப்பறை|கழனி|கொங்கு)', transcript):
            formatted_region = "கொங்கு மண்டலம் (மேற்கு தமிழ்நாடு)"
        elif re.search(r'(பாலாறு|காஞ்சி|தொண்டை|சென்னை|வட)', transcript):
            formatted_region = "தொண்டை மண்டலம் (வட தமிழ்நாடு)"
        elif re.search(r'(ஆடு|மாடு|காடு|வயல்|மலை|தோட்டம்|கிராமம்|ஊரு)', transcript):
            formatted_region = "தமிழ்நாடு (பாரம்பரிய கிராமப்புறப் பகுதி)"
        else:
            formatted_region = "தமிழ்நாடு (மரபுப் பகுதி)"

    # 2. Speaker Extraction (Name, Age, and Persona)
    speaker_name = ""
    speaker_age = ""

    # Name patterns in conversational Tamil
    name_patterns = [
        r'(?:என்\s+(?:பெயர்|பேரு|பேர்)\s*(?:வந்து|ஆகும்)?\s*[:=]?\s*)([஀-௿A-Za-z\s]+?)(?:\.|\,|\;|\s+எனக்கு|\s+நான்|\s+வயசு|\s+வயது|\s+ஊரு|\s+ஊர்|\s+பிறந்தது|\s*$)',
        r'(?:நான்\s+வந்து\s*)([஀-௿A-Za-z\s]+?)(?:\s+பேசுறேன்|\s+பேசுகிறேன்|\s+ஆகும்)',
        r'(?:பேசுவது|கூறுவது|சொல்வது)\s*([஀-௿A-Za-z\s]+?)(?:\.|\,|\;|\s*$)',
        r'(?:என்னை\s+அனைவரும்\s*)([஀-௿A-Za-z\s]+?)(?:\s+என்று\s+கூப்பிடுவார்கள்|\s+என்பார்கள்)'
    ]
    for pat in name_patterns:
        m = re.search(pat, transcript)
        if m:
            cand = m.group(1).strip()
            cand = re.sub(r'^(வந்து|ஒரு|நான்)\s+', '', cand).strip()
            if cand and 1 < len(cand) < 40:
                speaker_name = cand
                break

    # Age extraction (digits or Tamil words)
    age_patterns = [
        r'(?:எனக்கு\s*)?(?:வயசு|வயது)\s*(?:வந்து|இப்போது)?\s*(\d{1,3})',
        r'(\d{1,3})\s*(?:வயசு|வயது|ஆண்டு)',
    ]
    for pat in age_patterns:
        m = re.search(pat, transcript)
        if m:
            val = int(m.group(1))
            if 10 <= val <= 120:
                speaker_age = str(val)
                break

    if not speaker_age:
        for word, val in TAMIL_WORD_NUMBERS.items():
            if re.search(rf'\b{word}\s*(?:வயசு|வயது)', transcript):
                speaker_age = str(val)
                break

    # 3. Topic Classification
    topic = "வாய்மொழி வரலாறு"
    topic_scores = {
        "பாரம்பரிய விவசாயம்": len(re.findall(r'(விவசாயம்|பயிர்|நாத்து|நெல்|கம்பு|சோளம்|உழவு|ஏர்|கிணறு|மழை|விதை|மண்|மாடு|ஏத்த|கழனி|தோட்டம்|விவசாய|பண்ணை|கதிர்)', transcript)),
        "நாட்டுப்புறக் கதைகள்": len(re.findall(r'(கதை|ராஜா|ராணி|அரசன்|மந்திரி|காடு|சிங்கம்|பாட்டி|மாய|மந்திர|பூதம்|பேய்கதை|சொக்கட்டான்|நாட்டுப்புற|கதையா)', transcript)),
        "சித்த மருத்துவம்": len(re.findall(r'(மருந்து|கசாயம்|இலை|வேர்|மூலிகை|மருத்துவம்|நாடி|நோய்|பத்தியம்|சூரணம்|தைலம்|வேப்பிலை|துளசி|கைமருந்து|குணம்|பறிச்சு)', transcript)),
        "கிராமத்துக் கலைகள்": len(re.findall(r'(பாட்டு|கூத்து|கும்மி|கரகாட்டம்|நாடகம்|தவில்|நாதஸ்வரம்|உடுக்கை|வில்லுப்பாட்டு|கொட்டு|ஆட்டம்|கலைஞர்|இசை)', transcript)),
        "பண்டைய சடங்குகள்": len(re.findall(r'(சடங்கு|திருவிழா|சாமி|பூஜை|நேர்த்திக்கடன்|குலதெய்வம்|பலி|முனியாண்டி|அம்மன்|மாரியம்மன்|காவு|பொங்கல்|பழக்கம்|வழிபாடு)', transcript)),
    }
    best_topic = max(topic_scores, key=topic_scores.get)
    if topic_scores[best_topic] > 0:
        topic = best_topic

    # Persona Fallback based on Topic and Narrator Style
    full_speaker = speaker_name
    if speaker_age:
        if full_speaker:
            full_speaker = f"{full_speaker} (வயது {speaker_age})"
        else:
            full_speaker = f"பெரியவர் (வயது {speaker_age})"
    elif not full_speaker:
        m_rel = re.search(r'\b(தாத்தா|பாட்டி|பெரியவர்|விவசாயி|வைத்தியர்|கலைஞர்)\b', transcript)
        if m_rel:
            full_speaker = f"கிராமத்து {m_rel.group(1)}"
        elif topic == "பாரம்பரிய விவசாயம்":
            full_speaker = "கிராமத்து விவசாயப் பெரியவர்"
        elif topic == "சித்த மருத்துவம்":
            full_speaker = "மரபு மூலிகை வைத்தியர்"
        elif topic == "நாட்டுப்புறக் கதைகள்":
            full_speaker = "நாட்டுப்புறக் கதைசொல்லி"
        elif topic == "கிராமத்துக் கலைகள்":
            full_speaker = "கிராமியக் கலைஞர்"
        else:
            full_speaker = "வாய்மொழி வரலாற்றுப் பெரியவர்"

    # 4. Date & Timeline Extraction
    detected_year = ""
    year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', transcript)
    if year_match:
        detected_year = year_match.group(1)

    timeline_desc = ""
    time_rel_match = re.search(r'(\d+)\s*(?:வருஷம்|வருச|வருடம்|ஆண்டு)\s*(?:முன்னாடி|முன்பு)', transcript)
    if time_rel_match:
        timeline_desc = f"{time_rel_match.group(1)} ஆண்டுகளுக்கு முன்"
    elif re.search(r'(அந்தக்\s*காலத்துல|அந்தக்\s*காலம்|அந்த\s*காலத்தில்|முன்னொரு\s*காலத்தில்|பழைய\s*காலத்தில்|சின்ன\s*வயசுல|சிறு\s*வயதில்|தாத்தா\s*காலத்துல)', transcript):
        timeline_desc = "பழைய தலைமுறைக் காலகட்டம் (அந்தக் காலம்)"
    else:
        event_match = re.search(r'(சுதந்திரம்|வெள்ளையனே|போர்|பஞ்சம்|புயல்|வெள்ளம்)\s*(?:காலத்தில்|வந்தபோது|புதுசுல)', transcript)
        if event_match:
            timeline_desc = f"{event_match.group(0)} காலகட்டம்"
        else:
            timeline_desc = "நேரடி வாய்மொழிப் பதிவு"

    # Set HTML5 Date input
    if detected_year:
        html_date = f"{detected_year}-01-01"
    elif "அந்தக் காலம்" in timeline_desc or "முன்" in timeline_desc:
        html_date = "1970-01-01"
    else:
        html_date = datetime.now().strftime('%Y-%m-%d')

    # 5. Smart Title Synthesis
    subject_core = {
        "பாரம்பரிய விவசாயம்": "பாரம்பரிய விவசாயமும் உழவு முறையும்",
        "சித்த மருத்துவம்": "பாரம்பரிய மூலிகை மற்றும் மருத்துவக் குறிப்புகள்",
        "நாட்டுப்புறக் கதைகள்": "வழிவழியாக வந்த கிராமிய நாட்டுப்புறக் கதை",
        "கிராமத்துக் கலைகள்": "கிராமியக் கலை மற்றும் இசை மரபு",
        "பண்டைய சடங்குகள்": "பாரம்பரிய வழிபாட்டு முறைகளும் சடங்குகளும்",
        "வாய்மொழி வரலாறு": "பழைய தலைமுறையின் வாய்மொழி வரலாற்று நினைவுகள்"
    }.get(topic, "வாய்மொழி வரலாற்று நினைவுகள்")

    clean_town = loc_info.get("village_or_town") if loc_info else ""
    if clean_town in ("unknown", "வட்டார வழக்கு அடிப்படையில்", ""):
        clean_town = ""

    if speaker_name and clean_town:
        title = f"{clean_town} {speaker_name} அவர்களின் {subject_core}"
    elif speaker_name:
        title = f"{speaker_name} அவர்களின் {subject_core}"
    elif clean_town:
        title = f"{clean_town} வட்டார {subject_core}"
    else:
        title = subject_core

    # 6. Description / Summary
    desc_parts = []
    if full_speaker:
        desc_parts.append(f"கூறுபவர்: {full_speaker}")
    if formatted_region:
        desc_parts.append(f"வட்டாரம்: {formatted_region}")
    if timeline_desc or detected_year:
        desc_parts.append(f"காலக்கட்டம்: {timeline_desc or detected_year}")
    desc_parts.append(f"வகை: {topic}")

    first_sentence = transcript.strip().split('.')[0].replace('\n', ' ')
    if len(first_sentence) > 90:
        first_sentence = first_sentence[:90] + "..."
    if first_sentence:
        desc_parts.append(f"குறிப்பு: {first_sentence}")

    description = " | ".join(desc_parts)

    return {
        "storyteller": full_speaker,
        "speaker_name": speaker_name,
        "speaker_age": speaker_age,
        "region": formatted_region,
        "location_details": loc_info,
        "topic": topic,
        "date": html_date,
        "detected_year": detected_year,
        "timeline": timeline_desc,
        "title": title,
        "description": description
    }
