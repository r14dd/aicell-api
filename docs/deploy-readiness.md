# Deploya hazırlıq yoxlaması

Yoxlama tarixi: 9 oktyabr 2026. Branch: `white-collar` (`dev` ilə eyni kod + bu yoxlamada edilən 3 düzəliş).

**Hökm.** Kod demo kimi deploya hazırdır: təmiz volume ilə stack səhvsiz qalxır, testlər və kənardan yoxlama (`smoke.py`) yaşıldır, real sorğularla yoxlamada server xətası, məlumat sızması və ya pulun iki dəfə tutulması tapılmadı. Serverə çıxmazdan əvvəl bircə şey mütləq dəyişməlidir: **admin şifrəsi** (`SEED_STAFF_PASSWORD`, indi `aicell-demo`). Giriş (OTP) hələ yazılmayıb; qərara görə tətbiq serverdə `DEMO_AUTH=true` ilə demo abunəçi kimi işləyəcək.

## Qəbul edilmiş qərarlar (9 oktyabr)

| Məsələ | Qərar | Nəticəsi |
|---|---|---|
| `DEMO_AUTH` | `true` qalır | `Authorization` başlığı olmayan hər sorğu demo abunəçi (`994516643342`) kimi işləyir. Serverin ünvanını bilən hər kəs onun balansını xərcləyə və tarifini dəyişə bilər; bu, demo üçün qəbul olunub |
| Baza | SQLite qalır | Bir fayl, `data` volume-unda. Ehtiyat nüsxə əl ilə (əmr aşağıdadır) |
| Demo abunəçilər və simulyasiya olunan ödənişlər | Qalır | İstənilən abunəçi real ödəniş olmadan balansını artıra bilir (`GOOGLE_PAY_SIMULATED=true`, kart və akart artımı heç bir ödəniş sisteminə getmir) |

Bu konfiqurasiya (SQLite, `DEBUG=false`, `DEMO_AUTH=true`, simulyasiya olunan ödəniş) qərardan sonra təmiz stack-də yenidən yoxlandı:

- effektiv ayarlar konteynerdə oxundu: `DEBUG False | DEMO_AUTH True | DB sqlite3 /app/data/db.sqlite3 | GPAY_SIM True`;
- tokensiz axın: `GET users/me/` → demo abunəçi; kartla 10.00 və Google Pay (`simulated`) ilə 5.00 artım → `201`; sonra `POST tariffs/my/renew/` → `201` (əvvəl balans çatmırdı); `GET insights/` → `social_heavy`;
- `smoke.py` (tokenlə) → `All good.`; 32 qeyri-adi sorğudan heç biri `5xx` vermədi; başqasının id-ləri `404`;
- paralel pul sorğuları SQLite-da: 5.00 balansa 12 alış → 5 × `201`, 7 × `402`, balans `0.00`; eyni açarla 8 artım → balans bir dəfə artdı.

Bu sənəddə "yoxlandı" yazılan hər şey 9 oktyabrda lokal maşında, ayrıca qaldırılmış təmiz stack üzərində (`docker compose -p aicell-audit`, port 8030) yoxlanıb. Real serverdə, TLS arxasında və real domen ilə **heç nə yoxlanmayıb**.

## Kontekstdən fərqli çıxanlar

Tapşırıqda yazılanlarla repodakı vəziyyət üç yerdə üst-üstə düşmür; deploy edən bunu bilməlidir.

| Tapşırıqda | Repoda (yoxlandı) |
|---|---|
| Stack `db` (PostgreSQL) servisi qaldırır | `docker-compose.yml`-də `db` yoxdur. Baza `data` volume-undakı bir SQLite faylıdır (`DATABASE_URL: sqlite:////app/data/db.sqlite3`). `web`, `worker`, `beat`, `redis` qalxır |
| `white-collar` → `dev` PR-ı (#5) konflikt göstərir | #5 artıq `dev`-ə merge olunub (`2e7f9cc Merge pull request #5`). `git log origin/dev..white-collar` yoxlama başlayanda boş idi |
| Lokal stack `:8010`-da qalxır | Qalxır, amma `aicell-api-db-1` adlı köhnə PostgreSQL konteyneri də işləyir (`docker ps`). O, əvvəlki compose faylından qalıb və heç nə ona qoşulmur; `docker compose up -d --remove-orphans` onu silir |

## Linklər

| Nə | Lokal | Serverdə |
|---|---|---|
| API əsası | `http://localhost:8010/api/` | `https://<domen>/api/` |
| Swagger | `http://localhost:8010/api/swagger/` | `https://<domen>/api/swagger/` |
| OpenAPI sxemi | `http://localhost:8010/api/schema/` (`?format=json`) | eyni yol |
| Admin panel | `http://localhost:8010/admin/` | `https://<domen>/admin/` |
| Canlılıq | `http://localhost:8010/api/health/` | eyni yol |
| Hazırlıq (baza, Redis, broker) | `http://localhost:8010/api/health/ready/` | eyni yol |
| İstifadə statistikası (admin) | `http://localhost:8010/admin/usage/dailyusage/statistics/` | eyni yol |

Serverdə dəyişən yalnız sxem və host hissəsidir (`http://localhost:8010` → `https://<domen>`). Port `.env`-dəki `WEB_PORT` ilə təyin olunur.

**Admin hesabları** (`manage.py seed` yaradır, şifrə `SEED_STAFF_PASSWORD`, verilməsə `aicell-demo`):

| Login | Rol | Nə görür |
|---|---|---|
| `superadmin` | Superadmin | hər şey |
| `content` | Content manager | kataloq və bildirişlər (dəyişə bilir) |
| `support` | Support | abunəçilər, istifadə, insight-lar, statistika (yalnız baxış) |
| `finance` | Finance | billing (yalnız baxış) |

Şifrə yalnız hesab **ilk dəfə yarananda** qoyulur. Yəni `SEED_STAFF_PASSWORD` ilk `up`-dan əvvəl `.env`-də olmalıdır; sonradan dəyişmək hesabların şifrəsini dəyişmir (admin paneldən dəyişmək lazımdır).

**Demo token** (30 gün etibarlı JWT):

```sh
docker compose exec -T web python manage.py demo_token                # 994516643342
docker compose exec -T web python manage.py demo_token 994501000001   # istənilən seed nömrəsi
```

Seed olunan abunəçilər: `994516643342` (demo, IsteSen, balans 16.21) və `994501000001`–`994501000004` (hər birinin 30 günlük istifadə hekayəsi var).

## Deploy addımları

Serverdə Docker və Docker Compose olmalıdır. Aşağıdakı ardıcıllıq lokalda təmiz volume ilə yoxlanıb.

```sh
git clone https://github.com/r14dd/aicell-api.git && cd aicell-api
git checkout dev                      # və ya deploy olunacaq branch (bax Açıq suallar)

cp .env.example .env
# .env-də mütləq dəyiş (aşağıdakı cədvələ bax):
#   DJANGO_SECRET_KEY, SEED_STAFF_PASSWORD, DEMO_AUTH, DJANGO_ALLOWED_HOSTS,
#   CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS, SECURE_SSL_REDIRECT, SECURE_COOKIES
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY üçün

docker compose up -d --build
```

`web` konteyneri başlayanda özü `migrate`, `collectstatic` və `seed` işlədir, sonra gunicorn qalxır. `worker` və `beat` `web` sağlam olandan sonra başlayır.

Yoxlama:

```sh
docker compose ps                                   # web və redis "healthy", worker və beat "Up"
curl -s http://localhost:8010/api/health/ready/     # {"status":"ok","components":{"database":"ok","redis":"ok","broker":"ok"}}
docker compose logs web | grep -E "Applying|static files|Catalogue|Admin accounts"
docker compose logs worker | grep "ready"           # celery@… ready.
docker compose logs beat | tail -3                  # beat: Starting...
docker compose exec -T web python manage.py check --deploy

python3 scripts/smoke.py http://localhost:8010 \
  --token "$(docker compose exec -T web python manage.py demo_token)"
```

Təmiz stack-də alınan nəticə:

- 36 miqrasiya (16 app) səhvsiz keçdi; `189 static files copied, 174 post-processed`; seed 5 abunəçi və 4 admin hesabı yaratdı.
- Worker 5 task qeyd etdi (`purge_idempotency_keys`, `detect_insights`, `expire_activations`, `refresh_insights`, `refresh_offers`), beat başladı.
- `check --deploy`: yalnız 3 xəbərdarlıq (`W008`, `W012`, `W016`), üçü də lokal `.env`-də `SECURE_SSL_REDIRECT=false` və `SECURE_COOKIES=false` olduğu üçündür. TLS arxasında ikisi `true` olanda xəbərdarlıq qalmır (`tests/test_security.py::test_deploy_check_passes_without_warnings`).
- `smoke.py`: 378 çağırış (126 endpoint × az/en), `All good.`; dörd rolun hər biri admin panelə daxil oldu, icazəsiz səhifə `403` verdi.
- Admin paneli `DEBUG=false` ilə: `/admin/`, statistika səhifəsi, insight-lar, abunəçilər, tariflər, tranzaksiyalar `200`; `/static/unfold/css/styles.css` və JS faylları `200` (WhiteNoise verir). Statistika səhifəsində iki qrafik render olunur.
- Swagger `200`, sxem xətasız qurulur: 116 yol, 127 əməliyyat.

`smoke.py` demo abunəçinin hesabına yazır (balans artırır, paket alır). Real serverdə işlətdikdən sonra demo məlumatı ilkin vəziyyətə qaytarmaq üçün: `docker compose exec -T web python manage.py seed --reset`.

**Ehtiyat nüsxə** (yoxlandı, konteynerdə işləyir; işləyən bazadan təhlükəsiz surət alır):

```sh
docker compose exec -T web python -c "
import sqlite3
src = sqlite3.connect('/app/data/db.sqlite3'); dst = sqlite3.connect('/app/data/backup.sqlite3')
src.backup(dst); dst.close()"
docker compose cp web:/app/data/backup.sqlite3 ./backup-$(date +%F).sqlite3
```

## Production üçün dəyişməli olan tənzimləmələr

`docker-compose.yml` `DJANGO_DEBUG`-u həmişə `false` edir, `.env`-də nə yazılsa da. Qalanları `.env`-dən gəlir.

| Dəyişən | `.env.example`-da | Serverdə lazım olan | Səhv qalsa nə olur |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | `change-me-to-a-long-random-string` | uzun təsadüfi sətir | JWT tokenlər və admin sessiyaları bu açarla imzalanır; açarı bilən istənilən abunəçi üçün token düzəldə bilər. Boş olsa server qalxmır |
| `SEED_STAFF_PASSWORD` | `aicell-demo` | güclü şifrə, **ilk `up`-dan əvvəl** | `superadmin / aicell-demo` ilə hər kəs admin panelə girir (şifrə README-də və bu sənəddə açıq yazılıb) |
| `DEMO_AUTH` | `true` | `true` (qərar) | `Authorization` başlığı olmayan hər sorğu demo abunəçi (`994516643342`) kimi işləyir. `false` edilsə tokensiz sorğular `401` alır və tətbiqə token paylamaq lazım olur |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | serverin domeni (və daxili ad lazımdırsa `web`) | başqa host adı ilə gələn hər sorğu `400 Bad Request` |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8010` | `https://<domen>` | admin panelə giriş və hər forma `403 CSRF verification failed` |
| `CORS_ALLOWED_ORIGINS` | boş | brauzerdən çağıran saytların origin-ləri (mobil tətbiqə lazım deyil) | boş qalsa brauzer başqa origin-dən gələn sorğuları bloklayır; mobil tətbiqə təsir etmir |
| `SECURE_SSL_REDIRECT` | `false` | TLS arxasında `true` | `false` qalsa HTTP-dən HTTPS-ə yönləndirmə və HSTS olmur. TLS olmadan `true` etsəniz hər sorğu `301` ilə işləməyən `https://`-ə gedir (health yolları istisna) |
| `SECURE_COOKIES` | `false` | TLS arxasında `true` | `false` qalsa admin sessiya kuki-si şifrələnməmiş kanalla da göndərilir. TLS olmadan `true` etsəniz admin panelə girmək olmur |
| `DEMO_ADMIN_LOGIN` | `false` | `true` (demo) | `true`: admin login səhifəsində dörd düymə (`superadmin`, `content`, `support`, `finance`) şifrəsiz daxil edir. Səhifəni açan hər kəs superadmin kimi girə bilər |
| `GOOGLE_PAY_SIMULATED` | `true` | `true` (qərar) | `true`: `payment_token: "simulated"` ilə balans artır (real ödəniş yoxdur). `false`: Google Pay endpoint-i `501` qaytarır, çünki real token yoxlaması yazılmayıb |
| `ANTHROPIC_API_KEY` | boş | Laya model ilə işləməlidirsə açar | boş: Laya açar sözlərlə cavab verir (`narrate` hər insight üçün eyni ümumi cümləni deyir). Yoxlama zamanı bu dəyişən konteynerə ötürülmürdü, düzəldildi (`21cbd68`) |
| `INSIGHTS_QUIET_HOURS` | `true` | demo gecə göstəriləcəksə `false` | `true`: 23:00–08:00 (Bakı) arasında `GET /api/insights/` boş siyahı qaytarır |
| `THROTTLE_*` | 5, 5, 30, 300 /dəq | olduğu kimi qala bilər | boş dəyər həmin limiti söndürür |
| `WEB_PORT`, `REDIS_PORT` | `8010`, `63799` | serverdə boş olan portlar | port tutulubsa konteyner qalxmır |

**Compose faylında həll olunmamış məsələlər** (hər biri deploy edənin qərarıdır):

- **TLS yoxdur.** Stack sadə HTTP verir. Qarşısına TLS bağlayan reverse proxy (nginx, Caddy, Traefik) lazımdır. Proxy `X-Forwarded-Proto: https` və orijinal `Host` başlığını ötürməlidir: server HTTPS-i bu başlıqdan tanıyır (`config/settings.py:201`) və şəkil URL-lərini `Host`-dan qurur.
- **`web` portu bütün interfeyslərə açıqdır** (`0.0.0.0:8010`, `docker ps` ilə görüldü). Proxy eyni maşındadırsa portu `127.0.0.1:8010:8000` kimi bağlamaq lazımdır; əks halda proxy-ni keçib birbaşa HTTP ilə qoşulmaq və `X-Forwarded-Proto` başlığını saxtalaşdırmaq olar. Redis artıq yalnız `127.0.0.1`-ə bağlıdır.
- **Media faylları verilmir.** API cavablarındakı şəkil ünvanları (`/media/content/…png`) `404` qaytarır (yoxlandı: `banner-akart.png` → `404`). İki səbəb var: şəkil faylları repoda yoxdur, və `DEBUG=false` olanda Django `/media/`-nı ümumiyyətlə vermir (`config/urls.py`-dəki `static()` yalnız debug-da işləyir). Fayllar `media` volume-una qoyulmalı və proxy `/media/`-nı oradan verməlidir.
- **Baza bir SQLite faylıdır.** `data` volume-u silinsə (`docker compose down -v`) bütün məlumat gedir. Avtomatik ehtiyat nüsxə yoxdur; yuxarıdakı əmri cron-a qoymaq lazımdır. Bir server, bir neçə gunicorn worker üçün kifayətdir; bir neçə serverə yayılmır.
- **Seed hər başlanğıcda işləyir.** Mövcud sətirləri dəyişmir, amma demo abunəçi və dörd test nömrəsi real serverdə də yaranır. Onları istəmirsinizsə `web`-in `command`-ından `seed`-i çıxarıb kataloqu ayrıca yükləmək lazımdır.
- **Swagger UI CDN-dən yüklənir** (`cdn.jsdelivr.net/npm/swagger-ui-dist@latest`, səhifənin HTML-ində görüldü). Sxem serverdən gəlir, amma brauzerin internetə çıxışı olmasa səhifə boş qalır; versiya da sabitlənməyib.
- **Assistentin SSE axını sinxron worker tutur.** `gunicorn --workers 3` ilə eyni anda üç axın bütün worker-ləri məşğul edir. Yük altında yoxlanmayıb.
- **Log və monitorinq yoxdur.** Loglar yalnız `docker compose logs`-dadır; xəta izləmə (Sentry və s.) qurulmayıb.

## Tapılan bug-lar

### Düzəldilənlər

Hər biri `white-collar`-da ayrı commit-dir və testi var. **Hələ push olunmayıb.**

| Ciddilik | Nə | Necə görüldü | Commit |
|---|---|---|---|
| Orta | **Laya açarı konteynerə çatmırdı.** `docker-compose.yml` yalnız sadaladığı dəyişənləri ötürür; `ANTHROPIC_API_KEY`, `LAYA_*_MODEL`, `INSIGHTS_QUIET_HOURS`, `SECURE_HSTS_SECONDS` siyahıda yox idi. `.env`-ə açar yazılsa belə Docker-də Laya həmişə açar söz rejimində qalırdı | `config/settings.py`-nin oxuduğu dəyişənləri compose faylındakılarla müqayisə etdim | `21cbd68` + `tests/test_security.py::test_compose_passes_every_setting_a_deployment_may_change` |
| Orta | **Laya modelin natamam cavabında `500` verirdi.** Model `params` açarını buraxanda `KeyError`, cavab obyekt olmayanda (`None`, sətir, siyahı) `AttributeError` | `api/laya/brain.py`-ni oxudum; düzəlişsiz 5 yeni test yıxıldı, düzəlişlə keçdi. Real modellə yoxlanmayıb (açar yoxdur) | `93f2b27` + `tests/test_laya.py` |
| Aşağı | **`smoke.py` sağlam serverdə 15 "problem" göstərirdi.** Yeni yazma endpoint-ləri (`tariffs/subscribe`, `change`, `my/redesign`, `laya/plan`, `narrate`) üçün nümunə gövdə yox idi, boş `{}` göndərib `400` alırdı | Təmiz stack-də işlətdim: `15 problem(s)`. Düzəlişdən sonra: `All good.` Gövdələr demo abunəçinin tarifini dəyişməyəcək şəkildə seçilib | `bfab6eb` |

### Düzəldilməyənlər

| Ciddilik | Nə | Niyə düzəldilmədi |
|---|---|---|
| Orta | `laya/plan` cavabında `params`-a `insight_id` əlavə olunur. Tətbiq `applyRedesign` üçün bu `params`-ı olduğu kimi `tariffs/my/redesign/`-ə `values` kimi göndərsə, `400` alır (`insight_id` naməlum sürgü sayılır). Yoxlandı: `laya/plan` → `{'task': 'applyRedesign', 'params': {…, 'insight_id': 7001}}`; həmin `params` ilə `POST tariffs/my/redesign/` → `400 {"errors":{"values":{"insight_id":["Unknown slider"]}}}` | Cavab forması `docs/api/laya.md`-dəki müqavilədir; hansı tərəfin dəyişəcəyi qərar tələb edir |
| Aşağı | Paralel pul sorğuları testləri (`tests/test_concurrency.py`) yalnız PostgreSQL-də işləyir, CI isə SQLite-dadır: bu davranış avtomatik yoxlanmır | Testləri SQLite-a köçürmək ayrı işdir. Əl ilə yoxlandı (aşağıda) |
| Aşağı | `GET /api/insights/` oxuma olsa da bazaya yazır (detektorları işlədir, `delivered_at` qoyur) | Qəsdən belədir və sənəddə yazılıb; sadəcə bilmək lazımdır |

### Yoxlanıb problem tapılmayanlar

Real sorğularla, təmiz stack üzərində:

- **Qeyri-adi giriş:** 32 sorğu (30 rəqəmli id-lər, sürgüdə nəhəng ədəd, `true`, siyahı, iç-içə obyekt, 5000 simvolluq `plan_id`, `days=abc`, `amount: "NaN"`, `"1e400"`, pozuq JSON, `text/plain` gövdə) → heç biri `5xx` vermədi; `400`, `404` və `415` qaytardılar.
- **İzolyasiya:** ikinci abunəçinin tokeni ilə birincinin insight-ı (`7001`), təklifi (`9001`) və söhbəti (`3513323`) → hamısı `404`.
- **Təkrar sorğu:** eyni `Idempotency-Key` ilə iki alış → `201`, `201`, eyni gövdə, bir dəfə tutulub. Açarsız → `400`. Açarı başqa endpoint-də işlətmək → `400`.
- **Paralel sorğu (SQLite):** 5.00 balansa eyni anda 12 dənə 1.00-lıq alış → 5 × `201`, 7 × `402`, balans `0.00`. Eyni açarla eyni anda 8 balans artımı → 8 × `201`, balans bir dəfə (2.00) artdı.
- **Dil:** `Accept-Language: az|en` → `Content-Language` eyni dil və tərcümə olunmuş mətn; `de` → `en`. `sync_locale --check`: 240 mesaj, hamısı tərcümə olunub.
- **Limit:** pul endpoint-ində dəqiqədə 30 sorğudan sonra `429`, `Retry-After: 60`.
- **Testlər:** `uv run pytest` (SQLite) → düzəlişlərdən əvvəl 1454 keçdi, sonra 1460 keçdi; hər ikisində 10 skip (PostgreSQL və Redis tələb edənlər). `ruff check` və `ruff format --check` təmiz.

Yoxlanmayanlar: PostgreSQL ilə bu branch-in son vəziyyəti, yük altında davranış, real model ilə Laya, TLS arxasında işləmə.

## Yarımçıq qalan endpoint-lər və stub-lar

126 sənədləşdirilmiş endpoint-dən 81-i işləyir, 45-i `501 not_implemented` qaytarır (`detail`-də tətbiqin göstərəcəyi bildiriş mətni üç dildə gəlir). Siyahı koddakı `Todo(...)` yerlərindən çıxarılıb (44 handler + `GET content/games/?q=` axtarışı).

| Domen | Endpoint | Tamamlanması üçün nə lazımdır |
|---|---|---|
| users | `POST otp/send/`, `POST otp/verify/`, `POST token/refresh/`, `POST logout/` | SMS provayderi, OTP saxlama və yoxlama, refresh token; **giriş bunsuz yoxdur** |
| users | `PATCH me/`, `GET`/`PATCH me/app-settings/` | profil və tətbiq ayarları üçün model |
| users | `POST devices/` | push token saxlama, FCM/APNs inteqrasiyası |
| billing | `POST top-up/voucher/` | vauçer kodlarının mənbəyi |
| billing | `GET akart/`, `POST cards/`, `DELETE cards/<id>/`, `DELETE steam/accounts/<id>/` | saxlanmış ödəniş vasitələrinin idarəsi; kart üçün ekvayer tokenizasiyası |
| billing | `GET payments/`, `POST pay/number/`, `POST pay/aztelekom/`, `POST pay/utilities/` | başqa nömrə və kommunal ödənişlər üçün provayder inteqrasiyası |
| tariffs | `POST premium/activate/` | sənəd davranışı açıqlamır; məhsul qərarı |
| packs | `GET active/` | aktiv paketlərin siyahısı (məlumat `PackActivation`-da var, yalnız endpoint yazılmayıb) |
| kredit | `POST products/<slug>/take/` | kredit vermə qaydaları və borcun yazılması |
| sim | `POST line/internet-settings/`, `POST line/close/`, `GET roaming/countries/`, `POST services/<slug>/deactivate/`, `POST esim/transfer/`, `POST esim/recover/` | operator sistemləri ilə inteqrasiya; ölkə qiymətləri üçün kataloq |
| content | `GET notifications/options/`, `GET lottery/chances/`, `GET lottery/terms/` | məzmun və lotereya məntiqi |
| content | `POST games/tournament/join/`, `GET games/tournament/rules/`, `GET games/<slug>/launch/`, `GET games/?q=` | oyun provayderi, axtarış |
| content | `POST offers/apps/<id>/subscribe/`, `POST offers/aztelekom/order/` | tərəfdaş inteqrasiyaları |
| content | `GET gift-wheel/`, `POST gift-wheel/spin/`, `GET about/`, `GET map/`, `GET stickers/`, `GET help/`, `POST problem-report/` | məzmun; xəritə üçün mağaza məlumatı |
| referral | `GET terms/`, `POST events/` | şərtlərin mətni; `events/` xidmətlər üçün webhook-dur, tətbiqə aid deyil |
| assistant | `POST feedback/` | müraciətlərin saxlanması |

**İşləyən, amma simulyasiya olan hissələr:**

| Nə | İndi nə edir | Real olması üçün |
|---|---|---|
| Kart və akart ilə balans artımı | Heç bir ödəniş sistemi çağırılmır: sorğu gələn kimi balans artır | Ekvayer inteqrasiyası |
| Google Pay | Yalnız `payment_token: "simulated"` qəbul edir (`GOOGLE_PAY_SIMULATED=true` olanda); başqa token `501` | Tokenin ekvayerdə yoxlanması (`api/billing/views.py:199`-da `TODO(acquirer)`) |
| Steam balans artımı | Balansdan çıxır, Steam-ə heç nə göndərilmir | Steam tərəfdaşı |
| Paket alışı, tarif dəyişmə və yeniləmə | Balansdan çıxır və bazada yazır; şəbəkədə heç nə aktivləşmir. Qalıqlar istifadə etdikcə azalmır | Operatorun billing sistemi |
| İstifadə məlumatı (`usage`, `insights`, statistika) | Seed ilə yazılmış sintetik sətirlərdir | Şəbəkədən CDR/DPI axını (`usage.services.record_usage` tək giriş nöqtəsidir) |
| Assistent (`assistant/`) | Açar sözlərə görə cavab verir, ingiliscə | Model əsaslı responder (`ASSISTANT_RESPONDER`) |
| Laya (`laya/`) | `ANTHROPIC_API_KEY` yoxdursa açar sözlər; `narrate` ümumi cümlə deyir | Açar; model ilə davranış yoxlanmayıb |
| SIM ayarları (rouminq, yönləndirmə, SMS) | Bazada bayraq dəyişir | Operator sistemləri |
| Şəkillər | URL qaytarılır, fayl yoxdur (`404`) | Faylların yüklənməsi və `/media/`-nın verilməsi |

Koddakı yeganə `TODO` qeydi `api/billing/views.py:199`-dadır (Google Pay tokeni).

## Mobil komanda üçün

Sənədlər (`docs/api/*.md`) real cavablarla avtomatik tutuşdurulur: `tests/test_docs_conformance.py` hər cədvəl sətrini, `tests/test_swagger.py` yazılmış nümunələri canlı cavabla müqayisə edir, `smoke.py` isə 126 endpoint-i üç dildə çağırır. Hamısı yaşıldır, yəni sənəddə `ready` yazılan işləyir, `:todo` yazılan `501` qaytarır.

**İşinizə mane olanlar:**

1. **Giriş yoxdur.** `users/otp/*` və `token/refresh/` `501` qaytarır. Serverdə `DEMO_AUTH=true` olacaq: `Authorization` başlığı göndərməyən tətbiq demo abunəçi (`994516643342`) kimi işləyir. Başqa abunəçi (məsələn `994501000001`) üçün server tərəfdə `manage.py demo_token <nömrə>` ilə 30 günlük JWT alınır; refresh yoxdur.
2. **Aktiv paketlərin siyahısı yoxdur** (`packs/active/` `501`). Aktivləşmə yalnız alış cavabında gəlir; tətbiq onu özü saxlamalıdır.
3. **Şəkillər yüklənmir.** `image` sahələri düzgün formada URL-dir, amma `404` verir. Ehtiyat şəkil nəzərdə tutun.
4. **Push yoxdur** (`users/devices/` `501`). Insight-lar yalnız tətbiq `GET insights/` çağıranda gəlir.
5. **Laya `params`-ında `insight_id`.** `laya/plan` təsdiq cavabında tapşırığın `params`-ına `insight_id` əlavə edir. `applyRedesign`-i icra edəndə onu çıxarın, yoxsa `tariffs/my/redesign/` `400` qaytarır.
6. **Insight `task` adları endpoint parametrləri ilə eyni deyil.** `changeTariff.params.plan` → `tariffs/subscribe/` `{ "plan_id" }`; `activatePack.params.plan` → `packs/social/<slug>/activate/` `{ "plan_id" }`. Tam cədvəl `docs/api/insights.md`-də.

**Bilməli olduqlarınız (yoxlandı, sənəddəki kimi işləyir):**

- **Auth:** `Authorization: Bearer <jwt>`. Səhv və ya vaxtı keçmiş token `401` (`not_authenticated` / `token_expired`). Başqasının obyekti `404`.
- **`Idempotency-Key`:** balansı dəyişən 12 `POST`-da məcburidir (UUID). Yoxdursa `400`. Eyni açarla təkrar sorğu ilk cavabı qaytarır və heç nə tutmur; şəbəkə xətasında eyni açarla təkrar göndərin. Açarı başqa endpoint-də işlətmək `400`.
- **Dil:** `Accept-Language: az | en`; tanınmayan dil `en` sayılır. Cavabda `Content-Language` gəlir.
- **Limitlər:** pul əməliyyatları dəqiqədə 30, qalan hər şey dəqiqədə 300 (abunəçi üzrə). Aşanda `429` və `Retry-After` (saniyə).
- **Pul** həmişə iki onluqlu sətirdir (`"16.21"`). Tarixlər UTC ISO 8601; `tariffs/my/` və `insights/` tarixləri Bakı vaxtı ilə (`+04:00`).
- **Insight-lar gecə gəlmir:** 23:00–08:00 (Bakı) arasında `GET insights/` boş siyahı qaytarır. Yeni `info` insight 48 saatda bir verilir.
- **Tarif əməliyyatları:** `subscribe/`, `change/`, `my/renew/` balansdan çıxır və tam yeni dövr başladır. IsteSen kataloqda yoxdur: başqa tarifə keçəndən sonra geri qayıtmaq üçün endpoint yoxdur. Demo abunəçinin balansı (16.21) IsteSen-i yeniləməyə (19.10) çatmır.
- **`my/usage/` cəmi** tarif üstəgəl aktiv internet paketləridir (5 GB paketlə `"16"` → `"21"`). Bu, sənədin "aggregation" bölməsinin yozumudur; mobil kodu ilə tutuşdurulmayıb.
- **Yer tutucu məzmun:** story səhifələri, bannerlərin çoxu, oyunlar, təkliflər və bəzi tarif xüsusiyyətləri prototip üçün yazılıb. Forma sabitdir, məzmun dəyişəcək.

## Açıq suallar

1. **Push və PR.** `white-collar`-da 3 düzəliş və bu sənəd var, hələ push olunmayıb. Push və `dev`-ə yeni PR lazımdır; yoxsa serverə düzəlişsiz kod gedər (məsələn Laya açarı konteynerə çatmaz).
2. **PR #6 (`feature/insights`) ilə nə edilir?** O, insight işini ayrıca yazıb və `dev` ilə 15 faylda həqiqi konfliktdədir (`git merge-tree origin/dev origin/feature/insights`). İki tətbiq uyğun deyil: #6 cavabı `{ "insights": […] }` açarı ilə qaytarır, `dev`-dəki `{ "results": […] }`; `evidence` sahələri, nümunə id (`9101` / `7001`) və model (#6-da abunəçi və növ üzrə bir sətir) fərqlidir. Hər ikisi merge oluna bilməz. Laya `dev`-dəki forma ilə birlikdə yoxlandı (`narrate` və `plan` cavab verir). Qərar: #6 bağlanır, yoxsa `dev`-dəki insight kodu onunla əvəz olunur.
3. **Laya `insight_id` məsələsi** (yuxarıda): `params`-dan backend çıxarır, yoxsa tətbiq süzür.
4. **TLS, media və ehtiyat nüsxə** kimin öhdəsindədir və hansı proxy işlədiləcək.
5. **Laya üçün açar** (`ANTHROPIC_API_KEY`) serverdə veriləcəkmi? Verilməsə `narrate` hər insight üçün eyni ümumi cümləni deyir.
