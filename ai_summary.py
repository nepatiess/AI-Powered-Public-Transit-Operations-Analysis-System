import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

load_dotenv()  # .env dosyasindaki api keyi ortam degiskenine yukler

_client = None

def _get_client() -> genai.Client:
    global _client

    if _client is None:
        _client = genai.Client()

    return _client

SISTEM_TALIMATI = (
    "Sen bir toplu tasima operasyon analiz asistanisin. Sana JSON "
    "formatinda operasyon verisi verilecek. Bu veriyi operasyon "
    "ekibinin hizlica anlayabilecegi, 2-3 cumlelik, sade bir Turkce "
    "ozete cevir. SADECE sana verilen sayilara ve bilgilere dayan, "
    "hicbir sayi veya olay uydurma. Anlamli veri yoksa bunu belirt."
)

def _uret_yeniden_deneyerek(contents: str, deneme_sayisi: int = 3) -> str:
    client = _get_client()
    son_hata = None

    for deneme in range(1, deneme_sayisi + 1):
        try:
            yanit = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=contents,
            )
            return yanit.text
        except genai_errors.ServerError as e:
            son_hata = e
            if deneme < deneme_sayisi:
                time.sleep(1.5 * deneme)  # 1.5sn, 3sn... artan bekleme
                continue
            raise RuntimeError(
                f"Gemini şu an yoğun, {deneme_sayisi} deneme sonrası başarısız oldu. "
                f"Birkaç dakika sonra tekrar dene. (Detay: {e})"
            ) from son_hata

def ozet_uret(yapilandirilmis_veri: dict) -> str:
    client = _get_client()

    istem = f"{SISTEM_TALIMATI}\n\nBu veriyi özetle:\n{yapilandirilmis_veri}"

    return _uret_yeniden_deneyerek(istem)

def soru_yanitla(yapilandirilmis_veri: dict, soru: str) -> str:
    client = _get_client()

    istem = (
        f"{SISTEM_TALIMATI}\n\n"
        f"Elindeki veri:\n{yapilandirilmis_veri}\n\n"
        f"Operasyon ekibinden gelen soru: {soru}\n"
        f"SADECE yukaridaki veriye dayanarak cevap ver. "
        f"Veri bu soruyu yanitlamaya yetmiyorsa bunu acikca belirt, uydurma."
    )

    return _uret_yeniden_deneyerek(istem)