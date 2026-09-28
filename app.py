import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Ulasim Operasyon Analiz",
    layout="wide",
)

st.title("Ulasim Operasyon Analiz")

@st.cache_data(ttl=30)
def hatlari_getir():
    response = requests.get(
        f"{API_URL}/api/routes",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# --------------- API erişim kontrolü ---------------
try:
    hatlar = hatlari_getir()

except Exception:
    st.error(
        "API'ye ulasilamadi. FastAPI uygulamasinin calistigindan emin ol"
    )
    st.stop()

if not hatlar:
    st.warning(
        "Veritabaninda hic hat kaydi yok."
    )
    st.stop()

# --------------- Sol menü: Hat seçimi ---------------
hat_secenekleri = {
    f"{hat['RouteCode']} — {hat['RouteName']}": hat["RouteCode"]
    for hat in hatlar
}

secili_etiket = st.sidebar.selectbox(
    "Hat seç",
    list(hat_secenekleri.keys()),
)

route_code = hat_secenekleri[secili_etiket]

st.sidebar.markdown("---")

st.sidebar.caption(
    "Hat seçiniz."
)

# --------------- Hat özeti ---------------
with st.spinner("Veriler yükleniyor..."):
    try:
        response = requests.get(
            f"{API_URL}/api/routes/{route_code}/summary",
            timeout=30,
        )

    except Exception as e:
        st.error(
            f"API'ye ulasilamadi: {e}"
        )
        st.stop()

if response.status_code == 404:
    st.info(
        f"{route_code} hatti için sefer kaydi bulunamadi."
    )
    st.stop()

elif response.status_code != 200:
    try:
        detail = response.json().get(
            "detail",
            response.text,
        )

    except Exception:
        detail = response.text

    st.error(
        f"API hatası ({response.status_code}): {detail}"
    )
    st.stop()

ozet_data = response.json()

veri = ozet_data["veri"]
ozet_metni = ozet_data["ozet"]

# --------------- Problem detaylarını çek ---------------
try:
    problem_response = requests.get(
        f"{API_URL}/api/routes/{route_code}/problems",
        timeout=30,
    )
    if problem_response.status_code == 200:
        problemler = problem_response.json().get(
            "problemler",
            [],
        )
    else:
        problemler = []

except Exception:
    problemler = []

durak_atlama_sayisi = sum(
    1
    for problem in problemler
    if problem.get("tur") in {
        "DURAK_ATLAMA",
        "STOP_SKIPPED",
    }
)

# --------------- Metrikler ---------------
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Toplam Sefer",
    veri["totalTrips"],
)

col2.metric(
    "Problemli Sefer",
    veri["problemTrips"],
)

col3.metric(
    "GPS Problemi",
    veri["gpsProblems"],
)

col4.metric(
    "Atlanan Durak",
    durak_atlama_sayisi,
)

st.markdown("---")

# --------------- AI operasyon özeti ---------------
st.subheader("AI Operasyon Özeti")

st.info(
    ozet_metni
)

# --------------- Problem detayları ---------------
st.subheader("Problem Detayları")

problem_turleri = {
    "DURAK_ATLAMA": "Durak Atlama",
    "STOP_SKIPPED": "Durak Atlama",
    "ABNORMAL_DURATION": "Anormal Sefer Süresi",
    "GPS_PROBLEM": "GPS Problemi",
    "GPS_SESSIZLIK": "GPS Sessizliği",
}

if problemler:

    problem_tablosu = [
        {
            "Sefer": (
                str(problem.get("seferId"))
                if problem.get("seferId") is not None
                else "-"
            ),
            "Plaka": problem.get("plaka") or "-",
            "Tarih": problem.get("tarih") or "-",
            "Problem Türü": problem_turleri.get(
                problem.get("tur"),
                problem.get("tur") or "-",
            ),
            "Problem Detayi": problem.get("detay") or "-",
        }
        for problem in problemler
    ]

    # Problem özeti
    toplam_problem = len(problem_tablosu)

    durak_problem = sum(
        1
        for problem in problemler
        if problem.get("tur") in {
            "DURAK_ATLAMA",
            "STOP_SKIPPED",
        }
    )

    anormal_sure_problem = sum(
        1
        for problem in problemler
        if problem.get("tur") == "ABNORMAL_DURATION"
    )

    gps_problem = sum(
        1
        for problem in problemler
        if problem.get("tur") in {
            "GPS_PROBLEM",
            "GPS_SESSIZLIK",
        }
    )

    problem_col1, problem_col2, problem_col3, problem_col4 = st.columns(4)

    problem_col1.metric(
        "Toplam Problem",
        toplam_problem,
    )

    problem_col2.metric(
        "Durak Atlama",
        durak_problem,
    )

    problem_col3.metric(
        "Anormal Süre",
        anormal_sure_problem,
    )

    problem_col4.metric(
        "GPS",
        gps_problem,
    )

    st.caption(
        f"Seçilen hatta toplam {toplam_problem} problem kaydı bulundu."
    )

    # Tablo yüksekliğini kayıt sayısına göre ayarla.
    tablo_yuksekligi = min(
        700,
        max(
            250,
            40 + len(problem_tablosu) * 35,
        ),
    )

    st.dataframe(
        problem_tablosu,
        use_container_width=True,
        hide_index=True,
        height=tablo_yuksekligi,
        column_config={
            "Sefer": st.column_config.TextColumn(
                "Sefer",
                width="small",
            ),
            "Plaka": st.column_config.TextColumn(
                "Plaka",
                width="medium",
            ),
            "Tarih": st.column_config.TextColumn(
                "Tarih",
                width="medium",
            ),
            "Problem Türü": st.column_config.TextColumn(
                "Problem Türü",
                width="medium",
            ),
            "Problem Detayi": st.column_config.TextColumn(
                "Problem Detayi",
                width="large",
            ),
        },
    )

else:
    st.success(
        "Bu hatta hiç problem tespit edilmedi."
    )

st.markdown("---")

# --------------- Hat bazlı AI soru-cevap ---------------
st.subheader("AI'ya Sor")

st.caption(
    "Yalnizca yan tarafta secilen hattin uygulama tarafindan "
    "hazirlanmiş anomali ve operasyon verilerine dayanarak "
    "cevap verir. Tüm veritabanina doğal dilde soru sormak "
    "için aşağidaki 'Veriye Sor' bölümünü kullanabilirsiniz."
)

soru = st.text_input(
    "Seçilen hat hakkinda bir soru sor:",
    placeholder=(
        "Örn: Hangi araçta daha çok problem var?"
    ),
    key="route_question",
)

if st.button(
    "Sor",
    type="primary",
    key="route_question_button",
):

    if not soru.strip():
        st.warning(
            "Lütfen bir soru gir."
        )

    else:
        with st.spinner(
            "Yanıt hazırlanıyor..."
        ):
            try:
                ask_response = requests.get(
                    f"{API_URL}/api/routes/{route_code}/ask",
                    params={
                        "soru": soru,
                    },
                    timeout=60,
                )

                if ask_response.status_code == 200:
                    cevap = ask_response.json().get(
                        "cevap",
                        "Yanıt alınamadı.",
                    )

                    st.write(
                        cevap
                    )

                else:
                    try:
                        detail = ask_response.json().get(
                            "detail",
                            ask_response.text,
                        )

                    except Exception:
                        detail = ask_response.text

                    st.error(
                        f"Hata: {detail}"
                    )

            except requests.Timeout:
                st.error(
                    "İstek zaman aşımına uğradı."
                )

            except Exception as e:
                st.error(
                    f"API'ye ulaşılamadı: {e}"
                )


st.markdown("---")

# --------------- Natural Language -> SQL ---------------
st.subheader(
    "Veriye Sor — Natural Language → SQL"
)

st.caption(
    "Bu bölüm doğal dilde yazılan soruyu Gemini ile SQL'e "
    "dönüştürür. Üretilen SQL güvenlik kontrollerinden "
    "geçirilir ve read-only veritabanı kullanıcısıyla "
    "çalıştırılır."
)

nl_soru = st.text_input(
    "Veritabanına bir soru sor:",
    placeholder=(
        "Örn: En fazla sefer yapan 5 aracı göster."
    ),
    key="nl_sql_question",
)

if st.button(
    "Veriyi Sorgula",
    type="primary",
    key="nl_sql_button",
):

    if not nl_soru.strip():
        st.warning(
            "Lütfen bir soru gir."
        )

    else:
        with st.spinner(
            "SQL oluşturuluyor ve sorgu çalıştırılıyor..."
        ):
            try:
                query_response = requests.post(
                    f"{API_URL}/api/query",
                    json={
                        "soru": nl_soru,
                    },
                    timeout=60,
                )

                # --------------- Başarılı sorgu ---------------
                if query_response.status_code == 200:
                    query_data = query_response.json()

                    st.success(
                        "Sorgu başarıyla çalıştırıldı."
                    )


                    st.subheader(
                        "AI Özeti"
                    )

                    st.info(
                        query_data.get(
                            "ozet",
                            "Özet oluşturulamadı.",
                        )
                    )

                    with st.expander(
                        "Üretilen SQL"
                    ):
                        st.code(
                            query_data.get(
                                "sql",
                                "",
                            ),
                            language="sql",
                        )

                    kayit_sayisi = query_data.get(
                        "kayitSayisi",
                        0,
                    )

                    st.caption(
                        f"Dönen kayıt sayısı: "
                        f"{kayit_sayisi}"
                    )


                    sonuc = query_data.get(
                        "sonuc",
                        [],
                    )

                    if sonuc:
                        st.subheader(
                            "Sorgu Sonucu"
                        )

                        st.dataframe(
                            sonuc,
                            use_container_width=True,
                            hide_index=True,
                        )

                    else:
                        st.info(
                            "Sorgu başarıyla çalıştı ancak "
                            "kayıt bulunamadı."
                        )


                # --------------- Validator tarafından engellenen sorgu ---------------
                elif query_response.status_code == 400:

                    try:
                        detail = query_response.json().get(
                            "detail",
                            "SQL güvenlik kontrolünden geçemedi.",
                        )

                    except Exception:
                        detail = query_response.text


                    st.warning(
                        "Sorgu güvenlik kontrolü tarafından "
                        f"engellendi: {detail}"
                    )


                # --------------- Request validation hatası ---------------
                elif query_response.status_code == 422:

                    try:
                        detail = query_response.json().get(
                            "detail",
                            "Girilen soru geçerli değil.",
                        )

                    except Exception:
                        detail = (
                            "Girilen soru geçerli değil."
                        )


                    st.warning(
                        f"Girilen soru geçerli değil: {detail}"
                    )

                # --------------- Diğer API hataları ---------------
                else:

                    try:
                        detail = query_response.json().get(
                            "detail",
                            query_response.text,
                        )

                    except Exception:
                        detail = query_response.text


                    st.error(
                        f"API hatası "
                        f"({query_response.status_code}): "
                        f"{detail}"
                    )

            # --------------- İstek zaman aşımına uğradı ---------------
            except requests.Timeout:
                st.error(
                    "İstek zaman aşımına uğradı."
                )

            except requests.ConnectionError:
                st.error(
                    "API'ye bağlanılamadı. "
                    "FastAPI uygulamasının çalıştığından "
                    "emin ol."
                )

            except Exception as e:
                st.error(
                    f"API'ye ulaşılamadı: {e}"
                )