# Wooseok News Bot 💙

Bot privado de Telegram para recibir noticias nuevas sobre Byeon Woo Seok.

## Qué hace esta primera versión

- Revisa Google News en coreano, inglés y español.
- Busca `변우석` y `"Byeon Woo Seok"`.
- Envía las noticias nuevas por Telegram.
- Guarda un historial para no repetirlas.
- Se ejecuta automáticamente con GitHub Actions cada 15 minutos.
- No publica nada en Instagram ni en X.

## Instalación desde teléfono o tablet

### 1. Sube estos archivos a tu repositorio

Descomprime el ZIP y sube todo respetando las carpetas, especialmente:

```text
.github/workflows/news.yml
data/seen.json
bot.py
requirements.txt
```

### 2. Añade los secretos

En el repositorio entra a:

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

Crea estos dos secretos:

```text
TELEGRAM_BOT_TOKEN
```

Valor: el token nuevo entregado por BotFather.

```text
TELEGRAM_CHAT_ID
```

Valor: tu ID personal de Telegram.

No pongas el token directamente dentro de `bot.py`.

### 3. Permite que Actions guarde el historial

Entra a:

```text
Settings
→ Actions
→ General
→ Workflow permissions
```

Selecciona:

```text
Read and write permissions
```

Guarda el cambio.

### 4. Ejecuta la primera prueba

Abre:

```text
Actions
→ Revisar noticias de Wooseok
→ Run workflow
→ Run workflow
```

La primera ejecución puede mandar hasta 8 noticias recientes. Después solo enviará noticias nuevas.

## Si Telegram muestra un error 403

Comprueba lo siguiente:

1. Abre tu propio bot en Telegram.
2. Pulsa **Start** y envíale `/start`.
3. El `TELEGRAM_CHAT_ID` debe ser tu ID de usuario, no el ID del bot.
4. El token debe ser el token nuevo y vigente de ese mismo bot.

## Importante

Google News RSS no es una API oficial documentada para desarrolladores y puede cambiar. Esta versión sirve como MVP. Después se pueden añadir Naver API, fuentes oficiales, traducción y mejores filtros.

## Próximas mejoras

- Naver News API.
- Traducción coreano → español.
- Resúmenes.
- Clasificación por drama, evento, marca o entrevista.
- Monitoreo de cuentas oficiales mediante métodos permitidos.
- Agrupación de noticias duplicadas entre medios.
