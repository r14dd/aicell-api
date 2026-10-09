# Mobil tətbiqdə giriş

Abunəçi tətbiqə yalnız telefon nömrəsi ilə, şifrəsiz daxil olur. Daxil olandan sonra hər abunəçi yalnız öz məlumatını görür: balans, tarif, paketlər, əməliyyatlar, bildirişlər və s.

Tam bələdçi: [mobile-integration.md, bölmə 4](mobile-integration.md#4-giriş-auth).

## Server

| | |
|---|---|
| API | `http://167.235.198.61:8010/api/` |
| Swagger | `http://167.235.198.61:8010/api/swagger/` |

## Hesablar

Bu nömrələr serverdə hazırdır. Hər birinin öz balansı, tarifi və 30 günlük istifadə tarixçəsi var.

| Nömrə | Ad | Tarif | Balans |
|---|---|---|---|
| `994516643342` | Qüdrət Abidzadə | IsteSen | `16.21` |
| `994501000001` | Test Abunəçi 1 | DigiMax 5GB | `4.02` |
| `994501000002` | Test Abunəçi 2 | DigiMax 5GB | `5.00` |
| `994501000003` | Test Abunəçi 3 | DigiMax 10GB | `10.00` |
| `994501000004` | Test Abunəçi 4 | DigiMax 10GB | `9.10` |

## Axın

SMS hələ göndərilmir. Təsdiq kodu hər nömrə üçün `000000`-dır.

1. İstifadəçi nömrəsini yazır. Tətbiq `POST /api/users/otp/send/` göndərir və cavabdakı `request_id`-ni götürür.
2. Tətbiq dərhal `POST /api/users/otp/verify/` göndərir: `request_id` və `"code": "000000"`. Bu halda istifadəçi kod yazmır, giriş şifrəsiz olur.
3. Cavabdakı `access` və `refresh` tokenlərini təhlükəsiz yaddaşda saxlayın: iOS-da Keychain, Android-də Keystore və ya EncryptedSharedPreferences. `subscriber` sahəsi `GET /api/users/me/` cavabı ilə eynidir.
4. Bundan sonra hər sorğuda `Authorization: Bearer <access>` göndərin.
5. `401` və `"code": "token_expired"` gələrsə, `POST /api/users/token/refresh/` ilə yeni `access` alın və sorğunu təkrarlayın.
6. Refresh `400 invalid_token` qaytararsa, tokenləri silin və istifadəçini nömrə ekranına qaytarın.
7. Çıxış: tokenləri tətbiqdə silin. `logout/` endpoint-i hələ `501` qaytarır.

Gələcəkdə SMS qoşulanda 2-ci addımda istifadəçidən kod soruşulacaq. Kod ekranını indidən hazır saxlayıb hələlik keçmək məsləhətdir.

## Sorğular

Giriş endpoint-lərinə `Authorization` başlığı göndərilmir. Bütün sorğular `Content-Type: application/json` ilə gedir; `Accept-Language: az` (və ya `ru`, `en`) xəta mətnlərinin dilini seçir.

```http
POST /api/users/otp/send/
{ "msisdn": "994501000001" }

200 { "request_id": "9f2c…", "ttl": 300, "resend_after": 60 }
```

```http
POST /api/users/otp/verify/
{ "request_id": "9f2c…", "code": "000000" }

200 {
  "access": "<jwt>",
  "refresh": "<jwt>",
  "subscriber": { "id": 2, "msisdn": "994501000001", "display_msisdn": "050 100 00 01",
                  "display_name": "Test Abunəçi 1", "line_type": "prepaid", "language": "az",
                  "app_version": null, "is_premium": false }
}
```

```http
POST /api/users/token/refresh/
{ "refresh": "<jwt>" }

200 { "access": "<jwt>" }
```

```http
GET /api/users/me/
Authorization: Bearer <access>
```

`access` 30 gün, `refresh` 90 gün etibarlıdır.

## Xətalar

Hər xəta `{ "code": "...", "detail": "..." }` formasındadır. `detail` istifadəçiyə göstərilə bilər, `Accept-Language` dilindədir.

| Hal | HTTP | `code` | Tətbiq nə edir |
|---|---|---|---|
| Nömrə formatı səhvdir | 400 | `validation_error` | `errors.msisdn` mətnini sahənin altında göstər |
| Belə abunəçi yoxdur | 404 | `not_found` | "Nömrə tapılmadı" |
| Eyni nömrəyə 60 saniyədən tez yenidən `send` | 429 | `rate_limited` | `detail`-i göstər, gözlə |
| Dəqiqədə 5-dən çox giriş cəhdi (IP və ya nömrə üzrə) | 429 | `rate_limited` | `Retry-After` başlığı qədər gözlə |
| Kod səhvdir | 400 | `invalid_code` | `attempts_left` göstər; `0` olanda yenidən `send` |
| `request_id`-nin vaxtı bitib (5 dəqiqə) və ya artıq istifadə olunub | 400 | `invalid_code`, `attempts_left: 0` | Yenidən `send` |
| Token yoxdur və ya səhvdir | 401 | `not_authenticated` | Nömrə ekranına qaytar |
| `access`-in vaxtı bitib | 401 | `token_expired` | Refresh, sonra sorğunu təkrarla |
| `refresh` səhvdir və ya vaxtı bitib | 400 | `invalid_token` | Tokenləri sil, nömrə ekranına qaytar |

## Bilmək lazım olanlar

- Nömrəni bilən hər kəs o abunəçi kimi daxil ola bilər. Bu, demo və test üçündür; real istifadəçilərə açılmazdan əvvəl SMS qoşulmalıdır.
- Admin hesabları (`superadmin`, `content`, `support`, `finance`) mobil tətbiqdən daxil ola bilmir.
- Server hələ HTTPS deyil (`http://`). iOS-da App Transport Security, Android-də `usesCleartextTraffic` / network security config üçün bu IP-yə istisna lazımdır.
