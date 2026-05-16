# Sistema de Leads Allka

Robô diário que enriquece leads do **Redrive** com análise de site, Instagram (Apify),
anúncios Meta/Google e geração de briefing comercial por IA, criando o lead no
**Bitrix24** automaticamente. Roda em VPS atrás do **Traefik**.

---

## Fluxo

```
08:00 (America/Sao_Paulo)
  ↓
Busca 20 leads no Redrive
  ↓
Salva no banco como pending
  ↓
Para cada lead:
  → Analisa site (HTML: Meta Pixel, GTag, GTM, WhatsApp, formulário, links)
  → Analisa Instagram via Apify
  → Consulta anúncios Meta (Ad Library) + Google (stub)
  → Gera análise IA (OpenAI, JSON mode)
  → Cria lead no Bitrix24 com campos UF_CRM_*
  → Marca como sent_to_bitrix
```

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async · Alembic · APScheduler · httpx · BeautifulSoup4 ·
Playwright (opcional) · OpenAI · Apify · Bitrix24 REST · Docker · Traefik · Postgres (Supabase)

## Estrutura

```
app/
  main.py            # FastAPI + lifespan que sobe o scheduler
  config.py          # pydantic-settings
  database.py        # engine async + SessionLocal
  scheduler.py       # APScheduler: cron 08:00
  models/            # Lead, LeadAnalysis (schema "leads")
  repositories/      # lead_repository (CRUD)
  services/          # redrive, website, instagram, ads, ai, bitrix
  workers/           # lead_worker (orquestra um lead)
  routers/           # health + leads (listar / run-now / retry)
alembic/             # migrações (cria schema "leads")
tests/               # smoke
Dockerfile           # multi-stage
docker-compose.yml   # labels Traefik
entrypoint.sh        # `alembic upgrade head` + uvicorn
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. Mínimo para subir:

| Variável | Como obter |
|---|---|
| `DATABASE_URL` | Supabase → Project Settings → Database → **Connection string (URI)**. Substitua `postgres://` por `postgresql+asyncpg://`. |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `META_ACCESS_TOKEN` | https://developers.facebook.com → seu app → Access Token (com permissão `ads_read`). |
| `APIFY_TOKEN` | Apify Console → Settings → Integrations → API tokens. |
| `REDRIVE_API_TOKEN` + `REDRIVE_BASE_URL` | Painel Redrive (quando o token for emitido). |
| `BITRIX_WEBHOOK_URL` | Bitrix24 → Aplicativos → Webhooks → Webhook de entrada → URL completa (sem barra no fim). |
| `ADMIN_TOKEN` | Você define. Protege `POST /leads/run-now` e `POST /leads/{id}/retry`. |
| `APP_DOMAIN` | Domínio que o Traefik vai rotear. Ex.: `leads.allka.com.br`. |

Flags de operação importantes:

- `SCHEDULER_ENABLED=true` — desliga o cron sem precisar mexer no código.
- `PLAYWRIGHT_ENABLED=false` — quando `true`, sites com pouco HTML são re-analisados com Chromium.
- `GOOGLE_ADS_ENABLED=false` — anúncios Google ficam como stub até definir provedor.

## Rodar local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # preencher
alembic upgrade head
uvicorn app.main:app --reload
```

Sanity: `curl http://localhost:8000/health` deve retornar `{"status":"ok","database":"ok"}`.

## Rodar produção (VPS com Traefik)

Pré-requisito na VPS: rede Docker externa do Traefik (default `traefik_proxy`) já criada e
um certresolver Let's Encrypt configurado (default `letsencrypt`).

```bash
git clone https://github.com/reynario/leads_allka.git
cd leads_allka
cp .env.example .env
nano .env                    # preencher tokens reais
docker compose up -d --build
docker compose logs -f app
```

A primeira execução roda `alembic upgrade head`, que cria o **schema `leads`** com as tabelas
`leads.leads` e `leads.lead_analysis` (sem mexer no schema `public` do Supabase compartilhado).

## Endpoints

- `GET /` — info do serviço
- `GET /health` — checa banco
- `GET /leads?status=&limit=&offset=` — lista leads
- `GET /leads/{id}` — detalhe + análise
- `POST /leads/run-now` — dispara o job agora (header `X-Admin-Token`)
- `POST /leads/{id}/retry` — reseta lead para `pending` (header `X-Admin-Token`)

## Trigger manual

```bash
curl -X POST https://leads.allka.com.br/leads/run-now \
     -H "X-Admin-Token: <ADMIN_TOKEN>"
```

## Bitrix24 — campos UF_CRM_*

Antes da primeira execução, crie em **Configurações → CRM → Campos personalizados → Lead**:

| Campo | Tipo |
|---|---|
| `UF_CRM_ANALISE_IA` | Texto longo |
| `UF_CRM_SCORE_IA` | Número |
| `UF_CRM_META_PIXEL` | Texto |
| `UF_CRM_GOOGLE_TAG` | Texto |
| `UF_CRM_INSTAGRAM_STATUS` | Texto |
| `UF_CRM_META_ADS` | Texto |
| `UF_CRM_GOOGLE_ADS` | Texto |

Mapping fica em [app/services/bitrix.py](app/services/bitrix.py) (`UF_FIELDS`) caso precise renomear.

## Testes

```bash
pytest -q
```

Smoke tests não exigem banco — só checam que o app sobe e o OpenAPI carrega.

## Próximos passos (v2)

- Celery + Redis para escala horizontal
- Screenshots reais de anúncios via Playwright
- Provedor real de Google Ads (Transparency Center / SerpAPI)
- Alertas Slack/Telegram em falha do job
- Dashboard web
