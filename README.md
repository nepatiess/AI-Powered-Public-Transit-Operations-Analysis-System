# AI Destekli Toplu Taşıma Operasyon Analiz Sistemi

- Staj bitirme projesi kapsamında geliştirilen; toplu taşıma operasyon verilerinden araç, hat, durak ve sefer bazlı problemleri tespit eden, sonuçları REST API üzerinden sunan ve Google Gemini ile analiz/özetleme yapabilen uçtan uca bir sistemdir.

- Sistem ayrıca doğal dilde sorulan sorulardan güvenli SQL sorguları üreterek SQL Server üzerinde read-only kullanıcı ile çalıştırabilmektedir.

## Mimari

<img src="https://raw.githubusercontent.com/nepatiess/AI-Powered-Public-Transit-Operations-Analysis-System/refs/heads/main/diagrams/Project's%20Architecture.png" >

## Teknolojiler

- **Veritabanı:** SQL Server
- **SQL:** T-SQL, JOIN, CTE, Window Functions, GROUP BY, CASE, Temp Table, Stored Procedure
- **Backend:** Python, FastAPI
- **Database Connection:** pyodbc
- **Yapay Zekâ:** Google Gemini API
- **NL→SQL Validation:** SQLGlot
- **Dashboard:** Streamlit
- **Test:** pytest, FastAPI TestClient
- **Environment Management:** python-dotenv

## Proje Yapısı

<img src="https://raw.githubusercontent.com/nepatiess/AI-Powered-Public-Transit-Operations-Analysis-System/refs/heads/main/diagrams/Project%20Structure.png" width="280" align="left" alt="Project Structure" style="margin-right: 20px;">

## Veritabanı

Proje `PublicTransportDB` veritabanını kullanır.

Temel tablolar:

| Tablo | Açıklama |
|---|---|
| `Routes_` | Hat bilgileri |
| `RouteStops` | Hatların durak ve durak sırası bilgileri |
| `ValidatorTrips` | Araçların gerçekleştirdiği seferler |
| `StopPassages` | Sefer sırasında gerçekleşen durak geçişleri |
| `VehicleLocations` | Araçların GPS kayıtları |

Veriler proje kapsamında test ve analiz amacıyla oluşturulmuş sentetik verilerdir.

## SQL Çalışmaları

Proje kapsamında aşağıdaki SQL konuları uygulanmıştır:

- JOIN
- CTE
- Window Functions (`LAG`, `RANK`)
- GROUP BY
- CASE
- Temp Table
- Stored Procedure
- Index analizi
- Execution Plan analizi

SQL sorguları `Queries.sql`, index çalışmaları `Indexes.sql`, günlük anomali raporu Stored Procedure'ü ise `sp_DailyAnomalyReport.sql` içerisinde bulunmaktadır.

### Index Optimizasyonu

`VehicleLocations` tablosunda plaka ve zaman bazlı GPS sorgularını hızlandırmak amacıyla aşağıdaki yapıda covering nonclustered index kullanılmıştır:

```sql
CREATE NONCLUSTERED INDEX IX_VehicleLocations_LicensePlate_RecordedAt
ON VehicleLocations (LicensePlate, RecordedAt)
INCLUDE (Latitude, Longitude, SpeedKmh);
```

## Anomali Tespitleri

### Durak Atlama

Bir seferin geçmesi gereken duraklar `RouteStops`, gerçekleşen geçişler ise `StopPassages` üzerinden karşılaştırılır.

Beklenen bir durağın geçiş kaydı bulunmuyorsa `STOP_SKIPPED` anomalisi oluşturulur.

### Anormal Sefer Süresi

Gerçekleşen sefer süresi hattın `NormalDuration` değerinin %20 üzerinde olduğunda anormal süre olarak değerlendirilir.

Anomali tipi:

```text
ABNORMAL_DURATION
```

### GPS Kayıt Boşluğu

Aynı aracın ardışık GPS kayıtları `LAG()` Window Function kullanılarak karşılaştırılır.

İki GPS kaydı arasında 20 dakikadan fazla fark bulunması durumunda GPS problemi oluşturulur.

### GPS Sessizliği

Bir aracın son GPS kaydından itibaren 20 dakikadan fazla kayıt göndermediği durumlar ayrıca tespit edilir.

Sentetik/historical veri kullanıldığı için karşılaştırmada sistem saati yerine dataset içerisindeki en güncel `RecordedAt` değeri referans alınır.

## API Endpoint'leri

| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/routes` | Hatları listeler |
| GET | `/api/routes/{routeCode}/problems` | Hat üzerindeki anomalileri getirir |
| GET | `/api/routes/{routeCode}/summary` | Hat istatistiklerini ve AI özetini getirir |
| GET | `/api/routes/{routeCode}/ask?soru=...` | Mevcut hat/anomali verisine göre AI ile soru-cevap yapar |
| GET | `/api/vehicles/{plate}` | Araç bilgilerini ve anomalilerini getirir |
| GET | `/api/stops/{stopId}` | Durak bazlı atlanma istatistiklerini getirir |
| GET | `/api/anomalies` | Tüm anomalileri getirir |
| POST | `/api/query` | Doğal dildeki soruyu güvenli SQL sorgusuna dönüştürerek çalıştırır |

Swagger dokümantasyonu:

```text
http://127.0.0.1:8000/docs
```

## Yapay Zekâ Entegrasyonu

Google Gemini iki farklı amaçla kullanılmaktadır.

### 1. Operasyon Özeti ve Soru-Cevap

`ai_summary.py` üzerinden uygulamanın oluşturduğu structured data Gemini'ye gönderilir.

Bu yapı:

- hat özetlerinin oluşturulması,
- anomali verilerinin yorumlanması,
- hat hakkında doğal dilde soru sorulması

için kullanılır.

Bu aşamada Gemini doğrudan veritabanına erişmez.

### 2. Natural Language → SQL

`nl_sql.py`, kullanıcının doğal dilde sorduğu sorudan SQL Server sorgusu oluşturur.

Örnek soru:

```text
En fazla sefer yapan 5 aracı göster.
```

Üretilebilecek SQL:

```sql
SELECT TOP 5
    LicensePlate,
    COUNT(TripID) AS TotalTrips
FROM ValidatorTrips
GROUP BY LicensePlate
ORDER BY TotalTrips DESC;
```

SQL doğrudan çalıştırılmadan önce güvenlik katmanından geçirilir.

## NL→SQL Güvenliği

AI tarafından oluşturulan SQL'e doğrudan güvenilmez.

Aşağıdaki kontroller uygulanmaktadır:

- Sadece `SELECT` sorgularına izin verilir.
- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `MERGE`, `EXEC`, `GRANT`, `REVOKE` ve benzeri komutlar engellenir.
- Sadece allow-list içerisinde bulunan tablolar kullanılabilir.
- Sadece allow-list içerisinde bulunan kolonlar kullanılabilir.
- `SELECT *` kullanımına izin verilmez.
- Birden fazla SQL statement çalıştırılması engellenir.
- SQL, SQLGlot ile parse edilerek kontrol edilir.
- Sonuç sayısı maksimum `TOP 100` ile sınırlandırılır.
- AI daha yüksek bir `TOP` değeri üretirse maksimum `TOP 100` olacak şekilde sınırlandırılır.
- Sorgular ayrı bir read-only SQL Server kullanıcısı üzerinden çalıştırılır.
- Query timeout uygulanır.
- Çalıştırılan SQL sorguları loglanır.

### Read-only Database User

NL→SQL sorguları normal uygulama bağlantısından ayrı olarak:

```text
PublicTransportReader
```

kullanıcısıyla çalıştırılır.

Bu kullanıcı yalnızca veri okuma yetkisine sahiptir. `INSERT`, `UPDATE`, `DELETE` ve `EXECUTE` işlemleri için yetkisi bulunmamaktadır.

## SQL Logging

Doğrulanan ve çalıştırılan AI-generated SQL sorguları:

```text
logs/nl_sql.log
```

dosyasına yazılır.

## Testler

NL→SQL güvenlik katmanı pytest ile otomatik olarak test edilmektedir.

Test edilen başlıca durumlar:

- geçerli SELECT sorgusu
- `SELECT *` engelleme
- izin verilmeyen kolon
- izin verilmeyen tablo
- DELETE engelleme
- UPDATE engelleme
- multiple statement engelleme
- JOIN sorguları
- mevcut güvenli TOP değerinin korunması
- `TOP 100` üzerindeki değerlerin sınırlandırılması

Ayrıca `/api/query` endpointi FastAPI `TestClient` ile API seviyesinde test edilmektedir.

Testleri çalıştırmak için:

```bash
pytest -v
```

NL→SQL unit testlerini ayrı çalıştırmak için:

```bash
pytest test_nl_sql.py -v
```

## Kurulum

### 1. Python paketlerini yükle

```bash
pip install -r requirements.txt
```

### 2. SQL Server bağlantısını ayarla

`database.py` içerisindeki SQL Server ve database bilgilerini kendi ortamına göre düzenle.

### 3. API'yi çalıştır

```bash
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### 4. Dashboard'u çalıştır

İkinci terminalde:

```bash
streamlit run app.py
```

Dashboard:

```text
http://localhost:8501
```

## requirements.txt

Projede kullanılan Python bağımlılıkları:

```text
fastapi
uvicorn[standard]
pyodbc
python-dotenv
google-genai
streamlit
requests
sqlglot
```
