# 🩸 LifeLink — شبكة إنقاذ وتبرع بالدم

> **لأن كل قطرة دم قد تنقذ روحاً.**

LifeLink هي منصة ويب مفتوحة المصدر (Open Source) تربط **المتبرعين بالدم** مع **المستشفيات والمرضى** الذين يحتاجون إلى دم عاجل. تهدف إلى تقليل الوقت بين "الحاجة" و"الإنقاذ" إلى أدنى حد.

---

## ✨ الميزات

- 📝 **تسجيل المتبرعين** — فصيلة الدم، المدينة، بيانات التواصل
- 🚨 **نداءات استغاثة** — نشر طلبات دم عاجلة مع مستوى الأهمية (حرجة/عاجلة/عادية)
- 🔍 **بحث وفلترة** — حسب فصيلة الدم، المدينة، مستوى الأهمية، الحالة
- 📱 **متجاوب 100%** — Mobile-first design
- 🎨 **واجهة عالمية** — Tailwind CSS + animations
- 🐳 **Docker-ready** — نشر سهل
- 🔌 **REST API** — CRUD كامل (JSON)

---

## 🛠️ التقنيات

- **Backend:** Python 3.11+ / Flask 3.1
- **Database:** SQLite (Flask-SQLAlchemy)
- **Frontend:** HTML5 + Tailwind CSS (CDN) + Vanilla JS
- **Fonts:** Tajawal (Arabic)
- **Deployment:** Docker

---

## 🚀 التشغيل (Run Locally)

```bash
# 1. Clone
git clone https://github.com/<your-username>/lifelink-app.git
cd lifelink-app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

افتح المتصفح على: http://127.0.0.1:5000

---

## 🐳 تشغيل عبر Docker

```bash
docker build -t lifelink .
docker run -p 5000:5000 lifelink
```

---

## 📡 API Endpoints

### Donors
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/donors` | List donors (filters: `blood_type`, `city`, `available`) |
| GET | `/api/donors/<id>` | Get donor by ID |
| POST | `/api/donors` | Register new donor |
| PUT | `/api/donors/<id>` | Update donor |
| DELETE | `/api/donors/<id>` | Delete donor |
| GET | `/api/donors/search?blood_type=&city=` | Search available donors |

### Emergencies
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/emergencies` | List (filters: `status`, `blood_type`, `city`, `urgency`) |
| GET | `/api/emergencies/<id>` | Get by ID |
| POST | `/api/emergencies` | Create emergency request |
| PUT | `/api/emergencies/<id>` | Update (e.g. status=fulfilled) |
| DELETE | `/api/emergencies/<id>` | Delete |
| GET | `/api/emergencies/open` | Open emergencies sorted by urgency |

### Health
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |

---

## 🤝 المساهمة (Contributing)

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 الترخيص (License)

MIT License — free to use, modify, and distribute.

---

## 🌟 Vision

LifeLink believes that **no one should die waiting for blood**. Every registered donor is a potential lifesaver. Every second saved is a life gained.

**Made with ❤️ for humanity.**

---

## 🧾 Technical Debt / Future Work

Notes from a **Deep Multi-Agent Audit** performed with the **nexus-core** council
(members: profiler, analyst, critic). Verdict: `reject` (score 0.15). Tracked in
[Issue #1](https://github.com/tibatechapp-ship-it/lifelink-app/issues/1).

- [ ] **Authentication / Authorization** for the APIs (protect donor & patient privacy).
- [ ] **Migrate SQLite → PostgreSQL** for scalability under high concurrency.
- [ ] **Rate Limiting** to prevent abuse / DDoS on public endpoints.
- [ ] Pagination on list endpoints.
- [ ] CSRF protection for browser forms.

### Already addressed
- Input validation (ranges, enums, regex) on all donor/emergency endpoints.
- XSS escaping in templates via `esc()`.
- DB indexes on `blood_type`, `city`, `status`, `urgency` + composite indexes.
- Timezone-aware UTC timestamps (`datetime.now(timezone.utc)`).
