# Mobil inteqrasiya bələdçisi

aicell backend-inə mobil tətbiqi qoşmaq üçün lazım olan hər şey: ünvanlar, başlıqlar, formatlar, xətalar və hər endpoint-in sorğu və cavabı.

- Bütün nümunələr serverin real cavablarından götürülüb. Uzun siyahılar qısaldılıb (`// … daha N element`), uzun mətnlər `…` ilə kəsilib.
- Canlı sənəd: `/api/swagger/` (hər endpoint-i brauzerdən sınamaq olar), sxem: `/api/schema/`.
- Planlanan, amma hələ qurulmamış endpoint-lərin nəzərdə tutulan formaları: [docs/api/](api/overview.md).

## Mündəricat

1. [Tez başlanğıc](#1-tez-başlanğıc)
2. [Sorğu başlıqları](#2-sorğu-başlıqları)
3. [Cavab başlıqları](#3-cavab-başlıqları)
4. [Giriş (auth)](#4-giriş-auth)
5. [Məlumat formatları](#5-məlumat-formatları)
6. [Xətalar](#6-xətalar)
7. [Pul əməliyyatları və Idempotency-Key](#7-pul-əməliyyatları-və-idempotency-key)
8. [Limitlər (429)](#8-limitlər-429)
9. [Dil](#9-dil)
10. [Endpoint vəziyyətləri](#10-endpoint-vəziyyətləri)
11. [Məlumat modeli](#11-məlumat-modeli)
12. Domenlər: [users](#12-users) · [billing](#13-billing) · [tariffs](#14-tariffs) · [packs](#15-packs) · [kredit](#16-kredit) · [sim](#17-sim) · [content](#18-content) · [referral](#19-referral) · [assistant](#20-assistant) · [usage](#21-usage) · [insights](#22-insights)
13. [Tipik axınlar](#23-tipik-axınlar)
14. [Məlum məhdudiyyətlər](#24-məlum-məhdudiyyətlər)
15. [Bütün endpoint-lərin siyahısı](#25-bütün-endpoint-lərin-siyahısı)

---

## 1. Tez başlanğıc

| | |
|---|---|
| Baza ünvanı | `<host>/api/` — lokal Docker-də `http://localhost:8010/api/` |
| Format | Sorğu və cavab JSON, UTF-8 |
| Yolun sonu | Hər yol `/` ilə bitir. `/api/users/me` (sonda `/` olmadan) `404` qaytarır |
| Giriş | `Authorization: Bearer <token>` (bax [bölmə 4](#4-giriş-auth)) |
| Hazır hesablar | `994516643342` və `994501000001`–`994501000004`, hər biri 30 günlük istifadə tarixçəsi ilə (bax [bölmə 4](#4-giriş-auth)) |

İlk sorğu:

```sh
curl http://localhost:8010/api/users/me/ \
  -H "Authorization: Bearer <token>" \
  -H "Accept-Language: az"
```

## 2. Sorğu başlıqları

| Başlıq | Nə vaxt | Dəyər | Qeyd |
|---|---|---|---|
| `Authorization` | hər sorğuda (giriş endpoint-ləri istisna) | `Bearer <access-jwt>` | Yoxdursa və ya səhvdirsə `401` |
| `Accept-Language` | hər sorğuda | `az`, `ru` və ya `en` | Yoxdursa və ya başqa dildirsə `en` işləyir |
| `Content-Type` | gövdəsi olan sorğularda (`POST`, `PATCH`) | `application/json` | Başqa tip `415 unsupported_media_type` qaytarır |
| `Accept` | istəyə görə | `application/json` | Yalnız assistentin mesaj endpoint-ində fərq yaradır (bax [bölmə 20](#20-assistant)) |
| `Idempotency-Key` | pul köçürən 12 `POST`-da məcburi | UUID, hər cəhd üçün yeni | Bax [bölmə 7](#7-pul-əməliyyatları-və-idempotency-key) |
| `X-App-Version` | istəyə görə | məs. `5.1.0 (13557)` | `GET users/me/` cavabında `app_version` kimi geri qayıdır |
| `X-Platform` | istəyə görə | `ios`, `android`, `web` | Hələlik server oxumur; göndərmək zərər vermir |

## 3. Cavab başlıqları

| Başlıq | Mənası |
|---|---|
| `Content-Type` | `application/json`; assistent axınında `text/event-stream` |
| `Content-Language` | Cavabın yazıldığı dil: `az`, `ru` və ya `en` |
| `Vary` | `Accept-Language` daxildir: cavabı keşləyirsinizsə, dili açara daxil edin |
| `Retry-After` | Yalnız `429` cavabında: neçə saniyədən sonra təkrar cəhd etmək olar |
| `WWW-Authenticate` | Yalnız `401` cavabında: `Bearer realm="api"` |
| `Allow` | Həmin yolun qəbul etdiyi metodlar |

Sağlamlıq endpoint-ləri (`/api/health/`, `/api/health/ready/`) dil başlığına baxmır və `Content-Language` qaytarmır.

## 4. Giriş (auth)

Tətbiqdə login ekranı hələ yoxdur və `users/otp/*` endpoint-ləri qurulmayıb (`501`). İki yol var:

1. **Demo token.** Backend tərəfdə `python manage.py demo_token` (Docker-də `docker compose exec -T web python manage.py demo_token`) demo abunəçi üçün 30 günlük token çap edir. Onu `Authorization: Bearer <token>` kimi göndərin.
2. **`DEMO_AUTH` rejimi.** Serverdə `DEMO_AUTH=true` olanda `Authorization` başlığı **olmayan** hər sorğu demo abunəçi kimi işləyir. Bu rejim susmaya görə bağlıdır; açıq olub-olmadığını backend komandasından soruşun. Açıq olsa belə, başlıq göndərilibsə, o yoxlanır.

Token ilə bağlı cavablar:

| Hal | HTTP | `code` | Tətbiq nə etməlidir |
|---|---|---|---|
| Başlıq yoxdur, token səhvdir və ya abunəçi deaktivdir | 401 | `not_authenticated` | Girişə yönləndir |
| Tokenin vaxtı bitib | 401 | `token_expired` | Tokeni yenilə (hələlik: yeni demo token) |

`token/refresh/` hələ `501` qaytarır, ona görə token 30 gün etibarlıdır.

### Hazır hesablar

Beş abunəçi var; hər birinin son 30 günə aid istifadə tarixçəsi, alışları və tarifi seed ilə yaradılır.

| Nömrə | Hekayə | Tarif | Balans |
|---|---|---|---|
| `994516643342` | Demo abunəçi: orta istifadə, yarıdan çoxu Instagram; açıq şəxsi təklifi var | IsteSen | `16.21` |
| `994501000001` | YouTube-a çox baxır, 5 GB-ı üç günə bitirir, 5 əlavə paket alıb | DigiMax 5GB | `4.02` |
| `994501000002` | Yalnız zəng edir, mobil internetdən heç istifadə etməyib | DigiMax 5GB | `5.00` |
| `994501000003` | Tez-tez xaricə gedir, kiçik rouminq paketləri alır | DigiMax 10GB | `10.00` |
| `994501000004` | Tarazlı istifadə: cari tarifi ona uyğundur | DigiMax 10GB | `9.10` |

Hər nömrə üçün token: `python manage.py demo_token 994501000001`. `DEMO_AUTH` rejimi yalnız demo abunəçiyə (`994516643342`) aiddir; qalanları üçün token lazımdır.

## 5. Məlumat formatları

| Növ | Format | Nümunə | Qeyd |
|---|---|---|---|
| Pul | iki onluqlu **sətir** | `"16.21"` | Rəqəm kimi yox, sətir kimi gəlir. Valyuta həmişə AZN-dir. Çıxılan məbləğ mənfidir: `"-0.99"` |
| Tarix-vaxt | ISO 8601, UTC | `"2026-10-02T12:39:00Z"` | Tətbiq yerli vaxta özü çevirir |
| Yalnız tarix | `YYYY-MM-DD` | `"2026-10-25"` | |
| Telefon nömrəsi | `994XXXXXXXXX` | `"994516643342"` | Göstərmək üçün `display_msisdn`: `"051 664 33 42"` |
| Siyahı | `{ "results": [...] }` | | |
| Səhifələnən siyahı | `{ "results": [...], "next": "<kursor>" \| null }` | | Bax aşağıda |
| Şəkil | tam URL | `"https://<host>/media/content/banner-akart.png"` | |
| Daxili keçid | Expo Router yolu və ya `null` | `"/kredit/tamamla"` | `null` olanda keçid yoxdur |
| İdentifikator | ya tam ədəd, ya da sətir (slug) | `42`, `"unlimited-1h"` | Hər endpoint-də göstərilib |

İstisna: `GET tariffs/my/` cavabındakı ödəniş tarixləri Bakı vaxtı ilə gəlir (`"2026-10-25T08:00:00+04:00"`).

**Səhifələmə.** Dörd siyahı səhifələnir: `billing/transactions/`, `billing/top-ups/`, `content/notifications/`, `assistant/conversations/<id>/messages/`.

| Parametr | Mənası |
|---|---|
| `?limit=` | Səhifə ölçüsü, 1–200, susmaya görə 50 |
| `?cursor=` | Əvvəlki cavabdakı `next` dəyəri |

`next` `null` olanda son səhifədir. Kursoru dəyişmədən geri göndərin; içini təhlil etməyin.

## 6. Xətalar

Bütün xətalar eyni formadadır:

```json
{ "code": "insufficient_balance", "detail": "Bu paket üçün balans kifayət etmir" }
```

- **`code`** sabitdir və dildən asılı deyil: tətbiq məntiqini ona görə qurun.
- **`detail`** insan üçündür, `Accept-Language` dilində gəlir: istifadəçiyə göstərmək olar.

| HTTP | `code` | Nə vaxt | Tətbiq nə etməlidir |
|---|---|---|---|
| 400 | `validation_error` | Gövdə, query və ya başlıq səhvdir | `detail`-i göstər; `errors` varsa sahələrin yanında göstər |
| 401 | `not_authenticated` / `token_expired` | Bax [bölmə 4](#4-giriş-auth) | |
| 402 | `insufficient_balance` | Balans çatmır | Balans artırmağı təklif et |
| 403 | `forbidden` | İcazə yoxdur | |
| 404 | `not_found` | Yol və ya obyekt yoxdur (başqasının obyekti də `404` verir) | |
| 405 | `method_not_allowed` | Bu yol həmin metodu qəbul etmir | |
| 409 | `already_active` | Paket və ya xidmət artıq aktivdir | Vəziyyəti yenilə |
| 409 | `offer_closed` | Şəxsi təklif artıq qəbul, rədd edilib və ya vaxtı bitib | Təklifi ekrandan götür |
| 415 | `unsupported_media_type` | `Content-Type` `application/json` deyil | |
| 429 | `rate_limited` | Limit aşılıb | `Retry-After` qədər gözlə |
| 501 | `not_implemented` | Endpoint hələ qurulmayıb | `detail`-i bildiriş (toast) kimi göstər |

Sahə xətaları olan `400` nümunəsi (`errors` hər sahə üçün mesaj siyahısıdır, `detail` isə ilk mesajdır):

```json
{
  "code": "validation_error",
  "detail": "Enter the first 6 digits of the card",
  "errors": {
    "card_bin": ["Enter the first 6 digits of the card"],
    "amount": ["This field is required."]
  }
}
```

Biznes yoxlamasından gələn `400`-də `errors` olmur: `{ "code": "validation_error", "detail": "Unknown pack" }`.

## 7. Pul əməliyyatları və Idempotency-Key

Balansı dəyişən 12 endpoint var:

| Endpoint | Nə edir |
|---|---|
| `POST billing/top-up/card/` | Balansı kartla artırır |
| `POST billing/top-up/akart/` | Balansı akart ilə artırır |
| `POST billing/top-up/google-pay/` | Balansı Google Pay ilə artırır |
| `POST billing/steam/top-up/` | Balansdan Steam hesabına ödəyir |
| `POST packs/internet/purchase/` | İnternet paketi alır |
| `POST packs/social/<slug>/activate/` | Sosial paketi aktivləşdirir |
| `POST packs/roaming/purchase/` | Rouminq paketi alır |
| `POST sim/services/<slug>/subscribe/` | Xidmətə abunə olur |
| `POST usage/offers/<id>/accept/` | Şəxsi təklifi təklif qiymətinə alır |
| `POST tariffs/subscribe/` | Kataloq planına keçir |
| `POST tariffs/change/` | Səhifəsi olmayan tarif kartına keçir |
| `POST tariffs/my/renew/` | Cari tarifi indi yeniləyir |

Qaydalar:

- Hər birində `Idempotency-Key: <uuid>` **məcburidir**. Yoxdursa və ya UUID deyilsə: `400 validation_error`.
- Hər **istifadəçi cəhdi** üçün yeni UUID yaradın. Şəbəkə xətasında **eyni** açarla təkrar göndərin: server ilk cavabı qaytarır və ikinci dəfə pul çıxmır.
- Uğursuz cəhd (`402`, `400`, `409`) yadda saxlanmır: eyni açarla yenidən cəhd etmək olar.
- Bir açarı başqa endpoint-də işlətmək `400` verir.
- Açarlar 7 gün saxlanılır.
- Cavabların hamısında yeni `balance` var: ayrıca `balance/` sorğusuna ehtiyac yoxdur.

## 8. Limitlər (429)

| Nəyə aiddir | Susmaya görə limit | Nəyə görə sayılır |
|---|---|---|
| `users/otp/*` | dəqiqədə 5 | IP ünvanı və ayrıca telefon nömrəsi |
| Pul köçürən 9 `POST` | dəqiqədə 30 | abunəçi |
| Qalan bütün endpoint-lər | dəqiqədə 300 | abunəçi |
| Assistentə mesaj | dəqiqədə 20 | abunəçi |

Limit aşılanda cavab `429`, `code: "rate_limited"` və `Retry-After: <saniyə>` başlığı ilə gəlir. İstisna: assistentin öz limiti `Retry-After` göndərmir, bir dəqiqə gözləmək kifayətdir.

## 9. Dil

`Accept-Language` ilə dəyişənlər:

- xəta mesajları (`detail`, `errors`), uğur mesajları (`message`), `501` bildirişləri;
- kataloq mətnləri: tarif, paket, xidmət adları və təsvirləri, story-lər, bannerlər, lotereya qaydaları;
- ekran mətnləri: etiketlər (`label`), başlıqlar, düymə yazıları (`cta`), ay adları.

Dəyişməyənlər: `code`, identifikatorlar, qiymətlər, tarixlər, brend adları (`DigiMax`, `SimKredit`).

Diqqət: əməliyyat adı (`transactions[].title`) və aktivləşdirmə adı (`activation.label`) **alış anındakı dildə** bazaya yazılır və sonradan dəyişmir. Assistentin cavabları hələlik həmişə ingiliscədir.

## 10. Endpoint vəziyyətləri

| Vəziyyət | Mənası |
|---|---|
| `ready` | Tam işləyir |
| `:todo` | Yol hazırdır, amma `501 not_implemented` qaytarır. `detail`-də göstəriləcək bildiriş mətni var. Tətbiq bu yollara indidən qoşula bilər |
| `:dummy` | Assistent: başdan-sona işləyir, amma cavabı süni intellekt yox, açar sözlər verir |

126 endpoint-dən 81-i işləyir (75 `ready`, 6 `:dummy`), 45-i `:todo`-dur. `laya/` endpoint-ləri [docs/api/laya.md](api/laya.md)-də təsvir olunub. Tam siyahı [bölmə 25](#25-bütün-endpoint-lərin-siyahısı)-də.

## 11. Məlumat modeli

Hər şey abunəçiyə bağlıdır. Abunəçi yalnız öz məlumatını görür və dəyişir.

| Obyekt | Nədir | Haradan oxunur |
|---|---|---|
| Abunəçi | Nömrə, ad, xətt tipi (`prepaid` / `postpaid`), Premium olub-olmaması | `users/me/` |
| Pul kisəsi | Abunəçinin balansı | `billing/balance/` |
| Əməliyyat | Balansın hər dəyişməsi; məbləğ işarəlidir | `billing/transactions/` |
| Balans artımı | Kart, akart və ya Google Pay ilə artım | `billing/top-ups/` |
| Saxlanmış kart, Steam hesabı | | `billing/cards/`, `billing/steam/accounts/` |
| Abunəçinin tarifi | Qiymət, ödəniş tarixləri, qalan internet, dəqiqə | `tariffs/my/`, `tariffs/my/usage/` |
| Paket aktivləşdirməsi | Alınmış paket: nə vaxt başlayıb, nə vaxt bitir | alış cavabında (`activation`) |
| SIM profili | Xətt, yönləndirmə, rouminq, SMS ayarları, PUK | `sim/…` |
| Xidmət abunəliyi | Qoşulmuş ödənişli xidmət | `sim/services/` (`activated`) |
| Bildiriş | Abunəçiyə göndərilən mesaj, oxunub-oxunmaması | `content/notifications/` |
| Story baxışı | Hansı story-yə baxılıb | `content/stories/` (`viewed`) |
| Referal profili | Dəvət kodu və qazanc | `referral/me/` |
| Söhbət və mesaj | Dəstək söhbətləri | `assistant/…` |
| Gündəlik istifadə | Hər gün üçün internet (tətbiqlər üzrə), dəqiqə, SMS, rouminq | `usage/summary/` |
| Şəxsi təklif | Bir abunəçiyə xüsusi qiymətə təklif olunan paket | `usage/recommendations/` (`offer`) |

**Kataloq** (hamı üçün eynidir, admin paneldən redaktə olunur, üç dildə saxlanır): tarif ailələri və planları, internet/sosial/rouminq paketləri, kredit məhsulları, SIM xidmətləri, story-lər, bannerlər, sürətli əməllər, lotereya bölmələri, oyunlar, təkliflər, referal addımları.

Kataloq cavabları serverdə 5 dəqiqəyə qədər keşlənir; adminin dəyişikliyi keşi dərhal təmizləyir.

---

## 12. users

Baza yolu: `/api/users/`

### `GET me/` — abunəçinin profili

```jsonc
{
  "app_version": null,
  "display_msisdn": "051 664 33 42",
  "display_name": "Qüdrət Abidzadə",
  "id": 15,
  "is_premium": false,
  "language": "en",
  "line_type": "prepaid",
  "msisdn": "994516643342"
}
```

| Sahə | Tip | Mənası |
|---|---|---|
| `id` | ədəd | Abunəçinin daxili nömrəsi |
| `msisdn` | sətir | Nömrə, `994XXXXXXXXX` |
| `display_msisdn` | sətir | Göstərmək üçün formatlanmış nömrə |
| `display_name` | sətir | Ad və soyad |
| `line_type` | sətir | `prepaid` və ya `postpaid` |
| `language` | sətir | Abunəçinin dili: `az`, `ru`, `en` |
| `app_version` | sətir \| null | `X-App-Version` başlığının əksi: `"Version 5.1.0 (13557)"`. Başlıq yoxdursa `null` |
| `is_premium` | bool | Premium abunəçidirmi |

`:todo` olanlar: `POST otp/send/`, `POST otp/verify/`, `POST token/refresh/`, `POST logout/`, `PATCH me/`, `GET`/`PATCH me/app-settings/`, `POST devices/`.

---

## 13. billing

Baza yolu: `/api/billing/`

### `GET balance/` — balans

```jsonc
{ "balance": "16.21", "currency": "AZN", "month": "2026-10", "top_ups_this_month": "16.00" }
```

| Sahə | Mənası |
|---|---|
| `balance` | Cari balans |
| `currency` | Həmişə `AZN` |
| `top_ups_this_month` | Bu ay (Bakı vaxtı ilə) edilən artımların cəmi |
| `month` | Həmin ay, `YYYY-MM` |

### `GET transactions/` — əməliyyatlar (səhifələnir)

Ən yenidən köhnəyə.

```jsonc
{
  "next": null,
  "results": [
    {
      "amount": "15.00",
      "created_at": "2026-10-02T12:39:00Z",
      "id": 34,
      "kind": "top_up",
      "title": "Number balance"
    },
    {
      "amount": "1.00",
      "created_at": "2026-10-02T12:34:00Z",
      "id": 33,
      "kind": "top_up",
      "title": "Number balance"
    }
  ]
}
```

| Sahə | Mənası |
|---|---|
| `id` | ədəd |
| `kind` | `top_up` (artım), `purchase` (alış), `payment` (ödəniş), `credit` (kredit) |
| `title` | Əməliyyatın adı, yazıldığı dildə |
| `amount` | İşarəli məbləğ: artım müsbət, xərc mənfi |
| `created_at` | UTC vaxt |

### `GET top-ups/?from=&to=` — balans artımları (səhifələnir)

`from` və `to` daxil olmaqla Bakı vaxtı ilə tarixlərdir (`YYYY-MM-DD`), ikisi də istəyə görədir. Səhv tarix `400` verir.

```jsonc
{
  "next": null,
  "results": [
    { "amount": "15.00", "created_at": "2026-10-02T12:39:00Z", "id": 14, "method": "card" },
    { "amount": "1.00", "created_at": "2026-10-02T12:34:00Z", "id": 13, "method": "card" }
  ]
}
```

`method`: `card`, `akart`, `google_pay`.

### `GET top-up/methods/` — artım üsulları

```jsonc
{
  "banner": {
    "alt": "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan",
    "deep_link": "/kredit/tamamla",
    "image": "https://<host>/media/content/banner-akart.png"
  },
  "google_pay": {
    "available": true,
    "max": "500.00",
    "min": "1.00",
    "note": "We don't charge any fees for Google Pay top-ups"
  },
  "methods": [
    { "deep_link": "/top-up/card", "key": "card", "label": "Top up from bank card" },
    { "deep_link": "/top-up/akart", "key": "akart", "label": "akart" }
    // … daha 2 element
  ]
}
```

| Sahə | Mənası |
|---|---|
| `banner` | Ekranın yuxarısındakı banner: `image`, `alt` (şəkil mətni), `deep_link` |
| `methods[]` | Üsul siyahısı: `key` (`card`, `akart`, `voucher`, `kredit`), `label`, `deep_link` |
| `google_pay` | `available`, `min` və `max` məbləğ, `note` (altındakı qeyd) |

### `POST top-up/card/` — kartla artım (pul)

Sorğu:

```json
{ "card_bin": "416300", "amount": "25.00" }
```

| Sahə | Məcburi | Qayda |
|---|---|---|
| `card_bin` | bəli | Kartın ilk 6 rəqəmi |
| `amount` | bəli | `1.00`–`500.00` |

Cavab `201`:

```jsonc
{
  "balance": "41.21",
  "top_up": {
    "amount": "25.00",
    "created_at": "2026-10-09T12:24:05Z",
    "id": 15,
    "method": "card",
    "status": "completed"
  },
  "transaction": { "amount": "25.00", "id": 35, "title": "Number balance" }
}
```

| Sahə | Mənası |
|---|---|
| `top_up` | Artım qeydi: `id`, `method`, `amount`, `status` (`completed`), `created_at` |
| `transaction` | Yaranan əməliyyat: `id`, `title`, `amount` |
| `balance` | Yeni balans |

Xətalar: `400` (səhv sahə və ya açar).

### `POST top-up/akart/` — akart ilə artım (pul)

```json
{ "akart_msisdn": "994516643342", "amount": "20.00", "save": true }
```

| Sahə | Məcburi | Qayda |
|---|---|---|
| `akart_msisdn` | bəli | `994XXXXXXXXX` |
| `amount` | bəli | `1.00`–`500.00` |
| `save` | xeyr | `true` olsa, nömrə yadda saxlanılır |

Cavab kart artımı ilə eynidir, üstəgəl `saved_akart`: `save` `true` olanda `{ "id", "msisdn" }`, əks halda `null`.

```jsonc
{
  "balance": "36.21",
  "saved_akart": { "id": 1, "msisdn": "994516643342" },
  "top_up": {
    "amount": "20.00",
    "created_at": "2026-10-09T12:24:05Z",
    "id": 15,
    "method": "akart",
    "status": "completed"
  },
  "transaction": { "amount": "20.00", "id": 35, "title": "Number balance" }
}
```

### `POST top-up/google-pay/` — Google Pay ilə artım (pul)

```json
{ "amount": "20.00", "payment_token": "simulated", "card_last4": "4471" }
```

| Sahə | Məcburi | Qayda |
|---|---|---|
| `amount` | bəli | `1.00`–`500.00` |
| `payment_token` | bəli | Demo rejimində `"simulated"` |
| `card_last4` | xeyr | 4 rəqəm |

Cavab kart artımı ilə eynidir (`method: "google_pay"`). **Real Google Pay tokeni hələ qəbul edilmir**: `"simulated"`-dən başqa hər dəyər `501` qaytarır.

### `GET cards/` — saxlanmış kartlar

```jsonc
{
  "results": [
    { "brand": "mastercard", "expiry": "09/28", "id": 3, "is_default": true, "last4": "4471" }
  ]
}
```

`brand` kiçik hərflə (`mastercard`), `expiry` `MM/YY`, əsas kart (`is_default`) birinci gəlir.

### `GET steam/accounts/` — Steam hesabları

```jsonc
{
  "chips": ["5", "10", "25", "50"],
  "limits": { "max": "50.00", "min": "1.00" },
  "results": [
    {
      "id": 3,
      "last_amount": "10.00",
      "last_topped_at": "2026-10-08T09:00:00Z",
      "name": "gamer_01"
    }
  ]
}
```

| Sahə | Mənası |
|---|---|
| `results[]` | Saxlanmış hesablar: `id`, `name`, `last_amount` (son məbləğ və ya `null`), `last_topped_at` |
| `limits` | Bir ödənişin `min` və `max` məbləği |
| `chips` | Sürətli seçim düymələrinin məbləğləri |

### `POST steam/top-up/` — Steam-ə ödəniş (pul)

```json
{ "account": "gamer_01", "amount": "10.00", "save": true }
```

| Sahə | Məcburi | Qayda |
|---|---|---|
| `account` | bəli | Steam hesabının adı |
| `amount` | bəli | `1.00`–`50.00` |
| `save` | xeyr | `true` olsa, hesab yadda saxlanılır |

Cavab `201`:

```jsonc
{
  "balance": "6.21",
  "steam_top_up": { "account": "gamer_01", "amount": "10.00", "id": 1 },
  "transaction": { "amount": "-10.00", "id": 35, "title": "Steam balance gamer_01" }
}
```

Xətalar: `400` (məbləğ aralıqdan kənardır), `402` (balans çatmır).

`:todo` olanlar: `POST top-up/voucher/`, `GET akart/`, `POST cards/`, `DELETE cards/<id>/`, `GET payments/`, `POST pay/number/`, `POST pay/aztelekom/`, `POST pay/utilities/`, `DELETE steam/accounts/<id>/`.

---

## 14. tariffs

Baza yolu: `/api/tariffs/`

### `GET catalogue/` və `GET catalogue/<family>/?plan=`

Birincisi bütün ailələri `{ "results": [...] }` kimi, ikincisi bir ailəni qaytarır. `<family>`: `digimax`, `premium-plus`. `?plan=` seçilmiş planı təyin edir; verilməsə, ailənin əsas planı seçilir. Naməlum plan `400`, naməlum ailə `404`.

```jsonc
{
  "badges": ["PREPAID"],
  "cta": "Subscribe for 18.00 ₼",
  "id": "digimax",
  "is_premium": false,
  "name": "DigiMax",
  "note": "When the subscription fee of the tariff is paid, the line of the number wil…",
  "plans": [
    {
      "features": [
        { "kind": "internet", "label": "Internet", "value": "5 GB" }
        // … daha 3 element
      ],
      "hot": false,
      "id": "digimax-5",
      "price": "12.00",
      "title": "DigiMax 5GB"
    },
    {
      "features": [
        { "kind": "internet", "label": "Internet", "value": "10 GB" }
        // … daha 4 element
      ],
      "hot": true,
      "id": "digimax-10",
      "price": "18.00",
      "title": "DigiMax 10GB"
    }
    // … daha 1 element
  ],
  "selected_plan": "digimax-10",
  "subtitle": null,
  "total_price": [
    {
      "heading": "When you use all package, prices will be next:",
      "rows": [
        { "label": "Internet - 1MB", "price": "0.05" }
        // … daha 3 element
      ],
      "tone": "secondary"
    },
    {
      "heading": "If monthly fee is not paid:",
      "rows": [
        { "label": "Internet - 1MB", "price": "0.10" }
        // … daha 3 element
      ],
      "tone": "red"
    }
  ]
}
```

| Sahə | Mənası |
|---|---|
| `id` | Ailənin slug-ı |
| `name`, `subtitle` | Ad və alt başlıq (`null` ola bilər) |
| `badges` | Nişanlar, məs. `["PREPAID"]` |
| `is_premium` | Premium ailədirmi |
| `plans[]` | Planlar: `id`, `title`, `price`, `hot` (populyardırmı), `features[]` |
| `plans[].features[]` | `kind` (`internet`, `calls`, `sms`, `social`, `roaming`, `validity`), `label`, `value`, bəzən `socials` (tətbiq açarları) |
| `selected_plan` | Seçilmiş planın `id`-si |
| `total_price[]` | Qiymət cədvəli blokları: `heading`, `tone` (`secondary` və ya `red`), `rows[]` (`label`, `price`) |
| `note` | Altdakı qeyd |
| `cta` | Düymə yazısı, seçilmiş planın qiyməti ilə |

### `GET hot/` — populyar tariflər

```jsonc
{
  "results": [
    {
      "family_id": "digimax",
      "features": [
        { "kind": "data", "value": "10 GB" }
        // … daha 2 element
      ],
      "id": "digimax-10",
      "price": "18.00",
      "socials": ["whatsapp", "telegram"],
      "title": "DigiMax 10GB"
    },
    {
      "family_id": "premium-plus",
      "features": [
        { "kind": "data", "value": "60 GB" }
        // … daha 3 element
      ],
      "id": "premium-60",
      "price": "60.00",
      "socials": ["whatsapp", "telegram", "instagram", "youtube"],
      "title": "Premium+ 60GB"
    }
    // … daha 1 element
  ]
}
```

`family_id` kartın açdığı ailədir. `features[].kind` burada `data`, `minutes`, `sms`, `roaming`-dir.

### `GET change/` — tarifi dəyiş ekranı

```jsonc
{
  "results": [
    {
      "cards": [
        {
          "family_id": "digimax",
          "features": [
            { "kind": "data", "value": "5-25 GB" }
            // … daha 1 element
          ],
          "id": "digimax",
          "is_new": false,
          "period": "28 days",
          "price": "12-30",
          "socials": ["whatsapp", "telegram", "instagram"],
          "tagline": "Internet, calls and social networks in one tariff",
          "title": "DigiMax"
        }
        // … daha 1 element
      ],
      "id": "digimax",
      "title": "DigiMax"
    },
    {
      "cards": [
        {
          "family_id": "premium-plus",
          "features": [
            { "kind": "data", "value": "60-100 GB" }
            // … daha 1 element
          ],
          "id": "premium-plus",
          "is_new": false,
          "period": "30 days",
          "price": "60-90",
          "socials": ["whatsapp", "telegram", "instagram", "youtube"],
          "tagline": "Unlimited calls and a personal curator",
          "title": "Premium+"
        }
        // … daha 1 element
      ],
      "id": "premium",
      "title": "Premium"
    }
  ]
}
```

Kartda `price` aralıq ola bilər (`"12-30"`). `family_id` `null` deyilsə, kart kataloq səhifəsinə (`catalogue/<family_id>/`) aparır.

### `GET premium/`

```jsonc
{
  "benefits": [
    { "key": "curator", "text": "Personal curator for all your needs" },
    { "key": "priority", "text": "Priority service in customer care and stores" }
    // … daha 6 element
  ],
  "logo": "https://<host>/media/content/premium-logo.png",
  "note": "To access the Premium theme you must log in with Premium number as main acc…"
}
```

### `GET my/` — mənim tarifim

```jsonc
{
  "banner": {
    "alt": "All you need and more!",
    "deep_link": "/internet-packs",
    "image": "https://<host>/media/content/banner-want-more.png"
  },
  "charging_note": "Charging interval: 1 minute for calls",
  "family": "istesen",
  "lines": [
    { "label": "Current tariff", "value": "19.10 ₼/month" },
    { "label": "Next renewal", "value": "19.10 ₼/month" }
  ],
  "payment_details": [
    { "label": "Validity period", "value": "30 d." },
    { "label": "Activation date", "value": "2026-09-24T00:00:00+04:00" }
    // … daha 3 element
  ],
  "pills": ["CURRENT TARIFF", "PREPAID"],
  "renew": {
    "body": "By renewing tariff, the remaining balance will be annulled but the existing…",
    "title": "Renew tariff"
  },
  "title": "IsteSen",
  "total_price": [
    {
      "heading": "When you use all package, prices will be next:",
      "rows": [
        { "label": "Internet - 1MB", "price": "0.05" }
        // … daha 3 element
      ],
      "tone": "secondary"
    },
    {
      "heading": "If monthly fee is not paid:",
      "rows": [
        { "label": "Internet - 1MB", "price": "0.10" }
        // … daha 3 element
      ],
      "tone": "red"
    }
  ],
  "usage": [
    {
      "kind": "internet",
      "label": "Internet",
      "ratio": 0.45,
      "remaining": "7.20",
      "remaining_unit": "GB",
      "total": "16",
      "total_unit": "GB"
    },
    {
      "kind": "messaging",
      "label": "Messaging",
      "ratio": 0.98,
      "remaining": "1003",
      "remaining_unit": "MB",
      "total": "1",
      "total_unit": "GB"
    }
    // … daha 1 element
  ]
}
```

| Sahə | Mənası |
|---|---|
| `family`, `title` | Tarifin slug-ı və adı |
| `pills` | Başlıqdakı nişanlar |
| `lines[]` | "Cari tarif" və "Növbəti yenilənmə" sətirləri: `label`, `value` |
| `usage[]` | Qalıq sətirləri (aşağıda) |
| `payment_details[]` | `label` və `value` cütləri. Tarix dəyərləri `+04:00` ilə ISO formatındadır, tətbiq formatlamalıdır |
| `total_price[]` | Kataloqdakı ilə eyni forma |
| `charging_note`, `banner`, `renew` | Qeyd, banner və "tarifi yenilə" pəncərəsinin mətni |

`usage[]` sətri:

| Sahə | Mənası |
|---|---|
| `kind` | `internet`, `messaging`, `calls` |
| `label` | Etiket |
| `remaining`, `remaining_unit` | Qalan miqdar və vahidi |
| `total`, `total_unit` | Ümumi miqdar və vahidi |
| `ratio` | Qalığın payı, 0–1 arası ədəd (irəliləyiş zolağı üçün) |

### `GET my/usage/` — qalıq

```jsonc
{
  "aggregation": [
    {
      "body": "The total shows the sum of the internet in your tariff and in all of your a…",
      "title": "For internet"
    },
    {
      "body": "The total shows the sum of the local minutes in your tariff and in all of y…",
      "title": "For calls"
    }
  ],
  "period_left": { "days": 15, "hours": 15 },
  "remaining": { "data_gb": "7.20", "data_total_gb": "16", "minutes": 30, "minutes_total": 30 },
  "renewal_label": "Renews 25 October, 08:00",
  "rows": [
    {
      "kind": "internet",
      "label": "Internet",
      "ratio": 0.45,
      "remaining": "7.20",
      "remaining_unit": "GB",
      "total": "16",
      "total_unit": "GB"
    },
    {
      "kind": "messaging",
      "label": "Messaging",
      "ratio": 0.98,
      "remaining": "1003",
      "remaining_unit": "MB",
      "total": "1",
      "total_unit": "GB"
    }
    // … daha 1 element
  ],
  "tariff": "IsteSen"
}
```

| Sahə | Mənası |
|---|---|
| `tariff` | Tarifin adı |
| `renewal_label` | Hazır mətn, seçilmiş dildə |
| `period_left` | Yenilənməyə qalan `days` və `hours` |
| `remaining` | `data_gb` (sətir), `data_total_gb` (sətir), `minutes`, `minutes_total` (ədəd). İnternet rəqəmləri tarif **üstəgəl** həcmi bəlli olan aktiv internet paketləridir (izah pəncərəsindəki cəm): 5 GB paket alınanda `"7.20"`/`"16"` → `"12.20"`/`"21"` olur. Paketin nə qədərinin işləndiyi izlənmir, ona görə aktiv paket tam sayılır |
| `rows[]` | `my/` cavabındakı `usage[]` ilə eyni (yalnız tarif, paketsiz) |
| `aggregation[]` | İzah pəncərəsinin mətnləri: `title`, `body` |

### `GET my/redesign/` — tarifi yenidən qur

```jsonc
{
  "estimate": "19.10",
  "pricing": { "base": "19.10", "per_gb": "0.50", "per_minute": "0.02" },
  "sliders": [
    { "key": "internet", "label": "Internet GB", "max": 16, "min": 0, "step": 1, "value": 16 },
    { "key": "calls", "label": "Local calls min.", "max": 350, "min": 30, "step": 10, "value": 30 }
    // … daha 3 element
  ]
}
```

Sürgülər: `key`, `label`, `min`, `max`, `step`, `value` (cari dəyər). Canlı qiyməti tətbiq hesablayır:

```
estimate = base
         + per_gb     × (internet − 16 + instagramFb + youtube + tiktok)
         + per_minute × (calls − 30)
```

### `POST my/redesign/` — sürgüləri yadda saxla

```jsonc
// sorğu
{ "values": { "internet": 10, "calls": 100, "instagramFb": 5, "youtube": 2, "tiktok": 0 } }
```

Cavab `200`, forması `GET my/redesign/` ilə eynidir (yeni `value`-lar və `estimate`):

```jsonc
{
  "estimate": "21.00",
  "pricing": { "base": "19.10", "per_gb": "0.50", "per_minute": "0.02" },
  "sliders": [
    { "key": "internet", "label": "Internet GB", "max": 16, "min": 0, "step": 1, "value": 10 },
    { "key": "calls", "label": "Local calls min.", "max": 350, "min": 30, "step": 10, "value": 100 }
    // … daha 3 element
  ]
}
```

- Bütün sürgü açarları məcburidir, dəyərlər tam ədəddir. `min`–`max` aralığından kənar və ya `step`-ə düşməyən dəyər: `400`, `errors.values.<key>`.
- **Heç nə tutulmur.** Saxlanan dəyərlər növbəti yenilənmənin qiymətini və həcmini təyin edir: `GET my/`-də "Növbəti yenilənmə" sətri yeni qiyməti göstərir, qalıqlar isə `POST my/renew/`-dən sonra dəyişir.
- Yalnız IsteSen tarifində işləyir; başqa tarifdə `400`.

### `POST subscribe/`, `POST change/`, `POST my/renew/` — tarifi al, dəyiş, yenilə

Üçü də pul əməliyyatıdır: `Idempotency-Key` məcburidir ([bölmə 7](#7-pul-əməliyyatları-və-idempotency-key)).

| Endpoint | Gövdə | Ekran |
|---|---|---|
| `POST subscribe/` | `{ "plan_id": "digimax-5" }` | Kataloq səhifəsində "Subscribe for X ₼" |
| `POST change/` | `{ "tariff_id": "digimax-3gb" }` | "Tarifi dəyiş" ekranında `family_id`-si `null` olan kart |
| `POST my/renew/` | `{}` | "Renew tariff" pəncərəsi → Renew |

Cavab `201`, üçündə eyni forma:

```jsonc
{
  "balance": "4.21",
  "tariff": {
    "activated_at": "2026-10-09T16:24:05+04:00",
    "family": "digimax",
    "next_payment_at": "2026-11-06T16:24:05+04:00",
    "plan_id": "digimax-5",
    "price": "12.00",
    "title": "DigiMax 5GB",
    "validity_days": 28
  },
  "transaction": { "amount": "-12.00", "id": 35, "title": "DigiMax 5GB tariff" }
}
```

| Sahə | Mənası |
|---|---|
| `tariff` | Yeni vəziyyət: `family`, `plan_id` (IsteSen üçün `null`), `title`, `price`, `validity_days`, `activated_at`, `next_payment_at` (`+04:00`) |
| `transaction` | Balansdan çıxılan məbləğ: `id`, `title`, `amount` (mənfi) |
| `balance` | Yeni balans |

Davranış:

- Balansdan qiymət çıxılır və **tam yeni dövr başlayır**: qalıqlar ümumi həcmə bərabər olur, tarixlər irəli çəkilir. Köhnə dövrün qalığı silinir, aktiv paketlər qalır. Uğurdan sonra `GET my/` və `GET my/usage/`-ni yenidən çağırın.
- Balans çatmırsa `402 insufficient_balance`, heç nə dəyişmir.
- Abunəçi artıq həmin tarifdədirsə `409 already_active` (yeniləmək üçün `my/renew/`).
- `change/`: `family_id`-si olan kart `400` qaytarır, onun planı `subscribe/` ilə seçilir.
- `my/renew/`: "Növbəti yenilənmə" qiymətini tutur. IsteSen saxlanmış sürgü dəyərləri ilə yenilənir (redesign burada qüvvəyə minir), kataloq planı isə cari kataloq qiyməti ilə. Demo abunəçinin balansı (16.21) IsteSen-i yeniləməyə (19.10) çatmır: əvvəl balans artırılmalıdır.
- Limitsiz zəngli planlarda (`premium-60`, `premium-100`) dəqiqə sətrində dövrün bütün dəqiqələri göstərilir (30 gün = `43200`).
- IsteSen kataloqda yoxdur: başqa tarifə keçəndən sonra geri qayıtmaq üçün endpoint yoxdur.

`:todo`: `POST premium/activate/`.

---

## 15. packs

Baza yolu: `/api/packs/`

### `GET internet/` — internet paketləri ekranı

```jsonc
{
  "categories": [
    { "id": "unlimited", "label": "Unlimited" },
    { "id": "high-volume", "label": "High-volume" }
    // … daha 3 element
  ],
  "msisdn": "994516643342",
  "packs": {
    "daily": [
      {
        "id": "daily-500mb",
        "label": "Daily 500 MB",
        "name": "500 MB",
        "price": "0.50",
        "renews": false,
        "sub": "1 day"
      }
      // … daha 1 element
    ],
    "high-volume": [
      {
        "id": "hv-20gb",
        "label": "High-volume 20 GB",
        "name": "20 GB",
        "price": "15.00",
        "renews": true,
        "sub": "30 days"
      }
      // … daha 2 element
    ],
    "unlimited": [
      {
        "id": "unlimited-1h",
        "label": "Unlimited 1 hour",
        "name": "1 hour",
        "price": "0.99",
        "renews": false,
        "sub": "Unlimited speed"
      }
      // … daha 2 element
    ],
    "weekly": [
      {
        "id": "weekly-2gb",
        "label": "Weekly 2 GB",
        "name": "2 GB",
        "price": "3.00",
        "renews": false,
        "sub": "7 days"
      }
      // … daha 1 element
    ]
  },
  "promo": {
    "gradient": ["#8C80FE", "#4670E2"],
    "sub": "For only 0.99 ₼",
    "title": "Unlimited entertainment is waiting for you!"
  },
  "social": [
    {
      "app": "teams",
      "auto_renew": true,
      "cta": "Subscribe",
      "id": "tehsil",
      "periods": ["Daily", "Monthly"],
      "range": "0.7-9.9",
      "special": false,
      "subtitle": "Join online classes with ease via Microsoft Teams.",
      "title": "Tehsil",
      "volume": "10-100 GB"
    },
    {
      "app": "instagram",
      "auto_renew": false,
      "cta": "Activate",
      "id": "instagram-facebook",
      "periods": ["Daily", "Monthly"],
      "range": "1-3",
      "special": true,
      "subtitle": "Scroll, post and watch stories without counting megabytes.",
      "title": "Instagram & Facebook",
      "volume": "1-5 GB"
    }
    // … daha 2 element
  ]
}
```

| Sahə | Mənası |
|---|---|
| `promo` | Yuxarıdakı promo: `title`, `sub`, `gradient` (iki rəng) |
| `categories[]` | Tablar: `id`, `label` |
| `packs` | Kateqoriya `id`-si üzrə paket siyahıları. `social` kateqoriyası burada yoxdur: onun kartları `social`-dadır |
| `packs.<id>[]` | `id`, `name`, `sub`, `price`, `renews` (avtomatik yenilənirmi), `label` (təsdiq pəncərəsindəki ad) |
| `social[]` | Sosial paket kartları: `id`, `title`, `subtitle`, `app` (ikon açarı), `range` (qiymət aralığı), `special`, `volume`, `periods`, `cta`, `auto_renew` |
| `msisdn` | Təsdiq pəncərəsindəki "nömrə üçün" sətri |

### `GET internet/top/` — TOP paketlər

```jsonc
{
  "results": [
    {
      "id": "unlimited-1h",
      "label": "Unlimited 1 hour",
      "name": "1 hour",
      "price": "0.99",
      "renews": false,
      "sub": "Unlimited speed"
    },
    {
      "id": "hv-20gb",
      "label": "High-volume 20 GB",
      "name": "20 GB",
      "price": "15.00",
      "renews": true,
      "sub": "30 days"
    }
    // … daha 1 element
  ]
}
```

### `POST internet/purchase/` — internet paketi al (pul)

```json
{ "pack_id": "unlimited-1h" }
```

Cavab `201`:

```jsonc
{
  "activation": {
    "activated_at": "2026-10-09T12:24:05Z",
    "auto_renew": false,
    "expires_at": "2026-10-09T13:24:05Z",
    "id": 19,
    "label": "Unlimited 1 hour",
    "pack_id": "unlimited-1h",
    "status": "active"
  },
  "balance": "15.22",
  "transaction": { "amount": "-0.99", "id": 35, "title": "Unlimited 1 hour pack" }
}
```

| Sahə | Mənası |
|---|---|
| `activation.id` | Aktivləşdirmənin nömrəsi |
| `activation.pack_id`, `label` | Hansı paket |
| `activation.status` | `active` |
| `activation.activated_at`, `expires_at` | Başlama və bitmə vaxtı (UTC) |
| `activation.auto_renew` | Avtomatik yenilənirmi |
| `transaction`, `balance` | Yaranan əməliyyat və yeni balans |

Xətalar: `400` (naməlum `pack_id`), `402` (balans çatmır). Eyni internet paketini təkrar almaq olar.

### `GET social/<slug>/` — sosial paketin detalı

`<slug>`: `tehsil`, `instagram-facebook`, `tiktok`, `youtube`.

```jsonc
{
  "app": "teams",
  "badge": "AUTO-RENEWAL",
  "cta": "Subscribe",
  "default_plan": "10gb",
  "id": "tehsil",
  "note": "The traffic of the pack is used only in the specified application. After th…",
  "plans": [
    { "id": "10gb", "price": "0.70", "title": "10 GB", "validity": "1 d." },
    { "id": "100gb", "price": "9.90", "title": "100 GB", "validity": "30 d." }
  ],
  "rows": [
    { "label": "Application traffic", "value": "10 GB" },
    { "label": "Validity period", "value": "1 d." }
    // … daha 1 element
  ],
  "title": "Tehsil"
}
```

`rows` əsas plana (`default_plan`) görə doldurulub; istifadəçi başqa plan seçəndə həcm və müddəti tətbiq plandan götürüb yeniləməlidir. `badge` avtomatik yenilənməyən paketlərdə `null`-dur.

### `POST social/<slug>/activate/` — sosial paketi aktivləşdir (pul)

```json
{ "plan_id": "100gb" }
```

```jsonc
{
  "activation": {
    "activated_at": "2026-10-09T12:24:05Z",
    "auto_renew": true,
    "expires_at": "2026-11-08T12:24:05Z",
    "id": 19,
    "label": "Tehsil 100 GB",
    "pack_id": "tehsil",
    "status": "active"
  },
  "balance": "6.31",
  "transaction": { "amount": "-9.90", "id": 35, "title": "Tehsil 100 GB" }
}
```

Xətalar: `400` (naməlum plan), `402`, `404` (naməlum paket), `409 already_active` (avtomatik yenilənən paket artıq aktivdir).

### `GET roaming/` — rouminq paketləri

```jsonc
{
  "confirm": {
    "body": "Roaming internet pack is activated immediately after purchasing. Are you su…",
    "confirm": "Yes, activate the pack",
    "decline": "No, thanks",
    "title": "You are not yet in the roaming area"
  },
  "results": [
    { "id": "r-500mb", "name": "500 MB", "price": "10.00", "sub": "3 days" },
    { "id": "r-2gb", "name": "2 GB", "price": "25.00", "sub": "10 days" }
    // … daha 1 element
  ]
}
```

`confirm` alışdan əvvəl göstərilən təsdiq pəncərəsinin mətnləridir.

### `POST roaming/purchase/` — rouminq paketi al (pul)

```json
{ "pack_id": "r-500mb" }
```

```jsonc
{
  "activation": {
    "activated_at": "2026-10-09T12:24:05Z",
    "auto_renew": false,
    "expires_at": "2026-10-12T12:24:05Z",
    "id": 19,
    "label": "Roaming 500 MB",
    "pack_id": "r-500mb",
    "status": "active"
  },
  "balance": "6.21",
  "transaction": { "amount": "-10.00", "id": 35, "title": "Roaming 500 MB pack" }
}
```

`:todo`: `GET active/` (aktiv paketlərin siyahısı). Hələlik aktivləşdirmə yalnız alış cavabında gəlir, onu tətbiq özündə saxlamalıdır.

---

## 16. kredit

Baza yolu: `/api/kredit/`

### `GET /api/kredit/` — kredit ekranı

```jsonc
{
  "debt": { "amount": "0.00", "items": [], "note": "no items" },
  "products": [
    {
      "chip": "1-3 ₼",
      "chip_icon": "coins",
      "deep_link": "/kredit/simkredit",
      "id": "simkredit",
      "name": "SimKredit",
      "subtitle": "Get now! Pay back at the next topup"
    },
    {
      "chip": "2 ₼",
      "chip_icon": "coins",
      "deep_link": "/kredit/simtaksit",
      "id": "simtaksit",
      "name": "SimTaksit",
      "subtitle": "Get now! Pay back within 32 days by 0.08 ₼"
    }
    // … daha 2 element
  ]
}
```

| Sahə | Mənası |
|---|---|
| `debt.amount` | Açıq borcun cəmi |
| `debt.note` | Hazır mətn (borc yoxdursa "no items") |
| `debt.items[]` | Borclar: `id`, `product`, `name`, `amount`, `created_at`. Hələlik həmişə boşdur |
| `products[]` | `id`, `name`, `subtitle`, `chip`, `chip_icon` (`coins`, `broadcast`), `deep_link`; `price` yalnız bəzi məhsullarda olur |

### `GET products/<slug>/` — məhsulun detalı

`<slug>`: `simkredit`, `simtaksit`, `internetkredit`, `ekstrakredit`.

```jsonc
{
  "amount": "2.00",
  "cta": "Get SimTaksit 2.00 ₼",
  "fee": "0.60",
  "id": "simtaksit",
  "name": "SimTaksit",
  "unit": "₼"
}
```

Əlavə sahələr yalnız aidiyyəti məhsulda gəlir: `options` (seçilə bilən məbləğlər, `simkredit`), `amount_mb` və `validity_days` (`internetkredit`).

### `GET tamamla/`

```jsonc
{
  "banner": {
    "alt": "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan",
    "image": "https://<host>/media/content/tamamla-hero.png"
  },
  "cta": { "label": "Get now!", "url": "https://links.akart.az/app/" },
  "steps": [
    "Apply for akart with ease: download the akart app and register",
    "Give permission to borrow up to 50.00 ₼ when your balance is not enough"
    // … daha 1 element
  ]
}
```

`cta.url` xarici keçiddir (tətbiqdən kənarda açılır).

`:todo`: `POST products/<slug>/take/` — `501` qaytarır, `detail`-də göstəriləcək bildiriş var (göndərilən `amount` mətndə əks olunur).

---

## 17. sim

Baza yolu: `/api/sim/`

### `GET /api/sim/` — SIM ayarları

```jsonc
{
  "badge": "4G (LTE) enabled",
  "details": [
    { "label": "One-way blocking", "value": "2026-10-25" },
    { "label": "Deactivation date", "value": "2027-01-23" }
  ],
  "lte_enabled": true,
  "msisdn": "994516643342",
  "rows": [
    { "deep_link": "/sim/line", "key": "line", "label": "Line settings" },
    { "deep_link": "/sim/roaming", "key": "roaming", "label": "Roaming settings" }
    // … daha 4 element
  ]
}
```

`details[].value` tarixdir (`YYYY-MM-DD`). `rows[]` ekrandakı keçid sətirləridir.

### `GET line/` və `PATCH line/` — xətt ayarları

```jsonc
{
  "call_forwarding_status": "Off",
  "mobile_internet": true,
  "second_line": true,
  "status": "open",
  "status_sub": "Line activation/suspension at subscriber’s request",
  "status_title": "Line status: Open",
  "texts": {
    "internet_settings_link": "Request automatic internet settings",
    "second_line_sub": "With call holding you can hold the first caller on the line and answer the …"
  }
}
```

`PATCH` gövdəsi (yalnız dəyişən sahələr):

```json
{ "mobile_internet": false }
```

Qəbul olunan sahələr: `mobile_internet`, `second_line` (ikisi də bool). Cavab `GET` ilə eyni formadadır. `status`: `open`, `suspended`, `closed`.

### `GET line/status/`

```jsonc
{
  "consequences": [
    "Your agreement will be automatically terminated",
    "Your line will be completely deactivated"
    // … daha 2 element
  ],
  "cta": "Close line",
  "fee": "20.00",
  "general": "You can activate or suspend your line upon request. The line can be closed …",
  "suspend_until": "2027-01-23",
  "title": "Line status: Open"
}
```

### `GET call-forwarding/` və `PATCH call-forwarding/`

```jsonc
{ "all": false, "busy": false, "unanswered": false, "unreachable": false }
```

`PATCH` gövdəsində dörd bool sahədən istənilənləri: `all`, `unanswered`, `busy`, `unreachable`. Qayda:

- `all: true` qalan üçünü `false` edir.
- `all` açıq ikən digərlərindən birini açmaq `400 validation_error` verir. Eyni sorğuda `all: false` də göndərilsə, qəbul olunur.

### `GET roaming/` və `PATCH roaming/`

```jsonc
{
  "changed_at": null,
  "enabled": false,
  "texts": {
    "packs_title": "Roaming packs",
    "search_placeholder": "Explore countries and tariffs",
    "search_title": "Search for country pricing"
  }
}
```

`PATCH` gövdəsi: `{ "enabled": true }`. `changed_at` yalnız vəziyyət həqiqətən dəyişəndə yenilənir. Rouminq paketləri `packs/roaming/`-dədir.

### `GET sms/` və `PATCH sms/`

```jsonc
{
  "language": "az",
  "languages": [
    { "id": "az", "name": "Azerbaijani" },
    { "id": "en", "name": "English" }
    // … daha 1 element
  ],
  "toggles": { "ads": true, "campaigns": true, "partners": true }
}
```

`PATCH` gövdəsi (yalnız dəyişənlər):

```json
{ "language": "en", "toggles": { "partners": false } }
```

`language`: `az`, `en`, `ru`. Göndərilməyən açarlar olduğu kimi qalır.

### `GET puk/`

```jsonc
{
  "codes": [
    { "label": "PUK 1", "value": "5839 0447" },
    { "label": "PUK 2", "value": "8815 4421" }
  ],
  "paragraphs": [
    [
      { "text": "After 3 incorrect entries of PIN 1 and PIN 2, the codes " }
      // … daha 2 element
    ],
    [
      { "text": "After 10 incorrect entries of a PUK code, the SIM card " }
      // … daha 2 element
    ]
  ]
}
```

`paragraphs` zəngin mətndir: hər abzas seqment siyahısıdır, `bold: true` olan seqment qalın yazılır.

### `GET services/` və `GET services/<slug>/`

`<slug>`: `missed-call`, `whos-calling`, `ringback-tone`.

```jsonc
{
  "results": [
    {
      "activated": false,
      "badge": "AUTO-RENEWAL",
      "id": "missed-call",
      "name": "Buraxılmış zəng",
      "period": "30 days",
      "price": "0.90",
      "sub": "Find out who called while you were unreachable"
    },
    {
      "activated": false,
      "badge": "AUTO-RENEWAL",
      "id": "whos-calling",
      "name": "Who is calling",
      "period": "30 days",
      "price": "1.00",
      "sub": "See the name of unknown callers"
    }
    // … daha 1 element
  ]
}
```

```jsonc
{
  "action": { "kind": "subscribe", "label": "Subscribe for 0.90 ₼" },
  "activated": false,
  "badge": "AUTO-RENEWAL",
  "id": "missed-call",
  "name": "Buraxılmış zəng",
  "period": "30 days",
  "price": "0.90",
  "sections": [
    { "text": "You receive an SMS about every call you missed while your phone was switche…" },
    {
      "rows": [
        { "label": "Price", "value": "0.90 ₼" }
        // … daha 2 element
      ]
    }
    // … daha 1 element
  ],
  "sub": "Find out who called while you were unreachable"
}
```

| Sahə | Mənası |
|---|---|
| `price` | Qiymət; xidmət aktivdirsə `null` |
| `activated` | Abunəçi bu xidmətə qoşulubmu |
| `badge` | Aktivdirsə "ACTIVATED", yoxsa "AUTO-RENEWAL" və ya `null` |
| `sections[]` | Detal səhifəsi. Hər element üç növdən biridir: `{ "text" }`, `{ "rows": [{ "label", "value" }] }`, `{ "option": { "id", "label", "sub" } }` |
| `action` | `kind`: `subscribe` və ya `deactivate`; `label`: düymə yazısı |

### `POST services/<slug>/subscribe/` — xidmətə abunə ol (pul)

```json
{ "options": ["xeber-ver"] }
```

`options` istəyə görədir; dəyərlər həmin xidmətin `sections` içindəki `option.id`-lərdir.

```jsonc
{
  "balance": "15.31",
  "subscription": {
    "id": 3,
    "next_payment_at": "2026-11-08T12:24:05Z",
    "service": "missed-call",
    "status": "active"
  },
  "transaction": { "amount": "-0.90", "title": "Buraxılmış zəng service" }
}
```

Xətalar: `400` (naməlum seçim), `402`, `404`, `409 already_active`.

### `GET esim/`

```jsonc
{
  "actions": [
    { "key": "transfer", "label": "Transfer to eSIM" },
    { "deep_link": "/esim/recover", "key": "recover", "label": "Recover eSIM" }
  ],
  "asan_note": "The use of the obtained eSIM “Asan İmza” service is possible only after the…",
  "benefits": [
    {
      "body": "Your eSIM stays secure, no physical card to lose or damage",
      "key": "safe",
      "title": "Safe & Reliable"
    },
    {
      "body": "Keep several numbers on one device and switch between them",
      "key": "flexible",
      "title": "Flexible"
    }
    // … daha 1 element
  ]
}
```

`:todo` olanlar: `POST line/internet-settings/`, `POST line/close/`, `GET roaming/countries/`, `POST services/<slug>/deactivate/`, `POST esim/transfer/`, `POST esim/recover/`.

---

## 18. content

Baza yolu: `/api/content/`

### `GET home/` — ana səhifə

```jsonc
{
  "banners": [
    {
      "alt": "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan",
      "deep_link": "/kredit/tamamla",
      "image": "https://<host>/media/content/banner-akart.png",
      "key": "akart"
    },
    {
      "alt": "Spin the Gift Wheel! A new gift every day",
      "deep_link": null,
      "image": "https://<host>/media/content/banner-spin.png",
      "key": "spin"
    }
    // … daha 8 element
  ],
  "lottery": {
    "cta": "Learn more about the lottery",
    "deep_link": "/lottery-rules",
    "starts_at": "2026-10-19",
    "subtitle": "Chance collection starts on 19 October 2026",
    "title": "30 il səninlə"
  },
  "quick_actions": [
    { "deep_link": "/kredit", "key": "simkredit", "label": "SimKredit" },
    { "deep_link": "/internet-packs", "key": "buy-internet", "label": "Buy internet" }
    // … daha 1 element
  ],
  "stories": [
    {
      "has_story": true,
      "image": "https://<host>/media/content/chip-gift-wheel.png",
      "key": "gift-wheel",
      "label": "Gift Wheel",
      "viewed": false
    },
    {
      "has_story": true,
      "image": "https://<host>/media/content/chip-roaming.png",
      "key": "roaming",
      "label": "Roaming",
      "viewed": false
    }
    // … daha 5 element
  ]
}
```

| Sahə | Mənası |
|---|---|
| `stories[]` | Story çipləri: `key`, `label`, `image`, `viewed`, `has_story`. Baxılanlar sonda gəlir |
| `quick_actions[]` | Sürətli əməllər: `key`, `label`, `deep_link` |
| `banners[]` | Karusel: `key`, `image`, `alt`, `deep_link` (`null` ola bilər) |
| `lottery` | Lotereya banneri: `title`, `subtitle`, `starts_at` (tarix), `cta`, `deep_link` |

### `GET stories/`, `GET stories/<key>/`, `POST stories/<key>/viewed/`

`stories/` `home/`-dakı `stories` ilə eyni çipləri `{ "results": [...] }` kimi qaytarır.

```jsonc
{
  "key": "especially",
  "next_key": "applications",
  "pages": [
    {
      "body": "Offers picked for the way you use your number.",
      "cta": null,
      "duration_ms": 5000,
      "image": "https://<host>/media/content/story-especially-1.png",
      "title": "Especially for you"
    },
    {
      "body": "Unlimited speed for only 0.99 ₼.",
      "cta": { "deep_link": "/internet-packs", "label": "Buy internet" },
      "duration_ms": 5000,
      "image": "https://<host>/media/content/story-especially-2.png",
      "title": "Unlimited 1 hour"
    }
  ],
  "prev_key": "roaming",
  "thumb": "https://<host>/media/content/chip-especially.png",
  "title": "Especially for you"
}
```

| Sahə | Mənası |
|---|---|
| `pages[]` | Səhifələr: `image`, `title`, `body`, `cta` (`{ "label", "deep_link" }` və ya `null`), `duration_ms` |
| `next_key`, `prev_key` | Qonşu story-lər (kənardadırsa `null`) |

`POST stories/<key>/viewed/` gövdəsizdir; cavab `{ "key": "especially", "viewed": true }`. Çip siyahının sonuna keçir.

### `GET banners/?placement=`

`placement`: `home` (susmaya görə), `products`, `benefits`, `partners`. Başqa dəyər `400` verir.

```jsonc
{
  "results": [
    {
      "alt": "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan",
      "deep_link": "/kredit/tamamla",
      "image": "https://<host>/media/content/banner-akart.png",
      "key": "akart"
    },
    {
      "alt": "Spin the Gift Wheel! A new gift every day",
      "deep_link": null,
      "image": "https://<host>/media/content/banner-spin.png",
      "key": "spin"
    }
    // … daha 8 element
  ]
}
```

### `GET notifications/?q=&from=&to=` (səhifələnir)

`q` başlıq və mətndə axtarır; `from` və `to` Bakı vaxtı ilə tarixlərdir.

```jsonc
{
  "next": null,
  "results": [
    {
      "body": "Chance collection starts on 19 October 2026.",
      "cta": { "deep_link": "/lottery-rules", "label": "Learn more about the lottery" },
      "id": "lottery",
      "read": false,
      "sent_at": "2026-10-01T09:00:00Z",
      "title": "30 il səninlə"
    },
    {
      "body": "Get 15 minutes of free time on your first Wingz ride when you pay with your…",
      "cta": null,
      "id": "wingz",
      "read": false,
      "sent_at": "2025-10-27T09:00:00Z",
      "title": "Activate Wingz scooter with your Azercell balance!"
    }
    // … daha 1 element
  ],
  "unread": 2
}
```

| Sahə | Mənası |
|---|---|
| `id` | **Sətir** (slug), ədəd deyil |
| `title`, `body` | Başlıq və mətn |
| `cta` | `{ "label", "deep_link" }` və ya `null` |
| `sent_at` | Göndərilmə vaxtı |
| `read` | Oxunubmu |
| `unread` (üst səviyyədə) | Zəng nişanı üçün oxunmamışların **ümumi** sayı; filtrdən asılı deyil |

Boş `results` "nəticə yoxdur" deməkdir.

### `GET notifications/<id>/` və `POST notifications/<id>/read/`

İkisi də bildirişi oxunmuş edir və onu qaytarır. **Diqqət:** `GET` də oxunmuş kimi işarələyir.

```jsonc
{
  "body": "Get 15 minutes of free time on your first Wingz ride when you pay with your…",
  "cta": null,
  "id": "wingz",
  "read": true,
  "sent_at": "2025-10-27T09:00:00Z",
  "title": "Activate Wingz scooter with your Azercell balance!"
}
```

### `GET lottery/rules/`

```jsonc
{
  "sections": [
    {
      "blocks": [
        {
          "kind": "p",
          "text": "We are launching the “30 il səninlə” lottery to celebrate 30 years together…"
        }
        // … daha 1 element
      ],
      "icon": null,
      "title": "About the lottery"
    },
    {
      "blocks": [
        {
          "bold": "Top up your balance with 5 AZN or more",
          "kind": "p",
          "num": "1.",
          "text": "and get 1 chance for every 5 AZN."
        }
        // … daha 2 element
      ],
      "icon": "Diamond",
      "title": "How to earn chances?"
    }
    // … daha 5 element
  ],
  "terms_url": null
}
```

`blocks[]` iki növdür: `{ "kind": "p", "text", "num"?, "bold"? }` (abzas; `num` nömrə, `bold` qalın başlanğıc) və `{ "kind": "example", "items": [{ "label", "value" }] }`.

### `GET games/`

```jsonc
{
  "games": [
    {
      "id": "ninja-saga-2",
      "image": "https://<host>/media/content/game-ninja-saga-2.png",
      "name": "Ninja Saga 2"
    },
    {
      "id": "fruit-slice",
      "image": "https://<host>/media/content/game-fruit-slice.png",
      "name": "Fruit Slice"
    }
    // … daha 6 element
  ],
  "reward_games": [
    {
      "id": "battle-for-gb",
      "image": "https://<host>/media/content/game-battle-for-gb.png",
      "name": "Battle for GB"
    }
  ],
  "tournament": {
    "cta": "Participate in the tournament",
    "ends_at": "2026-10-08T15:17:02Z",
    "game": "ninja-saga-2",
    "participants": 6708,
    "prize": "5 GB",
    "title": "Tournament"
  }
}
```

`tournament.game` oyunun `id`-sidir. **`?q=` ilə axtarış hələ `501` qaytarır.**

### `GET offers/apps/`, `offers/aztelekom/`, `perks/`, `campaigns/`

Hamısı eyni formadadır; `price` yalnız `offers/apps/`-də var.

```jsonc
{
  "results": [
    {
      "deep_link": null,
      "id": "kinon",
      "image": "https://<host>/media/content/offer-kinon.png",
      "name": "Kinon",
      "price": "4.99",
      "sub": "Films and series online"
    },
    {
      "deep_link": null,
      "id": "yandex-plus",
      "image": "https://<host>/media/content/offer-yandex-plus.png",
      "name": "Yandex Plus",
      "price": "5.90",
      "sub": "Music, films and cashback"
    }
    // … daha 1 element
  ]
}
```

### `POST app-rating/`

```json
{ "stars": 5 }
```

`stars` 1–5. Cavab `201`: `{ "message": "…" }` (4 və yuxarı üçün təşəkkür, aşağı üçün üzrxahlıq mətni).

`:todo` olanlar: `GET notifications/options/`, `GET lottery/chances/`, `GET lottery/terms/`, `GET games/<slug>/launch/`, `POST games/tournament/join/`, `GET games/tournament/rules/`, `POST offers/apps/<id>/subscribe/`, `POST offers/aztelekom/order/`, `GET gift-wheel/`, `POST gift-wheel/spin/`, `GET about/`, `GET map/`, `GET stickers/`, `GET help/`, `POST problem-report/`.

---

## 19. referral

Baza yolu: `/api/referral/`

### `GET me/`

```jsonc
{
  "code": "wa16Kg",
  "earned": "0.00",
  "headline": "Share Azercell app and get 3.00 ₼ bonus!",
  "share_message": "Join me on the Azercell app and use my referral code wa16Kg",
  "share_url": "https://azercell.com/app?ref=wa16Kg",
  "steps": [
    {
      "body": "Share your invitation link or referral code. The link can be sent an unlimi…",
      "title": "Invite a friend who doesn’t have an account on the Azercell app"
    },
    {
      "body": "Your friend must register for the first time using the link you shared and …",
      "title": "Your friend registers and easily uses the service."
    }
    // … daha 1 element
  ],
  "terms_url": null
}
```

| Sahə | Mənası |
|---|---|
| `code` | Abunəçinin dəvət kodu |
| `share_url`, `share_message` | Paylaşmaq üçün keçid və hazır mətn |
| `earned` | İndiyə qədər qazanılan məbləğ (hələlik həmişə `0.00`) |
| `headline`, `steps[]` | Başlıq və qaydalar (`title`, `body`) |
| `terms_url` | Hələlik `null` |

`:todo`: `GET terms/`, `POST events/` (xidmətlər üçün webhook, tətbiqə aid deyil).

---

## 20. assistant

Baza yolu: `/api/assistant/`. Vəziyyət `:dummy`: hər şey işləyir, amma cavabı açar sözlər verir və həmişə ingiliscədir.

### `GET inbox/` — dəstək ekranı

```jsonc
{
  "actions": [
    { "body": "We're here to help, just ask away!", "key": "ask", "title": "Ask a question" },
    {
      "body": "Your feedback helps us improve!",
      "key": "ideas",
      "title": "Share your ideas for new features"
    }
  ],
  "greeting": "How can we support you?",
  "items": [
    {
      "by": "AI Chat Bot",
      "conversation_id": 3513323,
      "external_id": "#3513323",
      "kind": "rate_prompt",
      "last_message_at": "2026-10-06T14:01:00Z",
      "title": "Rate your conversation",
      "unread": true
    }
  ],
  "unread": 1
}
```

| Sahə | Mənası |
|---|---|
| `unread` | Oxunmamış söhbətlərin sayı |
| `items[].kind` | `rate_prompt` (bağlanmış, hələ qiymətləndirilməmiş söhbət) və ya `conversation` |
| `items[].conversation_id` | Söhbətin `id`-si (ədəd); `external_id` göstərmək üçündür (`"#3513323"`) |
| `actions[]` | Ekrandakı iki düymə: `ask`, `ideas` |

### `GET conversations/` və `POST conversations/`

`POST` gövdəsi istəyə görədir: `{ "source": "mobile" }`. Cavab `201`:

```jsonc
{ "created_at": "2026-10-09T12:24:05Z", "external_id": "#3513324", "id": 3513324, "status": "open" }
```

### `GET conversations/<id>/messages/` — tarixçə (səhifələnir, köhnədən yeniyə)

```jsonc
{
  "next": null,
  "results": [
    {
      "content": "How much internet do I have left?",
      "created_at": "2026-10-06T14:00:00Z",
      "id": 5,
      "role": "user"
    },
    {
      "content": "You have 7.20 GB left until 25 October.",
      "created_at": "2026-10-06T14:01:00Z",
      "id": 6,
      "role": "assistant",
      "route": "usage"
    }
  ]
}
```

`role`: `user` və ya `assistant`. `route` yalnız assistentin mesajlarında var (cavabın mövzusu: `usage`, `balance`, `tariff`, `packs`, `roaming`, `kredit`, `fallback`).

### `POST conversations/<id>/messages/` — mesaj göndər

Sorğu:

```json
{ "content": "How much internet do I have left?", "source": "mobile" }
```

`content` məcburidir, ən çoxu 2000 simvol.

**Rejim 1 — axın (SSE), susmaya görə.** Cavab `200`, `Content-Type: text/event-stream`:

```
event: message
data: {"message_id": 812, "role": "user"}

data: {"text": "You have "}

data: {"text": "7.20 GB "}

data: {"text": "left until "}

data: {"text": "25 October."}

event: action
data: {"action": "navigate", "to": "/remaining-balance", "label": "Open remaining balance"}

event: log
data: {"message_id": 813, "route": "usage", "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "latency_ms": 0}

event: done
data: {}
```

| Hadisə | Mənası |
|---|---|
| `message` | İstifadəçinin mesajı saxlanıldı; `message_id` onun nömrəsidir |
| adsız (`event:` sətri yoxdur) | Cavabın bir parçası; `text`-ləri ardıcıl birləşdirin |
| `action` | Təklif olunan keçid: `to` (yol), `label` (düymə yazısı). Olmaya bilər |
| `log` | Cavab mesajının `message_id`-si və statistika |
| `done` | Axın bitdi |

**Rejim 2 — tək cavab.** `Accept: application/json` göndərilsə, cavab `201` və bütün mesaj bir gövdədə gəlir:

```jsonc
{
  "action": { "action": "navigate", "label": "Open remaining balance", "to": "/remaining-balance" },
  "message": {
    "content": "You have 7.20 GB left until 25 October.",
    "created_at": "2026-10-09T12:24:05Z",
    "id": 8,
    "role": "assistant",
    "route": "usage"
  },
  "user_message_id": 7
}
```

Xətalar: `400` (boş mesaj), `404` (söhbət yoxdur və ya başqasınındır), `429` (dəqiqədə 20 mesaj).

### `POST conversations/<id>/rate/`

```json
{ "stars": 4, "comment": "" }
```

`stars` 1–5, `comment` istəyə görə. Cavab `201`: `{ "message": "…" }`. Bundan sonra söhbət `inbox`-da `rate_prompt` kimi görünmür.

`:todo`: `POST feedback/`.

---

## 21. usage

Baza yolu: `/api/usage/`. Abunəçinin son 30 gündə nə etdiyi, ona hansı tarif və ya paketin uyğun olduğu və şəxsi təklif.

Bütün rəqəmləri backend kataloqdan və istifadə qeydlərindən hesablayır; süni intellekt iştirak etmir. **İstifadə qeydləri sintetikdir**: backend operator şəbəkəsinə qoşulmayıb, məlumat seed ilə yaradılır.

### `GET summary/?days=30` — istifadə profili

`days` 1–90 arasıdır, verilməsə 30.

```jsonc
{
  "daily_average": { "data_mb": 433, "minutes": 0.7, "sms": 0.2 },
  "data_by_app": [
    {
      "category": "social",
      "data_mb": 7145,
      "key": "instagram_facebook",
      "label": "Instagram & Facebook",
      "share": 0.55
    },
    { "category": "other", "data_mb": 2551, "key": "other", "label": "Other", "share": 0.2 }
    // … daha 3 element
  ],
  "data_by_category": [
    { "data_mb": 7776, "key": "social", "label": "Social networks", "share": 0.6 },
    { "data_mb": 2551, "key": "other", "label": "Other", "share": 0.2 }
    // … daha 2 element
  ],
  "data_ran_out": null,
  "headline": "12.7 GB, 20 min. and 6 SMS in 30 days; 19.10 ₼ paid",
  "segment": { "key": "balanced", "label": "Balanced use" },
  "services": [],
  "spend": {
    "addon_packs": { "amount": "0.00", "count": 0 },
    "other": "0.00",
    "roaming": { "amount": "0.00", "count": 0 },
    "tariff_fee": "19.10",
    "total": "19.10"
  },
  "totals": {
    "data_gb": "12.70",
    "data_mb": 13000,
    "minutes": 20,
    "roaming_data_mb": 0,
    "roaming_days": 0,
    "roaming_minutes": 0,
    "sms": 6
  },
  "window": { "days": 30, "from": "2026-09-10", "to": "2026-10-09" }
}
```

| Sahə | Mənası |
|---|---|
| `window` | Hesablanan dövr: gün sayı, başlanğıc və son tarix |
| `segment` | Abunəçinin tipi. `key`: `heavy_data`, `voice_only`, `roamer`, `balanced`, `low_usage`; `label` tərcümə olunur |
| `headline` | Hazır xülasə cümləsi |
| `totals` | Cəmlər: internet (`data_mb`, `data_gb`), `minutes`, `sms`, rouminq (`roaming_data_mb`, `roaming_minutes`, `roaming_days`) |
| `daily_average` | Gündəlik orta |
| `data_by_category[]` | Kateqoriya üzrə internet: `key` (`video`, `social`, `messaging`, `games`, `other`), `label`, `data_mb`, `share` (0–1) |
| `data_by_app[]` | Tətbiq üzrə internet: `key`, `label`, `category`, `data_mb`, `share` |
| `data_ran_out` | Tarifə daxil olan internetin bitdiyi gün (`day`, `date`, `period_days`) və ya `null` |
| `spend` | Xərclər: `tariff_fee`, `addon_packs` və `roaming` (`count`, `amount`), `other`, `total` |
| `services[]` | Aktiv ödənişli SIM xidmətləri |

### `GET recommendations/` — tövsiyələr və açıq təklif

Həmişə son 30 gün üçündür.

```jsonc
{
  "current_monthly_cost": "19.10",
  "fits": false,
  "insights": [
    {
      "category": "social",
      "sells": [
        {
          "action": {
            "action": "navigate",
            "label": "See the pack",
            "to": "/internet-packs/instagram-facebook"
          },
          "kind": "social_pack",
          "target_id": "instagram-facebook",
          "title": "Instagram & Facebook"
        }
        // … daha 2 element
      ],
      "share": 0.6,
      "text": "Social networks: 60% of your data"
    }
  ],
  "message": "You paid 19.10 ₼ in the last 30 days; with IsteSen, redesigned to your usag…",
  "offer": {
    "action": { "action": "navigate", "label": "See the offer", "to": "/offers/9001" },
    "expires_at": "2026-10-23T12:24:04Z",
    "id": 9001,
    "kind": "social_pack",
    "normal_price": "3.00",
    "offer_price": "2.00",
    "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
    "status": "shown",
    "target_id": "instagram-facebook:5gb",
    "title": "Instagram & Facebook 5 GB"
  },
  "recommendations": [
    {
      "action": { "action": "navigate", "label": "Redesign my tariff", "to": "/my-tariff/redesign" },
      "current_monthly_cost": "19.10",
      "evidence": ["Instagram & Facebook 55% of data", "12.7 GB used in 30 days, tariff includes 16 GB"],
      "kind": "redesign",
      "projected_monthly_cost": "17.60",
      "saving": "1.50",
      "target_id": "istesen",
      "title": "IsteSen, redesigned to your usage",
      "values": { "calls": 30, "instagramFb": 5, "internet": 5, "tiktok": 1, "youtube": 2 }
    }
  ],
  "segment": { "key": "balanced", "label": "Balanced use" },
  "window_days": 30
}
```

| Sahə | Mənası |
|---|---|
| `current_monthly_cost` | Abunəçinin faktiki ödədiyi: tarif haqqı, əlavə paketlər və rouminq |
| `fits` | `true` isə kataloqda bundan sərfəli heç nə yoxdur və `recommendations` boşdur. Bu, xəta deyil, normal cavabdır |
| `message` | Nəticəni rəqəmlərlə deyən hazır cümlə |
| `recommendations[]` | Ən çox qənaət edəndən başlayaraq sıralanıb |
| `recommendations[].kind` | `tariff_plan`, `internet_pack`, `social_pack` (`plan_id` ilə), `roaming_pack` (birdən çox lazımdırsa `quantity` ilə), `redesign` (`values`: IsteSen sürgülərinin dəyərləri) |
| `recommendations[].projected_monthly_cost` | Eyni 30 gün bu seçimlə neçəyə başa gələrdi |
| `recommendations[].saving` | Fərq. Yalnız daxil olan internet dövr bitmədən qurtarıbsa mənfi ola bilər |
| `recommendations[].evidence[]` | Tövsiyənin əsasları, rəqəmlərlə hazır cümlələr |
| `recommendations[].action` | Keçid: `to` (yol), `label` (düymə yazısı) |
| `insights[]` | Ən böyük kateqoriya haqqında fakt və onun üçün satıla bilənlər (`sells`). `sells` boş ola bilər (məsələn oyunlar) |
| `offer` | Açıq şəxsi təklif və ya `null`. Bu cavabda qayıtmaqla `shown` kimi işarələnir |

`offer` obyekti: `id`, `kind`, `target_id`, `title`, `normal_price`, `offer_price`, `reason`, `status` (`new`, `shown`, `accepted`, `declined`, `expired`), `expires_at`, `action`.

### `POST offers/<id>/accept/` — təklifi qəbul et (pul)

Gövdəsizdir, `Idempotency-Key` məcburidir. Paket təklif qiymətinə alınır və adi alış kimi aktivləşir. Cavab `201`:

```jsonc
{
  "activation": {
    "activated_at": "2026-10-09T12:24:05Z",
    "auto_renew": false,
    "expires_at": "2026-11-08T12:24:05Z",
    "id": 19,
    "label": "Instagram & Facebook 5 GB",
    "pack_id": "instagram-facebook",
    "status": "active"
  },
  "balance": "14.21",
  "offer": {
    "action": { "action": "navigate", "label": "See the offer", "to": "/offers/9001" },
    "expires_at": "2026-10-23T12:24:04Z",
    "id": 9001,
    "kind": "social_pack",
    "normal_price": "3.00",
    "offer_price": "2.00",
    "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
    "status": "accepted",
    "target_id": "instagram-facebook:5gb",
    "title": "Instagram & Facebook 5 GB"
  },
  "transaction": { "amount": "-2.00", "id": 35, "title": "Instagram & Facebook 5 GB" }
}
```

Xətalar: `402` (balans çatmır, təklif açıq qalır), `404` (təklif yoxdur və ya başqasınındır), `409 offer_closed` (artıq qəbul, rədd edilib və ya vaxtı bitib).

Tarif təklifi heç nə almır, çünki tarifin təklif qiymətinə alışı hələ qurulmayıb (adi qiymətə `tariffs/subscribe/` işləyir): cavab `200` və `{ "offer", "action" }` olur, təklif açıq qalır.

### `POST offers/<id>/decline/` — təklifi rədd et

```jsonc
{
  "offer": {
    "action": { "action": "navigate", "label": "See the offer", "to": "/offers/9001" },
    "expires_at": "2026-10-23T12:24:04Z",
    "id": 9001,
    "kind": "social_pack",
    "normal_price": "3.00",
    "offer_price": "2.00",
    "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
    "status": "declined",
    "target_id": "instagram-facebook:5gb",
    "title": "Instagram & Facebook 5 GB"
  }
}
```

Rədd etdikdən sonra 7 gün yeni təklif gəlmir. Yeni təklif yarananda abunəçiyə bildiriş də yazılır (`cta.deep_link`: `/offers/<id>`).

---

## 22. insights

Baza yolu: `/api/insights/`

Abunəçinin öz rəqəmlərindən **qaydalarla** tapılan müşahidələr və hər biri üçün kataloqdan **hesablanmış** təkliflər. Backend cümlə yazmır: `evidence` faktlardır, `offers` hazır qiymət və qənaətdir; mətni göstərən tərəf (assistent, kart, bildiriş) qurur. Heç bir model çağırılmır.

### `GET /` — indi göstərilə bilən insight-lar

```jsonc
{
  "results": [
    {
      "created_at": "2026-10-09T16:24:04+04:00",
      "evidence": {
        "by_app_gb": { "instagram_facebook": 7.0, "other": 2.5, "tiktok": 0.6, "whatsapp": 0.7, "youtube": 1.9 },
        "social_share": 0.55,
        "tiktok_gb_month": 0.6
      },
      "expires_at": "2026-10-16T16:24:04+04:00",
      "id": 7001,
      "kind": "social_heavy",
      "offers": [
        {
          "data_gb": 14.0,
          "label": "IsteSen+",
          "per_gb": null,
          "price": "18.10",
          "ref": "redesign",
          "saving": "1.00",
          "saving_year": "12.00",
          "task": {
            "name": "applyRedesign",
            "params": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
          },
          "validity": null,
          "values": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
        }
        // … daha 1 element
      ],
      "recommended": 0,
      "severity": "info",
      "status": "new"
    }
  ]
}
```

| Sahə | Mənası |
|---|---|
| `id` | Insight-ın id-si (`seen/`, `accept/`, `dismiss/` üçün) |
| `kind` | Növ (aşağıdakı cədvəl) |
| `severity` | `urgent` və ya `info`. `urgent` olanlar siyahıda birinci gəlir |
| `status` | `new`, `seen` (cavablananlar siyahıda olmur) |
| `created_at`, `expires_at` | Bakı vaxtı ilə (`+04:00`). 7 gündən sonra insight düşür |
| `evidence` | Faktlar. Hər `kind` üçün sahələr sabitdir |
| `offers[]` | Təkliflər, ən yaxşısı birinci |
| `recommended` | Tövsiyə olunan təklifin `offers`-dəki indeksi |

`offers[]` elementi:

| Sahə | Mənası |
|---|---|
| `ref` | Sabit açar: `internet:<slug>`, `social:<pack>:<plan>`, `roaming:<slug>`, `tariff:<slug>`, `redesign`, `top_up`, `kredit:<slug>` |
| `label`, `validity` | Ad və müddət, seçilmiş dildə (`validity` olmaya bilər: `null`) |
| `price` | Qiymət (sətir) |
| `data_gb`, `per_gb` | Həcm və 1 GB-ın qiyməti (limitsizdə `null`) |
| `saving` | Aylıq qənaət; yoxdursa və ya təklif indikindən bahadırsa `null` |
| `task` | Təklifi icra etmək üçün əməliyyat: `name` və `params` (aşağıda) |

Növlər:

| `kind` | Nə vaxt | `severity` |
|---|---|---|
| `overage` | Tarifin interneti bitib və bu gün paketdən kənar 20 MB-dan çox yazılıb | `urgent` |
| `renewal_shortfall` | Yenilənməyə 2 gün və ya az qalıb, balans çatmır | `urgent` |
| `video_heavy` | 5 GB+ paket 3 günə bitib və trafikin 60%-i videodur | `info` |
| `repeat_packs` | Cari dövrdə 2 və ya daha çox əlavə paket alınıb | `info` |
| `forecast_gap` | Tarifin 70%-i işlənib və cari templə yenilənməyə qədər çatmayacaq | `info` |
| `social_heavy` | Instagram & Facebook trafikin 40%-idir və ya TikTok ayda 4 GB-dır | `info` |
| `underused` | Son 3 dövrün hər birində internetin yarısı və ya çoxu qalıb | `info` |
| `roaming` | Son 3 gündə rouminqdə internet işlənib, rouminq paketi yoxdur | `info` |

`task` və onu icra edən endpoint (bu domen pul köçürmür):

| `task.name` | `params` | Endpoint |
|---|---|---|
| `buyPack` | `kind` (`internet` / `roaming`), `pack_id` | `POST packs/internet/purchase/` və ya `packs/roaming/purchase/`, gövdə `{ "pack_id" }` |
| `activatePack` | `slug`, `plan` | `POST packs/social/<slug>/activate/`, gövdə `{ "plan_id": plan }` |
| `changeTariff` | `plan` | `POST tariffs/subscribe/`, gövdə `{ "plan_id": plan }` |
| `applyRedesign` | sürgü dəyərləri | `POST tariffs/my/redesign/`, gövdə `{ "values": params }` |
| `topUp` | `amount` | `POST billing/top-up/card/` və ya başqa artım üsulu |
| `takeKredit` | `slug` | `POST kredit/products/<slug>/take/` (hələ `:todo`) |

Çatdırılma qaydaları serverdədir, tətbiq əlavə süzgəc qoymamalıdır:

- Hər çağırışda detektorlar yenidən işləyir: alış və ya balans artımı növbəti `GET`-də əks olunur.
- 23:00–08:00 (Bakı) arasında siyahı boş gəlir.
- `urgent` hamısı gəlir; yeni `info` insight 48 saatda bir dəfə verilir (göstərilən cavablanana və ya düşənə qədər eyni qalır).
- Eyni növdən ikinci açıq insight olmur; şərt aradan qalxanda insight özü bağlanır.

### `POST <id>/seen/`, `POST <id>/accept/`, `POST <id>/dismiss/`

- `seen/`: tətbiq insight-ı göstərdi (`new` → `seen`).
- `accept/`: istifadəçi "hə" dedi. Gövdə istəyə görə `{ "offer": 1 }` (verilməsə tövsiyə olunan). Cavabda insight və seçilmiş təklifin `task`-ı gəlir; **pul tutulmur**, `task` yuxarıdakı endpoint ilə icra olunur. Sonra həmin növ 2 gün yazılmır.
- `dismiss/`: istifadəçi "yox" dedi. Həmin növ 14 gün yazılmır.
- Təkrar cavab heç nəyi dəyişmir; başqasının insight-ı `404`; siyahıda olmayan `offer` `400`.

```jsonc
{
  "created_at": "2026-10-09T16:24:04+04:00",
  "evidence": {
    "by_app_gb": { "instagram_facebook": 7.0, "other": 2.5, "tiktok": 0.6, "whatsapp": 0.7, "youtube": 1.9 },
    "social_share": 0.55,
    "tiktok_gb_month": 0.6
  },
  "expires_at": "2026-10-16T16:24:04+04:00",
  "id": 7001,
  "kind": "social_heavy",
  "offers": [
    {
      "data_gb": 14.0,
      "label": "IsteSen+",
      "per_gb": null,
      "price": "18.10",
      "ref": "redesign",
      "saving": "1.00",
      "saving_year": "12.00",
      "task": {
        "name": "applyRedesign",
        "params": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
      },
      "validity": null,
      "values": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
    },
    {
      "data_gb": 5.0,
      "label": "Instagram & Facebook 5 GB",
      "per_gb": "0.60",
      "price": "3.00",
      "ref": "social:instagram-facebook:5gb",
      "saving": null,
      "task": {
        "name": "activatePack",
        "params": { "plan": "5gb", "slug": "instagram-facebook" }
      },
      "validity": "30 d."
    }
  ],
  "recommended": 0,
  "severity": "info",
  "status": "accepted",
  "task": {
    "name": "applyRedesign",
    "params": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
  }
}
```

### `GET advisor/` — istifadəyə uyğun tarif

Ayın indiki xərci ilə istifadəyə uyğun variantların müqayisəsi. "IsteSen+" ayrı tarif deyil: IsteSen konstruktorunun istifadəyə görə hesablanmış sürgü dəyərləridir, qiyməti `tariffs/my/redesign/`-dəki düsturla hesablanır.

```jsonc
{
  "candidates": [
    {
      "data_gb": 14,
      "id": "istesen-plus",
      "minutes": 30,
      "price": "18.10",
      "redesign": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 },
      "saving_month": "1.00",
      "saving_year": "12.00",
      "task": {
        "name": "applyRedesign",
        "params": { "calls": 30, "instagramFb": 5, "internet": 6, "tiktok": 1, "youtube": 2 }
      },
      "title": "IsteSen+",
      "total_month": "18.10"
    },
    {
      "data_gb": 25,
      "id": "digimax-25",
      "minutes": 500,
      "price": "30.00",
      "saving_month": "-10.90",
      "task": {
        "name": "changeTariff",
        "params": { "plan": "digimax-25" }
      },
      "title": "DigiMax 25GB",
      "total_month": "30.00"
    }
    // … daha 1 element
  ],
  "current": { "packs_month": "0.00", "price": "19.10", "tariff": "IsteSen", "total_month": "19.10" },
  "effective_from": "2026-10-25",
  "period_days": 30,
  "profile": {
    "by_app_gb": { "instagram_facebook": 7.0, "other": 2.5, "tiktok": 0.6, "whatsapp": 0.7, "youtube": 1.9 },
    "data_gb_month": 12.7,
    "minutes_month": 20
  },
  "recommended": "istesen-plus"
}
```

| Sahə | Mənası |
|---|---|
| `period_days` | Hesabın söykəndiyi tarixçə (ən çox 60 gün) |
| `profile` | Aylıq trafik (`data_gb_month`), tətbiqlərə görə GB, aylıq dəqiqə |
| `current` | İndiki tarif, qiyməti, aylıq paket xərci, aylıq cəm |
| `candidates[]` | Variantlar: `id`, `title`, `price`, `total_month`, `saving_month`, `data_gb`, `minutes`, `task`. `rejected` varsa variant uyğun deyil (`does_not_cover`, `usage_x4.7`) |
| `recommended` | Qalib variantın `id`-si; dəyişiklik 1 ₼-dan az qənaət verirsə `"current"` |
| `effective_from` | Növbəti yenilənmə tarixi (redesign o vaxt qüvvəyə minir) |

Abunəçinin tarifi yoxdursa `404`.

---

## 23. Tipik axınlar

**Ana səhifənin yüklənməsi** (hamısı paralel göndərilə bilər):

1. `GET users/me/` — ad və nömrə
2. `GET billing/balance/` — balans
3. `GET tariffs/my/usage/` — qalıq kartı
4. `GET content/home/` — story-lər, bannerlər
5. `GET billing/transactions/?limit=5` — son əməliyyatlar
6. `GET content/notifications/?limit=1` — zəng nişanı üçün `unread`

**Paket alışı:**

1. `GET packs/internet/` — siyahı və `msisdn`
2. İstifadəçi təsdiqləyir → tətbiq yeni UUID yaradır
3. `POST packs/internet/purchase/` + `Idempotency-Key`
4. `201`: cavabdakı `balance` ilə balansı yenilə, `activation`-ı göstər
5. `402`: balans artırmağı təklif et
6. Şəbəkə xətası və ya vaxt aşımı: **eyni** açarla təkrar göndər

**Balans artımı:** `GET billing/top-up/methods/` → `POST billing/top-up/card/` → cavabdakı `balance`.

**Xidmətə abunəlik:** `GET sim/services/<slug>/` → `action.kind == "subscribe"` isə `POST …/subscribe/` → sonra `GET sim/services/` (xidmət `activated: true` olur).

**Assistent:** `POST assistant/conversations/` → alınan `id` ilə `POST …/messages/` (SSE) → `action` gələrsə düymə göstər.

**Tövsiyə və təklif:** `GET usage/recommendations/` → `fits` `false` isə ilk tövsiyəni `evidence` ilə göstər, `action.to`-ya apar; `offer` varsa kart kimi göstər → `POST usage/offers/<id>/accept/` + `Idempotency-Key` və ya `…/decline/`.

## 24. Məlum məhdudiyyətlər

- **İstifadə məlumatı sintetikdir.** Şəbəkədən real axın yoxdur; 30 günlük tarixçələr seed ilə yazılır. Tövsiyələr həmin məlumat üzərində real hesablamadır.
- **Keçid yolları təxminidir.** `action.to` dəyərləri (`/offers/<id>`, `/my-tariff/redesign`, `/internet-packs/<slug>`) backend-in fərziyyəsidir; tətbiqdəki real yollarla uzlaşdırılmalıdır.
- **Şəkil faylları hələ serverdə yoxdur.** `image` URL-ləri düzgün formadadır, amma `404` qaytarır. Tətbiqdə ehtiyat şəkil nəzərdə tutun.
- **Kataloqun bir hissəsi yer tutucudur.** Story səhifələri, bannerlərin çoxu, lotereya bölmələri, oyunlar, təkliflər və bəzi paketlər prototip üçün yazılıb; forması sabitdir, məzmunu dəyişəcək.
- **Tərcümələr prototip üçün yazılıb**, operatorun təsdiqlənmiş mətnləri deyil.
- **Insight-lar da sintetik istifadə üzərində işləyir.** Qaydalar realdır, məlumat seed-dir. Saatlıq trafik olmadığı üçün "Teams" və "1 saatda 1 GB" siqnalları qurulmayıb.
- **Tarifin real sərfiyyatı izlənmir.** Tarif alınanda və yenilənəndə qalıqlar tam həcmə qayıdır, amma istifadə etdikcə azalmır (şəbəkə axını yoxdur).
- **`501` bildiriş mətnləri** əksər hallarda ümumi qəlibdədir ("… hələ bu prototipdə yoxdur").
- **Giriş yoxdur**: OTP, token yeniləmə və çıxış `501` qaytarır.
- **Aktiv paketlərin siyahısı yoxdur** (`packs/active/` `501`-dir).
- **Assistent süni intellektə qoşulmayıb** və ingiliscə cavab verir.
- **Google Pay** yalnız `"simulated"` tokeni qəbul edir.
- **`X-Platform`** oxunmur.

## 25. Bütün endpoint-lərin siyahısı

`pul` sütununda işarə olanlar `Idempotency-Key` tələb edir.

| Metod | Yol | Vəziyyət | Pul | Təsvir |
|---|---|---|---|---|
| POST | `/api/users/otp/send/` | `:todo` |  | Send an OTP to a number |
| POST | `/api/users/otp/verify/` | `:todo` |  | Verify an OTP and get tokens |
| POST | `/api/users/token/refresh/` | `:todo` |  | Refresh the access token |
| POST | `/api/users/logout/` | `:todo` |  | Sign out |
| GET | `/api/users/me/` | `ready` |  | My profile |
| PATCH | `/api/users/me/` | `:todo` |  | Update my profile |
| GET | `/api/users/me/app-settings/` | `:todo` |  | App settings: theme, language, push |
| PATCH | `/api/users/me/app-settings/` | `:todo` |  | Update app settings |
| POST | `/api/users/devices/` | `:todo` |  | Register a push token |
| GET | `/api/billing/balance/` | `ready` |  | Balance |
| GET | `/api/billing/transactions/` | `ready` |  | Recent transactions |
| GET | `/api/billing/top-ups/` | `ready` |  | Top-up history |
| GET | `/api/billing/top-up/methods/` | `ready` |  | Top-up methods |
| POST | `/api/billing/top-up/card/` | `ready` | ✓ | Top up from a bank card |
| POST | `/api/billing/top-up/akart/` | `ready` | ✓ | Top up with akart |
| POST | `/api/billing/top-up/voucher/` | `:todo` |  | Redeem a 13-digit voucher |
| POST | `/api/billing/top-up/google-pay/` | `ready` | ✓ | Top up with Google Pay |
| GET | `/api/billing/akart/` | `:todo` |  | Saved akart numbers |
| GET | `/api/billing/cards/` | `ready` |  | Saved cards |
| POST | `/api/billing/cards/` | `:todo` |  | Add a card |
| DELETE | `/api/billing/cards/<id>/` | `:todo` |  | Remove a card |
| GET | `/api/billing/payments/` | `:todo` |  | Payment history |
| POST | `/api/billing/pay/number/` | `:todo` |  | Top up another Azercell number |
| POST | `/api/billing/pay/aztelekom/` | `:todo` |  | Pay for Aztelekom home internet |
| POST | `/api/billing/pay/utilities/` | `:todo` |  | Pay for electricity, gas or water |
| GET | `/api/billing/steam/accounts/` | `ready` |  | Saved Steam accounts |
| POST | `/api/billing/steam/top-up/` | `ready` | ✓ | Top up a Steam account |
| DELETE | `/api/billing/steam/accounts/<id>/` | `:todo` |  | Remove a saved Steam account |
| GET | `/api/tariffs/catalogue/` | `ready` |  | All tariff families with their plans |
| GET | `/api/tariffs/catalogue/<family>/` | `ready` |  | One tariff family |
| GET | `/api/tariffs/hot/` | `ready` |  | Hot offers on tariffs |
| POST | `/api/tariffs/subscribe/` | `ready` | ✓ | Subscribe to a tariff plan |
| GET | `/api/tariffs/my/` | `ready` |  | My tariff |
| GET | `/api/tariffs/my/usage/` | `ready` |  | Remaining balance of my tariff |
| POST | `/api/tariffs/my/renew/` | `ready` | ✓ | Renew my tariff |
| GET | `/api/tariffs/my/redesign/` | `ready` |  | Redesign sliders and current estimate |
| POST | `/api/tariffs/my/redesign/` | `ready` |  | Save a redesigned tariff |
| GET | `/api/tariffs/change/` | `ready` |  | Change tariff groups and cards |
| POST | `/api/tariffs/change/` | `ready` | ✓ | Change to a tariff without a catalogue page |
| GET | `/api/tariffs/premium/` | `ready` |  | Premium benefits |
| POST | `/api/tariffs/premium/activate/` | `:todo` |  | Activate Premium |
| GET | `/api/packs/internet/` | `ready` |  | Internet packs page |
| GET | `/api/packs/internet/top/` | `ready` |  | TOP internet packs |
| POST | `/api/packs/internet/purchase/` | `ready` | ✓ | Buy an internet pack |
| GET | `/api/packs/social/<slug>/` | `ready` |  | Social pack detail |
| POST | `/api/packs/social/<slug>/activate/` | `ready` | ✓ | Activate a social pack |
| GET | `/api/packs/roaming/` | `ready` |  | Roaming packs |
| POST | `/api/packs/roaming/purchase/` | `ready` | ✓ | Buy a roaming pack |
| GET | `/api/packs/active/` | `:todo` |  | My active packs |
| GET | `/api/kredit/` | `ready` |  | Get Kredit page |
| GET | `/api/kredit/products/<slug>/` | `ready` |  | Credit product detail |
| POST | `/api/kredit/products/<slug>/take/` | `:todo` |  | Take a credit |
| GET | `/api/kredit/tamamla/` | `ready` |  | Tamamla page |
| GET | `/api/sim/` | `ready` |  | SIM settings overview |
| GET | `/api/sim/line/` | `ready` |  | Line settings |
| PATCH | `/api/sim/line/` | `ready` |  | Update line settings |
| POST | `/api/sim/line/internet-settings/` | `:todo` |  | Request automatic internet settings |
| GET | `/api/sim/line/status/` | `ready` |  | Line status page |
| POST | `/api/sim/line/close/` | `:todo` |  | Close the line |
| GET | `/api/sim/call-forwarding/` | `ready` |  | Call forwarding toggles |
| PATCH | `/api/sim/call-forwarding/` | `ready` |  | Update call forwarding |
| GET | `/api/sim/roaming/` | `ready` |  | Roaming state |
| PATCH | `/api/sim/roaming/` | `ready` |  | Turn roaming on or off |
| GET | `/api/sim/roaming/countries/` | `:todo` |  | Search country pricing |
| GET | `/api/sim/sms/` | `ready` |  | SMS settings |
| PATCH | `/api/sim/sms/` | `ready` |  | Update SMS settings |
| GET | `/api/sim/puk/` | `ready` |  | PUK codes |
| GET | `/api/sim/services/` | `ready` |  | Services |
| GET | `/api/sim/services/<slug>/` | `ready` |  | Service detail |
| POST | `/api/sim/services/<slug>/subscribe/` | `ready` | ✓ | Subscribe to a service |
| POST | `/api/sim/services/<slug>/deactivate/` | `:todo` |  | Deactivate a service |
| GET | `/api/sim/esim/` | `ready` |  | eSIM info page |
| POST | `/api/sim/esim/transfer/` | `:todo` |  | Transfer to eSIM |
| POST | `/api/sim/esim/recover/` | `:todo` |  | Recover an eSIM |
| GET | `/api/content/home/` | `ready` |  | Home feed |
| GET | `/api/content/stories/` | `ready` |  | Story shelf |
| GET | `/api/content/stories/<key>/` | `ready` |  | Story pages |
| POST | `/api/content/stories/<key>/viewed/` | `ready` |  | Mark a story viewed |
| GET | `/api/content/banners/` | `ready` |  | Banners by placement |
| GET | `/api/content/notifications/` | `ready` |  | Notifications |
| GET | `/api/content/notifications/options/` | `:todo` |  | Notification options menu |
| GET | `/api/content/notifications/<id>/` | `ready` |  | Notification detail |
| POST | `/api/content/notifications/<id>/read/` | `ready` |  | Mark a notification read |
| GET | `/api/content/lottery/rules/` | `ready` |  | Lottery rules |
| GET | `/api/content/lottery/chances/` | `:todo` |  | My lottery chances |
| GET | `/api/content/lottery/terms/` | `:todo` |  | Lottery terms |
| GET | `/api/content/games/` | `ready` |  | Games |
| GET | `/api/content/games/?q=` | `:todo` | | Game search |
| POST | `/api/content/games/tournament/join/` | `:todo` |  | Join the tournament |
| GET | `/api/content/games/tournament/rules/` | `:todo` |  | Tournament rules |
| GET | `/api/content/games/<slug>/launch/` | `:todo` |  | Launch a game |
| GET | `/api/content/offers/apps/` | `ready` |  | App offers |
| POST | `/api/content/offers/apps/<id>/subscribe/` | `:todo` |  | Subscribe to an app |
| GET | `/api/content/offers/aztelekom/` | `ready` |  | Aztelekom offers |
| POST | `/api/content/offers/aztelekom/order/` | `:todo` |  | Order Aztelekom |
| GET | `/api/content/perks/` | `ready` |  | Partner perks |
| GET | `/api/content/campaigns/` | `ready` |  | Campaigns |
| GET | `/api/content/gift-wheel/` | `:todo` |  | Gift Wheel state |
| POST | `/api/content/gift-wheel/spin/` | `:todo` |  | Spin the Gift Wheel |
| POST | `/api/content/app-rating/` | `ready` |  | Rate the app |
| GET | `/api/content/about/` | `:todo` |  | About Azercell |
| GET | `/api/content/map/` | `:todo` |  | Stores map |
| GET | `/api/content/stickers/` | `:todo` |  | Sticker packs |
| GET | `/api/content/help/` | `:todo` |  | Help & Support |
| POST | `/api/content/problem-report/` | `:todo` |  | Report a problem |
| GET | `/api/referral/me/` | `ready` |  | Invite & earn page |
| GET | `/api/referral/terms/` | `:todo` |  | Referral terms of use |
| POST | `/api/referral/events/` | `:todo` |  | Service webhook: a friend registered or qualified |
| GET | `/api/assistant/inbox/` | `:dummy` |  | Support inbox |
| GET | `/api/assistant/conversations/` | `:dummy` |  | My conversations |
| POST | `/api/assistant/conversations/` | `:dummy` |  | Start a conversation |
| GET | `/api/assistant/conversations/<id>/messages/` | `:dummy` |  | Conversation history |
| POST | `/api/assistant/conversations/<id>/messages/` | `:dummy` |  | Send a message |
| POST | `/api/assistant/conversations/<id>/rate/` | `:dummy` |  | Rate a conversation |
| POST | `/api/assistant/feedback/` | `:todo` |  | Share an idea for a new feature |
| GET | `/api/usage/summary/` | `ready` |  | 30-day usage profile |
| GET | `/api/usage/recommendations/` | `ready` |  | Recommendations and the open personal offer |
| POST | `/api/usage/offers/<id>/accept/` | `ready` | ✓ | Accept a personal offer |
| POST | `/api/usage/offers/<id>/decline/` | `ready` |  | Decline a personal offer |
| GET | `/api/insights/` | `ready` |  | Insights to show now |
| GET | `/api/insights/advisor/` | `ready` |  | The tariff setup that fits the usage |
| POST | `/api/insights/<id>/seen/` | `ready` |  | Mark an insight as shown |
| POST | `/api/insights/<id>/accept/` | `ready` |  | Accept an insight's offer |
| POST | `/api/insights/<id>/dismiss/` | `ready` |  | Dismiss an insight |
| POST | `/api/laya/plan/` | `ready` |  | Decide what to do with what the user said |
| POST | `/api/laya/narrate/` | `ready` |  | Say an insight aloud |

Əlavə olaraq sağlamlıq yoxlamaları (giriş tələb etmir): `GET /api/health/` → `{"status":"ok"}`, `GET /api/health/ready/` → baza, Redis və broker-in vəziyyəti (`200` və ya `503`).
