"""Azerbaijani and Russian text of the seeded catalogue, keyed by the English text.

Each entry is `english: (azerbaijani, russian)`. Quantities such as `5-25 GB`
or `30 days` are not listed: their numbers are kept and only the unit is
translated through `UNITS`.
"""

UNITS: dict[str, tuple[str, str]] = {
    "GB": ("GB", "ГБ"),
    "MB": ("MB", "МБ"),
    "SMS": ("SMS", "SMS"),
    "min.": ("dəq.", "мин."),
    "d.": ("gün", "дн."),
    "day": ("gün", "дн."),
    "days": ("gün", "дн."),
    "hour": ("saat", "ч."),
    "hours": ("saat", "ч."),
    "₼": ("₼", "₼"),
}

# Product and brand names read the same in every language.
SAME: set[str] = {
    "DigiMax",
    "DigiMax 3GB",
    "DigiMax 5GB",
    "DigiMax 10GB",
    "DigiMax 25GB",
    "Premium",
    "Premium+",
    "Premium+ 60GB",
    "Premium+ 100GB",
    "SMS",
    "Tehsil",
    "Instagram & Facebook",
    "TikTok",
    "YouTube",
    "Buraxılmış zəng",
    "Xəbər ver",
    "SimKredit",
    "Kredit",
    "30 il səninlə",
}

TEXTS: dict[str, tuple[str, str]] = {
    # --- tariffs ---
    "Internet": ("İnternet", "Интернет"),
    "Local calls": ("Ölkədaxili zənglər", "Звонки по стране"),
    "Validity period": ("Etibarlılıq müddəti", "Срок действия"),
    "Social networks": ("Sosial şəbəkələr", "Социальные сети"),
    "Unlimited": ("Limitsiz", "Безлимит"),
    "Roaming internet": ("Rouminqdə internet", "Интернет в роуминге"),
    "For those who expect more": ("Daha çoxunu gözləyənlər üçün", "Для тех, кто ждёт большего"),
    "When you use all package, prices will be next:": (
        "Paket tam istifadə olunduqdan sonra qiymətlər belə olacaq:",
        "После использования всего пакета цены будут следующими:",
    ),
    "If monthly fee is not paid:": (
        "Aylıq abunə haqqı ödənilmədikdə:",
        "Если абонентская плата не внесена:",
    ),
    "Internet - 1MB": ("İnternet - 1MB", "Интернет - 1МБ"),
    "Local calls - 1 min.": ("Ölkədaxili zənglər - 1 dəq.", "Звонки по стране - 1 мин."),
    "SMS - 1 pcs.": ("SMS - 1 ədəd", "SMS - 1 шт."),
    "International SMS - 1 pcs.": ("Beynəlxalq SMS - 1 ədəd", "Международное SMS - 1 шт."),
    "Internet, calls and social networks in one tariff": (
        "İnternet, zənglər və sosial şəbəkələr bir tarifdə",
        "Интернет, звонки и соцсети в одном тарифе",
    ),
    "The essentials at the lowest price": (
        "Ən vacib olanlar ən sərfəli qiymətə",
        "Всё необходимое по самой низкой цене",
    ),
    "Unlimited calls and a personal curator": (
        "Limitsiz zənglər və şəxsi kurator",
        "Безлимитные звонки и персональный куратор",
    ),
    "Premium service for everyday use": (
        "Gündəlik istifadə üçün Premium xidmət",
        "Премиальный сервис на каждый день",
    ),
    "Personal curator for all your needs": (
        "Bütün ehtiyaclarınız üçün şəxsi kurator",
        "Персональный куратор для всех ваших задач",
    ),
    "Priority service in customer care and stores": (
        "Müştəri xidmətlərində və mağazalarda növbəsiz xidmət",
        "Приоритетное обслуживание в службе поддержки и магазинах",
    ),
    "Exclusive Premium theme in the app": (
        "Tətbiqdə eksklüziv Premium mövzusu",
        "Эксклюзивная тема Premium в приложении",
    ),
    "Special roaming offers": ("Xüsusi rouminq təklifləri", "Специальные предложения в роуминге"),
    "Access to airport lounges": (
        "Hava limanlarının biznes zallarına giriş",
        "Доступ в бизнес-залы аэропортов",
    ),
    "Discounts from Premium partners": (
        "Premium tərəfdaşlardan endirimlər",
        "Скидки от партнёров Premium",
    ),
    "Gold number selection": ("Qızıl nömrə seçimi", "Выбор золотого номера"),
    "Invitations to private events": (
        "Qapalı tədbirlərə dəvətlər",
        "Приглашения на закрытые мероприятия",
    ),
    "Internet GB": ("İnternet GB", "Интернет ГБ"),
    "Local calls min.": ("Ölkədaxili zənglər dəq.", "Звонки по стране мин."),
    "Instagram & FB GB": ("Instagram və FB GB", "Instagram и FB ГБ"),
    "YouTube GB": ("YouTube GB", "YouTube ГБ"),
    "TikTok GB": ("TikTok GB", "TikTok ГБ"),
    # --- packs ---
    "High-volume": ("Böyük həcmli", "Большой объём"),
    "Weekly": ("Həftəlik", "Недельные"),
    "Daily": ("Günlük", "Дневные"),
    "Monthly": ("Aylıq", "Месячные"),
    "Social": ("Sosial", "Соцсети"),
    "Unlimited speed": ("Limitsiz sürət", "Скорость без ограничений"),
    "Unlimited 1 hour": ("Limitsiz 1 saat", "Безлимит 1 ч."),
    "Unlimited 3 hours": ("Limitsiz 3 saat", "Безлимит 3 ч."),
    "Unlimited 1 day": ("Limitsiz 1 gün", "Безлимит 1 дн."),
    "High-volume 20 GB": ("Böyük həcmli 20 GB", "Большой объём 20 ГБ"),
    "High-volume 50 GB": ("Böyük həcmli 50 GB", "Большой объём 50 ГБ"),
    "High-volume 100 GB": ("Böyük həcmli 100 GB", "Большой объём 100 ГБ"),
    "Weekly 2 GB": ("Həftəlik 2 GB", "Недельный 2 ГБ"),
    "Weekly 5 GB": ("Həftəlik 5 GB", "Недельный 5 ГБ"),
    "Daily 500 MB": ("Günlük 500 MB", "Дневной 500 МБ"),
    "Daily 1 GB": ("Günlük 1 GB", "Дневной 1 ГБ"),
    "Join online classes with ease via Microsoft Teams.": (
        "Microsoft Teams ilə onlayn dərslərə rahat qoşulun.",
        "Подключайтесь к онлайн-занятиям в Microsoft Teams без забот.",
    ),
    "Scroll, post and watch stories without counting megabytes.": (
        "Meqabaytları saymadan lenti vərəqləyin, paylaşın və storilərə baxın.",
        "Листайте ленту, публикуйте и смотрите сторис, не считая мегабайты.",
    ),
    "Watch and share videos on TikTok all day long.": (
        "Bütün gün TikTok-da videolara baxın və paylaşın.",
        "Смотрите и публикуйте видео в TikTok весь день.",
    ),
    "Stream your favourite channels in high quality.": (
        "Sevimli kanallarınıza yüksək keyfiyyətdə baxın.",
        "Смотрите любимые каналы в высоком качестве.",
    ),
    "Subscribe": ("Abunə ol", "Подписаться"),
    "Activate": ("Aktivləşdir", "Подключить"),
    # --- kredit ---
    "Get now! Pay back at the next topup": (
        "İndi al! Növbəti balans artımında qaytar",
        "Получите сейчас! Верните при следующем пополнении",
    ),
    "Get now! Pay back within 32 days by 0.08 ₼": (
        "İndi al! 32 gün ərzində hər gün 0.08 ₼ qaytar",
        "Получите сейчас! Возвращайте по 0.08 ₼ в течение 32 дней",
    ),
    # --- sim services ---
    "Find out who called while you were unreachable": (
        "Əlçatmaz olduğunuz zaman kimin zəng etdiyini öyrənin",
        "Узнайте, кто звонил, пока вы были недоступны",
    ),
    "You receive an SMS about every call you missed while your "
    "phone was switched off or out of coverage.": (
        "Telefonunuz sönülü və ya əhatə dairəsindən kənarda olarkən buraxdığınız "
        "hər zəng barədə SMS alırsınız.",
        "Вы получаете SMS о каждом звонке, пропущенном, пока телефон был "
        "выключен или вне зоны действия сети.",
    ),
    "Price": ("Qiymət", "Цена"),
    "Renews": ("Yenilənmə", "Продление"),
    "Automatically": ("Avtomatik", "Автоматически"),
    "Let the caller know when you are back in the network": (
        "Şəbəkəyə qayıtdığınız zaman zəng edənə xəbər verilsin",
        "Сообщить звонившему, когда вы снова будете в сети",
    ),
    "Who is calling": ("Kim zəng edir", "Кто звонит"),
    "See the name of unknown callers": (
        "Naməlum nömrələrin adını görün",
        "Узнавайте имена неизвестных абонентов",
    ),
    "The name of the caller is shown on the screen even when the number is not in your contacts.": (
        "Nömrə kontaktlarınızda olmasa belə, zəng edənin adı ekranda göstərilir.",
        "Имя звонящего отображается на экране, даже если номера нет в ваших контактах.",
    ),
    "Ringback tone": ("Zəng melodiyası", "Мелодия вместо гудков"),
    "Callers hear music instead of the standard tone": (
        "Zəng edənlər standart siqnal əvəzinə musiqi eşidir",
        "Звонящие слышат музыку вместо обычных гудков",
    ),
    "Choose a melody that callers hear while they wait for you to answer.": (
        "Zəng edənlərin cavabınızı gözləyərkən eşidəcəyi melodiyanı seçin.",
        "Выберите мелодию, которую слышат звонящие, пока ждут вашего ответа.",
    ),
    # --- stories ---
    "Gift Wheel": ("Hədiyyə çarxı", "Колесо подарков"),
    "Spin the Gift Wheel!": ("Hədiyyə çarxını fırladın!", "Крутите Колесо подарков!"),
    "A new gift is waiting for you every day.": (
        "Hər gün sizi yeni hədiyyə gözləyir.",
        "Каждый день вас ждёт новый подарок.",
    ),
    "Internet, minutes and more": (
        "İnternet, dəqiqələr və daha çox",
        "Интернет, минуты и не только",
    ),
    "Spin once a day and collect your prize.": (
        "Gündə bir dəfə fırladın və hədiyyənizi qazanın.",
        "Крутите раз в день и забирайте приз.",
    ),
    "Roaming": ("Rouminq", "Роуминг"),
    "Stay online abroad": ("Xaricdə onlayn qalın", "Оставайтесь на связи за границей"),
    "Roaming internet packs from 10 ₼.": (
        "Rouminq internet paketləri 10 ₼-dan.",
        "Интернет-пакеты в роуминге от 10 ₼.",
    ),
    "Roaming packs": ("Rouminq paketləri", "Роуминг-пакеты"),
    "Especially for you": ("Xüsusi olaraq sizin üçün", "Специально для вас"),
    "Offers picked for the way you use your number.": (
        "Nömrənizdən istifadə tərzinizə uyğun seçilmiş təkliflər.",
        "Предложения, подобранные под то, как вы пользуетесь номером.",
    ),
    "Unlimited speed for only 0.99 ₼.": (
        "Limitsiz sürət cəmi 0.99 ₼-a.",
        "Скорость без ограничений всего за 0.99 ₼.",
    ),
    "Buy internet": ("İnternet al", "Купить интернет"),
    "Applications": ("Tətbiqlər", "Приложения"),
    "Apps you will love": ("Sevəcəyiniz tətbiqlər", "Приложения, которые вам понравятся"),
    "Kinon, Yandex Plus and Litres with your balance.": (
        "Kinon, Yandex Plus və Litres balansınızla.",
        "Kinon, Yandex Plus и Litres с оплатой с баланса.",
    ),
    "Tariffs": ("Tariflər", "Тарифы"),
    "Internet, calls and social networks in one tariff.": (
        "İnternet, zənglər və sosial şəbəkələr bir tarifdə.",
        "Интернет, звонки и соцсети в одном тарифе.",
    ),
    "See tariffs": ("Tariflərə bax", "Смотреть тарифы"),
    "Out of balance?": ("Balansınız bitib?", "Закончился баланс?"),
    "Get now and pay back at the next top-up.": (
        "İndi alın, növbəti balans artımında qaytarın.",
        "Получите сейчас и верните при следующем пополнении.",
    ),
    "Get Kredit": ("Kredit al", "Получить Kredit"),
    "Chance collection starts on 19 October 2026.": (
        "Şansların toplanması 19 oktyabr 2026-cı ildə başlayır.",
        "Сбор шансов начинается 19 октября 2026 года.",
    ),
    "Learn more": ("Ətraflı", "Подробнее"),
    # --- home ---
    "SIM settings": ("SIM ayarları", "Настройки SIM"),
    "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan": (
        "akart ilə ani kredit! 50 ₼-dək ödənişlərinizi akart krediti ilə tamamlayın",
        "Мгновенный кредит с akart! Оплачивайте до 50 ₼ в кредит от akart",
    ),
    "Spin the Gift Wheel! A new gift every day": (
        "Hədiyyə çarxını fırladın! Hər gün yeni hədiyyə",
        "Крутите Колесо подарков! Новый подарок каждый день",
    ),
    "Unlimited entertainment is waiting for you!": (
        "Limitsiz əyləncə sizi gözləyir!",
        "Вас ждут развлечения без ограничений!",
    ),
    "30 il səninlə: collect chances and win": (
        "30 il səninlə: şans topla və qazan",
        "30 il səninlə: собирайте шансы и выигрывайте",
    ),
    "DigiMax: everything in one tariff": (
        "DigiMax: hər şey bir tarifdə",
        "DigiMax: всё в одном тарифе",
    ),
    "Stay online abroad with roaming packs": (
        "Rouminq paketləri ilə xaricdə onlayn qalın",
        "Оставайтесь на связи за границей с роуминг-пакетами",
    ),
    "Switch to eSIM in a few minutes": (
        "Bir neçə dəqiqəyə eSIM-ə keçin",
        "Перейдите на eSIM за несколько минут",
    ),
    "Top up Steam with your balance": (
        "Steam hesabınızı balansınızdan artırın",
        "Пополняйте Steam с баланса",
    ),
    "Share Azercell app and get 3.00 ₼ bonus!": (
        "Azercell tətbiqini paylaşın və 3.00 ₼ bonus qazanın!",
        "Поделитесь приложением Azercell и получите бонус 3.00 ₼!",
    ),
    "Premium: a personal curator for all your needs": (
        "Premium: bütün ehtiyaclarınız üçün şəxsi kurator",
        "Premium: персональный куратор для всех ваших задач",
    ),
    "All you need and more!": (
        "Sizə lazım olan hər şey və daha çoxu!",
        "Всё, что нужно, и даже больше!",
    ),
    "Activate Wingz scooter with your Azercell balance!": (
        "Wingz skuterini Azercell balansınızla aktivləşdirin!",
        "Активируйте самокат Wingz с баланса Azercell!",
    ),
    "Wolt+ with your Azercell number": (
        "Azercell nömrənizlə Wolt+",
        "Wolt+ с вашим номером Azercell",
    ),
    # --- lottery ---
    "About the lottery": ("Lotereya haqqında", "О лотерее"),
    "We are launching the “30 il səninlə” lottery to celebrate 30 years together "
    "with our subscribers.": (
        "Abunəçilərimizlə birlikdə keçən 30 ili qeyd etmək üçün “30 il səninlə” "
        "lotereyasına başlayırıq.",
        "Мы запускаем лотерею «30 il səninlə», чтобы отпраздновать 30 лет вместе "
        "с нашими абонентами.",
    ),
    "Collect chances from 19 October 2026 and take part in the draws.": (
        "19 oktyabr 2026-cı ildən şans toplayın və tirajlarda iştirak edin.",
        "Собирайте шансы с 19 октября 2026 года и участвуйте в розыгрышах.",
    ),
    "How to earn chances?": ("Şansları necə qazanmaq olar?", "Как получить шансы?"),
    "and get 1 chance for every 5 AZN.": (
        "və hər 5 AZN üçün 1 şans qazanın.",
        "и получайте 1 шанс за каждые 5 AZN.",
    ),
    "Top up your balance with 5 AZN or more": (
        "Balansınızı 5 AZN və daha çox artırın",
        "Пополните баланс на 5 AZN и больше",
    ),
    "Top-up of 5 AZN": ("5 AZN balans artımı", "Пополнение на 5 AZN"),
    "Top-up of 12 AZN": ("12 AZN balans artımı", "Пополнение на 12 AZN"),
    "1 chance": ("1 şans", "1 шанс"),
    "2 chances": ("2 şans", "2 шанса"),
    "and get 2 chances for each purchase.": (
        "və hər alış üçün 2 şans qazanın.",
        "и получайте 2 шанса за каждую покупку.",
    ),
    "Buy an internet pack in the app": (
        "Tətbiqdə internet paketi alın",
        "Купите интернет-пакет в приложении",
    ),
    "Prizes": ("Hədiyyələr", "Призы"),
    "Smartphones, internet packs and the main prize are drawn among all participants.": (
        "Smartfonlar, internet paketləri və əsas hədiyyə bütün iştirakçılar arasında oynanılır.",
        "Смартфоны, интернет-пакеты и главный приз разыгрываются среди всех участников.",
    ),
    "Draw dates": ("Tiraj tarixləri", "Даты розыгрышей"),
    "Draws are held weekly while the campaign lasts.": (
        "Kampaniya müddətində tirajlar hər həftə keçirilir.",
        "Розыгрыши проходят еженедельно в течение всей акции.",
    ),
    "Who can participate?": ("Kimlər iştirak edə bilər?", "Кто может участвовать?"),
    "All individual prepaid and postpaid subscribers aged 18 and over.": (
        "18 yaşdan yuxarı bütün fakturasız və fakturalı fərdi abunəçilər.",
        "Все индивидуальные абоненты предоплаты и постоплаты старше 18 лет.",
    ),
    "How are winners announced?": ("Qaliblər necə elan olunur?", "Как объявляют победителей?"),
    "Winners are contacted by phone and listed on the official website.": (
        "Qaliblərlə telefonla əlaqə saxlanılır və adları rəsmi saytda dərc olunur.",
        "С победителями связываются по телефону, а их имена публикуются на официальном сайте.",
    ),
    "Important notes": ("Vacib qeydlər", "Важные примечания"),
    "Chances are not transferable and cannot be exchanged for money.": (
        "Şanslar başqasına ötürülmür və pula dəyişdirilmir.",
        "Шансы нельзя передать другому лицу или обменять на деньги.",
    ),
    # --- games and offers ---
    "Tournament": ("Turnir", "Турнир"),
    "Participate in the tournament": ("Turnirdə iştirak et", "Участвовать в турнире"),
    "Films and series online": ("Filmlər və seriallar onlayn", "Фильмы и сериалы онлайн"),
    "Music, films and cashback": ("Musiqi, filmlər və keşbek", "Музыка, фильмы и кешбэк"),
    "E-books and audiobooks": ("Elektron və audio kitablar", "Электронные и аудиокниги"),
    "Home internet from Aztelekom": (
        "Aztelekom-dan ev interneti",
        "Домашний интернет от Aztelekom",
    ),
    "15 minutes of free scooter time": (
        "15 dəqiqə pulsuz skuter sürüşü",
        "15 минут бесплатной поездки на самокате",
    ),
    "Free delivery with your Azercell number": (
        "Azercell nömrənizlə pulsuz çatdırılma",
        "Бесплатная доставка с вашим номером Azercell",
    ),
    "Order a new number online": (
        "Yeni nömrəni onlayn sifariş edin",
        "Закажите новый номер онлайн",
    ),
    # --- referral ---
    "Invite a friend who doesn’t have an account on the Azercell app": (
        "Azercell tətbiqində hesabı olmayan dostunuzu dəvət edin",
        "Пригласите друга, у которого ещё нет аккаунта в приложении Azercell",
    ),
    "Share your invitation link or referral code. The link can be sent "
    "an unlimited number of times.": (
        "Dəvət keçidinizi və ya referal kodunuzu paylaşın. Keçidi istənilən qədər göndərmək olar.",
        "Поделитесь ссылкой-приглашением или реферальным кодом. Ссылку можно "
        "отправлять неограниченное число раз.",
    ),
    "Your friend registers and easily uses the service.": (
        "Dostunuz qeydiyyatdan keçir və xidmətdən rahat istifadə edir.",
        "Ваш друг регистрируется и легко пользуется сервисом.",
    ),
    "Your friend must register for the first time using the link you "
    "shared and benefit from the specified paid services. Use of the "
    "paid service must be done within 24 hours of registration.": (
        "Dostunuz paylaşdığınız keçidlə ilk dəfə qeydiyyatdan keçməli və göstərilən "
        "ödənişli xidmətlərdən yararlanmalıdır. Ödənişli xidmətdən qeydiyyatdan sonra "
        "24 saat ərzində istifadə edilməlidir.",
        "Ваш друг должен впервые зарегистрироваться по вашей ссылке и воспользоваться "
        "указанными платными услугами. Платной услугой нужно воспользоваться в течение "
        "24 часов после регистрации.",
    ),
    "Earn together with your friend": (
        "Dostunuzla birlikdə qazanın",
        "Зарабатывайте вместе с другом",
    ),
    "Once all eligibility requirements are confirmed, you will receive "
    "a bonus of 3.00 ₼. Your friend will also be granted 5GB of free internet.": (
        "Bütün şərtlər təsdiqləndikdən sonra 3.00 ₼ bonus alacaqsınız. Dostunuza da "
        "5GB pulsuz internet veriləcək.",
        "После подтверждения всех условий вы получите бонус 3.00 ₼. Ваш друг также "
        "получит 5GB бесплатного интернета.",
    ),
    # --- notifications ---
    "Welcome to the new Azercell app": (
        "Yeni Azercell tətbiqinə xoş gəlmisiniz",
        "Добро пожаловать в новое приложение Azercell",
    ),
    "Manage your number, tariff and payments in one place.": (
        "Nömrənizi, tarifinizi və ödənişlərinizi bir yerdən idarə edin.",
        "Управляйте номером, тарифом и платежами в одном месте.",
    ),
    "Get 15 minutes of free time on your first Wingz ride when you pay "
    "with your Azercell balance.": (
        "Azercell balansınızla ödədikdə ilk Wingz sürüşünüzdə 15 dəqiqə pulsuz vaxt qazanın.",
        "Получите 15 бесплатных минут в первой поездке на Wingz при оплате с баланса Azercell.",
    ),
    "Learn more about the lottery": ("Lotereya haqqında ətraflı", "Подробнее о лотерее"),
}
